"""AI + deterministic email review node with strict normalization and bounded output."""
import re
from typing import Any

from agents.state import AgentState
from services.llm import LLMService
from models.schemas import EmailReview, GeneratedEmail
from config.logging import logger


class ReviewNode:
    def __init__(self):
        self.llm = LLMService()
        logger.info("ReviewNode initialized")

    @staticmethod
    def _deterministic_checks(email: GeneratedEmail, evidence) -> dict:
        body = email.body or ""
        words = len(re.findall(r"\b\w+\b", body))
        spam_hits = [w for w in ("free", "click here", "act now", "limited time", "guaranteed") if w in body.lower()]
        length_score = 10 if 90 <= words <= 220 else 7 if 60 <= words <= 260 else 4
        spam_score = max(1, 10 - 2 * len(spam_hits))
        grounding_score = 9 if evidence and email.evidence_ids else (6 if not evidence else 3)
        return {"length_score": length_score, "spam_score": spam_score, "grounding_score": grounding_score, "spam_hits": spam_hits}

    @staticmethod
    def _normalize_review(raw: Any) -> EmailReview:
        """Normalize permissive model JSON before strict Pydantic validation."""
        if isinstance(raw, EmailReview):
            return raw
        data = dict(raw or {})

        score_fields = (
            "grammar_score", "professionalism_score", "spam_score", "personalization_score",
            "clarity_score", "length_score", "evidence_grounding_score", "hallucination_risk", "overall_score",
        )
        for field in score_fields:
            value = data.get(field, 5)
            if isinstance(value, str):
                m = re.search(r"-?\d+(?:\.\d+)?", value)
                value = float(m.group()) if m else 5
            try:
                value = int(round(float(value)))
            except (TypeError, ValueError):
                value = 5
            data[field] = max(0 if field == "hallucination_risk" else 1, min(10, value))

        for field in ("suggestions", "unsupported_claims"):
            value = data.get(field, [])
            if isinstance(value, str):
                parts = [re.sub(r"^[-*\d.)\s]+", "", x).strip() for x in re.split(r"\n+|;(?=\s)|(?<=\.)\s+(?=\d+\.)", value)]
                data[field] = [x for x in parts if x]
            elif isinstance(value, list):
                data[field] = [str(x).strip() for x in value if str(x).strip()]
            else:
                data[field] = []

        value = data.get("needs_rewrite", False)
        if isinstance(value, str):
            data["needs_rewrite"] = value.strip().lower() in {"true", "yes", "1", "rewrite"}
        else:
            data["needs_rewrite"] = bool(value)

        return EmailReview(**data)

    def __call__(self, state: AgentState) -> AgentState:
        emails = state.get("generated_emails", [])
        companies = state.get("companies", [])
        matches = state.get("matches", [])
        if not emails:
            state["errors"] = state.get("errors", []) + ["No emails to review"]
            return state

        reviews, needs_rewrite = [], []
        attempts = state.get("rewrite_attempts", 0)
        for i, raw_email in enumerate(emails):
            try:
                email = raw_email if isinstance(raw_email, GeneratedEmail) else GeneratedEmail(**raw_email)
                company = companies[i] if i < len(companies) else None
                match = matches[i] if i < len(matches) else None
                evidence = getattr(company, "evidence", []) if company else []
                deterministic = self._deterministic_checks(email, evidence)
                review = self.llm.review_email(email, company, match, evidence) if company and match else None

                if review is None:
                    base = min(10, max(1, round((deterministic["length_score"] + deterministic["spam_score"] + deterministic["grounding_score"] + max(1, min(10, email.personalization_score // 10)) + 8 + 8) / 6)))
                    review = EmailReview(
                        grammar_score=8, professionalism_score=8, spam_score=deterministic["spam_score"],
                        personalization_score=max(1, min(10, email.personalization_score // 10)),
                        clarity_score=8, length_score=deterministic["length_score"],
                        evidence_grounding_score=deterministic["grounding_score"],
                        hallucination_risk=10 - deterministic["grounding_score"], overall_score=base,
                        suggestions=["Add stronger evidence-backed personalization"] if deterministic["grounding_score"] < 8 else [],
                        unsupported_claims=[], needs_rewrite=base < 8,
                    )
                else:
                    if deterministic["spam_score"] < 6 or deterministic["length_score"] < 5:
                        review.needs_rewrite = True
                    if evidence and not email.evidence_ids:
                        review.evidence_grounding_score = min(review.evidence_grounding_score, 4)
                        review.needs_rewrite = True
                    review.overall_score = min(review.overall_score, 6) if review.needs_rewrite else review.overall_score
                reviews.append(review)
                needs_rewrite.append(review.needs_rewrite)
            except Exception as exc:
                logger.warning(f"Review failed for email {i}: {exc}")
                fallback = EmailReview(grammar_score=5, professionalism_score=5, spam_score=5, personalization_score=5, clarity_score=5, length_score=5, evidence_grounding_score=3, hallucination_risk=8, overall_score=5, suggestions=["Regenerate this email"], unsupported_claims=[], needs_rewrite=True)
                reviews.append(fallback)
                needs_rewrite.append(True)

        state["reviews"] = reviews
        state["needs_rewrite"] = needs_rewrite
        state["rewrite_attempts"] = attempts + 1
        state["email_reviewed"] = True
        return state
