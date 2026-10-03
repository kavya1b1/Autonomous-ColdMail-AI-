"""Pydantic schemas for ColdMail AI API and agent state."""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, EmailStr, Field


class CampaignGoal(str, Enum):
    INTERNSHIP = "internship"
    FULL_TIME = "full_time"
    REFERRAL = "referral"


class Tone(str, Enum):
    PROFESSIONAL = "professional"
    CONFIDENT = "confident"
    HUMBLE = "humble"
    ENTHUSIASTIC = "enthusiastic"


class ResearchEvidence(BaseModel):
    id: str
    claim: str
    source_url: str
    source_type: str = "company_website"
    supporting_text: Optional[str] = None
    confidence: float = Field(default=0.8, ge=0, le=1)
    retrieved_at: datetime = Field(default_factory=datetime.now)


class UserProfile(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None
    portfolio: Optional[str] = None
    leetcode: Optional[str] = None
    resume_path: Optional[str] = None
    resume_text: Optional[str] = None
    college: str
    degree: str
    graduation_year: int
    skills: List[str] = Field(default_factory=list)
    objective: str
    tone: Tone = Tone.PROFESSIONAL

    def to_context(self) -> str:
        parts = [
            f"Name: {self.name}",
            f"Education: {self.degree} at {self.college}, graduating {self.graduation_year}",
            f"Skills: {', '.join(self.skills)}",
            f"Objective: {self.objective}",
        ]
        if self.resume_text:
            parts.append(f"Resume evidence:\n{self.resume_text[:5000]}")
        for label, value in (("LinkedIn", self.linkedin), ("GitHub", self.github), ("LeetCode", self.leetcode), ("Portfolio", self.portfolio)):
            if value:
                parts.append(f"{label}: {value}")
        return "\n".join(parts)


class CompanyInfo(BaseModel):
    name: str
    domain: str
    description: Optional[str] = None
    tech_stack: List[str] = Field(default_factory=list)
    recent_news: Optional[str] = None
    culture_notes: Optional[str] = None
    careers_page: Optional[str] = None
    company_size: Optional[str] = None
    industry: Optional[str] = None
    role: Optional[str] = None
    is_personal_email: bool = False
    evidence: List[ResearchEvidence] = Field(default_factory=list)
    research_confidence: float = Field(default=0.0, ge=0, le=1)

    def to_context(self) -> str:
        parts = [f"Company: {self.name}"]
        if self.role:
            parts.append(f"Role: {self.role}")
        for label, value in (("About", self.description), ("Industry", self.industry), ("Recent News", self.recent_news), ("Culture", self.culture_notes), ("Size", self.company_size)):
            if value:
                parts.append(f"{label}: {value}")
        if self.tech_stack:
            parts.append(f"Tech Stack: {', '.join(self.tech_stack)}")
        if self.evidence:
            parts.append("Verified evidence:")
            parts.extend(f"[{e.id}] {e.claim} ({e.source_url})" for e in self.evidence)
        return "\n".join(parts)


class PersonalizationMatch(BaseModel):
    skill_matches: List[str] = Field(default_factory=list)
    talking_points: List[str] = Field(default_factory=list)
    hook: Optional[str] = None
    relevance_score: int = Field(default=5, ge=1, le=10)


class GeneratedEmail(BaseModel):
    recipient_email: str
    company_name: str
    subject: str
    body: str
    personalization_score: int = Field(ge=0, le=100)
    key_points_used: List[str] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)
    role: Optional[str] = None
    resume_attached: bool = False
    approved: bool = False
    sent: bool = False
    sent_at: Optional[datetime] = None


class GeneratedEmailPayload(BaseModel):
    subject: str = Field(min_length=1, max_length=100)
    body: str = Field(min_length=20)
    key_points_used: List[str] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)


class EmailCampaign(BaseModel):
    id: str
    goal: CampaignGoal
    recipients: List[str]
    emails: List[GeneratedEmail] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    sent_at: Optional[datetime] = None
    status: Literal["draft", "reviewing", "sending", "sent", "failed"] = "draft"
    stats: Dict[str, Any] = Field(default_factory=dict)


class ResumeParseResult(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    experience: List[Dict[str, Any]] = Field(default_factory=list)
    education: List[Dict[str, Any]] = Field(default_factory=list)
    projects: List[Dict[str, Any]] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    linkedin: Optional[str] = None
    github: Optional[str] = None
    portfolio: Optional[str] = None
    leetcode: Optional[str] = None
    raw_text: Optional[str] = None


class JobDescription(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    required_skills: List[str] = Field(default_factory=list)
    preferred_skills: List[str] = Field(default_factory=list)
    responsibilities: List[str] = Field(default_factory=list)
    experience_level: Optional[str] = None
    location: Optional[str] = None
    salary_range: Optional[str] = None
    tech_stack: List[str] = Field(default_factory=list)
    soft_skills: List[str] = Field(default_factory=list)
    raw_text: Optional[str] = None


class MatchScore(BaseModel):
    company_fit: float = Field(ge=0, le=100)
    skill_match: float = Field(ge=0, le=100)
    semantic_match: float = Field(default=0, ge=0, le=100)
    required_skill_match: float = Field(default=0, ge=0, le=100)
    preferred_skill_match: float = Field(default=0, ge=0, le=100)
    overall_score: float = Field(ge=0, le=100)
    talking_points: List[str] = Field(default_factory=list)
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    improvements: List[str] = Field(default_factory=list)


class EmailReview(BaseModel):
    grammar_score: int = Field(ge=1, le=10)
    professionalism_score: int = Field(ge=1, le=10)
    spam_score: int = Field(ge=1, le=10)
    personalization_score: int = Field(ge=1, le=10)
    clarity_score: int = Field(ge=1, le=10)
    length_score: int = Field(ge=1, le=10)
    evidence_grounding_score: int = Field(default=1, ge=1, le=10)
    hallucination_risk: int = Field(default=10, ge=0, le=10)
    overall_score: int = Field(ge=1, le=10)
    suggestions: List[str] = Field(default_factory=list)
    unsupported_claims: List[str] = Field(default_factory=list)
    needs_rewrite: bool = False


class CampaignStats(BaseModel):
    total_emails: int = 0
    sent: int = 0
    failed: int = 0
    replies: int = 0
    response_rate: float = 0.0
    avg_personalization: float = 0.0
    top_industries: List[str] = Field(default_factory=list)
    top_companies: List[str] = Field(default_factory=list)


class UserCreate(BaseModel):
    email: EmailStr
    name: str
    password: str = Field(min_length=8)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]


class UserPublic(BaseModel):
    id: int
    email: EmailStr
    name: str
    phone: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None
    portfolio: Optional[str] = None
    leetcode: Optional[str] = None
    college: Optional[str] = None
    degree: Optional[str] = None
    graduation_year: Optional[int] = None
    skills: List[str] = Field(default_factory=list)
    objective: Optional[str] = None
    tone: str = "professional"
    resume_path: Optional[str] = None
    resume_filename: Optional[str] = None
    profile_verified: bool = False
    profile_completeness: int = 0

    model_config = {"from_attributes": True}


class ExtractedOpportunity(BaseModel):
    company: str = ""
    email: str = ""
    role: str = ""
    job_description: str = ""


class ExtractRequest(BaseModel):
    raw_text: str = Field(..., min_length=1)


class ExtractResponse(BaseModel):
    opportunities: List[ExtractedOpportunity] = Field(default_factory=list)


class ProfileIn(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None
    portfolio: Optional[str] = None
    leetcode: Optional[str] = None
    resume_path: Optional[str] = None
    resume_text: Optional[str] = None
    college: str
    degree: str
    graduation_year: int
    skills: List[str] = Field(default_factory=list)
    objective: str
    tone: Tone = Tone.PROFESSIONAL


class GenerateCampaignRequest(BaseModel):
    profile: ProfileIn
    goal: CampaignGoal = CampaignGoal.FULL_TIME
    opportunities: List[ExtractedOpportunity] = Field(default_factory=list)


class GenerateCampaignResponse(BaseModel):
    thread_id: str
    emails: List[Dict[str, Any]] = Field(default_factory=list)
    awaiting_approval: bool = True
    errors: List[str] = Field(default_factory=list)


class EditedEmail(BaseModel):
    index: int
    role: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None


class ApproveRequest(BaseModel):
    thread_id: str
    approved_indices: List[int] = Field(default_factory=list)
    edited_emails: List[EditedEmail] = Field(default_factory=list)


class ApproveResponse(BaseModel):
    thread_id: str
    sent: int = 0
    failed: int = 0
    details: List[Dict[str, Any]] = Field(default_factory=list)


class CampaignSummary(BaseModel):
    thread_id: str
    goal: str
    created_at: str
    profile_name: Optional[str] = None
    total_emails: int = 0
    sent: int = 0
    failed: int = 0
    avg_personalization: float = 0.0
    status: str = "draft"
    companies: List[str] = Field(default_factory=list)
