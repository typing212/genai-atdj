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

# Constants

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

# 2026-05-07: PARSE_PROMPT extended with an "Already known from prior turns"
# block so multi-round clarification doesn't re-ask about slots earlier turns
# already pinned. Original prompt had only {playlist_summary} and {user_message};
# new prompt also has {pinned_slots}. Graph structure unchanged.
# PARSE_PROMPT = """\
# You are parsing an audio adjustment request for a tango DJ app.
#
# Current playlist context:
# {playlist_summary}
#
# Feature to parameter mapping:
# ...
# (original prompt body retained in git history; see commit prior to 2026-05-07)
# """
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

IMPORTANT — when the user mentions both the current song AND another scope (e.g. "this song is harsh, fix the next tanda" or "the current track sounds bad, can we improve the rest"), pick the SCOPE attached to the action verb ("fix", "improve", "make", "apply"), not the one they used as descriptive context. In both examples the correct answer is `next_tanda` / `rest`, not `current`. The current song mention is just the user describing what made them notice the problem.

Reset keywords (direction="reset", feature and magnitude are ignored):
- "back to default", "use original", "undo", "revert", "reset", "restore",
  "remove my changes", "go back to normal", "original version", "no enhancement"

Already known from prior turns (treat as filled; do NOT ask about these again unless the current user message explicitly contradicts them):
{pinned_slots}

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

Rules for known slots:
- For each slot listed in "Already known from prior turns", copy that exact value into the JSON output unchanged.
- Override a known slot ONLY when the current user message explicitly contradicts it. Examples that DO override: previously scope=next_tanda, current message "actually all of them" → scope=rest; previously direction=up, current message "actually quieter" → direction=down. Examples that do NOT override: a clarification reply that is silent about a slot already pinned.
- If the known slots together with the current message already specify enough to act (feature + direction + scope are all filled, OR direction=reset with a scope), set `needs_clarification` to false and leave `clarification_question`/`clarification_options` empty. Do not ask about a slot that is already pinned.

Rules for `clarification_options`:
- Write user-facing labels in plain English. The user reads them as a numbered menu.
- DO NOT include internal codes like "(up)", "(down)", "(rest)", "(loudness)", or any parenthesized direction/feature tags.
- Good: "Make it louder", "Make it quieter", "More noise reduction", "Less noise reduction".
- Bad:  "Increase loudness (up)", "Decrease loudness (down)", "Noise reduction up".
- Maximum 4 options. Pick the 4 most likely interpretations — long menus (8+) overwhelm the user. If you can't narrow it down, ask a more focused `clarification_question`.

Set `needs_clarification` to true ONLY when you genuinely cannot infer enough from the user message AND the known-slot block AND the playlist context to act. If the request is fully unambiguous, return false and leave `clarification_question`/`clarification_options` empty.

If the user asks to change something that is NOT one of the supported features (loudness/bass/presence/noise/highpass/limiter) — e.g. "make it more sparkly", "add reverb", "speed it up" — set `feature` to null, `needs_clarification` to true, and use `clarification_question` to explain (briefly) which adjustments ARE supported, then offer the closest supported choices in `clarification_options`.
"""


def _format_pinned_slots(state: AdjustmentState) -> str:
    """Render the prior-turn pinned slots as a human-readable block for the
    parse prompt. Returns "(none)" when nothing is pinned yet so the LLM has
    a stable token sequence to anchor on rather than an empty placeholder.
    """
    items = [
        ("scope",       state.get("scope")),
        ("feature",     state.get("feature")),
        ("direction",   state.get("direction")),
        ("magnitude",   state.get("magnitude")),
        ("target_name", state.get("target_name")),
    ]
    lines = [f"- {k}: {v}" for k, v in items if v]
    return "\n".join(lines) if lines else "(none)"


# State

class AdjustmentState(TypedDict):
    user_message: str
    playlist: list[dict]
    current_index: int
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

    reply: str
    activity_log: Annotated[list, operator.add]
    # Routing signal set by resolve_pending_menu so the graph can branch on whether
    # the user's reply mapped to an open menu option, cancelled it, or was off-topic.
    resolution_outcome: Optional[str]


def _log(node: str, level: str, message: str, summary: bool = False) -> dict:
    return {"timestamp": datetime.now().isoformat(), "node": node,
            "level": level, "message": message, "summary": summary}


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


# Pure helpers (exported for tests)

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


# Menu-pick resolver
# Without this layer, a reply like "1" or "cancel" goes straight into parse_request
# and the LLM treats it as a fresh ambiguous message. The resolver maps menu picks
# heuristically (cheap, no extra LLM call) so the graph can carry forward the prior
# turn's intent (rejection menu) or feed clean text into parse_request (clarification).

_WORD_TO_NUM = {
    "first": 0, "second": 1, "third": 2, "fourth": 3, "fifth": 4,
    "sixth": 5, "seventh": 6, "eighth": 7, "ninth": 8,
    "1st": 0, "2nd": 1, "3rd": 2, "4th": 3, "5th": 4,
}


def _match_option(msg: str, options: list[str]) -> Optional[str]:
    """Try to map a user reply to one of the menu options.
    Returns the matched option text, or None for no clear match."""
    if not options:
        return None
    msg_clean = msg.strip().lower().rstrip(".!?,)")

    # 1. Numeric: "1", "1.", "1)", "(1)"
    num_match = re.match(r"^\(?([1-9])\)?[\.\)]?\s*$", msg_clean)
    if num_match:
        idx = int(num_match.group(1)) - 1
        if 0 <= idx < len(options):
            return options[idx]

    # 2. Word number: "first", "second", ... possibly with "the " or "option " prefix
    stripped = re.sub(r"^(?:the\s+|option\s+)", "", msg_clean).strip()
    if stripped in _WORD_TO_NUM:
        idx = _WORD_TO_NUM[stripped]
        if 0 <= idx < len(options):
            return options[idx]

    # 3. Exact label match (case-insensitive)
    for opt in options:
        if opt.lower() == msg_clean:
            return opt

    # 4. Substring match (option text contained in user reply, or vice versa for short user replies).
    #    Match the LONGEST containing-pair to avoid "rest" matching every option that has the word "rest".
    best = None
    best_score = 0
    for opt in options:
        opt_lower = opt.lower()
        if opt_lower in msg_clean or msg_clean in opt_lower:
            score = min(len(opt_lower), len(msg_clean))
            if score > best_score:
                best = opt
                best_score = score
    return best


def resolve_pending_menu(state: AdjustmentState) -> dict:
    """Entry node. If a clarification or rejection menu is open from the prior
    turn, try to resolve the user's new reply to one of the offered options
    BEFORE falling through to parse_request. Sets `resolution_outcome` for routing."""
    msg = state.get("user_message", "") or ""
    rejection_opts = state.get("rejection_options") or []
    clarif_opts = state.get("clarification_options") or []

    # ── Case 1: a current-song rejection menu was emitted last turn ──
    if rejection_opts:
        chosen = _match_option(msg, rejection_opts)
        # Fallback: bare keyword "cancel" anywhere in a short reply
        if chosen is None and re.search(r"\bcancel\b|\bnever\s*mind\b|\bnope\b", msg.lower()):
            chosen = next((o for o in rejection_opts if "cancel" in o.lower()), None)
        if chosen:
            base = {
                "rejected": False,
                "rejection_options": [],
                "needs_clarification": False,
                "clarification_options": [],
                "clarification_question": "",
            }
            chosen_lower = chosen.lower()
            if "cancel" in chosen_lower:
                return {
                    **base,
                    "resolution_outcome": "cancelled",
                    "reply": "Okay — no adjustment applied.",
                    "activity_log": [
                        _log("resolve_pending_menu", "info",
                             f"User cancelled rejection menu (reply: {msg!r})"),
                        _log("resolve_pending_menu", "info",
                             "Cancelled — no adjustment applied", summary=True),
                    ],
                }
            if "all songs after" in chosen_lower or "rest" in chosen_lower:
                return {
                    **base,
                    "resolution_outcome": "scope_resolved",
                    "scope": "rest",
                    "activity_log": [_log("resolve_pending_menu", "info",
                        f"Resolved rejection menu pick → scope=rest "
                        f"(carrying forward feature={state.get('feature')!r}, "
                        f"direction={state.get('direction')!r})")],
                }
            if "next tanda" in chosen_lower or "next set" in chosen_lower:
                return {
                    **base,
                    "resolution_outcome": "scope_resolved",
                    "scope": "next_tanda",
                    "activity_log": [_log("resolve_pending_menu", "info",
                        f"Resolved rejection menu pick → scope=next_tanda "
                        f"(carrying forward feature={state.get('feature')!r}, "
                        f"direction={state.get('direction')!r})")],
                }
            if "next song" in chosen_lower or "next track" in chosen_lower:
                return {
                    **base,
                    "resolution_outcome": "scope_resolved",
                    "scope": "next_song",
                    "activity_log": [_log("resolve_pending_menu", "info",
                        "Resolved rejection menu pick → scope=next_song")],
                }

        # No match: clear the menu + stale SCOPE (the rejection menu was opened
        # because scope=current was wrong, so the new reply is almost certainly
        # a scope correction). KEEP feature/direction/magnitude — those were
        # validly pinned in earlier turns and dropping them forces the user to
        # re-specify the change every time they tweak scope.
        return {
            "resolution_outcome": "no_menu_match",
            "rejected": False,
            "rejection_options": [],
            "scope": None,
            "target_name": None,
            "activity_log": [_log("resolve_pending_menu", "info",
                "Rejection menu open but reply didn't match any option — clearing scope only "
                "(keeping feature/direction/magnitude) and falling through to parse_request")],
        }

    # ── Case 2: a clarification menu was emitted last turn ──
    if clarif_opts:
        chosen = _match_option(msg, clarif_opts)
        if chosen:
            return {
                "user_message": chosen,
                "needs_clarification": False,
                "clarification_options": [],
                "clarification_question": "",
                "resolution_outcome": "clarif_resolved",
                "activity_log": [_log("resolve_pending_menu", "info",
                    f"Resolved clarification reply {msg!r} → {chosen!r} (rewriting user_message)")],
            }
        # Off-topic during a clarification: clear the menu + stale scope; keep
        # feature/direction/magnitude (same reasoning as the rejection-no-match
        # branch above — don't make the user re-pin already-resolved intent).
        return {
            "resolution_outcome": "no_menu_match",
            "needs_clarification": False,
            "clarification_options": [],
            "clarification_question": "",
            "scope": None,
            "target_name": None,
            "activity_log": [_log("resolve_pending_menu", "info",
                "Clarification open but reply didn't match — clearing scope only "
                "and falling through to parse_request")],
        }

    # No menu was open
    return {"resolution_outcome": "no_menu"}


def emit_cancel(state: AdjustmentState) -> dict:
    """Terminal node when the user cancelled an open rejection/clarification."""
    return {"reply": state.get("reply") or "Okay — no adjustment applied."}


# Nodes

def parse_request(state: AdjustmentState) -> dict:
    summary = _playlist_summary(state["playlist"], state["current_index"])
    # 2026-05-07: feed the prior-turn pinned slots into the prompt so the LLM
    # does not re-ask about anything already resolved. The Python-side merge
    # and the enough_to_act override below remain as defense-in-depth.
    # prompt = PARSE_PROMPT.format(
    #     playlist_summary=summary,
    #     user_message=state["user_message"],
    # )
    pinned_slots = _format_pinned_slots(state)
    prompt = PARSE_PROMPT.format(
        playlist_summary=summary,
        pinned_slots=pinned_slots,
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

    # 2026-05-01: when a clarification reply only fills in PART of the slots
    # (e.g. user replies "Too loud" — gives feature/direction but no scope),
    # don't blow away prior state. Fall back to the previous turn's value when
    # the LLM returns null for a given field.
    merged_scope     = parsed.get("scope")     or state.get("scope")
    merged_feature   = parsed.get("feature")   or state.get("feature")
    merged_direction = parsed.get("direction") or state.get("direction")
    merged_magnitude = parsed.get("magnitude") or state.get("magnitude")
    merged_target    = parsed.get("target_name") or state.get("target_name")

    needs_clarif = bool(parsed.get("needs_clarification"))
    # 2026-05-01: when the merged state already has every slot we need, override
    # the LLM's needs_clarification=true. Otherwise the user picks a clarif
    # option, the LLM sees only that option text (not the prior context),
    # decides it's still ambiguous, and re-asks the same question forever.
    enough_to_act = bool(merged_feature and merged_direction and merged_scope)
    reset_only    = merged_direction == "reset" and bool(merged_scope)
    if needs_clarif and (enough_to_act or reset_only):
        needs_clarif = False

    return {
        "scope": merged_scope,
        "feature": merged_feature,
        "direction": merged_direction,
        "magnitude": merged_magnitude,
        "target_name": merged_target,
        "needs_clarification": needs_clarif,
        "clarification_question": "" if not needs_clarif else (parsed.get("clarification_question") or ""),
        "clarification_options": [] if not needs_clarif else (parsed.get("clarification_options") or []),
        "activity_log": [_log("parse_request", "info",
                               f"Parsed: scope={parsed.get('scope')} feature={parsed.get('feature')} "
                               f"direction={parsed.get('direction')} magnitude={parsed.get('magnitude')} "
                               f"→ merged scope={merged_scope} feature={merged_feature} direction={merged_direction} "
                               f"needs_clarif={needs_clarif}")],
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
        # "Apply to the next tanda only",  # original — DSP on 4 tango tracks (~80s)
        "Apply to the next song only",  # narrower scope, DSP on 1 track (~25s) — demo-friendly
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
        "activity_log": [
            _log("resolve_targets", "warning", "No target tracks found"),
            # 2026-05-01: surface the no-targets case on the on-screen Session Log too
            _log("resolve_targets", "warning",
                 "No tracks to adjust — nothing matched after the current position",
                 summary=True),
        ],
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
    # 2026-05-01: Quality Enhance toggle removed. Audio enhancement only runs
    # from the chat path now, so:
    #   - reset always deletes the processed file (nothing else maintains one)
    #   - we no longer store an "intent" to fold into a future PLAN (no PLAN hook)
    direction = state["direction"]
    target_indices = state["target_indices"]
    resolved_paths = state["resolved_paths"]
    overrides = state["computed_overrides"]
    output_dir = Path(state["output_dir"])

    if direction == "reset":
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
            "activity_log": [_log("execute_enhancement", "info",
                                   f"reset: deleted {deleted} processed files")],
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
            "reply": "No audio files found for the target tracks — they may not be in your local library.",
            "activity_log": [_log("execute_enhancement", "warning", "No valid file paths found for target tracks")],
        }

    try:
        results = enhance_tanda(valid_paths, output_dir, param_overrides=valid_overrides)
    except Exception as e:
        return {
            "execution_results": [],
            "reply": f"Enhancement failed: {e}",
            "activity_log": [_log("execute_enhancement", "error", str(e))],
        }

    return {
        "execution_results": results,
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
            "activity_log": [
                _log("format_reply", "info", "Formatted reset reply"),
                # 2026-05-01: summary entry for the on-screen Session Log
                _log("format_reply", "info",
                     f"Reset {deleted if deleted else n} track{'s' if (deleted if deleted else n) != 1 else ''} to default",
                     summary=True),
            ],
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

    # 2026-05-01: build a concise on-screen summary line
    summary_parts = []
    if magnitude_label:
        summary_parts.append(magnitude_label.capitalize())
    summary_parts.append(direction_word)
    summary_parts.append(feature_label)
    summary_parts.append(f"for {n} track{'s' if n != 1 else ''}")
    summary_msg = " ".join(summary_parts)

    return {
        "reply": reply,
        "activity_log": [
            _log("format_reply", "info", f"Formatted reply for {n} tracks"),
            # On-screen summary entry
            _log("format_reply", "info", summary_msg, summary=True),
        ],
    }


# Routing

def _route_after_resolve_menu(state: AdjustmentState) -> str:
    outcome = state.get("resolution_outcome")
    if outcome == "cancelled":
        return "emit_cancel"
    if outcome == "scope_resolved":
        # Skip parse_request entirely — feature/direction/magnitude are already
        # carried from the prior turn, and we just set scope. Go straight to
        # target resolution.
        return "resolve_targets"
    # clarif_resolved (user_message rewritten) and no_menu(_match) both go through parse_request normally.
    return "parse_request"


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


# Graph builder

def build_adjustment_graph() -> StateGraph:
    g = StateGraph(AdjustmentState)

    # 2026-05-01: new entry node `resolve_pending_menu` runs first to catch
    # menu-pick replies (numbers, keywords, option text) before parse_request.
    g.add_node("resolve_pending_menu", resolve_pending_menu)
    g.add_node("emit_cancel", emit_cancel)
    g.add_node("parse_request", parse_request)
    g.add_node("clarify", clarify_node)
    g.add_node("reject_current", reject_current)
    g.add_node("resolve_targets", resolve_targets_node)
    g.add_node("no_targets", no_targets_node)
    g.add_node("measure_reference", measure_reference)
    g.add_node("compute_adjustments", compute_adjustments)
    g.add_node("execute_enhancement", execute_enhancement)
    g.add_node("format_reply", format_reply)

    g.set_entry_point("resolve_pending_menu")
    g.add_conditional_edges("resolve_pending_menu", _route_after_resolve_menu, {
        "emit_cancel": "emit_cancel",
        "resolve_targets": "resolve_targets",
        "parse_request": "parse_request",
    })
    g.add_edge("emit_cancel", END)
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
