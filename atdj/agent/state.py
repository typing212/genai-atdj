import operator
from typing import TypedDict, Annotated, Optional
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage
from atdj.schemas.session import MilongaSession
from atdj.schemas.tanda import Tanda
from atdj.schemas.feedback import FeedbackEvent


class LogEntry(TypedDict):
    timestamp: str
    node: str
    level: str    # "info" | "warning" | "error" | "decision"
    message: str


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    session: MilongaSession
    energy_arc: list[float]
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