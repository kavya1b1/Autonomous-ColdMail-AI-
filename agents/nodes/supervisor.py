"""Supervisor Agent - Decides workflow routing"""
from typing import Literal
from config.logging import logger
from agents.state import AgentState


class SupervisorAgent:
    """
    Supervisor agent that decides which node to execute next
    based on current state and conditional logic.
    """

    def __init__(self):
        self.max_rewrites = 3
        logger.info("SupervisorAgent initialized")

    def decide_next(self, state: AgentState) -> Literal[
        "research", "parse_resume", "parse_jd", "match", 
        "write", "review", "human_approval", "send", "end"
    ]:
        """Decide next node based on state"""

        # Check for errors
        if state.get("errors") and len(state["errors"]) > 5:
            logger.error("Too many errors, ending workflow")
            return "end"

        # Step 1: Parse resume if path provided and no profile
        if state.get("resume_path") and not state.get("user_profile"):
            logger.info("Supervisor: Route to parse_resume")
            return "parse_resume"

        # Step 2: Parse job description if provided
        if state.get("job_description") and not state.get("matches"):
            logger.info("Supervisor: Route to parse_jd")
            return "parse_jd"

        # Step 3: Research companies
        if not state.get("companies") or state.get("current_company_index", 0) < len(state.get("recipient_emails", [])):
            logger.info("Supervisor: Route to research")
            return "research"

        # Step 4: Match skills
        if not state.get("matches") or len(state.get("matches", [])) < len(state.get("companies", [])):
            logger.info("Supervisor: Route to match")
            return "match"

        # Step 5: Write emails
        if not state.get("generated_emails") or state.get("current_email_index", 0) < len(state.get("companies", [])):
            logger.info("Supervisor: Route to write")
            return "write"

        # Step 6: Review emails
        if state.get("generated_emails") and not state.get("reviews"):
            logger.info("Supervisor: Route to review")
            return "review"

        # Step 7: Handle rewrites if needed
        if state.get("needs_rewrite") and any(state["needs_rewrite"]):
            if state.get("rewrite_attempts", 0) < self.max_rewrites:
                logger.info("Supervisor: Route to write (rewrite)")
                return "write"
            else:
                logger.warning("Max rewrites reached, continuing")

        # Step 8: Human approval
        if not state.get("approved_indices"):
            logger.info("Supervisor: Route to human_approval")
            return "human_approval"

        # Step 9: Send emails
        if state.get("approved_indices") and not state.get("send_results"):
            logger.info("Supervisor: Route to send")
            return "send"

        logger.info("Supervisor: Workflow complete")
        return "end"

    def should_continue_research(self, state: AgentState) -> bool:
        """Check if more companies need research"""
        idx = state.get("current_company_index", 0)
        total = len(state.get("recipient_emails", []))
        return idx < total

    def should_continue_writing(self, state: AgentState) -> bool:
        """Check if more emails need writing"""
        idx = state.get("current_email_index", 0)
        total = len(state.get("companies", []))
        return idx < total
