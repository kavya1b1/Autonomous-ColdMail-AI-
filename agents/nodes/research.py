"""Evidence-backed research node with bounded concurrency and graceful failures."""
from concurrent.futures import ThreadPoolExecutor, as_completed

from agents.state import AgentState
from agents.researcher import CompanyResearcher
from models.schemas import CompanyInfo
from config.logging import logger
from config.settings import settings


class ResearchNode:
    def __init__(self):
        self.researcher = CompanyResearcher(timeout=settings.RESEARCH_HTTP_TIMEOUT)
        self.max_workers = max(1, min(settings.RESEARCH_MAX_CONCURRENCY, 8))
        logger.info("ResearchNode initialized")

    def _research_one(self, index, email, known_name):
        try:
            result = self.researcher.research(email, known_name=known_name)
            return index, CompanyInfo(**result), None
        except Exception as exc:
            logger.warning(f"Research failed for {email}: {exc}")
            domain = email.split("@", 1)[1] if "@" in email else ""
            company = CompanyInfo(
                name=known_name or (email.split("@", 1)[0].capitalize() if email else "Unknown"),
                domain=domain,
                description="Research unavailable; use only information supplied in the opportunity.",
                research_confidence=0.0,
            )
            return index, company, f"Research unavailable for {email}: {exc}"

    def __call__(self, state: AgentState) -> AgentState:
        emails = state.get("recipient_emails", [])
        known_names = state.get("known_company_names", [])
        if not emails:
            state["errors"] = state.get("errors", []) + ["No recipient emails provided"]
            state["companies"] = []
            return state

        companies = [None] * len(emails)
        errors = []
        logger.info(f"ResearchNode starting: {len(emails)} contacts, max_workers={self.max_workers}")

        with ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix="research") as pool:
            futures = {
                pool.submit(self._research_one, i, email, known_names[i] if i < len(known_names) else None): i
                for i, email in enumerate(emails)
            }
            for future in as_completed(futures):
                index, company, error = future.result()
                companies[index] = company
                if error:
                    errors.append(error)

        state["companies"] = companies
        state["company_researched"] = True
        if errors:
            state["errors"] = state.get("errors", []) + errors
        logger.info(f"ResearchNode completed: {len(companies)} companies ({len(errors)} research failures)")
        return state
