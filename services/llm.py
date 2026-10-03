"""Groq LLM service with validated structured outputs."""
import json
import os
import re
from typing import Any, Optional

from dotenv import load_dotenv
try:
    from groq import Groq
except ImportError:
    Groq = None

from config.logging import logger
from config.settings import settings
from models.schemas import EmailReview, GeneratedEmailPayload, ResearchEvidence

load_dotenv()


class LLMService:
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY", "")
        self.client = Groq(api_key=self.api_key) if self.api_key and Groq else None
        self.model = settings.GROQ_MODEL
        self.temperature = settings.GROQ_TEMPERATURE
        self.max_tokens = settings.GROQ_MAX_TOKENS

    def is_available(self) -> bool:
        return bool(self.client and self.api_key)

    @staticmethod
    def _parse_json(content: str) -> dict:
        cleaned = re.sub(r"^```(?:json)?|```$", "", (content or "").strip()).strip()
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start >= 0 and end > start:
            cleaned = cleaned[start:end + 1]
        data = json.loads(cleaned)
        if not isinstance(data, dict):
            raise ValueError("Expected a JSON object")
        return data

    def _chat(self, system: str, user: str, max_tokens: Optional[int] = None, temperature: Optional[float] = None) -> str:
        if not self.is_available():
            raise RuntimeError("GROQ_API_KEY is not configured")
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=self.temperature if temperature is None else temperature,
            max_tokens=max_tokens or self.max_tokens,
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content.strip()

    def generate_email_structured(self, **kwargs: Any) -> Optional[GeneratedEmailPayload]:
        evidence = kwargs.get("evidence", [])
        evidence_text = "\n".join(f"[{e.id}] {e.claim} | {e.source_url}" for e in evidence) or "No verified company evidence available."
        job = kwargs.get("job")
        job_text = getattr(job, "raw_text", "")[:5000] if job else ""
        required = ", ".join(getattr(job, "required_skills", []) or []) if job else ""
        system = """You write polished, human-sounding job outreach emails that are substantive but not bloated. Never invent experience or company facts. Every company-specific factual claim must be supported by one of the supplied evidence IDs. If evidence is insufficient, use neutral wording instead. Do not claim the candidate has a skill unless it appears in the supplied profile."""
        contact_mode = "networking/referral" if kwargs.get("is_personal_email") else "job application"
        user = f"""Candidate: {kwargs['profile_name']} — {kwargs['profile_degree']} at {kwargs['profile_college']}, graduating {kwargs['profile_grad_year']}
Skills: {', '.join(kwargs.get('profile_skills', [])[:12])}
Objective: {kwargs.get('profile_objective', '')}
Company: {kwargs['company_name']}
Industry: {kwargs.get('company_industry') or ''}
Role: {kwargs['role']}
Tone: {kwargs['tone']}
Verified company evidence:
{evidence_text}
Job requirements: {required}
Job context: {job_text}
Outreach mode: {contact_mode}
Match talking points: {', '.join(kwargs.get('talking_points', []))}

Write 140-200 words. Use 4-5 short paragraphs: greeting, specific hook, candidate-role fit with 2-3 relevant skills/projects, motivation/value, and a clear CTA. Avoid filler and generic praise. For networking/referral mode, ask for advice or a referral rather than claiming a formal application. For job application mode, include a specific evidence-backed hook and a clear CTA. Mention the resume attachment. In the signature, print the FULL URLs exactly as supplied for every available link (LinkedIn, GitHub, LeetCode, Portfolio), not just the platform names. Do not use Markdown links. End with the candidate name and available links. Do not add fields outside the response schema."""
        email_schema = {
            "type": "json_schema",
            "json_schema": {
                "name": "generated_email",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "subject": {"type": "string"},
                        "body": {"type": "string"},
                        "key_points_used": {"type": "array", "items": {"type": "string"}},
                        "evidence_ids": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["subject", "body", "key_points_used", "evidence_ids"],
                    "additionalProperties": False,
                },
            },
        }
        try:
            if not self.is_available():
                raise RuntimeError("GROQ_API_KEY is not configured")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.3,
                max_tokens=1400,
                reasoning_effort="low",
                response_format=email_schema,
            )
            content = (response.choices[0].message.content or "").strip()
            if not content:
                raise ValueError("empty structured email response")
            return GeneratedEmailPayload(**self._parse_json(content))
        except Exception as exc:
            logger.warning(f"Structured email generation failed: {exc}")
            return None

    def generate_email(self, **kwargs: Any) -> Optional[str]:
        result = self.generate_email_structured(**kwargs)
        return result.body if result else None

    def generate_subject(self, profile_name: str, role: str, company_name: str, is_personal: bool = False) -> str:
        if not self.is_available():
            return f"Application for {role} at {company_name} — {profile_name}"[:60]
        try:
            data = self._parse_json(self._chat(
                "Return JSON only: {\"subject\": \"...\"}. Keep the subject professional and under 60 characters.",
                f"Write a subject for {profile_name} contacting {company_name} about {role}.",
                max_tokens=80,
                temperature=0.6,
            ))
            return str(data.get("subject", "Application inquiry"))[:60]
        except Exception:
            return f"Application for {role} at {company_name} — {profile_name}"[:60]

    def review_email(self, email, company, match, evidence) -> Optional[EmailReview]:
        if not self.is_available():
            return None
        evidence_text = "\n".join(f"[{e.id}] {e.claim} | {e.source_url}" for e in evidence) or "None"
        system = """You are a strict reviewer for professional cold outreach. Return ONLY JSON matching the requested schema. Score 1-10. Identify unsupported company-specific claims and hallucination risk. needs_rewrite must be true when overall quality is below 8, grounding is weak, or unsupported claims exist."""
        user = f"""Email subject: {email.subject}
Email body:
{email.body}

Company: {company.name}
Role: {email.role}
Verified evidence:
{evidence_text}
Match score: {match.overall_score}

Return scores as integers from 1 to 10 (hallucination_risk may be 0). Return suggestions and unsupported_claims as JSON arrays of strings. Return needs_rewrite as a boolean."""
        review_schema = {
            "type": "json_schema",
            "json_schema": {
                "name": "email_review",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "grammar_score": {"type": "integer", "minimum": 1, "maximum": 10},
                        "professionalism_score": {"type": "integer", "minimum": 1, "maximum": 10},
                        "spam_score": {"type": "integer", "minimum": 1, "maximum": 10},
                        "personalization_score": {"type": "integer", "minimum": 1, "maximum": 10},
                        "clarity_score": {"type": "integer", "minimum": 1, "maximum": 10},
                        "length_score": {"type": "integer", "minimum": 1, "maximum": 10},
                        "evidence_grounding_score": {"type": "integer", "minimum": 1, "maximum": 10},
                        "hallucination_risk": {"type": "integer", "minimum": 0, "maximum": 10},
                        "overall_score": {"type": "integer", "minimum": 1, "maximum": 10},
                        "suggestions": {"type": "array", "items": {"type": "string"}},
                        "unsupported_claims": {"type": "array", "items": {"type": "string"}},
                        "needs_rewrite": {"type": "boolean"},
                    },
                    "required": ["grammar_score", "professionalism_score", "spam_score", "personalization_score", "clarity_score", "length_score", "evidence_grounding_score", "hallucination_risk", "overall_score", "suggestions", "unsupported_claims", "needs_rewrite"],
                    "additionalProperties": False,
                },
            },
        }
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                temperature=0.0,
                max_tokens=500,
                reasoning_effort="low",
                response_format=review_schema,
            )
            content = (response.choices[0].message.content or "").strip()
            if not content:
                raise ValueError("empty review response")
            from agents.nodes.review import ReviewNode
            return ReviewNode._normalize_review(self._parse_json(content))
        except Exception as exc:
            logger.warning(f"Structured review failed: {exc}")
            return None
