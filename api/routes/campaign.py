"""Campaign routes: generate emails, approve + send, fetch status, list for analytics.

This wraps the existing ColdMailWorkflow (LangGraph StateGraph: research ->
match -> write -> review -> human_approval -> send) exactly as the previous
Streamlit UI drove it — the only change is that it's now invoked over HTTP
instead of in-process from Streamlit callbacks, using the same thread_id /
checkpointer pattern to pause at human_approval and resume after the user
approves.

Every route requires an authenticated user; campaigns are scoped to (and only
ever readable/writable by) the user that created them, and a snapshot of each
campaign is persisted to the database so history survives a server restart.
"""
import uuid
from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.dependencies.db import get_db
from api.dependencies.security import get_current_user
from api.dependencies.store import campaign_registry, workflow
from config.logging import logger
from models.database.models import CampaignRecordDB, UserDB
from utils.email_links import normalize_email_links_from_profile
from utils.pdf_utils import extract_text_from_pdf_path
from models.schemas import (
    ApproveRequest,
    ApproveResponse,
    CampaignGoal,
    GenerateCampaignRequest,
    GenerateCampaignResponse,
    JobDescription,
    UserProfile,
)

router = APIRouter(prefix="/api/campaign", tags=["campaign"])


def _email_to_dict(email: Any, index: int, company: Any = None, match: Any = None, review: Any = None) -> Dict[str, Any]:
    data = dict(email if isinstance(email, dict) else email.model_dump())
    data["index"] = index
    if company is not None:
        data["evidence"] = [e.model_dump() if hasattr(e, "model_dump") else e for e in getattr(company, "evidence", [])]
        data["research_confidence"] = getattr(company, "research_confidence", 0.0)
    if match is not None:
        data["match"] = match.model_dump() if hasattr(match, "model_dump") else match
    if review is not None:
        data["review"] = review.model_dump() if hasattr(review, "model_dump") else review
    return data


def _owned_campaign(thread_id: str, user: UserDB) -> Dict[str, Any]:
    """Look up a campaign in the in-memory registry and enforce ownership."""
    reg = campaign_registry.get(thread_id)
    if reg is None or reg.get("user_id") != user.id:
        raise HTTPException(
            status_code=404,
            detail="Campaign not found (it may have expired if the server restarted).",
        )
    return reg


def _persist_snapshot(reg: Dict[str, Any], db: Session) -> None:
    """Upsert a JSON snapshot of the campaign into CampaignRecordDB so it
    survives a server restart (the LangGraph MemorySaver checkpoint does not)."""
    try:
        record = db.query(CampaignRecordDB).filter(CampaignRecordDB.thread_id == reg["thread_id"]).first()
        if record is None:
            record = CampaignRecordDB(thread_id=reg["thread_id"], user_id=reg["user_id"])
        record.goal = reg.get("goal", "full_time")
        record.status = reg.get("status", "draft")
        record.total_emails = reg.get("total_emails", 0)
        record.sent = reg.get("sent", 0)
        record.failed = reg.get("failed", 0)
        record.avg_personalization = reg.get("avg_personalization", 0.0)
        record.companies = reg.get("companies", [])
        record.emails = reg.get("emails_snapshot", [])
        if reg.get("status") in ("sent", "simulated", "failed"):
            record.sent_at = datetime.utcnow()
        db.add(record)
        db.commit()
    except Exception as e:
        logger.warning(f"Could not persist campaign snapshot for {reg.get('thread_id')}: {e}")
        db.rollback()


@router.post("/generate", response_model=GenerateCampaignResponse)
async def generate_campaign(
    payload: GenerateCampaignRequest,
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Run the AI pipeline (Research -> Match -> Personalize -> Write -> Review)
    for every extracted/edited opportunity, pausing at human approval."""

    opportunities = [o for o in payload.opportunities if o.email and "@" in o.email]
    if not opportunities:
        raise HTTPException(
            status_code=400,
            detail="At least one opportunity with a valid email address is required.",
        )

    try:
        profile_data = payload.profile.model_dump()
        if not profile_data.get("resume_text") and profile_data.get("resume_path"):
            extracted = extract_text_from_pdf_path(profile_data["resume_path"])
            if not extracted.startswith("[Error"):
                profile_data["resume_text"] = extracted
        profile = UserProfile(**profile_data)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid profile: {e}")

    thread_id = f"thread_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

    parsed_jobs = [
        JobDescription(raw_text=o.job_description or None, title=o.role or None)
        for o in opportunities
    ]

    initial_state = {
        "user_profile": profile,
        "recipient_emails": [o.email for o in opportunities],
        "goal": payload.goal,
        "roles": [o.role for o in opportunities],
        "job_descriptions": [o.job_description for o in opportunities],
        "parsed_jobs": parsed_jobs,
        "known_company_names": [o.company for o in opportunities],
        "companies": [],
        "matches": [],
        "generated_emails": [],
        "reviews": [],
        "needs_rewrite": [],
        "rewrite_attempts": 0,
        "approved_indices": [],
        "approval_submitted": False,
        "awaiting_approval": False,
        "email_reviewed": False,
        "email_written": False,
        "matched": False,
        "company_researched": False,
        "errors": [],
        "logs": [],
        "session_id": str(uuid.uuid4()),
        "timestamp": datetime.now().isoformat(),
    }

    try:
        result = workflow.run(initial_state, thread_id=thread_id)
    except Exception as e:
        logger.error(f"Workflow generate error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Email generation failed: {e}")

    emails = result.values.get("generated_emails", [])
    companies = result.values.get("companies", [])
    matches = result.values.get("matches", [])
    reviews = result.values.get("reviews", [])
    errors = result.values.get("errors", [])

    if not emails:
        detail = "No emails were generated."
        if errors:
            detail += " " + "; ".join(errors)
        raise HTTPException(status_code=500, detail=detail)

    email_dicts = [e if isinstance(e, dict) else e.model_dump() for e in emails]

    reg = {
        "thread_id": thread_id,
        "user_id": current_user.id,
        "goal": payload.goal.value if isinstance(payload.goal, CampaignGoal) else str(payload.goal),
        "created_at": datetime.now().isoformat(),
        "profile_name": profile.name,
        "total_emails": len(emails),
        "companies": [d.get("company_name") for d in email_dicts],
        "sent": 0,
        "failed": 0,
        "avg_personalization": 0.0,
        "status": "awaiting_approval",
        "resume_path": profile.resume_path,
        "emails_snapshot": email_dicts,
    }
    campaign_registry[thread_id] = reg
    _persist_snapshot(reg, db)

    return GenerateCampaignResponse(
        thread_id=thread_id,
        emails=[_email_to_dict(e, i, companies[i] if i < len(companies) else None, matches[i] if i < len(matches) else None, reviews[i] if i < len(reviews) else None) for i, e in enumerate(emails)],
        awaiting_approval=bool(result.values.get("awaiting_approval", True)),
        errors=errors,
    )


@router.post("/approve", response_model=ApproveResponse)
async def approve_campaign(
    payload: ApproveRequest,
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Apply any user edits + approvals, resume the paused workflow, and send."""

    reg = _owned_campaign(payload.thread_id, current_user)

    if not payload.approved_indices:
        raise HTTPException(status_code=400, detail="Select at least one email to approve before sending.")
    total_emails = reg.get("total_emails", 0)
    invalid = [i for i in payload.approved_indices if i < 0 or i >= total_emails]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Invalid email indices: {invalid}")

    config = {"configurable": {"thread_id": payload.thread_id}}

    try:
        state = workflow.graph.get_state(config)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Campaign state not found: {e}")

    emails = state.values.get("generated_emails", [])
    if not emails:
        raise HTTPException(status_code=400, detail="No generated emails found for this campaign.")

    profile = state.values.get("user_profile")

    # Apply any inline edits (role/subject/body) the user made during review,
    # then re-run the deterministic link sanitizer on every body — this is the
    # last line of defense so a manual edit can never reintroduce LeetCode/GFG/
    # duplicate/arbitrary links into the email that actually gets sent.
    updated_emails = []
    for i, email in enumerate(emails):
        email_data = email if isinstance(email, dict) else email.model_dump()
        edit = next((e for e in payload.edited_emails if e.index == i), None)
        if edit:
            if edit.role is not None and edit.role != "":
                email_data["role"] = edit.role
            if edit.subject is not None and edit.subject != "":
                email_data["subject"] = edit.subject
            if edit.body is not None and edit.body != "":
                email_data["body"] = edit.body
        if profile is not None:
            email_data["body"] = normalize_email_links_from_profile(email_data["body"], profile)
        updated_emails.append(email_data)

    update_values = {
        "generated_emails": updated_emails,
        "approved_indices": payload.approved_indices,
        "approval_submitted": True,
        "awaiting_approval": False,
    }

    try:
        workflow.graph.update_state(config, update_values)
        for event in workflow.graph.stream(None, config):
            if "__end__" not in event:
                logger.info(f"Send event: {list(event.keys())}")
        final_state = workflow.graph.get_state(config)
    except Exception as e:
        logger.error(f"Workflow approve/send error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Sending failed: {e}")

    send_results = final_state.values.get("send_results", {"sent": 0, "failed": 0, "details": []})

    reg["sent"] = send_results.get("sent", 0)
    reg["failed"] = send_results.get("failed", 0)
    reg["status"] = "sent" if send_results.get("sent", 0) else ("simulated" if any(d.get("demo") for d in send_results.get("details", [])) else "failed")
    reg["emails_snapshot"] = updated_emails
    try:
        scores = [e.get("personalization_score", 0) for e in updated_emails]
        reg["avg_personalization"] = round(sum(scores) / len(scores), 1) if scores else 0.0
    except Exception:
        pass
    _persist_snapshot(reg, db)

    return ApproveResponse(
        thread_id=payload.thread_id,
        sent=send_results.get("sent", 0),
        failed=send_results.get("failed", 0),
        details=send_results.get("details", []),
    )


@router.get("/{thread_id}")
async def get_campaign(thread_id: str, current_user: UserDB = Depends(get_current_user)):
    """Fetch the current state of a campaign (for review page reloads / status polling)."""
    _owned_campaign(thread_id, current_user)
    config = {"configurable": {"thread_id": thread_id}}
    try:
        state = workflow.graph.get_state(config)
    except Exception:
        raise HTTPException(status_code=404, detail="Campaign not found.")

    if not state.values:
        raise HTTPException(status_code=404, detail="Campaign not found.")

    emails = state.values.get("generated_emails", [])
    companies = state.values.get("companies", [])
    matches = state.values.get("matches", [])
    reviews = state.values.get("reviews", [])
    return {
        "thread_id": thread_id,
        "emails": [_email_to_dict(e, i, companies[i] if i < len(companies) else None, matches[i] if i < len(matches) else None, reviews[i] if i < len(reviews) else None) for i, e in enumerate(emails)],
        "awaiting_approval": state.values.get("awaiting_approval", False),
        "send_results": state.values.get("send_results", {}),
        "errors": state.values.get("errors", []),
    }


@router.get("")
async def list_campaigns(current_user: UserDB = Depends(get_current_user), db: Session = Depends(get_db)):
    """List the current user's campaigns (this session's live ones plus persisted
    history from previous server restarts), and rollup stats for the dashboard."""
    live = [c for c in campaign_registry.values() if c.get("user_id") == current_user.id]
    live_ids = {c["thread_id"] for c in live}

    records = (
        db.query(CampaignRecordDB)
        .filter(CampaignRecordDB.user_id == current_user.id)
        .order_by(CampaignRecordDB.created_at.desc())
        .all()
    )
    persisted = [
        {
            "thread_id": r.thread_id,
            "goal": r.goal,
            "created_at": r.created_at.isoformat(),
            "profile_name": current_user.name,
            "total_emails": r.total_emails,
            "companies": r.companies or [],
            "sent": r.sent,
            "failed": r.failed,
            "avg_personalization": r.avg_personalization,
            "status": r.status,
        }
        for r in records
        if r.thread_id not in live_ids
    ]

    campaigns = sorted(live + persisted, key=lambda c: c["created_at"], reverse=True)

    total_sent = sum(c.get("sent", 0) for c in campaigns)
    total_failed = sum(c.get("failed", 0) for c in campaigns)
    total_emails = sum(c.get("total_emails", 0) for c in campaigns)
    scored = [c.get("avg_personalization", 0) for c in campaigns if c.get("avg_personalization")]
    avg_score = round(sum(scored) / len(scored), 1) if scored else 0.0

    return {
        "campaigns": campaigns,
        "summary": {
            "total_campaigns": len(campaigns),
            "total_emails": total_emails,
            "total_sent": total_sent,
            "total_failed": total_failed,
            "avg_personalization": avg_score,
        },
    }
