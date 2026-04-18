from atdj.agent.state import AgentState


def route_after_tanda_planner(state: AgentState) -> str:
    """Decide where to go after tanda_planner."""
    if state.get("error_message") and state.get("retry_count", 0) < 3:
        return "tanda_planner"
    if state.get("needs_cortina"):
        return "cortina_selector"
    return "queue_publisher"


def route_after_queue_publisher(state: AgentState) -> str:
    """Decide where to go after queue_publisher."""
    if state.get("session_complete"):
        return "session_summary"
    if state.get("feedback_pending"):
        return "feedback_handler"
    return "tanda_planner"


def route_after_feedback_handler(state: AgentState) -> str:
    """Decide where to go after feedback_handler."""
    if state.get("session_complete"):
        return "session_summary"
    return "tanda_planner"