"""LangGraph state definitions"""
from typing import TypedDict, List, Dict, Any, Optional
from models.schemas import (
    UserProfile, CompanyInfo, MatchScore, 
    GeneratedEmail, EmailCampaign, CampaignGoal,
    ResumeParseResult, JobDescription, EmailReview
)


class AgentState(TypedDict):
    """Shared state across all LangGraph nodes"""
    # Input
    user_profile: Optional[UserProfile]
    recipient_emails: List[str]
    goal: CampaignGoal
    resume_path: Optional[str]
    job_description: Optional[JobDescription]
    roles: List[str]                    # ← NEW: target roles per recipient
    job_descriptions: List[str]          # ← NEW: raw JD texts
    parsed_jobs: List[JobDescription]    # ← NEW: parsed JDs
    known_company_names: List[str]       # ← NEW: AI-extracted company names per recipient (optional, may be empty strings)

    # Research
    companies: List[CompanyInfo]

    # Matching
    matches: List[MatchScore]

    # Writing
    generated_emails: List[GeneratedEmail]

    # Review
    reviews: List[EmailReview]
    needs_rewrite: List[bool]
    rewrite_attempts: int

    # Sending
    campaign: Optional[EmailCampaign]
    send_results: Dict[str, Any]

    # Control
    next_step: str
    errors: List[str]
    logs: List[str]

    # Human approval
    awaiting_approval: bool
    approved_indices: List[int]
    approval_submitted: bool

    # Metadata
    session_id: str
    timestamp: str