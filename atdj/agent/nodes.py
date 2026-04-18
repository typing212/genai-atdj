from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage
from atdj.agent.state import AgentState
from atdj.agent.tools import search_catalog, validate_tanda, get_energy_target, select_cortina
from atdj.config import GOOGLE_API_KEY, GEMINI_MODEL
import uuid


def _get_llm():
    return ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        google_api_key=GOOGLE_API_KEY,
    )


def session_init(state: AgentState) -> dict:
    """Initialize the session — load catalog, compute energy arc."""
    total_tandas = state["session"].target_duration_minutes // 15
    energy_arc = []
    for i in range(total_tandas):
        progress = i / total_tandas
        if progress < 0.4:
            energy_arc.append(0.3 + (progress / 0.4) * 0.4)
        elif progress < 0.6:
            energy_arc.append(0.7 + ((progress - 0.4) / 0.2) * 0.2)
        else:
            energy_arc.append(0.9 - ((progress - 0.6) / 0.4) * 0.4)
    return {
        "energy_arc": energy_arc,
        "current_tanda_index": 0,
        "upcoming_tandas": [],
        "pending_feedback": [],
        "needs_cortina": False,
        "session_complete": False,
        "feedback_pending": False,
        "retry_count": 0,
        "messages": [AIMessage(content="Session initialized. Ready to plan tandas.")],
    }


def tanda_planner(state: AgentState) -> dict:
    """Use the LLM to plan the next tanda."""
    idx = state["current_tanda_index"]
    total = len(state["energy_arc"])

    if idx >= total:
        return {"session_complete": True}

    energy_target = state["energy_arc"][idx]
    played_ids = [
        t.id for t in state.get("upcoming_tandas", [])
    ]

    prompt = f"""You are an expert Tango DJ planning a milonga session.
Plan tanda number {idx + 1} of {total}.
Target energy level: {energy_target:.2f} (0=calm, 1=intense)
Already used track IDs: {played_ids}

Use the search_catalog tool to find tracks, then validate_tanda to check they form a valid tanda.
A valid tanda needs 3-4 tracks from the same orchestra, same style, same decade.
Return the list of track IDs you selected."""

    llm = _get_llm()
    llm_with_tools = llm.bind_tools([search_catalog, validate_tanda, get_energy_target])
    response = llm_with_tools.invoke([HumanMessage(content=prompt)])

    return {
        "messages": [response],
        "last_agent_action": "tanda_planned",
        "retry_count": 0,
        "needs_cortina": True,
    }


def cortina_selector(state: AgentState) -> dict:
    """Select a cortina to follow the current tanda."""
    preceding_style = "tango"
    if state["upcoming_tandas"]:
        preceding_style = state["upcoming_tandas"][-1].style

    result = select_cortina.invoke({
        "preceding_style": preceding_style,
        "duration_seconds": 20.0,
    })

    return {
        "needs_cortina": False,
        "last_agent_action": "cortina_selected",
        "messages": [AIMessage(content=f"Cortina selected: {result.get('id', 'unknown')}")],
    }


def queue_publisher(state: AgentState) -> dict:
    """Publish the current tanda to the queue and advance the index."""
    idx = state["current_tanda_index"]
    total = len(state["energy_arc"])
    session_complete = (idx + 1) >= total

    return {
        "current_tanda_index": idx + 1,
        "session_complete": session_complete,
        "last_agent_action": "queue_published",
        "messages": [AIMessage(content=f"Tanda {idx + 1} published to queue.")],
    }


def feedback_handler(state: AgentState) -> dict:
    """Handle incoming feedback events from the UI."""
    feedback_list = state.get("pending_feedback", [])
    if not feedback_list:
        return {"feedback_pending": False}

    latest = feedback_list[-1]
    return {
        "pending_feedback": [],
        "feedback_pending": False,
        "last_agent_action": "feedback_handled",
        "messages": [AIMessage(content=f"Feedback processed: {latest.event_type}")],
    }


def session_summary(state: AgentState) -> dict:
    """Wrap up the session."""
    total = state["current_tanda_index"]
    return {
        "last_agent_action": "session_complete",
        "messages": [AIMessage(content=f"Session complete! Planned {total} tandas.")],
    }