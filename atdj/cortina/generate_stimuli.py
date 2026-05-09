"""
Generate cortina stimuli for evaluation.
Run from project root: uv run python doc/report/generate_stimuli.py
"""
import sys
from pathlib import Path

# Make sure the project root is on sys.path
_project_root = str(Path(__file__).parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from pathlib import Path
import pandas as pd
from atdj.config import REDUCED_CATALOG_PATH, GEMINI_API_KEY
from atdj.cortina.generator import generate_cortina, _summarize_tanda
from atdj.cortina.pool import find_best_cortina
from atdj.config import ROOT_DIR

OUT_DIR = ROOT_DIR / "data" / "cortinas" / "eval"
OUT_DIR.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(REDUCED_CATALOG_PATH)

# Replace these with the exact values you found in Step 1
CONTEXTS = [
    ("tango_dagostino",   "tango",   "Angel D'Agostino",   "1940s"),
    ("vals_deangelis",    "vals",    "Alfredo De Angelis",  "1940s"),
    ("milonga_dagostino", "milonga", "Angel D'Agostino",    "1940s"),
    ("tango_gobbi",       "tango",   "Alfredo Gobbi",       "1940s"),
    ("milonga_troilo",    "milonga", "Anibal Troilo",        "1940s"),
]

log = []

for label, style, orchestra, decade in CONTEXTS:
    print(f"\n── {label} ──")

    subset = df[
        (df["style"] == style) &
        (df["orchestra"].str.lower() == orchestra.lower()) &
        (df["decade"] == decade)
    ].head(4)

    if subset.empty:
        print(f"  SKIP — no tracks found, check orchestra spelling")
        continue

    tracks = subset.to_dict(orient="records")
    summary = _summarize_tanda(tracks)
    print(f"  Summary: {summary}")

    # Pool clip
    pool_result = find_best_cortina(summary, exclude=[])
    print(f"  Pool → {pool_result['title']}  |  {pool_result['file_path']}")

    # Generated clip
    if GEMINI_API_KEY:
        try:
            gen_result = generate_cortina(
                prev_tracks=tracks,
                next_style=None,
                output_dir=OUT_DIR / label,
                api_key=GEMINI_API_KEY,
            )
            print(f"  Generated → {gen_result['file_path']}")
            print(f"  Prompt: {gen_result['music_prompt']}")
            log.append({
                "label": label,
                "pool_file": pool_result["file_path"],
                "pool_title": pool_result["title"],
                "gen_file": gen_result["file_path"],
                "gen_prompt": gen_result["music_prompt"],
                "summary": summary,
            })
        except Exception as e:
            print(f"  Lyria failed: {e}")
    else:
        print("  No GEMINI_API_KEY — skipping generation")

# Save log
import json
log_path = OUT_DIR / "stimuli_log.json"
log_path.write_text(json.dumps(log, indent=2))
print(f"\nLog saved to {log_path}")