# Proposal: Agent Activity Log & Real-Time Status Updates

## Problem

The agent nodes (`session_init`, `tanda_planner`, `cortina_selector`, `queue_publisher`, `feedback_handler`, `session_summary`) each append an `AIMessage` to `state["messages"]` and set `last_agent_action`. But these messages are internal to LangGraph — they accumulate in state and are never surfaced to the UI in real time.

The UI already has a **Session Log** panel (`page_main.py` line 1163) that renders `st.session_state["agent_notifications"]`, but it's populated with hardcoded stub data. There's no bridge from the agent's actual execution to this panel.

### What the user currently sees

- Hardcoded stub notifications ("Session started — 8 tandas planned", etc.)
- No indication of which node is currently running
- No visibility into agent decisions (why it picked a certain orchestra, why it retried)
- No error feedback (if `tanda_planner` retries 3 times, user doesn't know)

### What the user should see

- Live updates as each node completes: "Planning tanda 3 of 8...", "Cortina selected: La Cumparsita", "Tanda 3 published to queue"
- Decision explanations: "Picked Di Sarli — highest scoring combo for energy 0.7"
- Warnings: "Tanda planner retry 2/3 — not enough tracks matched filters"
- Timing: how long each step took (useful for debugging latency)

## Proposed Design

### 1. Add `activity_log` to AgentState

```python
# state.py
class LogEntry(TypedDict):
    timestamp: str          # ISO format
    node: str               # which node produced this
    level: str              # "info" | "warning" | "error" | "decision"
    message: str            # human-readable description

class AgentState(TypedDict):
    # ... existing fields ...
    activity_log: Annotated[list[LogEntry], operator.add]  # append-only
```

Using `operator.add` (same pattern as `add_messages`) so each node can return new entries without overwriting previous ones.

### 2. Each node emits structured log entries

```python
# nodes.py
from datetime import datetime

def _log(node: str, level: str, message: str) -> dict:
    return {
        "timestamp": datetime.now().isoformat(),
        "node": node,
        "level": level,
        "message": message,
    }

def session_init(state: AgentState) -> dict:
    total_tandas = state["session"].target_duration_minutes // 15
    # ... existing logic ...
    return {
        # ... existing return values ...
        "activity_log": [
            _log("session_init", "info", f"Session started — {total_tandas} tandas planned."),
            _log("session_init", "info", f"Energy arc: {' → '.join(f'{e:.0%}' for e in energy_arc[:4])}…"),
        ],
    }

def tanda_planner(state: AgentState) -> dict:
    idx = state["current_tanda_index"]
    total = len(state["energy_arc"])
    energy = state["energy_arc"][idx]
    # ... existing LLM call ...
    entries = [_log("tanda_planner", "info", f"Planning tanda {idx+1}/{total} (energy target: {energy:.0%})")]
    if state.get("retry_count", 0) > 0:
        entries.append(_log("tanda_planner", "warning",
                            f"Retry {state['retry_count']}/3 — previous attempt failed"))
    return {
        # ... existing return values ...
        "activity_log": entries,
    }

def cortina_selector(state: AgentState) -> dict:
    # ... existing logic ...
    return {
        # ... existing return values ...
        "activity_log": [
            _log("cortina_selector", "info", f"Cortina selected: {result.get('title', 'unknown')}")
        ],
    }

def queue_publisher(state: AgentState) -> dict:
    idx = state["current_tanda_index"]
    # ... existing logic ...
    return {
        # ... existing return values ...
        "activity_log": [
            _log("queue_publisher", "info", f"Tanda {idx+1} published to queue.")
        ],
    }

def feedback_handler(state: AgentState) -> dict:
    # ... existing logic ...
    entries = []
    if feedback_list:
        entries.append(_log("feedback_handler", "info",
                            f"Feedback processed: {latest.event_type}"))
    else:
        entries.append(_log("feedback_handler", "info", "No pending feedback — continuing."))
    return {
        # ... existing return values ...
        "activity_log": entries,
    }

def session_summary(state: AgentState) -> dict:
    total = state["current_tanda_index"]
    return {
        # ... existing return values ...
        "activity_log": [
            _log("session_summary", "info", f"Session complete! Planned {total} tandas.")
        ],
    }
```

### 3. UI reads `activity_log` from state instead of stub data

```python
# page_main.py — replace stub notifications
# Instead of hardcoded agent_notifications, read from agent state:

level_colors = {
    "info":     ("#E8F4FD", "#1A6FAD"),
    "decision": ("#E8F8E8", "#2D8A4E"),
    "warning":  ("#FEF9E7", "#B7770D"),
    "error":    ("#FDE8E8", "#C44040"),
}
```

The Session Log panel already renders from `st.session_state["agent_notifications"]`. The bridge is:
- After each agent graph step, copy new `activity_log` entries to `st.session_state["agent_notifications"]`
- Map `level` to the existing color scheme (info → blue, warning → yellow, error → red, decision → green)

### 4. Optional: Add timing to log entries

Each node can measure its own execution time and include it:

```python
def tanda_planner(state: AgentState) -> dict:
    import time
    t0 = time.time()
    # ... LLM call ...
    elapsed = time.time() - t0
    entries = [
        _log("tanda_planner", "info",
             f"Tanda {idx+1}/{total} planned in {elapsed:.1f}s (energy: {energy:.0%})")
    ]
```

This helps the DJ see if the agent is slow (LLM latency) and decide whether to switch scoring methods.

## What Changes

| File | Change |
|---|---|
| `atdj/agent/state.py` | Add `LogEntry` TypedDict, add `activity_log` field with `operator.add` reducer |
| `atdj/agent/nodes.py` | Each node returns `activity_log` entries with structured info |
| `atdj/ui/page_main.py` | Replace stub `agent_notifications` with real `activity_log` from agent state |

## What Stays the Same

- The agent graph structure — no new nodes, no new edges
- The LLM prompts — log entries are about observability, not reasoning
- The existing `messages` field — kept for LangGraph's internal message passing
- The Session Log panel UI — same look, just real data instead of stubs

## Log Levels

| Level | Color | When |
|---|---|---|
| `info` | Blue | Normal progress: "Planning tanda 3/8", "Cortina selected" |
| `decision` | Green | Agent reasoning: "Picked Di Sarli — highest scoring combo" |
| `warning` | Yellow | Retries, fallbacks: "Retry 2/3", "Fell back to SBERT scoring" |
| `error` | Red | Failures: "No tracks matched filters", "LLM call timed out" |

## Example Session Log (What the DJ Sees)

```
[info]     Session started — 8 tandas planned.
[info]     Energy arc: 30% → 45% → 60% → 75%…
[info]     Tanda 1/8 planned in 2.3s (energy: 30%)
[decision] Picked Canaro — warm opening, low energy match
[info]     Cortina selected: La Cumparsita (cortina cut)
[info]     Tanda 1 published to queue.
[info]     Tanda 2/8 planned in 1.8s (energy: 45%)
[warning]  Retry 1/3 — not enough D'Arienzo tracks in 1940s
[decision] Switched to Tanturi 1940s — 4 tracks available
[info]     Cortina selected: Poema (cortina cut)
[info]     Tanda 2 published to queue.
```

## Effort Estimate

~2 hours:
- ~30 min: Add `LogEntry` + `activity_log` to state
- ~45 min: Update all 6 nodes to emit log entries
- ~45 min: Wire UI to read from agent state instead of stubs
