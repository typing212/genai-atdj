import time
from datetime import datetime
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage
from atdj.agent.state import AgentState
from atdj.agent.tools import search_catalog, search_catalog_rag, validate_tanda, get_energy_target, select_cortina
from atdj.config import get_ui_llm
import json
from atdj.config import ROOT_DIR


def _get_llm():
    return get_ui_llm()


def _log(node: str, level: str, message: str) -> dict:
    return {
        "timestamp": datetime.now().isoformat(),
        "node": node,
        "level": level,
        "message": message,
    }


def session_init(state: AgentState) -> dict:
    """Initialize the planning run."""
    # Original (Tina): total_tandas = state["session"].target_duration_minutes // 15
    # The schema field was removed; total_tandas is driven by session_plan from the UI.
    session_plan = state.get("session_plan") or []
    total_tandas = len(session_plan)

    # Original (Tina) — preserved below. Computed an energy_arc curve and put it
    # in state. Removed: the user-facing Energy Arc chart reads actual track
    # energies, so the internal target curve added no value and was misleading
    # in logs. tanda_planner now sources its tanda count from session_plan only.
    # energy_map = {"low": 0.3, "moderate": 0.6, "high": 0.9}
    # arc_pattern = []
    # for i in range(total_tandas):
    #     progress = i / total_tandas
    #     if progress < 0.3:
    #         arc_pattern.append("low")
    #     elif progress < 0.5:
    #         arc_pattern.append("moderate")
    #     elif progress < 0.75:
    #         arc_pattern.append("high")
    #     else:
    #         arc_pattern.append("moderate")
    # energy_arc = [energy_map[label] for label in arc_pattern]

    return {
        # "energy_arc": energy_arc,   # removed — see comment above
        "current_tanda_index": 0,
        "upcoming_tandas": [],
        "pending_feedback": [],
        "needs_cortina": False,
        "session_complete": False,
        "feedback_pending": False,
        "retry_count": 0,
        "agent_log": ["✓ Plan initialised"],
        "messages": [AIMessage(content="Plan initialised. Ready to select tandas.")],
        # Original (Tina) wording preserved below.
        # _log("session_init", "info", f"Session started — {total_tandas} tandas planned."),
        # _log("session_init", "info", f"Energy arc: {' → '.join(f'{e:.0%}' for e in energy_arc)}"),
        "activity_log": [
            _log("session_init", "info", f"Plan started — {total_tandas} tanda(s) requested."),
        ],
    }


def tanda_planner(state: AgentState) -> dict:
    """Plan the next tanda by calling search_catalog_rag (RAG-based selection)."""
    import time
    t0 = time.time()

    idx = state["current_tanda_index"]
    # Original (Tina): total = len(state["energy_arc"])
    # energy_arc was removed from state; tanda count now comes from session_plan.
    session_plan = state.get("session_plan") or []
    total = len(session_plan)

    if idx >= total:
        return {"session_complete": True}

    # Original (Tina): derived a per-tanda mood from energy_arc to seed the LLM prompt.
    # energy_target = state["energy_arc"][idx]
    # energy_label = "low" if energy_target < 0.4 else "high" if energy_target > 0.7 else "moderate"
    # mood = {
    #     "low": "smooth and romantic, gentle tempo",
    #     "moderate": "danceable and rhythmic, moderate energy",
    #     "high": "energetic and intense, fast tempo",
    # }[energy_label]
    # prompt = f"""You are an expert Tango DJ planning tanda {idx + 1} of {total}.
    # Target energy level: {energy_target:.2f} (0=calm, 1=intense).
    # Mood: {mood}
    # Plan a tanda using natural language description."""
    # llm = _get_llm()
    # llm_with_tools = llm.bind_tools([search_catalog_rag, validate_tanda, get_energy_target])
    # response = llm_with_tools.invoke([HumanMessage(content=prompt)])

    if idx < len(session_plan):
        tanda_prompt, tanda_style = session_plan[idx]
    else:
        # Defensive fallback if the graph is invoked without a session_plan;
        # not reached from the UI today.
        tanda_prompt = "tango from the 1940s"
        tanda_style = "tango"

    raw_tracks = search_catalog_rag.invoke({"prompt": tanda_prompt})
    tanda_rules = {"tango": 4, "vals": 3, "milonga": 3}
    error_reason = ""
    if raw_tracks and isinstance(raw_tracks[0], dict) and "error" in raw_tracks[0]:
        # search_catalog_rag wraps any internal failure as [{"error": str(e)}]
        error_reason = str(raw_tracks[0]["error"])
        tracks = []
    elif raw_tracks:
        tracks = raw_tracks[: tanda_rules.get(tanda_style, 4)]
    else:
        tracks = []
        error_reason = "no candidates matched the prompt"

    response = AIMessage(content=f"Tanda {idx + 1}: selected {len(tracks)} {tanda_style} tracks")

    elapsed = time.time() - t0
    agent_log = state.get("agent_log", [])

    # Original (Tina) — preserved below. The unconditional "Tanda N/M planned"
    # info line was misleading when 0 tracks came back; energy reference was
    # also dropped along with energy_arc.
    # entries = [
    #     _log("tanda_planner", "info",
    #          f"Tanda {idx+1}/{total} planned in {elapsed:.1f}s "
    #          f"(energy: {energy_target:.0%}, {len(tracks)} tracks)"),
    # ]
    entries = []
    if tracks:
        entries.append(_log("tanda_planner", "info",
            f"Tanda {idx+1}/{total} planned in {elapsed:.1f}s ({len(tracks)} tracks)"))
    else:
        entries.append(_log("tanda_planner", "warning",
            f"Tanda {idx+1}/{total} failed in {elapsed:.1f}s — no tracks selected ({error_reason})"))

    if state.get("retry_count", 0) > 0:
        entries.append(_log("tanda_planner", "warning",
                            f"Retry {state['retry_count']}/3 — previous attempt failed"))

    picked = state.get("picked_tracks") or []
    # Original (Tina): agent_log entry referenced energy_target. Dropped the energy reference.
    # "agent_log": agent_log + [f"✓ Tanda {idx + 1} planned (energy: {energy_target:.2f})"],
    return {
        "messages": [response],
        "last_agent_action": "tanda_planned" if tracks else "tanda_failed",
        "retry_count": 0,
        "needs_cortina": bool(tracks),
        "agent_log": agent_log + [f"✓ Tanda {idx + 1} planned"],
        "activity_log": entries,
        "picked_tracks": picked + [tracks],
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
    # Original (Tina): total = len(state["energy_arc"])
    # energy_arc was removed; use session_plan length as the canonical tanda count.
    total = len(state.get("session_plan") or [])
    session_complete = (idx + 1) >= total

    # Original (Tina): always logged "Tanda N published to queue."
    # Branch on whether tanda_planner actually selected tracks so the message
    # doesn't lie when a tanda was skipped due to an empty result.
    failed = state.get("last_agent_action") == "tanda_failed"
    msg = f"Tanda {idx + 1} skipped (no tracks)" if failed else f"Tanda {idx + 1} published to queue."
    level = "warning" if failed else "info"

    return {
        "current_tanda_index": idx + 1,
        "session_complete": session_complete,
        "last_agent_action": "queue_published",
        "messages": [AIMessage(content=msg)],
        "activity_log": [
            _log("queue_publisher", level, msg),
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
        # Original (Tina): "energy_arc": state["energy_arc"],   ← removed with energy_arc
        "planning_mode": getattr(state["session"], "planning_mode", "convention"),
        "feedback_events_received": len(state.get("pending_feedback", [])),
        "agent_actions": [
            msg.content for msg in state.get("messages", [])
            if hasattr(msg, "content") and msg.content
        ],
        "activity_log": state.get("activity_log", []),
    }

    # Original (Tina): wrote logs into doc/ which is for documentation, polluting it
    # with one JSON per PLAN request. Relocated to data/log/ so they don't mix with docs.
    # log_dir = ROOT_DIR / "doc"
    # log_dir.mkdir(exist_ok=True)
    # log_path = log_dir / f"session_log_{timestamp}.json"
    log_dir = ROOT_DIR / "data" / "log"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"session_log_{timestamp}.json"

    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)

    # Original (Tina) — preserved below. `total` was the attempted count, not
    # the successful count, so the message was misleading when some tandas
    # came back empty. Now reports successful vs attempted and elevates to
    # warning level if any failed.
    # return {
    #     "last_agent_action": "session_complete",
    #     "messages": [AIMessage(content=f"Session complete! Planned {total} tandas. Log saved to {log_path.name}")],
    #     "activity_log": [
    #         _log("session_summary", "info", f"Session complete! Planned {total} tandas."),
    #         _log("session_summary", "info", f"Log saved to {log_path.name}"),
    #     ],
    # }
    successful = sum(1 for t in state.get("picked_tracks", []) if t)
    if successful == total:
        msg = f"Plan complete: {total} tanda(s)."
        level = "info"
    else:
        msg = f"Plan complete: {successful} of {total} tanda(s) succeeded."
        level = "warning"

    return {
        "last_agent_action": "session_complete",
        "messages": [AIMessage(content=f"{msg} Log saved to {log_path.name}")],
        "activity_log": [
            _log("session_summary", level, msg),
            _log("session_summary", "info", f"Log saved to {log_path.name}"),
        ],
    }