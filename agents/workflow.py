"""LangGraph workflow builder"""
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from typing import Literal

from agents.state import AgentState
from agents.nodes.research import ResearchNode
from agents.nodes.parse import ResumeParserNode, JobDescriptionParserNode
from agents.nodes.match import MatchNode
from agents.nodes.write import WriteNode
from agents.nodes.review import ReviewNode
from agents.nodes.human_approval import HumanApprovalNode
from agents.nodes.send import SendNode
from config.logging import logger


class ColdMailWorkflow:
    def __init__(self):
        self.builder = StateGraph(AgentState)
        self._build_graph()
        logger.info("ColdMailWorkflow initialized with LangGraph")

    def _build_graph(self):
        self.builder.add_node("parse_resume", ResumeParserNode())
        self.builder.add_node("parse_jd", JobDescriptionParserNode())
        self.builder.add_node("research", ResearchNode())
        self.builder.add_node("match", MatchNode())
        self.builder.add_node("write", WriteNode())
        self.builder.add_node("review", ReviewNode())
        self.builder.add_node("human_approval", HumanApprovalNode())
        self.builder.add_node("send", SendNode())

        self.builder.set_entry_point("research")

        # Linear flow
        self.builder.add_edge("research", "match")
        self.builder.add_edge("match", "write")
        self.builder.add_edge("write", "review")

        # Review can rewrite or move to approval
        self.builder.add_conditional_edges(
            "review",
            self._after_review,
            {"rewrite": "write", "approve": "human_approval", "end": END}
        )

        # Human approval: either pause (end) or send
        self.builder.add_conditional_edges(
            "human_approval",
            self._after_approval,
            {"send": "send", "pause": END}  # pause = wait for user
        )

        self.builder.add_edge("send", END)

        allowed_types = [
            "Tone", "CampaignGoal",
            "UserProfile", "CompanyInfo", "ResearchEvidence", "PersonalizationMatch",
            "GeneratedEmail", "GeneratedEmailPayload", "EmailCampaign", "ResumeParseResult",
            "JobDescription", "MatchScore", "EmailReview", "CampaignStats", "UserCreate",
            "UserLogin", "Token", "ExtractedOpportunity", "ExtractRequest", "ExtractResponse",
            "ProfileIn", "GenerateCampaignRequest", "GenerateCampaignResponse", "EditedEmail",
            "ApproveRequest", "ApproveResponse", "CampaignSummary",
        ]
        # Explicitly allowlist our first-party Pydantic state types. This removes the
        # future-breaking unregistered-type warnings and hardens checkpoint loading.
        serde = JsonPlusSerializer(
            allowed_msgpack_modules=[("models.schemas", name) for name in allowed_types]
        )
        self.graph = self.builder.compile(checkpointer=MemorySaver(serde=serde))
        logger.info("LangGraph compiled successfully")

    def _after_review(self, state: AgentState) -> Literal["rewrite", "approve", "end"]:
        if state.get("errors") and len(state["errors"]) > 5:
            return "end"
        needs_rewrite = state.get("needs_rewrite", [])
        attempts = state.get("rewrite_attempts", 0)
        if any(needs_rewrite) and attempts < 2:
            return "rewrite"
        return "approve"

    def _after_approval(self, state: AgentState) -> Literal["send", "pause"]:
        """If user has approved, send. Otherwise pause for UI."""
        if state.get("awaiting_approval"):
            # Still waiting for user input
            return "pause"
        if state.get("approved_indices"):
            return "send"
        return "pause"

    def run(self, initial_state: AgentState, thread_id: str = None):
        config = {"configurable": {"thread_id": thread_id or "default"}}
        logger.info(f"Starting workflow with thread_id: {thread_id}")

        for event in self.graph.stream(initial_state, config):
            if "__end__" not in event:
                logger.info(f"Workflow event: {list(event.keys())}")

        final_state = self.graph.get_state(config)
        return final_state

    def get_graphviz(self):
        return self.graph.get_graph().draw_mermaid()