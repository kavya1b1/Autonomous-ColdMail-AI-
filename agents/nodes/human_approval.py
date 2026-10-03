"""Human Approval Node"""
from agents.state import AgentState
from config.logging import logger


class HumanApprovalNode:
    """Handles approval for ALL generated emails."""
    
    def __init__(self):
        logger.info("HumanApprovalNode initialized")
    
    def __call__(self, state: AgentState) -> AgentState:
        logger.info("HumanApprovalNode starting...")
        
        emails = state.get("generated_emails", [])
        
        if not emails:
            logger.warning("HumanApprovalNode: 0 emails need approval")
            state["awaiting_approval"] = False
            state["approved_indices"] = []
            state["approval_submitted"] = False
            return state
        
        # Only treat approval as submitted when the API/UI explicitly resumes the thread.
        if state.get("approval_submitted", False):
            logger.info(f"HumanApprovalNode: Using submitted indices: {state.get("approved_indices", [])}")
            state["awaiting_approval"] = False
            return state
        
        # First run: pause for human approval
        logger.info("HumanApprovalNode: Pausing for human approval")
        state["awaiting_approval"] = True
        state["approved_indices"] = []
        state["approval_submitted"] = False
        return state