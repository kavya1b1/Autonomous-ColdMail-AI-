"""Shared, process-wide state for the API layer.

- `workflow`: a single ColdMailWorkflow instance (and its LangGraph
  MemorySaver checkpointer) shared across requests, so that a campaign
  started by POST /api/campaign/generate can later be resumed by
  POST /api/campaign/approve using its thread_id — mirroring exactly how
  the original Streamlit UI kept one workflow instance in st.session_state.

- `campaign_registry`: a lightweight in-memory index of campaign metadata
  (used to power the dashboard/analytics views). The project's Postgres
  models exist but were never actually wired into the workflow in the
  original codebase, so this keeps campaign summaries available for the UI
  without reaching into unused infrastructure. It resets on server restart,
  same as the LangGraph MemorySaver checkpointer itself.
"""
from typing import Any, Dict

from agents.workflow import ColdMailWorkflow

workflow = ColdMailWorkflow()

campaign_registry: Dict[str, Dict[str, Any]] = {}
