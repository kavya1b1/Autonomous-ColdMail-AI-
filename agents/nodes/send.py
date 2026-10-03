"""Send Node with a hard human-approval safety gate."""
from agents.state import AgentState
from agents.sender import EmailSender
from models.schemas import GeneratedEmail
from config.logging import logger


class SendNode:
    def __init__(self):
        self.sender = EmailSender()
        logger.info("SendNode initialized")

    def __call__(self, state: AgentState) -> AgentState:
        logger.info("SendNode starting...")
        emails = state.get("generated_emails", [])
        approved_indices = state.get("approved_indices", [])

        if not state.get("approval_submitted") or not approved_indices:
            logger.warning("SendNode blocked: explicit human approval is missing")
            state["send_results"] = {"sent": 0, "failed": 0, "details": [], "blocked": True}
            state["errors"] = state.get("errors", []) + ["Real sending blocked: explicit human approval is required."]
            return state

        profile = state.get("user_profile")
        resume_path = profile.get("resume_path") if isinstance(profile, dict) else getattr(profile, "resume_path", None)
        results = {"sent": 0, "failed": 0, "details": [], "blocked": False}

        for idx in approved_indices:
            if idx < 0 or idx >= len(emails):
                results["failed"] += 1
                results["details"].append({"success": False, "error": f"Invalid approved index: {idx}"})
                continue
            try:
                email = emails[idx] if isinstance(emails[idx], GeneratedEmail) else GeneratedEmail(**emails[idx])
                email.approved = True
                result = self.sender.send(email, resume_path=resume_path, approval_verified=True)
                results["sent"] += int(bool(result.get("success")))
                results["failed"] += int(not result.get("success"))
                results["details"].append(result)
            except Exception as exc:
                results["failed"] += 1
                results["details"].append({"success": False, "error": str(exc)})

        state["send_results"] = results
        logger.info(f"SendNode completed: {results['sent']} sent, {results['failed']} failed")
        return state
