# Proposal: Audio Enhancement Node in LangGraph Agent

## Problem

The audio enhancement pipeline (WP-08) works as a standalone module, but it's not integrated into the agent's planning flow. A DJ using the UI has to either pre-process all tracks or skip enhancement entirely. We want enhancement to happen automatically when the agent plans a tanda — but only when the DJ enables it.

## Current Agent Flow

```
session_init → tanda_planner → cortina_selector → queue_publisher → (next cycle)
```

The agent plans a tanda, selects a cortina, and publishes to the queue. No audio processing happens.

## Proposed Change

Add one new node: **`audio_enhancer`**, placed after `queue_publisher`.

```
session_init → tanda_planner → cortina_selector → queue_publisher → audio_enhancer → (next cycle)
```

### What `audio_enhancer` does

1. Check if `enhancement_enabled` is `True` in state (controlled by a UI toggle)
2. If `False` → pass through, return state unchanged
3. If `True` → call `enhance_tanda(track_paths, output_dir)` on the current tanda's tracks
4. Update the tanda's file paths in the queue to point to the enhanced WAV files
5. If enhancement fails for any reason, keep the original file paths (graceful fallback)

### Why this position in the graph

- The tanda is already planned and validated — we know exactly which tracks to enhance
- Enhancement runs during the previous tanda's playback (~10 min window, pipeline takes ~5 seconds per track)
- Cortinas don't need enhancement, so we skip them
- If enhancement fails, original files still play — no disruption

## Changes Required

| File | Change |
|---|---|
| `atdj/agent/state.py` | Add `enhancement_enabled: bool` field to `AgentState` |
| `atdj/agent/nodes.py` | Add `audio_enhancer` node function |
| `atdj/agent/graph.py` | Add node and update edge: `queue_publisher → audio_enhancer` |
| `atdj/ui/page_main.py` | Add toggle switch that sets `enhancement_enabled` in session state |

### What we don't need to change

- `tanda_planner` and its tools — planning logic stays the same
- `cortina_selector` — cortinas don't get enhanced
- LLM prompts — enhancement is automatic, not a reasoning decision
- `atdj/audio/enhancement.py` — already built and tested

## How It Connects to WP-08

The node calls functions from `atdj/audio/enhancement.py` (already built and tested):

```
audio_enhancer node
    │
    ├── enhance_tanda(track_paths, output_dir)     ← from atdj.audio.enhancement
    │       │
    │       ├── analyze_tanda_tracks()              ← measures SNR, LUFS, spectral centroid
    │       ├── compute_per_track_params()           ← derives adaptive noise_prop, EQ per track
    │       └── enhance_track() × 3                  ← runs the full pipeline on each track
    │               │
    │               ├── noise reduction
    │               ├── EQ (adaptive gains)
    │               ├── LUFS normalization
    │               ├── limiter
    │               └── dynamic hiss filter
    │
    └── updates tanda file paths → enhanced WAVs
```

The node itself is a thin wrapper — all the DSP logic lives in `enhancement.py`.

## Example Node Implementation

```python
from pathlib import Path
from atdj.audio.enhancement import enhance_tanda

def audio_enhancer(state: AgentState) -> dict:
    if not state.get("enhancement_enabled", False):
        return {}  # UI toggle is off, pass through

    tanda = state["upcoming_tandas"][-1]
    track_paths = [resolve_file_path(t.filename) for t in tanda.tracks]
    output_dir = Path("data/processed/enhanced")

    try:
        # This calls analyze_tanda_tracks → compute_per_track_params → enhance_track
        # Takes ~5 seconds per track, runs during previous tanda playback
        results = enhance_tanda(track_paths, output_dir)
        # Point queue to enhanced files instead of originals
        for track, result in zip(tanda.tracks, results):
            track.enhanced_file_path = result["output_path"]
    except Exception:
        pass  # enhancement failed — keep original file paths, no disruption

    return {"upcoming_tandas": state["upcoming_tandas"]}
```

## Effort Estimate

~2-3 hours — the enhancement logic is already built and tested. This is mostly wiring.
