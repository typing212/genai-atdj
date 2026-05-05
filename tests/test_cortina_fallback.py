"""
Step-by-step test of the full cortina fallback chain:
  Lyria  →  pool  →  placeholder

Run from the project root:
    python test_cortina_fallback.py
    python test_cortina_fallback.py --skip-lyria      # skip Lyria, go straight to pool
    python test_cortina_fallback.py --force-rebuild   # re-extract pool_features.csv even if it exists

Each step prints exactly what it found, what it returned, and why it fell through.
"""

import argparse
import os
import sys
from pathlib import Path

# ── Path setup ────────────────────────────────────────────────────────────────
# Works whether you run from project root or from atdj/ui/
_HERE = Path(__file__).resolve().parent
for _candidate in [_HERE, _HERE.parent, _HERE.parent.parent]:
    if (_candidate / "atdj").is_dir():
        sys.path.insert(0, str(_candidate))
        break

from atdj.config import ROOT_DIR, GEMINI_API_KEY  # noqa: E402

POOL_DIR     = ROOT_DIR / "data" / "cortinas" / "pool"
FEATURES_CSV = ROOT_DIR / "data" / "cortinas" / "pool_features.csv"
GENERATED_DIR = ROOT_DIR / "data" / "cortinas" / "generated"

SEP = "─" * 60

# ── Fake tanda summary (what _summarize_tanda would produce) ──────────────────
FAKE_TRACKS = [
    {"title": "El Choclo",    "orchestra": "Carlos Di Sarli", "style": "tango",
     "decade": "1940s", "energy": 0.55, "bpm": 62.0},
    {"title": "Bahia Blanca", "orchestra": "Carlos Di Sarli", "style": "tango",
     "decade": "1940s", "energy": 0.50, "bpm": 60.0},
    {"title": "Cara Sucia",   "orchestra": "Carlos Di Sarli", "style": "tango",
     "decade": "1940s", "energy": 0.58, "bpm": 63.0},
]


def section(title: str) -> None:
    print(f"\n{SEP}\n  {title}\n{SEP}")


# ── Step 0: environment ───────────────────────────────────────────────────────

def check_environment() -> None:
    section("STEP 0 — Environment")
    print(f"ROOT_DIR      : {ROOT_DIR}")
    print(f"POOL_DIR      : {POOL_DIR}")
    print(f"FEATURES_CSV  : {FEATURES_CSV}")
    print(f"GENERATED_DIR : {GENERATED_DIR}")

    gemini_key = GEMINI_API_KEY or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    print(f"\nGEMINI_API_KEY set : {'✅ yes' if gemini_key else '❌ no  (Lyria will be skipped)'}")

    pool_files = list(POOL_DIR.glob("*.mp3")) + list(POOL_DIR.glob("*.wav")) if POOL_DIR.exists() else []
    print(f"Pool directory     : {'✅ exists' if POOL_DIR.exists() else '❌ missing — create it'}")
    print(f"Pool audio files   : {len(pool_files)} file(s)")
    for f in pool_files[:8]:
        print(f"    {f.name}")
    if len(pool_files) > 8:
        print(f"    … and {len(pool_files) - 8} more")

    csv_ok = FEATURES_CSV.exists()
    print(f"pool_features.csv  : {'✅ exists' if csv_ok else '⚠️  missing (will be built on first run)'}")
    if csv_ok:
        import pandas as pd
        df = pd.read_csv(FEATURES_CSV)
        print(f"    → {len(df)} rows")
        print(df.to_string(index=False) if len(df) <= 10 else df.head(10).to_string(index=False))


# ── Step 1: _summarize_tanda ──────────────────────────────────────────────────

def test_summarize() -> dict:
    section("STEP 1 — _summarize_tanda()")
    from atdj.cortina.generator import _summarize_tanda
    summary = _summarize_tanda(FAKE_TRACKS)
    print("Input tracks:")
    for t in FAKE_TRACKS:
        print(f"    {t['title']} | {t['orchestra']} | energy={t['energy']} | bpm={t['bpm']}")
    print(f"\nResult summary:")
    for k, v in summary.items():
        print(f"    {k:15s}: {v}")
    return summary


# ── Step 2: pool feature build ────────────────────────────────────────────────

def test_build_pool(force: bool = False) -> None:
    section("STEP 2 — build_pool_features()")
    from atdj.cortina.pool import build_pool_features, POOL_DIR, FEATURES_CSV

    pool_files = list(POOL_DIR.glob("*.mp3")) + list(POOL_DIR.glob("*.wav")) if POOL_DIR.exists() else []
    if not pool_files:
        print(f"⚠️  POOL_DIR is empty: {POOL_DIR}")
        print("   Add some non-tango mp3/wav files there, then re-run.")
        print("   → Skipping feature extraction.")
        return

    if FEATURES_CSV.exists() and not force:
        print(f"pool_features.csv already exists — skipping extraction.")
        print("   Run with --force-rebuild to re-extract.")
        return

    print(f"Extracting features for {len(pool_files)} file(s) …")
    try:
        df = build_pool_features(force=True)
        print(f"\n✅ Built features for {len(df)} tracks.")
        print(df.to_string(index=False))
    except Exception as e:
        print(f"❌ build_pool_features() raised: {type(e).__name__}: {e}")


# ── Step 3: find_best_cortina (pool) ─────────────────────────────────────────

def test_pool(summary: dict) -> dict | None:
    section("STEP 3 — find_best_cortina() from pool")
    from atdj.cortina.pool import find_best_cortina, FEATURES_CSV

    if not FEATURES_CSV.exists():
        print(f"⚠️  pool_features.csv not found at {FEATURES_CSV}")
        print("   Run Step 2 first (needs audio files in pool dir).")
        return None

    try:
        result = find_best_cortina(summary)
        if result.get("source") == "agent":
            print("⚠️  find_best_cortina() returned the placeholder — CSV was empty.")
        else:
            print(f"✅ Pool selected: {result['title']}")
            print(f"   file_path : {result.get('file_path', '(none)')}")
            print(f"   duration  : {result.get('duration')}")
            print(f"   source    : {result.get('source')}")
            fp = result.get("file_path")
            if fp:
                exists = Path(fp).exists()
                print(f"   file exists on disk: {'✅' if exists else '❌ NOT FOUND — path is stale'}")
        return result
    except FileNotFoundError as e:
        print(f"❌ FileNotFoundError: {e}")
        print("   Pool directory is empty — add mp3s and re-run Step 2.")
        return None
    except Exception as e:
        print(f"❌ {type(e).__name__}: {e}")
        return None


# ── Step 4: Lyria generation ──────────────────────────────────────────────────

def test_lyria(summary: dict, skip: bool = False) -> dict | None:
    section("STEP 4 — generate_cortina() via Lyria")

    gemini_key = GEMINI_API_KEY or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not gemini_key:
        print("⚠️  No GEMINI_API_KEY found — skipping Lyria test.")
        print("   Set GEMINI_API_KEY in your .env to enable this.")
        return None

    if skip:
        print("Skipped via --skip-lyria flag.")
        return None

    from atdj.cortina.generator import generate_cortina
    print(f"Calling Lyria for a tango → vals cortina …")
    print(f"Output dir: {GENERATED_DIR}")
    try:
        result = generate_cortina(
            prev_tracks=FAKE_TRACKS,
            next_style="vals",
            output_dir=GENERATED_DIR,
            api_key=gemini_key,
        )
        print(f"\n✅ Lyria generated: {result['title']}")
        print(f"   file_path    : {result.get('file_path')}")
        print(f"   duration     : {result.get('duration')}")
        print(f"   music_prompt : {result.get('music_prompt', '')[:120]} …")
        fp = result.get("file_path")
        if fp:
            size = Path(fp).stat().st_size if Path(fp).exists() else 0
            print(f"   file size    : {size:,} bytes {'✅' if size > 1000 else '❌ suspiciously small'}")
        return result
    except Exception as e:
        print(f"❌ {type(e).__name__}: {e}")
        return None


# ── Step 5: full _pick_cortina chain ─────────────────────────────────────────

def test_pick_cortina_chain(summary: dict, skip_lyria: bool = False) -> None:
    section("STEP 5 — Full _pick_cortina() chain (mirrors page_main.py logic)")

    gemini_key = GEMINI_API_KEY or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    placeholder = {"type": "cortina", "title": "Cortina", "duration": "0:20", "source": "agent"}

    # 1. Lyria
    result = None
    if gemini_key and not skip_lyria:
        print("Trying Lyria …")
        try:
            from atdj.cortina.generator import generate_cortina
            result = generate_cortina(
                prev_tracks=FAKE_TRACKS,
                next_style="vals",
                output_dir=GENERATED_DIR,
                api_key=gemini_key,
            )
            print(f"  ✅ Lyria succeeded → {result['title']}")
        except Exception as e:
            print(f"  ❌ Lyria failed: {type(e).__name__}: {e} → falling through to pool")
    else:
        print("  ⏭  Lyria skipped (no key or --skip-lyria)")

    # 2. Pool
    if result is None:
        print("Trying pool …")
        try:
            from atdj.cortina.pool import find_best_cortina
            result = find_best_cortina(summary)
            if result.get("source") == "agent":
                print("  ⚠️  Pool returned placeholder (CSV empty) → falling through")
                result = None
            else:
                print(f"  ✅ Pool succeeded → {result['title']}")
        except Exception as e:
            print(f"  ❌ Pool failed: {type(e).__name__}: {e} → falling through to placeholder")

    # 3. Placeholder
    if result is None:
        result = placeholder
        print(f"  ⚠️  Using silent placeholder: {result}")

    print(f"\nFinal result:")
    for k, v in result.items():
        print(f"    {k:15s}: {v}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Debug the cortina fallback chain.")
    parser.add_argument("--skip-lyria",    action="store_true", help="Skip Lyria and go straight to pool")
    parser.add_argument("--force-rebuild", action="store_true", help="Force re-extraction of pool_features.csv")
    args = parser.parse_args()

    check_environment()
    summary = test_summarize()
    test_build_pool(force=args.force_rebuild)
    test_pool(summary)
    test_lyria(summary, skip=args.skip_lyria)
    test_pick_cortina_chain(summary, skip_lyria=args.skip_lyria)

    print(f"\n{SEP}")
    print("  Done. Fix any ❌ above and re-run.")
    print(SEP)


if __name__ == "__main__":
    main()
