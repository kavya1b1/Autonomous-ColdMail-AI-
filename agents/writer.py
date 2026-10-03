"""Evidence-grounded personalized email writer."""
from models.schemas import GeneratedEmail, UserProfile, CompanyInfo, MatchScore, JobDescription
from services.llm import LLMService
from services.hybrid_retrieval import HybridRetriever, build_profile_documents
from config.logging import logger
from utils.email_links import normalize_email_links_from_profile
import re


class EmailWriter:
    def __init__(self):
        self.llm = LLMService()

    def write(self, profile: UserProfile, company: CompanyInfo, match: MatchScore, recipient_email: str = "", role: str = None, job: JobDescription = None) -> GeneratedEmail:
        role_text = role or company.role or (job.title if job else None) or "relevant position"
        if not recipient_email:
            recipient_email = f"careers@{company.domain}" if company.domain and not company.is_personal_email else ""
        evidence = company.evidence or []

        portfolio_context = ""
        try:
            docs = build_profile_documents(profile)
            if docs:
                hits = HybridRetriever(docs).search(f"{company.name} {role_text} {' '.join(match.talking_points)}", k=4)
                portfolio_context = "\n".join(h["text"] for h in hits)
        except Exception as exc:
            logger.warning(f"Portfolio retrieval unavailable: {exc}")

        if self.llm.is_available():
            payload = self.llm.generate_email_structured(
                profile_name=profile.name,
                profile_degree=profile.degree,
                profile_college=profile.college,
                profile_grad_year=profile.graduation_year,
                profile_skills=profile.skills,
                profile_objective=profile.objective,
                profile_links={"linkedin": profile.linkedin, "portfolio": profile.portfolio, "github": profile.github, "leetcode": getattr(profile, "leetcode", None)},
                company_name=company.name,
                company_description=company.description,
                company_industry=company.industry,
                role=role_text,
                talking_points=match.talking_points + ([f"Candidate evidence: {portfolio_context[:1800]}"] if portfolio_context else []),
                tone=profile.tone.value if hasattr(profile.tone, "value") else str(profile.tone),
                is_personal_email=company.is_personal_email,
                job=job,
                evidence=evidence,
            )
            if payload:
                body = self._ensure_email_quality(payload.body, profile, company, match, role_text)
                body = self._ensure_contact_links(body, profile)
                return GeneratedEmail(
                    recipient_email=recipient_email,
                    company_name=company.name,
                    subject=payload.subject,
                    body=body,
                    personalization_score=min(100, int(match.overall_score)),
                    key_points_used=payload.key_points_used or match.talking_points,
                    evidence_ids=payload.evidence_ids,
                    role=role_text,
                    resume_attached=True,
                )

        body, subject = self._fallback_template(profile, company, match, role_text, job)
        body = self._ensure_email_quality(body, profile, company, match, role_text)
        body = self._ensure_contact_links(body, profile)
        return GeneratedEmail(
            recipient_email=recipient_email,
            company_name=company.name,
            subject=subject,
            body=body,
            personalization_score=min(100, int(match.overall_score)),
            key_points_used=match.talking_points or ["Role alignment"],
            evidence_ids=[e.id for e in evidence],
            role=role_text,
            resume_attached=True,
        )


    @staticmethod
    def _word_count(text: str) -> int:
        return len(re.findall(r"\b\w+[\w'’-]*\b", text or ""))

    def _ensure_email_quality(self, body: str, profile: UserProfile, company: CompanyInfo, match: MatchScore, role: str) -> str:
        """Keep the single-pass LLM output substantive without another LLM call."""
        body = (body or "").strip()
        if self._word_count(body) >= 120:
            return body

        points = [p.strip() for p in (match.talking_points or []) if p and p.strip()]
        strengths = [p.strip() for p in (match.strengths or []) if p and p.strip()]
        skill_text = ", ".join(profile.skills[:6]) or "AI and software development"
        fit_point = points[1] if len(points) > 1 else (strengths[0] if strengths else f"my background in {skill_text}")
        addition = (
            f"\n\nBeyond the initial fit, I would be excited to contribute to the {role} role through practical work across {skill_text}. "
            f"{fit_point.rstrip('.')}. I am especially interested in opportunities where I can turn these skills into useful, production-oriented solutions while learning from the team."
        )
        if self._word_count(body) < 100:
            addition += (
                f"\n\nI have attached my resume for a fuller view of my projects and background. "
                "If my profile looks relevant, I would appreciate the opportunity to briefly discuss the role, team, and how I could contribute."
            )
        return body + addition

    @staticmethod
    def _ensure_contact_links(body: str, profile: UserProfile) -> str:
        """Deterministically sanitize links: strip anything the LLM added (LeetCode,
        GeeksforGeeks, duplicates, arbitrary URLs) and append exactly LinkedIn / GitHub /
        Portfolio, sourced only from the user's saved profile, each exactly once.
        """
        return normalize_email_links_from_profile(body, profile)

    def _fallback_template(self, profile, company, match, role, job=None):
        skills = ", ".join(profile.skills[:5]) or "relevant technologies"
        hook = match.talking_points[0] if match.talking_points else f"the {role} opportunity"
        body = f"""Hi Team at {company.name},\n\nI'm {profile.name}, a {profile.degree} student at {profile.college}, graduating {profile.graduation_year}. I'm reaching out regarding the {role} opportunity.\n\nI was particularly interested because {hook}. My background includes {skills}, and I would be excited to apply that experience to the role while continuing to learn.\n\nI've attached my resume for additional context. Would you be open to a brief conversation about whether my background could be a fit?\n\nBest regards,\n{profile.name}\n{profile.linkedin or ''}\n{profile.github or ''}\n{profile.portfolio or ''}"""
        return body, f"Application for {role} at {company.name} — {profile.name}"[:60]

    def write_batch(self, profile, companies, matches, recipient_emails=None, roles=None, jobs=None):
        recipient_emails = recipient_emails or []
        roles = roles or []
        jobs = jobs or []
        return [self.write(profile, c, m, recipient_emails[i] if i < len(recipient_emails) else "", roles[i] if i < len(roles) else None, jobs[i] if i < len(jobs) else None) for i, (c, m) in enumerate(zip(companies, matches))]
