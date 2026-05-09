"""
eval_02_qa_accuracy_latency.py
================================
Systematic Q&A evaluation: accuracy, latency, and grounding quality.
"""
from __future__ import annotations

# Load .env FIRST before any atdj module reads API keys at import time
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]   # tests/test_rag/ → project root
sys.path.insert(0, str(ROOT))                # for `from atdj.config import ...`
sys.path.insert(0, str(ROOT / "atdj" / "rag"))  # for bare `from query import ...`

from query import answer_question  # type: ignore


def _build_llm():
    """Build a Claude LLM for eval, bypassing Streamlit's get_ui_llm()."""
    from langchain_anthropic import ChatAnthropic
    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-20250514")
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise ValueError("No ANTHROPIC_API_KEY found in environment. Add it to your .env file.")
    return ChatAnthropic(model=model, anthropic_api_key=key)


# ── Test suite ────────────────────────────────────────────────────────────

@dataclass
class QACase:
    question: str
    must_contain: list[str] = field(default_factory=list)
    must_not_contain: list[str] = field(default_factory=list)
    category: str = "factual"
    difficulty: str = "easy"


QA_SUITE: list[QACase] = [
    # ── Factual / orchestra bios ──────────────────────────────────────────
    QACase(
        question="Who is Carlos Di Sarli?",
        must_contain=["di sarli", "orchestra", "tango"],
        must_not_contain=[],  # other orchestras may appear as legitimate contrast
        category="orchestra",
        difficulty="easy",
    ),
    QACase(
        question="What is Juan D'Arienzo known for?",
        must_contain=["d'arienzo", "rhythm"],
        must_not_contain=[],  # other orchestras may appear as legitimate contrast
        category="orchestra",
        difficulty="easy",
    ),
    QACase(
        question="Tell me about Osvaldo Pugliese's style.",
        must_contain=["pugliese"],
        must_not_contain=[],  # other orchestras may appear as legitimate contrast
        category="orchestra",
        difficulty="medium",
    ),
    QACase(
        question="Who was Anibal Troilo?",
        must_contain=["troilo"],
        must_not_contain=[],  # other orchestras may appear as legitimate era context
        category="orchestra",
        difficulty="easy",
    ),

    # ── Style / terminology ───────────────────────────────────────────────
    QACase(
        question="What is the difference between tango and vals?",
        must_contain=["vals", "tango"],
        must_not_contain=[],  # milonga may reasonably appear as context for the third style
        category="style",
        difficulty="easy",
    ),
    QACase(
        question="What is a milonga in the context of Argentine tango?",
        must_contain=["milonga"],
        category="style",
        difficulty="easy",
    ),
    QACase(
        question="What is a tanda?",
        must_contain=["tanda"],
        must_not_contain=["cortina is a tanda"],
        category="style",
        difficulty="easy",
    ),
    QACase(
        question="What is a cortina and why is it used?",
        must_contain=["cortina"],
        category="style",
        difficulty="medium",
    ),
    QACase(
        question="What does 'Golden Age of tango' refer to?",
        must_contain=["golden age", "1940"],
        category="style",
        difficulty="medium",
    ),

    # ── Comparison ────────────────────────────────────────────────────────
    QACase(
        question="How does Di Sarli's style compare to D'Arienzo's?",
        must_contain=["di sarli", "d'arienzo"],
        category="comparison",
        difficulty="medium",
    ),
    QACase(
        question="What are the differences between tango, vals, and milonga for social dancing?",
        must_contain=["tango", "vals", "milonga"],
        category="comparison",
        difficulty="hard",
    ),

    # ── Catalog-grounded questions ────────────────────────────────────────
    QACase(
        question="What BPM range is typical for a fast tango?",
        must_contain=["bpm", "fast"],
        category="factual",
        difficulty="medium",
    ),
    QACase(
        question="What makes a tango track highly danceable?",
        must_contain=["danceable", "rhythm"],
        category="factual",
        difficulty="medium",
    ),

    # ── Off-topic / robustness ────────────────────────────────────────────
    QACase(
        question="What is the capital of France?",
        must_contain=["paris"],
        must_not_contain=["tanda", "orchestra"],  # shouldn't force tango framing
        category="off-topic",
        difficulty="easy",
    ),
    QACase(
        question="Can you recommend a tango to play for a beginner dancer?",
        must_contain=["tango"],
        category="factual",
        difficulty="hard",
    ),

    # ── Edge / tricky ─────────────────────────────────────────────────────
    QACase(
        question="Is tango music the same as tango dance music?",
        must_contain=["tango"],
        category="factual",
        difficulty="hard",
    ),
    QACase(
        question="How many tracks are typically in a tanda?",
        must_contain=["3", "4"],
        category="factual",
        difficulty="medium",
    ),
    QACase(
        question="What is canyengue?",
        must_contain=["canyengue"],
        category="style",
        difficulty="hard",
    ),
]

QUICK_SUITE = QA_SUITE[:6]


# ── Evaluation helpers ────────────────────────────────────────────────────

def _check_contains(answer: str, terms: list[str]) -> list[bool]:
    low = answer.lower()
    return [t.lower() in low for t in terms]


def _run_case(case: QACase, llm, include_web: bool = True) -> dict:
    t0 = time.perf_counter()
    try:
        answer = answer_question(case.question, llm=llm,
                                 include_web_knowledge=include_web)
        error = None
    except Exception as exc:  # noqa: BLE001
        answer = ""
        error = str(exc)
    latency = time.perf_counter() - t0

    mc_results = _check_contains(answer, case.must_contain)
    mnc_results = _check_contains(answer, case.must_not_contain)

    pass_rate = sum(mc_results) / len(mc_results) if mc_results else 1.0
    hallucination_rate = sum(mnc_results) / len(mnc_results) if mnc_results else 0.0

    return dict(
        question=case.question,
        category=case.category,
        difficulty=case.difficulty,
        latency_s=round(latency, 3),
        answer_length=len(answer),
        pass_rate=round(pass_rate, 3),
        hallucination_rate=round(hallucination_rate, 3),
        n_must_contain=len(mc_results),
        n_must_contain_pass=sum(mc_results),
        must_contain_detail={t: p for t, p in zip(case.must_contain, mc_results)},
        n_must_not_contain=len(mnc_results),
        n_hallucination_fire=sum(mnc_results),
        must_not_contain_detail={t: p for t, p in zip(case.must_not_contain, mnc_results)},
        answer_preview=answer[:300],
        error=error,
    )


def _print_result(row: dict, idx: int, total: int) -> None:
    status = "✓" if row["pass_rate"] == 1.0 and row["hallucination_rate"] == 0.0 else "✗"
    print(f"\n[{idx}/{total}] {status}  [{row['category']}/{row['difficulty']}]  "
          f"latency={row['latency_s']:.2f}s  "
          f"pass={row['pass_rate']:.0%}  "
          f"halluc={row['hallucination_rate']:.0%}")
    print(f"  Q: {row['question']!r}")
    if row["error"]:
        print(f"  ERROR: {row['error']}")
    else:
        print(f"  A: {row['answer_preview']!r}...")
    if row["n_must_contain"] > 0:
        for term, passed in row["must_contain_detail"].items():
            icon = "✓" if passed else "✗"
            print(f"    must_contain   {icon}  {term!r}")
    if row["n_must_not_contain"] > 0:
        for term, fired in row["must_not_contain_detail"].items():
            icon = "✗(FIRED)" if fired else "✓(clean)"
            print(f"    must_NOT_contain {icon}  {term!r}")


def _aggregate_report(rows: list[dict]) -> None:
    df = pd.DataFrame(rows)
    print("\n" + "=" * 60)
    print("AGGREGATE Q&A EVALUATION REPORT")
    print("=" * 60)

    print(f"\nOverall pass rate:        {df['pass_rate'].mean():.1%}")
    print(f"Overall hallucination:    {df['hallucination_rate'].mean():.1%}")
    print(f"Mean latency:             {df['latency_s'].mean():.2f}s")
    print(f"Median latency:           {df['latency_s'].median():.2f}s")
    print(f"p90 latency:              {df['latency_s'].quantile(0.9):.2f}s")
    print(f"Max latency:              {df['latency_s'].max():.2f}s")

    print("\nBy category:")
    for cat, grp in df.groupby("category"):
        print(f"  {cat:<14}  pass={grp['pass_rate'].mean():.1%}  "
              f"latency={grp['latency_s'].mean():.2f}s  "
              f"n={len(grp)}")

    print("\nBy difficulty:")
    for diff, grp in df.groupby("difficulty"):
        print(f"  {diff:<8}  pass={grp['pass_rate'].mean():.1%}  "
              f"latency={grp['latency_s'].mean():.2f}s  "
              f"n={len(grp)}")

    failing = df[df["pass_rate"] < 1.0]
    if not failing.empty:
        print(f"\nFailing cases ({len(failing)}):")
        for _, row in failing.iterrows():
            print(f"  • {row['question']!r}  pass={row['pass_rate']:.0%}")

    halluc = df[df["hallucination_rate"] > 0.0]
    if not halluc.empty:
        print(f"\nHallucination-risk cases ({len(halluc)}):")
        for _, row in halluc.iterrows():
            print(f"  • {row['question']!r}  halluc_rate={row['hallucination_rate']:.0%}")


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--no-web", action="store_true",
                        help="Disable web knowledge fetch (faster, tests RAG-only)")
    parser.add_argument("--out-dir", default=".")
    args = parser.parse_args()

    suite = QUICK_SUITE if args.quick else QA_SUITE
    include_web = not args.no_web
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Running {len(suite)} Q&A cases  "
          f"(web={'on' if include_web else 'off'}) ...\n")

    print("Building LLM ...")
    llm = _build_llm()

    all_rows: list[dict] = []
    for i, case in enumerate(suite, 1):
        row = _run_case(case, llm=llm, include_web=include_web)
        _print_result(row, i, len(suite))
        all_rows.append(row)

    _aggregate_report(all_rows)

    # ── Save ──────────────────────────────────────────────────────────────
    json_path = out_dir / "eval_02_qa_results.json"
    with open(json_path, "w") as f:
        json.dump(all_rows, f, indent=2, default=str)
    print(f"\n✓ Full results  → {json_path}")

    flat = [{k: v for k, v in r.items()
             if not isinstance(v, dict)} for r in all_rows]
    csv_path = out_dir / "eval_02_qa_summary.csv"
    pd.DataFrame(flat).to_csv(csv_path, index=False)
    print(f"✓ Flat summary  → {csv_path}")


if __name__ == "__main__":
    main()
