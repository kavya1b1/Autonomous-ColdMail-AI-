"""Email Writer Node"""
from agents.state import AgentState
from agents.writer import EmailWriter
from models.schemas import GeneratedEmail, UserProfile, CompanyInfo, MatchScore, JobDescription
from config.logging import logger


class WriteNode:
    """Generates personalized cold emails for ALL companies."""
    
    def __init__(self):
        self.writer = EmailWriter()
        logger.info("WriteNode initialized")
    
    def __call__(self, state: AgentState) -> AgentState:
        logger.info("WriteNode starting...")
        
        profile_data = state.get("user_profile")
        companies = state.get("companies", [])
        matches = state.get("matches", [])
        recipient_emails = state.get("recipient_emails", [])
        roles = state.get("roles", [])
        jobs = state.get("parsed_jobs", [])
        
        if not companies:
            logger.warning("WriteNode: No companies to write for")
            state["errors"] = state.get("errors", []) + ["No companies to write for"]
            return state
        
        if not profile_data:
            logger.warning("WriteNode: No user profile")
            state["errors"] = state.get("errors", []) + ["No user profile"]
            return state
        
        if isinstance(profile_data, dict):
            profile = UserProfile(**profile_data)
        else:
            profile = profile_data
        
        emails = self.writer.write_batch(
            profile=profile,
            companies=companies,
            matches=matches,
            recipient_emails=recipient_emails,
            roles=roles,
            jobs=jobs,
        )
        
        state["generated_emails"] = emails
        state["email_written"] = True
        logger.info(f"WriteNode completed: {len(emails)} emails")
        return state