"""Semantic and explainable resume-to-JD matcher."""
import re
from functools import lru_cache
from typing import List, Optional

from models.schemas import MatchScore, UserProfile, CompanyInfo, JobDescription
from config.logging import logger

ALIASES = {
    "genai": "generative ai", "gen ai": "generative ai", "llms": "llm", "large language models": "llm",
    "ml": "machine learning", "dl": "deep learning", "cv": "computer vision", "js": "javascript",
    "ts": "typescript", "postgres": "postgresql", "k8s": "kubernetes", "restful api": "rest api",
}


def normalize_skill(skill: str) -> str:
    value = re.sub(r"\s+", " ", (skill or "").strip().lower())
    return ALIASES.get(value, value)


@lru_cache(maxsize=1)
def _get_embedder():
    try:
        from sentence_transformers import SentenceTransformer
        from config.settings import settings
        return SentenceTransformer(settings.EMBEDDING_MODEL)
    except Exception as exc:
        logger.warning(f"Semantic matcher unavailable; using lexical fallback: {exc}")
        return None


class PersonalizationMatcher:
    """Combines exact/normalized skill matching with embedding similarity."""

    def _semantic_score(self, user_items: List[str], target_items: List[str]) -> float:
        if not user_items or not target_items:
            return 0.0
        model = _get_embedder()
        if model is None:
            user_set = {normalize_skill(x) for x in user_items}
            target_set = {normalize_skill(x) for x in target_items}
            return 100.0 * len(user_set & target_set) / max(1, len(target_set))
        try:
            user_emb = model.encode(user_items, normalize_embeddings=True, show_progress_bar=False)
            target_emb = model.encode(target_items, normalize_embeddings=True, show_progress_bar=False)
            similarities = target_emb @ user_emb.T
            best = similarities.max(axis=1)
            return float(((best + 1.0) / 2.0).mean() * 100)
        except Exception as exc:
            logger.warning(f"Semantic scoring failed; using lexical fallback: {exc}")
            user_set = {normalize_skill(x) for x in user_items}
            target_set = {normalize_skill(x) for x in target_items}
            return 100.0 * len(user_set & target_set) / max(1, len(target_set))

    def _matches(self, user_skills: List[str], targets: List[str]) -> tuple[list[str], list[str]]:
        user_norm = {normalize_skill(s): s for s in user_skills if s.strip()}
        matched, missing = [], []
        for target in targets:
            n = normalize_skill(target)
            if n in user_norm:
                matched.append(user_norm[n])
            else:
                missing.append(target)
        return list(dict.fromkeys(matched)), list(dict.fromkeys(missing))

    def match(self, profile: UserProfile, company: CompanyInfo, job: Optional[JobDescription] = None) -> MatchScore:
        logger.info(f"Matching {profile.name} against {company.name}...")
        job = job or JobDescription()
        user_skills = list(dict.fromkeys(profile.skills or []))
        required = list(dict.fromkeys(job.required_skills or []))
        preferred = list(dict.fromkeys(job.preferred_skills or []))
        tech = list(dict.fromkeys((job.tech_stack or []) + (company.tech_stack or [])))

        if not required:
            required = tech[:]
        exact_required, missing_required = self._matches(user_skills, required)
        exact_preferred, missing_preferred = self._matches(user_skills, preferred)

        required_sem = self._semantic_score(user_skills, required) if required else 60.0
        preferred_sem = self._semantic_score(user_skills, preferred) if preferred else 60.0
        tech_sem = self._semantic_score(user_skills, tech) if tech else 60.0

        required_exact = 100 * len(exact_required) / max(1, len(required)) if required else 60.0
        preferred_exact = 100 * len(exact_preferred) / max(1, len(preferred)) if preferred else 60.0
        required_match = 0.55 * required_exact + 0.45 * required_sem
        preferred_match = 0.55 * preferred_exact + 0.45 * preferred_sem
        skill_match = 0.70 * required_match + 0.20 * preferred_match + 0.10 * tech_sem

        company_text = " ".join(x for x in [company.description, company.industry, company.culture_notes] if x)
        objective_sem = self._semantic_score([profile.objective], [company_text]) if company_text else 60.0
        company_fit = min(100.0, max(35.0, objective_sem))
        overall = 0.82 * skill_match + 0.18 * company_fit

        talking_points, strengths, weaknesses, improvements = [], [], [], []
        if exact_required:
            talking_points.append(f"Direct experience with {', '.join(exact_required[:5])}")
            strengths.append(f"Matches required skills: {', '.join(exact_required[:6])}")
        if missing_required:
            weaknesses.append(f"Required-skill gaps: {', '.join(missing_required[:6])}")
            improvements.append("Lead with the strongest transferable evidence instead of claiming missing skills")
        if exact_preferred:
            strengths.append(f"Preferred-skill alignment: {', '.join(exact_preferred[:5])}")
        if job.responsibilities:
            talking_points.append(f"Relevant responsibility: {job.responsibilities[0][:120]}")
        if company.tech_stack and self._matches(user_skills, company.tech_stack)[0]:
            talking_points.append(f"Relevant company technology: {', '.join(self._matches(user_skills, company.tech_stack)[0][:4])}")

        if not talking_points:
            talking_points.append(f"Interest in {company.name} and the {job.title or company.role or 'role'} opportunity")

        return MatchScore(
            company_fit=round(company_fit, 1),
            skill_match=round(skill_match, 1),
            semantic_match=round((required_sem if required else tech_sem), 1),
            required_skill_match=round(required_match, 1),
            preferred_skill_match=round(preferred_match, 1),
            overall_score=round(overall, 1),
            talking_points=talking_points,
            strengths=strengths,
            weaknesses=weaknesses,
            improvements=improvements,
        )

    def match_batch(self, profile: UserProfile, companies: List[CompanyInfo], jobs: List[JobDescription] = None) -> List[MatchScore]:
        jobs = jobs or [None] * len(companies)
        while len(jobs) < len(companies):
            jobs.append(None)
        return [self.match(profile, company, job) for company, job in zip(companies, jobs)]
