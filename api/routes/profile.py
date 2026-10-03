"""Profile management routes: per-user profile persistence + resume upload.

Previously this read/wrote a single shared ``profile.json`` file for every
visitor. It's now backed by the authenticated user's row in the database, so
each account has its own profile, resume, and verification state.
"""
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from api.dependencies.db import get_db
from api.dependencies.security import get_current_user
from api.routes.auth import to_public
from agents.nodes.parse import ResumeParserNode
from config.logging import logger
from models.database.models import UserDB
from models.schemas import ProfileIn
from utils.pdf_utils import extract_text_from_pdf_bytes  # noqa: F401 (kept available for reuse)

router = APIRouter(prefix="/api/profile", tags=["profile"])

BASE_DIR = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


@router.get("")
async def get_profile(current_user: UserDB = Depends(get_current_user)):
    """Return the current user's saved profile."""
    return to_public(current_user)


@router.put("")
async def update_profile(
    profile: ProfileIn,
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Save/update the current user's profile used to personalize campaigns."""
    current_user.name = profile.name.strip()
    current_user.phone = profile.phone
    current_user.linkedin = profile.linkedin
    current_user.github = profile.github
    current_user.portfolio = profile.portfolio
    current_user.leetcode = profile.leetcode
    current_user.resume_path = profile.resume_path or current_user.resume_path
    current_user.college = profile.college
    current_user.degree = profile.degree
    current_user.graduation_year = profile.graduation_year
    current_user.skills = profile.skills
    current_user.objective = profile.objective
    current_user.tone = profile.tone.value if hasattr(profile.tone, "value") else str(profile.tone)

    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    logger.info(f"Profile updated for {current_user.email}")
    return {"status": "saved", "profile": to_public(current_user)}


@router.post("/verify")
async def verify_profile(
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark the current user's profile as reviewed/confirmed.

    Called when the user clicks "Confirm Profile & Continue" on the
    post-login profile-verification screen; gates entry into the dashboard.
    """
    required = [current_user.name, current_user.college, current_user.degree, current_user.objective]
    if not all(required):
        raise HTTPException(
            status_code=400,
            detail="Please complete your profile (name, college, degree, objective) before continuing.",
        )
    current_user.profile_verified = True
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return {"status": "verified", "profile": to_public(current_user)}


@router.post("/resume")
async def upload_resume(
    file: UploadFile = File(...),
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload a resume PDF: store it server-side (for attaching to sent emails)
    and best-effort parse contact details/skills to help prefill the profile form.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    user_dir = UPLOAD_DIR / f"user_{current_user.id}"
    user_dir.mkdir(exist_ok=True)
    file_id = uuid.uuid4().hex[:10]
    dest_path = user_dir / f"resume_{file_id}.pdf"
    with open(dest_path, "wb") as f:
        f.write(contents)

    parsed: dict = {}
    try:
        parser = ResumeParserNode()
        result = parser._parse_pdf(str(dest_path))
        parsed = {
            "name": result.name,
            "email": result.email,
            "phone": result.phone,
            "linkedin": result.linkedin,
            "github": result.github,
            "portfolio": result.portfolio,
            "leetcode": result.leetcode,
            "skills": result.skills,
        }
    except Exception as e:
        # Non-fatal: the resume is still saved and attachable even if parsing fails
        logger.warning(f"Resume parse failed (non-fatal): {e}")

    current_user.resume_path = str(dest_path)
    current_user.resume_filename = file.filename
    db.add(current_user)
    db.commit()

    return {
        "resume_path": str(dest_path),
        "filename": file.filename,
        "parsed": parsed,
    }
