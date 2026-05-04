import time
import json
from datetime import datetime
from langchain_core.messages import AIMessage
from atdj.agent.state import AgentState
from atdj.agent.tools import search_catalog_rag, select_cortina
from atdj.config import ROOT_DIR


def _log(node: str, level: str, message: str, summary: bool = False) -> dict:
    return {
        "timestamp": datetime.now().isoformat(),
        "node": node,
        "level": level,
        "message": message,
        "summary": summary,
    }


def session_init(state: AgentState) -> dict:
    """Initialize the planning run."""
    session_plan = state.get("session_plan") or []
    total_tandas = len(session_plan)

    return {
        "current_tanda_index": 0,
        "upcoming_tandas": [],
        "pending_feedback": [],
        "needs_cortina": False,
        "session_complete": False,
        "feedback_pending": False,
        "retry_count": 0,
        "agent_log": ["✓ Plan initialised"],
        "messages": [AIMessage(content="Plan initialised. Ready to select tandas.")],
        "activity_log": [
            _log("session_init", "info", f"Plan started — {total_tandas} tanda(s) requested.", summary=True),
        ],
    }


def tanda_planner(state: AgentState) -> dict:
    """Plan the next tanda by calling search_catalog_rag (RAG-based selection)."""
    t0 = time.time()

    idx = state["current_tanda_index"]
    session_plan = state.get("session_plan") or []
    total = len(session_plan)

    if idx >= total:
        return {"session_complete": True}

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
        "selected_cortinas": [{
            "title": title,
            "filename": result.get("filename"),
            "duration_seconds": result.get("duration_seconds", 20.0),
        }],
    }


def queue_publisher(state: AgentState) -> dict:
    """Publish the current tanda to the queue and advance the index."""
    idx = state["current_tanda_index"]
    total = len(state.get("session_plan") or [])
    session_complete = (idx + 1) >= total

    failed = state.get("last_agent_action") == "tanda_failed"
    msg = f"Tanda {idx + 1} skipped (no tracks)" if failed else f"Tanda {idx + 1} published to queue."
    level = "warning" if failed else "info"

    # Single summary entry per tanda for the on-screen log — combines planner +
    # cortina + publish into one user-facing line so users see one line per tanda
    # instead of three.
    picked_per_tanda = state.get("picked_tracks") or []
    this_tanda = picked_per_tanda[idx] if idx < len(picked_per_tanda) else []
    if failed or not this_tanda:
        summary_msg = f"Tanda {idx + 1}/{total} skipped — no tracks"
        summary_level = "warning"
    else:
        track_count = len(this_tanda)
        first = this_tanda[0] if this_tanda else {}
        orch = first.get("orchestra") or "?"
        summary_msg = f"Tanda {idx + 1}/{total} ready: {track_count} tracks ({orch})"
        summary_level = "info"

    return {
        "current_tanda_index": idx + 1,
        "session_complete": session_complete,
        "last_agent_action": "queue_published",
        "messages": [AIMessage(content=msg)],
        "activity_log": [
            _log("queue_publisher", level, msg),
            _log("queue_publisher", summary_level, summary_msg, summary=True),
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
    total = state["current_tanda_index"]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    log = {
        "session_id": str(state["session"].id),
        "session_name": state["session"].name,
        "timestamp": timestamp,
        "total_tandas_planned": total,
        "feedback_events_received": len(state.get("pending_feedback", [])),
        "agent_actions": [
            msg.content for msg in state.get("messages", [])
            if hasattr(msg, "content") and msg.content
        ],
        "activity_log": state.get("activity_log", []),
    }

    log_dir = ROOT_DIR / "data" / "log"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"session_log_{timestamp}.json"

    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)

    successful = sum(1 for t in state.get("picked_tracks", []) if t)
    failed_count = total - successful
    if total == 0:
        msg = "Plan completed — no tandas attempted"
        level = "warning"
    elif successful == total:
        msg = f"Plan complete — {total} tanda{'s' if total != 1 else ''} ready"
        level = "info"
    elif successful == 0:
        msg = "Plan failed — no tandas could be planned"
        level = "warning"
    else:
        msg = f"Plan complete — {successful} of {total} tandas ready ({failed_count} failed)"
        level = "warning"

    return {
        "last_agent_action": "session_complete",
        "messages": [AIMessage(content=f"{msg}. Log saved to {log_path.name}")],
        "activity_log": [
            _log("session_summary", level, msg, summary=True),
            _log("session_summary", "info", f"Log saved to {log_path.name}", summary=True),
        ],
    }
