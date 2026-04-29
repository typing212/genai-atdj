"""Mini LangGraph for natural-language audio adjustment requests.

Flow: parse_request → resolve_targets → measure_reference → compute_adjustments
      → execute_enhancement → format_reply

Short-circuits to clarify_node or reject_current when needed.
"""
from __future__ import annotations

import json
import operator
import re
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional

from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from atdj.audio.enhancement import (
    analyze_tanda_tracks,
    compute_per_track_params,
    enhance_tanda,
)
from atdj.config import PROCESSED_DIR, get_ui_llm

# ── Constants ─────────────────────────────────────────────────────────────────

FEATURE_PARAM = {
    "loudness": "target_lufs",
    "bass": "eq_low_gain",
    "presence": "eq_vocal_gain",
    "noise": "noise_prop",
    "highpass": "highpass_hz",
    "limiter": "limiter_threshold_db",
}

MAGNITUDE_DELTA = {
    "loudness": {"small": 1.5,  "medium": 3.0,  "large": 5.0},
    "bass":     {"small": 0.5,  "medium": 1.0,  "large": 2.0},
    "presence": {"small": 0.5,  "medium": 1.0,  "large": 2.0},
    "noise":    {"small": 0.1,  "medium": 0.2,  "large": 0.3},
    "highpass": {"small": 20.0, "medium": 40.0, "large": 60.0},
    "limiter":  {"small": 0.5,  "medium": 1.0,  "large": 2.0},
}

DEFAULT_PARAMS = {
    "target_lufs": -14.0,
    "noise_prop": 0.5,
    "eq_low_gain": 2.0,
    "eq_vocal_gain": 1.5,
    "highpass_hz": 80.0,
    "hiss_cutoff_override": None,
    "limiter_threshold_db": -1.0,
}

PARSE_PROMPT = """\
You are parsing an audio adjustment request for a tango DJ app.

Current playlist context:
{playlist_summary}

Feature to parameter mapping:
- loudness  : overall volume level (LUFS)
- bass      : low-frequency warmth (800 Hz shelf)
- presence  : vocal clarity / brightness (2000 Hz peak)
- noise     : background hiss / noise reduction amount
- highpass  : low-rumble cutoff frequency
- limiter   : peak ceiling / dynamic headroom

Magnitude keywords:
- small  : "a bit", "slightly", "a touch", "just a little", "a tad"
- medium : "more", "noticeably", "somewhat", "quite"
- large  : "much more", "a lot", "significantly", "very"

Scope keywords:
- current   : "this song", "the one playing", "current track", "now playing"
- next_song : "the next song", "next track", "next one"
- next_tanda: "the next tanda", "next set"
- rest      : "following", "rest", "everything after", "from here on", "all after"
- specific  : user names an orchestra, style, or song title

Reset keywords (direction="reset", feature and magnitude are ignored):
- "back to default", "use original", "undo", "revert", "reset", "restore",
  "remove my changes", "go back to normal", "original version", "no enhancement"

User message: "{user_message}"

Return a JSON object with exactly these fields (no markdown, no extra text):
{{
  "scope": "current|next_song|next_tanda|rest|specific|null",
  "feature": "loudness|bass|presence|noise|highpass|limiter|null",
  "direction": "up|down|reset|null",
  "magnitude": "small|medium|large|null",
  "target_name": "<orchestra/style/title string or null>",
  "needs_clarification": true|false,
  "clarification_question": "<question string or null>",
  "clarification_options": ["option1", "option2"] or []
}}
"""


# ── State ─────────────────────────────────────────────────────────────────────

class AdjustmentState(TypedDict):
    user_message: str
    playlist: list[dict]
    current_index: int
    auto_enhance_on: bool
    output_dir: str
    resolved_paths: dict           # {playlist_index(int): raw_file_path_str}

    scope: Optional[str]
    feature: Optional[str]
    direction: Optional[str]
    magnitude: Optional[str]
    target_name: Optional[str]

    needs_clarification: bool
    clarification_question: str
    clarification_options: list[str]
    rejected: bool
    rejection_options: list[str]

    target_indices: list[int]
    reference_params: Optional[dict]
    computed_overrides: list[dict]
    execution_results: list[dict]

    store_intent: bool
    intent_to_store: Optional[dict]

    reply: str
    activity_log: Annotated[list, operator.add]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _log(node: str, level: str, message: str) -> dict:
    return {"timestamp": datetime.now().isoformat(), "node": node,
            "level": level, "message": message}


def _playlist_summary(playlist: list[dict], current_index: int) -> str:
    lines = []
    current = playlist[current_index] if 0 <= current_index < len(playlist) else None
    if current and current.get("type") == "song":
        lines.append(f"NOW PLAYING (index {current_index}): {current.get('title')} "
                     f"| {current.get('orchestra')} | {current.get('style')} "
                     f"| tanda_id={current.get('tanda_id', '?')}")
    upcoming = [
        (i, item) for i, item in enumerate(playlist)
        if i > current_index and item.get("type") == "song"
    ][:6]
    for i, item in upcoming:
        lines.append(f"  [{i}] {item.get('title')} | {item.get('orchestra')} "
                     f"| {item.get('style')} | tanda_id={item.get('tanda_id', '?')}")
    return "\n".join(lines) if lines else "Playlist is empty."


def _parse_llm_json(text: str) -> dict:
    text = text.strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group())
    raise ValueError(f"No JSON object found in LLM response: {text!r}")


def _get_llm():
    return get_ui_llm()


# ── Pure helpers (exported for tests) ────────────────────────────────────────

def apply_constraint(direction: str, ref_value: float, delta: float,
                     track_auto_value: float) -> float:
    """Apply relative floor/ceiling constraint for a single parameter value."""
    if direction == "reset":
        return track_auto_value
    requested_target = ref_value + delta * (1 if direction == "up" else -1)
    if direction == "up":
        return max(track_auto_value, requested_target)
    return min(track_auto_value, requested_target)


def resolve_targets(scope: str, playlist: list[dict], current_index: int,
                    target_name: Optional[str]) -> list[int]:
    """Map a scope string to concrete playlist indices (songs only, not cortinas)."""
    songs_after = [
        i for i, item in enumerate(playlist)
        if i > current_index and item.get("type") == "song"
    ]
    if scope == "next_song":
        return songs_after[:1]
    if scope == "next_tanda":
        current_item = playlist[current_index] if 0 <= current_index < len(playlist) else {}
        current_tid = current_item.get("tanda_id")
        next_tid = None
        for i in songs_after:
            tid = playlist[i].get("tanda_id")
            if tid != current_tid:
                next_tid = tid
                break
        if next_tid is None:
            return []
        return [i for i in songs_after if playlist[i].get("tanda_id") == next_tid]
    if scope == "rest":
        return songs_after
    if scope == "specific" and target_name:
        name_lower = target_name.lower()
        return [
            i for i, item in enumerate(playlist)
            if i > current_index and item.get("type") == "song" and (
                name_lower in (item.get("orchestra") or "").lower() or
                name_lower in (item.get("style") or "").lower() or
                name_lower in (item.get("title") or "").lower()
            )
        ]
    return []


def compute_intent_overrides(intent: dict, track_count: int) -> list[dict]:
    """Compute per-track overrides from a stored intent using DEFAULT_PARAMS as reference.

    Used by the PLAN handler to apply a persisted intent to a freshly planned session.
    """
    feature = intent.get("feature")
    direction = intent.get("direction")
    magnitude = intent.get("magnitude", "small")
    if not feature or not direction or direction == "reset":
        return [{} for _ in range(track_count)]
    param_key = FEATURE_PARAM.get(feature)
    if not param_key:
        return [{} for _ in range(track_count)]
    ref_value = DEFAULT_PARAMS[param_key]
    delta = MAGNITUDE_DELTA[feature][magnitude]
    requested_target = ref_value + delta * (1 if direction == "up" else -1)
    override = {param_key: requested_target}
    return [override for _ in range(track_count)]


# ── Nodes ─────────────────────────────────────────────────────────────────────

def parse_request(state: AdjustmentState) -> dict:
    summary = _playlist_summary(state["playlist"], state["current_index"])
    prompt = PARSE_PROMPT.format(
        playlist_summary=summary,
        user_message=state["user_message"],
    )
    llm = _get_llm()
    parsed = None
    for attempt in range(3):
        try:
            resp = llm.invoke([HumanMessage(content=prompt)])
            parsed = _parse_llm_json(resp.content)
            break
        except Exception:
            if attempt == 2:
                return {
                    "needs_clarification": True,
                    "clarification_question": "I had trouble understanding that. Could you rephrase your audio adjustment request?",
                    "clarification_options": ["Make it louder", "Make it quieter", "Less harsh", "Less noisy"],
                    "activity_log": [_log("parse_request", "warning", "JSON parse failed after 3 attempts")],
                }

    return {
        "scope": parsed.get("scope") or None,
        "feature": parsed.get("feature") or None,
        "direction": parsed.get("direction") or None,
        "magnitude": parsed.get("magnitude") or None,
        "target_name": parsed.get("target_name") or None,
        "needs_clarification": bool(parsed.get("needs_clarification")),
        "clarification_question": parsed.get("clarification_question") or "",
        "clarification_options": parsed.get("clarification_options") or [],
        "activity_log": [_log("parse_request", "info",
                               f"Parsed: scope={parsed.get('scope')} feature={parsed.get('feature')} "
                               f"direction={parsed.get('direction')} magnitude={parsed.get('magnitude')}")],
    }


def clarify_node(state: AdjustmentState) -> dict:
    q = state.get("clarification_question", "Could you clarify your audio request?")
    opts = state.get("clarification_options", [])
    opts_text = "\n".join(f"{i+1}. {o}" for i, o in enumerate(opts)) if opts else ""
    reply = q + ("\n\n" + opts_text if opts_text else "")
    return {
        "reply": reply,
        "activity_log": [_log("clarify_node", "info", "Sent clarification question to user")],
    }


def reject_current(state: AdjustmentState) -> dict:
    options = [
        "Apply to all songs after this one (rest of session)",
        "Apply to the next tanda only",
        "Cancel",
    ]
    opts_text = "\n".join(f"{i+1}. {o}" for i, o in enumerate(options))
    return {
        "rejected": True,
        "rejection_options": options,
        "reply": (
            "Cannot modify a track that is already playing. Would you like to:\n\n"
            + opts_text
        ),
        "activity_log": [_log("reject_current", "info", "Current song requested — offered alternatives")],
    }


def resolve_targets_node(state: AdjustmentState) -> dict:
    indices = resolve_targets(
        state["scope"], state["playlist"], state["current_index"], state.get("target_name")
    )
    log_msg = f"Resolved {len(indices)} target tracks for scope={state['scope']}"
    return {
        "target_indices": indices,
        "activity_log": [_log("resolve_targets", "info", log_msg)],
    }


def no_targets_node(state: AdjustmentState) -> dict:
    return {
        "reply": "No tracks found matching that description after the current position.",
        "activity_log": [_log("resolve_targets", "warning", "No target tracks found")],
    }


def measure_reference(state: AdjustmentState) -> dict:
    if state.get("direction") == "reset":
        return {
            "reference_params": DEFAULT_PARAMS.copy(),
            "activity_log": [_log("measure_reference", "info", "Reset direction — skipped measurement, using defaults")],
        }
    current_path = state["resolved_paths"].get(state["current_index"])
    if not current_path or not Path(current_path).exists():
        return {
            "reference_params": DEFAULT_PARAMS.copy(),
            "activity_log": [_log("measure_reference", "warning",
                                   "Current song file not found — using default params as reference")],
        }
    try:
        profiles = analyze_tanda_tracks([Path(current_path)])
        params_list, _ = compute_per_track_params(profiles)
        ref = params_list[0]
        return {
            "reference_params": ref,
            "activity_log": [_log("measure_reference", "info",
                                   f"Measured current song: lufs={profiles[0]['lufs']:.1f} "
                                   f"snr={profiles[0]['snr']:.1f} centroid={profiles[0]['spectral_centroid']:.0f}Hz")],
        }
    except Exception as e:
        return {
            "reference_params": DEFAULT_PARAMS.copy(),
            "activity_log": [_log("measure_reference", "warning", f"Measurement failed ({e}) — using defaults")],
        }


def compute_adjustments(state: AdjustmentState) -> dict:
    direction = state["direction"]
    feature = state.get("feature")
    magnitude = state.get("magnitude", "small")
    ref_params = state["reference_params"] or DEFAULT_PARAMS
    target_indices = state["target_indices"]
    resolved_paths = state["resolved_paths"]

    if direction == "reset":
        overrides = [{} for _ in target_indices]
        return {
            "computed_overrides": overrides,
            "activity_log": [_log("compute_adjustments", "info",
                                   f"Reset: {len(target_indices)} tracks will be re-enhanced adaptively")],
        }

    param_key = FEATURE_PARAM.get(feature)
    if not param_key:
        return {
            "computed_overrides": [{} for _ in target_indices],
            "activity_log": [_log("compute_adjustments", "warning", f"Unknown feature: {feature}")],
        }

    ref_value = ref_params.get(param_key, DEFAULT_PARAMS[param_key])
    delta = MAGNITUDE_DELTA[feature][magnitude]

    target_paths = [
        Path(resolved_paths[i]) for i in target_indices
        if resolved_paths.get(i) and Path(resolved_paths[i]).exists()
    ]

    if target_paths:
        try:
            profiles = analyze_tanda_tracks(target_paths)
            auto_params_list, _ = compute_per_track_params(profiles)
        except Exception:
            auto_params_list = [DEFAULT_PARAMS.copy() for _ in target_paths]
    else:
        auto_params_list = []

    overrides = []
    path_idx = 0
    for i in target_indices:
        if resolved_paths.get(i) and Path(resolved_paths[i]).exists():
            auto_val = auto_params_list[path_idx].get(param_key, DEFAULT_PARAMS[param_key])
            path_idx += 1
        else:
            auto_val = DEFAULT_PARAMS[param_key]
        final_val = apply_constraint(direction, ref_value, delta, auto_val)
        overrides.append({param_key: final_val})

    return {
        "computed_overrides": overrides,
        "activity_log": [_log("compute_adjustments", "info",
                               f"Computed overrides for {len(overrides)} tracks: "
                               f"feature={feature} direction={direction} magnitude={magnitude} "
                               f"ref={ref_value:.2f} delta={delta}")],
    }


def execute_enhancement(state: AdjustmentState) -> dict:
    direction = state["direction"]
    auto_enhance_on = state["auto_enhance_on"]
    target_indices = state["target_indices"]
    resolved_paths = state["resolved_paths"]
    overrides = state["computed_overrides"]
    output_dir = Path(state["output_dir"])

    if direction == "reset" and not auto_enhance_on:
        deleted = 0
        for i in target_indices:
            raw_path = resolved_paths.get(i)
            if raw_path:
                stem = Path(raw_path).stem
                processed = PROCESSED_DIR / (stem + "_enhanced.wav")
                if processed.exists():
                    processed.unlink()
                    deleted += 1
        return {
            "execution_results": [{"deleted": deleted}],
            "store_intent": False,
            "intent_to_store": None,
            "activity_log": [_log("execute_enhancement", "info",
                                   f"auto_enhance OFF + reset: deleted {deleted} processed files")],
        }

    valid_paths = [
        Path(resolved_paths[i]) for i in target_indices
        if resolved_paths.get(i) and Path(resolved_paths[i]).exists()
    ]
    valid_overrides = [
        overrides[j] for j, i in enumerate(target_indices)
        if resolved_paths.get(i) and Path(resolved_paths[i]).exists()
    ]

    if not valid_paths:
        return {
            "execution_results": [],
            "store_intent": False,
            "intent_to_store": None,
            "reply": "No audio files found for the target tracks — they may not be in your local library.",
            "activity_log": [_log("execute_enhancement", "warning", "No valid file paths found for target tracks")],
        }

    try:
        results = enhance_tanda(
            valid_paths, output_dir,
            param_overrides=valid_overrides if direction != "reset" else None,
        )
    except Exception as e:
        return {
            "execution_results": [],
            "store_intent": False,
            "intent_to_store": None,
            "reply": f"Enhancement failed: {e}",
            "activity_log": [_log("execute_enhancement", "error", str(e))],
        }

    should_store = auto_enhance_on and direction != "reset"
    return {
        "execution_results": results,
        "store_intent": should_store,
        "intent_to_store": {
            "feature": state.get("feature"),
            "direction": direction,
            "magnitude": state.get("magnitude", "small"),
        } if should_store else None,
        "activity_log": [_log("execute_enhancement", "info",
                               f"Enhanced {len(results)} tracks successfully")],
    }


def format_reply(state: AdjustmentState) -> dict:
    results = state.get("execution_results", [])
    direction = state.get("direction")
    feature = state.get("feature")
    magnitude = state.get("magnitude")
    n = len(results)

    if not results:
        return {"reply": state.get("reply") or "No tracks were modified."}

    if direction == "reset":
        deleted = results[0].get("deleted", 0) if results and "deleted" in results[0] else n
        return {
            "reply": f"Reverted {deleted if deleted else n} tracks to their default adaptive enhancement.",
            "activity_log": [_log("format_reply", "info", "Formatted reset reply")],
        }

    direction_word = "increased" if direction == "up" else "reduced"
    feature_label = {
        "loudness": "loudness", "bass": "bass", "presence": "vocal presence",
        "noise": "noise reduction", "highpass": "low-cut filter", "limiter": "limiter ceiling",
    }.get(feature, feature or "audio parameter")
    magnitude_label = {"small": "slightly", "medium": "moderately", "large": "significantly"}.get(
        magnitude, ""
    )

    reply = (
        f"Done! {magnitude_label.capitalize()} {direction_word} {feature_label} "
        f"for {n} track{'s' if n != 1 else ''}. "
        f"Tracks that were already {'louder' if direction == 'up' else 'softer'} "
        f"than the target were left unchanged."
    ).strip()

    if state.get("store_intent"):
        reply += "\n\nThis preference will also apply to future session plans while Auto Enhance is on."

    return {
        "reply": reply,
        "activity_log": [_log("format_reply", "info", f"Formatted reply for {n} tracks")],
    }


# ── Routing ───────────────────────────────────────────────────────────────────

def _route_after_parse(state: AdjustmentState) -> str:
    if state.get("needs_clarification"):
        return "clarify"
    if state.get("scope") == "current":
        return "reject_current"
    return "resolve_targets"


def _route_after_resolve(state: AdjustmentState) -> str:
    if not state.get("target_indices"):
        return "no_targets"
    return "measure_reference"


# ── Graph builder ──────────────────────────────────────────────────────────────

def build_adjustment_graph() -> StateGraph:
    g = StateGraph(AdjustmentState)

    g.add_node("parse_request", parse_request)
    g.add_node("clarify", clarify_node)
    g.add_node("reject_current", reject_current)
    g.add_node("resolve_targets", resolve_targets_node)
    g.add_node("no_targets", no_targets_node)
    g.add_node("measure_reference", measure_reference)
    g.add_node("compute_adjustments", compute_adjustments)
    g.add_node("execute_enhancement", execute_enhancement)
    g.add_node("format_reply", format_reply)

    g.set_entry_point("parse_request")
    g.add_conditional_edges("parse_request", _route_after_parse, {
        "clarify": "clarify",
        "reject_current": "reject_current",
        "resolve_targets": "resolve_targets",
    })
    g.add_edge("clarify", END)
    g.add_edge("reject_current", END)
    g.add_conditional_edges("resolve_targets", _route_after_resolve, {
        "no_targets": "no_targets",
        "measure_reference": "measure_reference",
    })
    g.add_edge("no_targets", END)
    g.add_edge("measure_reference", "compute_adjustments")
    g.add_edge("compute_adjustments", "execute_enhancement")
    g.add_edge("execute_enhancement", "format_reply")
    g.add_edge("format_reply", END)

    return g.compile()
