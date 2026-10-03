"""Match Agent Node for LangGraph"""
from agents.state import AgentState
from agents.matcher import PersonalizationMatcher
from models.schemas import UserProfile, CompanyInfo, MatchScore, JobDescription
from config.logging import logger


class MatchNode:
    """Match user profile against ALL researched companies."""
    
    def __init__(self):
        self.matcher = PersonalizationMatcher()
        logger.info("MatchNode initialized")
    
    def __call__(self, state: AgentState) -> AgentState:
        logger.info("MatchNode starting...")
        
        profile_data = state.get("user_profile")
        companies = state.get("companies", [])
        jobs = state.get("parsed_jobs", [])
        
        if not companies:
            logger.warning("MatchNode: No companies to match")
            state["errors"] = state.get("errors", []) + ["No companies to match"]
            return state
        
        if not profile_data:
            logger.warning("MatchNode: No user profile")
            state["errors"] = state.get("errors", []) + ["No user profile"]
            return state
        
        if isinstance(profile_data, dict):
            profile = UserProfile(**profile_data)
        else:
            profile = profile_data
        
        # Ensure jobs list matches companies length
        while len(jobs) < len(companies):
            jobs.append(JobDescription())
        
        matches = []
        
        for company, job in zip(companies, jobs):
            try:
                if isinstance(company, dict):
                    company = CompanyInfo(**company)
                if isinstance(job, dict):
                    job = JobDescription(**job)
                
                match_result = self.matcher.match(profile, company, job)
                matches.append(match_result)
                logger.info(f"Matched {company.name}: {match_result.overall_score:.1f}")
                
            except Exception as e:
                logger.warning(f"Match failed for {company}: {e}")
                matches.append(MatchScore(company_fit=50, skill_match=50, overall_score=50, talking_points=["General interest"]))
        
        state["matches"] = matches
        state["matched"] = True
        logger.info(f"MatchNode completed: {len(matches)} matches")
        return state