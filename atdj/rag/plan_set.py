"""
plan_set.py
-----------
Plans a full milonga set: N tandas in a fixed style order, drawn from a
single user prompt, with no repeated combo_key across the set.

Core idea
---------
  1. Translate the user prompt ONCE → base_bundle  (LLM call happens here)
  2. For each slot in set_schema, build a slot_bundle by overriding only
     the 'style' field in base_bundle.
  3. Run select_tanda() on the catalog restricted to tracks whose combo_key
     has not yet been used.
  4. Collect results into a SetResult.

This keeps select_tanda() completely unchanged — it is just called
once per slot with a narrowed catalog pool.

Default set schema (traditional milonga structure):
    Tango · Tango · Vals · Tango · Tango · Milonga

Usage (standalone):
    python plan_set.py --prompt "romantic 1940s Di Sarli style, smooth and elegant"
    python plan_set.py --prompt "..." --schema tango tango vals tango tango milonga
    python plan_set.py --fixed-merged '{"style":null,"bpm_label":"moderate",...}' \\
                       --schema tango vals milonga

Or import:
    from plan_set import plan_set, SetResult, DEFAULT_SET_SCHEMA
    from select_tanda import select_tanda
    import pandas as pd

    df  = pd.read_csv("../../data/reduced_catalog.csv")
    result = plan_set(
        prompt="romantic 1940s, smooth",
        catalog_df=df,
        provider="gemini",
    )
    for slot in result.slots:
        print(slot.combo_key, slot.mean_score)
"""

from __future__ import annotations

import copy
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pandas as pd

# ---------------------------------------------------------------------------
# Allow running from any working directory by finding select_tanda on the path
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent
for _candidate in [_HERE, _HERE / "atdj" / "rag", Path("atdj/rag")]:
    if (_candidate / "select_tanda.py").exists():
        sys.path.insert(0, str(_candidate))
        break

from select_tanda import select_tanda, TandaResult  # noqa: E402


# ── Constants ──────────────────────────────────────────────────────────────

DEFAULT_SET_SCHEMA: list[str] = [
    "tango",
    "tango",
    "vals",
    "tango",
    "tango",
    "milonga",
]

VALID_STYLES = {"tango", "vals", "milonga"}


# ── Result dataclass ───────────────────────────────────────────────────────

@dataclass
class SetResult:
    """
    The output of plan_set().

    Attributes
    ----------
    slots : list[TandaResult]
        One TandaResult per position in set_schema.  A slot with an empty
        tanda list means selection failed for that position (see warnings).
    set_schema : list[str]
        The style order that was requested.
    base_bundle : dict
        The merged feature bundle produced from the user prompt (shared across
        all slots before style injection).
    used_combo_keys : list[str]
        The combo_key chosen for each slot, in order.  Empty string = failed slot.
    warnings : list[str]
        Human-readable messages for any slot that could not be filled.
    """
    slots:           list[TandaResult]
    set_schema:      list[str]
    base_bundle:     dict
    used_combo_keys: list[str]
    warnings:        list[str] = field(default_factory=list)


# ── Prompt translation helper ──────────────────────────────────────────────

def _translate_prompt(
    prompt: str,
    catalog_df: pd.DataFrame,
    provider: str,
) -> dict:
    """
    Run the two-layer LLM translation and return the merged bundle dict.
    Falls back to a minimal bundle if the import or API call fails.
    """
    try:
        # Support both flat layout (prompt_to_features.py in same dir) and
        # the package layout (atdj/rag/prompt_to_features.py).
        for _candidate in [_HERE, _HERE / "atdj" / "rag", Path("atdj/rag")]:
            if (_candidate / "prompt_to_features.py").exists():
                sys.path.insert(0, str(_candidate))
                break

        from prompt_to_features import build_translator  # type: ignore
        translator = build_translator(catalog_df, provider=provider)
        bundle = translator.translate(prompt)
        merged: dict = bundle.merged if hasattr(bundle, "merged") else bundle
        return merged
    except Exception as exc:
        print(f"[plan_set] WARNING: LLM translation failed ({exc.__class__.__name__}: {exc})")
        print("[plan_set] Using minimal fallback bundle — style, scoring, and tags will be generic.")
        return {
            "year": None, "decade": None, "orchestra": None, "singer": None,
            "style": None, "album": None,
            "bpm_label": "moderate", "danceability_label": "moderate",
            "key": None, "chords_changes_rate": "moderate",
            "energy_label": "moderate",
            "tags": [],
        }


# ── Slot bundle builder ────────────────────────────────────────────────────

def _make_slot_bundle(base_bundle: dict, slot_style: str) -> dict:
    """
    Return a shallow copy of base_bundle with style overridden to slot_style.

    The style field is the ONLY thing that changes between slots.  All mood,
    energy, tempo, and tag constraints from the user's original prompt carry
    through unchanged — they describe the *feel* of the whole set.
    """
    slot = copy.copy(base_bundle)
    slot["style"] = slot_style.lower().strip()
    return slot


# ── Main planner ───────────────────────────────────────────────────────────

def plan_set(
    catalog_df: pd.DataFrame,
    prompt: Optional[str] = None,
    base_bundle: Optional[dict] = None,
    set_schema: Optional[list[str]] = None,
    provider: str = "gemini",
    verbose: bool = False,
) -> SetResult:
    """
    Plan a full milonga set.

    Parameters
    ----------
    catalog_df : pd.DataFrame
        Full catalog, must contain a 'combo_key' column.
    prompt : str, optional
        Natural-language DJ prompt.  Required unless base_bundle is given.
    base_bundle : dict, optional
        Pre-built merged feature dict (skips LLM call).  Useful for testing
        or when the caller has already translated the prompt.
    set_schema : list[str], optional
        Style order, e.g. ["tango","tango","vals","tango","tango","milonga"].
        Defaults to DEFAULT_SET_SCHEMA.
    provider : str
        LLM provider ("gemini", "claude", "openai").  Only used when prompt
        is given and base_bundle is None.
    verbose : bool
        If True, print per-slot select_tanda output.  If False, suppress it.

    Returns
    -------
    SetResult
    """
    if prompt is None and base_bundle is None:
        raise ValueError("Provide either 'prompt' or 'base_bundle'.")

    schema = [s.lower().strip() for s in (set_schema or DEFAULT_SET_SCHEMA)]

    # Validate schema
    bad = [s for s in schema if s not in VALID_STYLES]
    if bad:
        raise ValueError(f"Unknown style(s) in set_schema: {bad}. Must be in {VALID_STYLES}.")

    if "combo_key" not in catalog_df.columns:
        raise ValueError("catalog_df must contain a 'combo_key' column.")

    # Step 1: translate prompt (once)
    if base_bundle is not None:
        resolved_bundle = copy.deepcopy(base_bundle)
    else:
        resolved_bundle = _translate_prompt(prompt, catalog_df, provider)

    slots:           list[TandaResult] = []
    used_combo_keys: list[str]         = []
    warnings:        list[str]         = []

    # Step 2: iterate over slots
    for slot_idx, slot_style in enumerate(schema, start=1):
        slot_label = f"Slot {slot_idx}/{len(schema)}  [{slot_style}]"

        # Build the slot-specific bundle (style injected)
        slot_bundle = _make_slot_bundle(resolved_bundle, slot_style)

        # Restrict pool: remove all combo_keys already used in this set
        if used_combo_keys:
            pool = catalog_df[~catalog_df["combo_key"].isin(used_combo_keys)].copy()
        else:
            pool = catalog_df.copy()

        tracks_before = len(pool)
        excluded = len(catalog_df) - tracks_before

        if verbose:
            print(f"\n[plan_set] {slot_label}  "
                  f"pool={tracks_before} tracks  (excluded {excluded} from {len(used_combo_keys)} used keys)")

        # Suppress select_tanda's own prints unless verbose
        if not verbose:
            import io, contextlib
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                result = select_tanda(slot_bundle, pool)
        else:
            result = select_tanda(slot_bundle, pool)

        slots.append(result)

        if result.tanda:
            used_combo_keys.append(result.combo_key)
            if verbose:
                print(f"[plan_set] {slot_label}  → {result.combo_key}  "
                      f"mean_score={result.mean_score:.4f}")
        else:
            used_combo_keys.append("")
            msg = (
                f"Slot {slot_idx} ({slot_style}): no valid tanda found. "
                f"Pool had {tracks_before} tracks after excluding "
                f"{len([k for k in used_combo_keys[:-1] if k])} combo_keys."
            )
            warnings.append(msg)
            if verbose:
                print(f"[plan_set] WARNING: {msg}")

    return SetResult(
        slots=slots,
        set_schema=schema,
        base_bundle=resolved_bundle,
        used_combo_keys=used_combo_keys,
        warnings=warnings,
    )


# ── CLI ────────────────────────────────────────────────────────────────────

def _cli_main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Plan a full milonga set from a natural-language prompt."
    )
    parser.add_argument("--prompt", "-p", default=None,
                        help="Natural-language DJ prompt.")
    parser.add_argument("--fixed-merged", default=None,
                        help="JSON string with a pre-built merged bundle (skips LLM).")
    parser.add_argument("--csv", default="../../data/reduced_catalog.csv",
                        help="Path to reduced_catalog.csv.")
    parser.add_argument("--schema", nargs="+",
                        default=DEFAULT_SET_SCHEMA,
                        metavar="STYLE",
                        help="Style order, e.g. --schema tango tango vals tango tango milonga")
    parser.add_argument("--provider", default=os.getenv("LLM_PROVIDER", "gemini"),
                        help="LLM provider: gemini | claude | openai")
    args = parser.parse_args()

    if args.prompt is None and args.fixed_merged is None:
        parser.error("Provide --prompt or --fixed-merged.")

    bundle = json.loads(args.fixed_merged) if args.fixed_merged else None

    df = pd.read_csv(args.csv)
    result = plan_set(
        catalog_df=df,
        prompt=args.prompt,
        base_bundle=bundle,
        set_schema=args.schema,
        provider=args.provider,
        verbose=True,
    )

    print("\n" + "═" * 60)
    print("SET RESULT")
    print("═" * 60)
    for i, (slot, style, ck) in enumerate(
        zip(result.slots, result.set_schema, result.used_combo_keys), start=1
    ):
        status = f"score={slot.mean_score:.4f}" if slot.tanda else "FAILED"
        print(f"  {i}. [{style:<8}]  {ck or '—':<45}  {status}")

    if result.warnings:
        print("\nWarnings:")
        for w in result.warnings:
            print(f"  ⚠  {w}")
    print("═" * 60)


if __name__ == "__main__":
    _cli_main()
