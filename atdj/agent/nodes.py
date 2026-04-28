import time
from datetime import datetime
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage
from atdj.agent.state import AgentState
from atdj.agent.tools import search_catalog, search_catalog_rag, validate_tanda, get_energy_target, select_cortina
from atdj.config import GOOGLE_API_KEY, GEMINI_MODEL
import json
from atdj.config import ROOT_DIR


def _get_llm():
    return ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        google_api_key=GOOGLE_API_KEY,
    )


def _log(node: str, level: str, message: str) -> dict:
    return {
        "timestamp": datetime.now().isoformat(),
        "node": node,
        "level": level,
        "message": message,
    }


def session_init(state: AgentState) -> dict:
    """Initialize the session — load catalog, compute energy arc."""
    total_tandas = state["session"].target_duration_minutes // 15

    energy_map = {"low": 0.3, "moderate": 0.6, "high": 0.9}
    arc_pattern = []
    for i in range(total_tandas):
        progress = i / total_tandas
        if progress < 0.3:
            arc_pattern.append("low")
        elif progress < 0.5:
            arc_pattern.append("moderate")
        elif progress < 0.75:
            arc_pattern.append("high")
        else:
            arc_pattern.append("moderate")

    energy_arc = [energy_map[label] for label in arc_pattern]

    return {
        "energy_arc": energy_arc,
        "current_tanda_index": 0,
        "upcoming_tandas": [],
        "pending_feedback": [],
        "needs_cortina": False,
        "session_complete": False,
        "feedback_pending": False,
        "retry_count": 0,
        "agent_log": ["✓ Session initialized — energy arc computed"],
        "messages": [AIMessage(content="Session initialized. Ready to plan tandas.")],
        "activity_log": [
            _log("session_init", "info", f"Session started — {total_tandas} tandas planned."),
            _log("session_init", "info", f"Energy arc: {' → '.join(f'{e:.0%}' for e in energy_arc)}"),
        ],
    }


def tanda_planner(state: AgentState) -> dict:
    """Use the LLM to plan the next tanda."""
    import time
    t0 = time.time()

    idx = state["current_tanda_index"]
    total = len(state["energy_arc"])

    if idx >= total:
        return {"session_complete": True}

    energy_target = state["energy_arc"][idx]
    energy_label = "low" if energy_target < 0.4 else "high" if energy_target > 0.7 else "moderate"
    mood = {
        "low": "smooth and romantic, gentle tempo",
        "moderate": "danceable and rhythmic, moderate energy",
        "high": "energetic and intense, fast tempo",
    }[energy_label]

    prompt = f"""You are an expert Tango DJ planning tanda {idx + 1} of {total}.
Target energy level: {energy_target:.2f} (0=calm, 1=intense).
Mood: {mood}
Plan a tanda using natural language description."""

    llm = _get_llm()
    llm_with_tools = llm.bind_tools([search_catalog_rag, validate_tanda, get_energy_target])
    response = llm_with_tools.invoke([HumanMessage(content=prompt)])

    elapsed = time.time() - t0
    agent_log = state.get("agent_log", [])

    entries = [
        _log("tanda_planner", "info", f"Tanda {idx+1}/{total} planned in {elapsed:.1f}s (energy: {energy_target:.0%})"),
    ]
    if state.get("retry_count", 0) > 0:
        entries.append(_log("tanda_planner", "warning",
                            f"Retry {state['retry_count']}/3 — previous attempt failed"))

    return {
        "messages": [response],
        "last_agent_action": "tanda_planned",
        "retry_count": 0,
        "needs_cortina": True,
        "agent_log": agent_log + [f"✓ Tanda {idx + 1} planned (energy: {energy_target:.2f})"],
        "activity_log": entries,
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

    title = result.get("title", result.get("filename", "unknown"))

    return {
        "needs_cortina": False,
        "last_agent_action": "cortina_selected",
        "messages": [AIMessage(content=f"Cortina selected: {title}")],
        "activity_log": [
            _log("cortina_selector", "info", f"Cortina selected: {title}"),
        ],
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
        "activity_log": [
            _log("queue_publisher", "info", f"Tanda {idx + 1} published to queue."),
        ],
    }


def feedback_handler(state: AgentState) -> dict:
    """Handle incoming feedback events from the UI."""
    feedback_list = state.get("pending_feedback", [])
    entries = []

    if not feedback_list:
        entries.append(_log("feedback_handler", "info", "No pending feedback — continuing."))
        return {"feedback_pending": False, "activity_log": entries}

    latest = feedback_list[-1]
    entries.append(_log("feedback_handler", "info", f"Feedback processed: {latest.event_type}"))

    return {
        "pending_feedback": [],
        "feedback_pending": False,
        "last_agent_action": "feedback_handled",
        "messages": [AIMessage(content=f"Feedback processed: {latest.event_type}")],
        "activity_log": entries,
    }


def session_summary(state: AgentState) -> dict:
    """Wrap up the session and save a log."""
    import json
    from datetime import datetime
    total = state["current_tanda_index"]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    log = {
        "session_id": str(state["session"].id),
        "session_name": state["session"].name,
        "timestamp": timestamp,
        "total_tandas_planned": total,
        "energy_arc": state["energy_arc"],
        "planning_mode": getattr(state["session"], "planning_mode", "convention"),
        "feedback_events_received": len(state.get("pending_feedback", [])),
        "agent_actions": [
            msg.content for msg in state.get("messages", [])
            if hasattr(msg, "content") and msg.content
        ],
        "activity_log": state.get("activity_log", []),
    }

    log_dir = ROOT_DIR / "doc"
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / f"session_log_{timestamp}.json"

    with open(log_path, "w") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)

    return {
        "last_agent_action": "session_complete",
        "messages": [AIMessage(content=f"Session complete! Planned {total} tandas. Log saved to {log_path.name}")],
        "activity_log": [
            _log("session_summary", "info", f"Session complete! Planned {total} tandas."),
            _log("session_summary", "info", f"Log saved to {log_path.name}"),
        ],
    }