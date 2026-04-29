import operator
from typing import TypedDict, Annotated, Optional
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage
from atdj.schemas.session import PlanSession
from atdj.schemas.tanda import Tanda
from atdj.schemas.feedback import FeedbackEvent


class LogEntry(TypedDict):
    timestamp: str
    node: str
    level: str    # "info" | "warning" | "error" | "decision"
    message: str


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    session: PlanSession
    # Original (Tina): energy_arc was a planning-target curve (low→high→moderate)
    # computed in session_init and read by tanda_planner to derive a per-tanda mood.
    # Removed — the user-facing Energy Arc chart now reads actual selected-track
    # energies directly from the catalog, so the internal target curve is unused.
    # energy_arc: list[float]
    current_tanda_index: int
    upcoming_tandas: list[Tanda]
    pending_feedback: list[FeedbackEvent]
    needs_cortina: bool
    session_complete: bool
    feedback_pending: bool
    candidate_tracks: list[dict]
    current_tanda_draft: Optional[dict]
    last_agent_action: Optional[str]
    qa_question: Optional[str]
    qa_answer: Optional[str]
    error_message: Optional[str]
    retry_count: int
    agent_log: list[str]
    activity_log: Annotated[list[LogEntry], operator.add]
    # Per-tanda prompts handed in from the UI (one tuple per tanda: (prompt, style)),
    # and the tracks each call to tanda_planner selects. The UI reads picked_tracks
    # from the final state to build the playlist — this lets tanda_planner own the
    # selection step end-to-end instead of running it in a separate loop in page_main.py.
    session_plan: list[tuple[str, str]]
    picked_tracks: list[list[dict]]