# Proposal: Smart Tanda Scoring via WP-02 Methods

## Problem

The current `search_catalog` tool in `atdj/agent/tools.py` picks tandas by metadata only — filter by style/decade/orchestra, then `random.choice`. It doesn't use the scoring methods explored in WP-02 (CLAP, CoT LLM, SBERT), so the agent can't judge whether tracks actually *sound good together*.

Meanwhile, `notebooks/02d_tanda_session.ipynb` already has `build_tanda()` which takes a scores Series and finds the highest-scoring orchestra+singer combo — but it's stuck in a notebook, not wired into the agent.

## Architecture Problem: We're Not Really Using LangGraph

The current agent flow is:

```
session_init → tanda_planner → cortina_selector → queue_publisher → (loop)
```

This is essentially a **linear chain** — LangGraph adds no value over plain LangChain here. The conditional edges barely branch (just retry logic). Worse, `tanda_planner` binds LLM tools (`search_catalog`, `validate_tanda`) but **never executes them** — the tool calls sit in `messages` and nobody runs them.

On top of that, the smart tanda scoring proposal originally nested a CoT LLM call inside `search_catalog`. That means:
1. Outer Gemini call (`tanda_planner`) → decides to call `search_catalog` (it always will)
2. Inner Gemini call (CoT scoring inside `search_catalog`) → actually scores the tracks

This is redundant — two LLM roundtrips where only the inner one does real work.

### Fix: Merge scoring into `tanda_planner` directly

The `tanda_planner` node should own the scoring logic — no outer LLM call to decide "should I search?", because the answer is always yes. The node:
1. Reads the energy target from `energy_arc`
2. Builds a natural language prompt from the target
3. Calls the scoring method directly (CoT / CLAP / SBERT)
4. Calls `build_tanda()` with the scores
5. Returns the tanda + scoring context

One LLM call (CoT scoring), not two. The node handles method selection based on state, not the LLM.

### Better use of LangGraph

With this refactor, we can actually leverage LangGraph features:

```
session_init
    │
    ├──→ tanda_planner ──→ cortina_selector ──┐
    │         │                                │
    │         ├── (if enhancement_enabled) ────┤
    │         │   audio_enhancer (parallel)     │
    │         │                                │
    │    queue_publisher ←─────────────────────┘
    │         │
    │    ┌────┴────┐
    │    │ DJ chat  │  ← human-in-the-loop: DJ can approve, reject, or modify
    │    └────┬────┘
    │         │
    └─── (next cycle)
```

What this unlocks:
- **Parallel branches**: audio enhancement runs while cortina is selected
- **Human-in-the-loop**: DJ can approve/reject a tanda before it hits the queue
- **Streaming**: state updates push to the UI as nodes execute (for the activity log)

## Proposed Flow

```
1. READ ENERGY TARGET (from arc, no LLM needed)
   tanda_planner reads energy_arc[current_index]
   Constructs prompt: "tango at 70% energy" or uses DJ's chat input
        │
2. SCORE ALL SONGS (one of three methods, chosen by the node)
        │
        ├── Method 2 (CoT LLM) — PREFERRED, best quality, ~2s latency (1 Gemini call)
        │     Gemini reads prompt + feature catalog → outputs feature ranges + weights
        │     → scores_from_cot_a_result() reconstructs per-song scores
        │
        ├── Method 1 (CLAP) — fallback if LLM unavailable, ~1s latency
        │     Encode prompt as text embedding, compare to audio embeddings
        │     ⚠ Requires style extracted from prompt first (regex/keyword)
        │     ⚠ Style is a HARD FILTER — CLAP only ranks within the correct style
        │
        └── Method 3 (SBERT) — fastest fallback, <0.5s, no API call
              Embed prompt, compute feature directions, rank by percentile
              ⚠ Same hard style filter required
        │
3. BUILD TANDA (from 02d_tanda_session.ipynb)
   build_tanda(scores, df, session, style, planning_mode)
        │
        ├── Convention mode: group by (orchestra, singer), pick combo with
        │   highest average score, enforce decade consistency + session no-repeat
        │
        └── Flexible mode: just pick top-N songs within the style
```

## Key Design Decisions

### Style is always a hard filter
All three methods score within a style. For Methods 1 and 3, style must be extracted from the prompt first (regex: "milonga" → milonga, "vals" → vals, default → tango). Method 2 (CoT LLM) can infer style from context, but we still apply it as a hard filter on the catalog before scoring.

### The node picks the scoring method (not the LLM)
The `tanda_planner` node decides based on availability, not LLM reasoning — because the choice is deterministic:

| Factor | Method 2 (CoT LLM) | Method 1 (CLAP) | Method 3 (SBERT) |
|---|---|---|---|
| Quality | Best | Good | Decent |
| Latency | ~2s (API call) | ~1s (local) | <0.5s (local) |
| Requires API | Yes (Gemini) | No | No |
| Requires audio embeddings | No | Yes (precomputed) | No |

Default: try Method 2. If API unavailable or latency budget tight, fall back to 3 (fastest) or 1 (if embeddings cached).

### `build_tanda()` is reused as-is
The function from `02d_tanda_session.ipynb` already handles:
- Convention vs flexible mode
- Tanda size rules (4 for tango, 3 for vals/milonga)
- Session no-repeat tracking
- Decade consistency
- Fallback when combos are exhausted

No need to rewrite — extract it to a production module and call it.

## What Changes

| File | Change |
|---|---|
| `atdj/tanda/builder.py` (new) | Extract `build_tanda()`, `SessionTracker`, score reconstruction functions from 02d notebook |
| `atdj/agent/state.py` | Add `session_tracker: SessionTracker` to persist no-repeat state across cycles |
| `atdj/agent/nodes.py` | Rewrite `tanda_planner` — call scoring + build_tanda directly, no LLM tool binding |
| `atdj/agent/tools.py` | Remove `search_catalog` (scoring logic moves into the node) |
| `atdj/agent/graph.py` | Add human-in-the-loop checkpoint after tanda_planner (optional) |

## Example: New `tanda_planner` Node (Pseudocode)

```python
from atdj.tanda.builder import (
    build_tanda, SessionTracker,
    scores_from_cot_a_result,
    scores_from_sbert_direction_result,
    scores_from_clap_result,
)

def tanda_planner(state: AgentState) -> dict:
    idx = state["current_tanda_index"]
    total = len(state["energy_arc"])
    if idx >= total:
        return {"session_complete": True}

    energy = state["energy_arc"][idx]
    style = _pick_style_for_position(idx, total)  # tango/vals/milonga rotation
    prompt = f"{style} at {energy:.0%} energy"

    # ── Score ────────────────────────────────────────────────────────
    # Node picks method directly — no LLM call needed for this decision.
    # Default to CoT (best quality), fall back to local methods if unavailable.
    df = _load_catalog()
    method = "cot_llm"
    try:
        result = call_cot_llm(prompt, feature_catalog)
        scores = scores_from_cot_a_result(result, df)
    except Exception:
        method = "sbert"
        scores = scores_from_sbert_direction_result(prompt, df)

    # ── Build tanda ──────────────────────────────────────────────────
    session = state["session_tracker"]
    planning_mode = state.get("planning_mode", "convention")
    tanda = build_tanda(scores, df, session, style=style,
                        planning_mode=planning_mode)

    # ── Scoring context ──────────────────────────────────────────────
    # Return enough info for the activity log and chat to explain the choice.
    # Without this, the DJ only sees track names and can't understand
    # *why* these tracks were chosen — the whole point of smart scoring.
    combo_scores = (
        scores.groupby([df["orchestra"], df["singer"]])
        .mean()
        .sort_values(ascending=False)
    )
    top = combo_scores.index[0]
    runner_up = combo_scores.index[1] if len(combo_scores) > 1 else None

    scoring_context = {
        "method_used": method,
        "top_combo": f"{top[0]} + {top[1]}",
        "top_combo_avg_score": round(float(combo_scores.iloc[0]), 3),
        "runner_up": (
            f"{runner_up[0]} + {runner_up[1]} ({combo_scores.iloc[1]:.3f})"
            if runner_up else None
        ),
        # This gives downstream nodes (and the chat) enough info to say:
        # "I picked Tanturi + Castillo (0.82) over Di Sarli + Rufino (0.76)
        #  because their 1942 recordings scored highest for rhythmic energy."
        # Without it, we'd have smart scoring with no way to explain it.
    }

    return {
        "upcoming_tandas": state["upcoming_tandas"] + [tanda],
        "scoring_context": scoring_context,
        "needs_cortina": True,
        "last_agent_action": "tanda_planned",
        "retry_count": 0,
        "activity_log": [
            _log("tanda_planner", "info",
                 f"Tanda {idx+1}/{total} planned ({style}, energy {energy:.0%})"),
            _log("tanda_planner", "decision",
                 f"Picked {scoring_context['top_combo']} "
                 f"(score {scoring_context['top_combo_avg_score']}) "
                 f"via {method}"
                 + (f", runner-up: {scoring_context['runner_up']}"
                    if scoring_context['runner_up'] else "")),
        ],
    }
```

### Where does the chat explanation come from?

The `tanda_planner` no longer calls an LLM for planning — it calls one for *scoring* (CoT Method 2). The chat explanation needs a separate, lightweight LLM call that reads `scoring_context` and produces a DJ-friendly message. This could be:

1. **A `chat_responder` node** after `tanda_planner` — takes `scoring_context` and generates a one-liner for the chat
2. **Part of the DJ chat flow** — when the DJ asks "why this tanda?", the LLM reads `scoring_context` from state and explains

Option 2 is simpler and avoids an extra LLM call every cycle. The scoring context sits in state, and the chat LLM uses it on demand.

## Dependencies

- WP-02 notebooks must be rerun with new data first (separate task in `wp02-notebook-data-migration.md`)
- CLAP embeddings need to be precomputed and cached for Method 1
- Feature catalog (`feature_catalog.pkl`) must exist for Method 2

## Effort Estimate

~5-6 hours:
- ~1 hour: extract `build_tanda` + score functions to `atdj/tanda/builder.py`
- ~1.5 hours: rewrite `tanda_planner` node with direct scoring (remove LLM tool binding)
- ~1 hour: add method selection + fallback logic
- ~0.5 hour: add scoring context to state + activity log integration
- ~1-2 hours: testing with real prompts and all three methods
