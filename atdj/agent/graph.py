from langgraph.graph import StateGraph, START, END
from atdj.agent.state import AgentState
from atdj.agent.nodes import (
    session_init,
    tanda_planner,
    cortina_selector,
    queue_publisher,
    feedback_handler,
    session_summary,
)
from atdj.agent.edges import (
    route_after_tanda_planner,
    route_after_queue_publisher,
    route_after_feedback_handler,
)


_compiled_graph_cache = None


def build_graph():
    """Build and compile the LangGraph agent.

    Memoised at module level — the compiled `StateGraph` is stateless across
    chat turns (state lives in the per-call `AgentState` typed dict, not on
    the graph). Compiling takes ~50-150ms; caching it saves that on every
    chat turn after the first.
    """
    global _compiled_graph_cache
    if _compiled_graph_cache is not None:
        return _compiled_graph_cache

    graph = StateGraph(AgentState)

    # Add all nodes
    graph.add_node("session_init", session_init)
    graph.add_node("tanda_planner", tanda_planner)
    graph.add_node("cortina_selector", cortina_selector)
    graph.add_node("queue_publisher", queue_publisher)
    graph.add_node("feedback_handler", feedback_handler)
    graph.add_node("session_summary", session_summary)

    # Entry point
    graph.add_edge(START, "session_init")
    graph.add_edge("session_init", "tanda_planner")

    # Conditional routing
    graph.add_conditional_edges(
        "tanda_planner",
        route_after_tanda_planner,
        {
            "tanda_planner": "tanda_planner",
            "cortina_selector": "cortina_selector",
            "queue_publisher": "queue_publisher",
        },
    )
    graph.add_edge("cortina_selector", "queue_publisher")
    graph.add_conditional_edges(
        "queue_publisher",
        route_after_queue_publisher,
        {
            "tanda_planner": "tanda_planner",
            "feedback_handler": "feedback_handler",
            "session_summary": "session_summary",
        },
    )
    graph.add_conditional_edges(
        "feedback_handler",
        route_after_feedback_handler,
        {
            "tanda_planner": "tanda_planner",
            "session_summary": "session_summary",
        },
    )
    graph.add_edge("session_summary", END)

    _compiled_graph_cache = graph.compile()
    return _compiled_graph_cache