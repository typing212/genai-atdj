"""
atdj/rag/prompt_to_features.py
------------------------------
Provider-agnostic two-layer prompt translation for AT-DJ.

Supports OpenAI, Anthropic Claude, and Google Gemini via a shared
abstract base class.  The active provider is chosen by the LLM_PROVIDER
environment variable (or the `provider` argument).

Layer 1  – regex-only:  extracts year / decade
Layer 2  – LLM:         extracts all other structured fields

The output TranslationBundle.merged dict is what select_tanda.py consumes.

Run from project root:
    uv run python -m atdj.rag.prompt_to_features \
      --csv data/reduced_catalog.csv \
      --prompt "romantic vals from the 1940s, not too fast"

Or import:
    from atdj.rag.prompt_to_features import build_translator, load_catalog
    df   = load_catalog("data/reduced_catalog.csv")
    t    = build_translator(df)               # uses LLM_PROVIDER env var
    bundle = t.translate("calm Di Sarli tango, 1940s")
"""

from __future__ import annotations

import functools
import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")

KEY_REGEX = re.compile(r"^[A-G](?:b|#)?$")
ALLOWED_STYLE = {"tango", "vals", "milonga", None}
ALLOWED_BPM_LABEL = {"slow", "moderate", "fast", "very fast"}
ALLOWED_TRI_LABEL = {"low", "moderate", "high"}


# ── Data classes ──────────────────────────────────────────────────────────

@dataclass
class Layer1Result:
    year: Optional[int]
    decade: Optional[str]


@dataclass
class Layer2Result:
    orchestra: Optional[str]
    singer: Optional[str]
    style: Optional[str]
    album: Optional[str]
    bpm_label: str
    danceability_label: str
    key: Optional[str]
    chords_changes_rate: str
    energy_label: str
    tags: list[str]


@dataclass
class TranslationBundle:
    prompt: str
    layer1: Layer1Result
    layer2: Layer2Result
    merged: dict[str, Any]
    metadata: dict[str, Any]


# ── Catalog helpers ───────────────────────────────────────────────────────

def _load_catalog_raw(csv_path: str | Path) -> pd.DataFrame:
    """Actual CSV read + validation. Called by both cache layers."""
    df = pd.read_csv(Path(csv_path))
    required = {
        "title", "orchestra", "singer", "year", "decade", "style", "album",
        "bpm_label", "danceability_label", "key", "chords_changes_rate",
        "energy_label", "tags",
    }
    # chords_changes_rate may be stored as chords_changes_rate_label
    if "chords_changes_rate" not in df.columns and "chords_changes_rate_label" in df.columns:
        df["chords_changes_rate"] = df["chords_changes_rate_label"]
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"Missing required columns in catalog: {missing}")
    return df


# Plain-Python module-level cache: resolved path string → DataFrame.
# Used when Streamlit is not running (CLI, tests, debug scripts).
_catalog_cache: dict[str, pd.DataFrame] = {}


def _st_is_running() -> bool:
    """Return True only when code is executing inside a live Streamlit session."""
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        return get_script_run_ctx() is not None
    except Exception:
        return False


def load_catalog(csv_path: str | Path) -> pd.DataFrame:
    """
    Load and validate the track catalog CSV.

    • Inside a Streamlit session  → st.cache_data (survives reruns, one read per session).
    • Outside Streamlit (CLI / tests) → module-level dict keyed by resolved path.

    The public signature is unchanged: pass any relative or absolute path.
    """
    if _st_is_running():
        # Import here so the module works without Streamlit installed.
        import streamlit as st

        # Wrap with cache_data at call-time — no show_spinner so it's safe
        # to call from any thread context, including tests that import st.
        @st.cache_data
        def _cached(path_str: str) -> pd.DataFrame:
            return _load_catalog_raw(path_str)

        return _cached(str(Path(csv_path).resolve()))

    # Plain-Python path — module-level dict cache.
    key = str(Path(csv_path).resolve())
    if key not in _catalog_cache:
        _catalog_cache[key] = _load_catalog_raw(csv_path)
    return _catalog_cache[key]


def _build_catalog_context(df: pd.DataFrame) -> str:
    def top_values(col: str, n: int = 12) -> list[str]:
        return (
            df[col].dropna().astype(str).value_counts().head(n).index.tolist()
        )

    context = {
        "styles_present": sorted(df["style"].dropna().astype(str).unique().tolist()),
        "common_orchestras": top_values("orchestra", 15),
        "common_singers": top_values("singer", 15),
        "common_albums": top_values("album", 15),
        "keys_present": sorted(df["key"].dropna().astype(str).unique().tolist()),
        "label_spaces": {
            "bpm_label": sorted(ALLOWED_BPM_LABEL),
            "danceability_label": sorted(ALLOWED_TRI_LABEL),
            "chords_changes_rate": sorted(ALLOWED_TRI_LABEL),
            "energy_label": sorted(ALLOWED_TRI_LABEL),
            "style": ["tango", "vals", "milonga", None],
        },
    }
    return json.dumps(context, ensure_ascii=False, indent=2)


# ── Layer 1 (regex) ───────────────────────────────────────────────────────

def extract_year_decade(prompt: str) -> Layer1Result:
    decade_match = re.search(r"(?<!\d)(1[89]\d0|20\d0)s(?!\d)", prompt)
    decade = f"{decade_match.group(1)}s" if decade_match else None

    year_match = re.search(r"(?<!\d)(1[89]\d{2}|20\d{2})(?!\d|s)", prompt)
    year = int(year_match.group(1)) if year_match else None

    return Layer1Result(year=year, decade=decade)


# ── Prompts ───────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert Argentine Tango DJ assistant.

Your job is to extract structured fields from a user prompt.

Rules:
- Return JSON only.
- Do not add markdown fences.
- Do not omit required fields.
- bpm_label must be exactly one of: slow, moderate, fast, very fast
- danceability_label must be exactly one of: low, moderate, high
- chords_changes_rate must be exactly one of: low, moderate, high
- energy_label must be exactly one of: low, moderate, high
- style must be one of: tango, vals, milonga, or null
- key may be null, but if the user implies a musical key, normalize it to pitch class only
- output key must be exactly one of: A, Bb, B, C, C#, D, Eb, E, F, F#, G, Ab
- tags must be exactly 5 short descriptive words or short phrases (adjectives or nouns)
- tags must NOT repeat explicit metadata fields such as style, orchestra, singer, album, year, decade, or key
- Good examples of tags: happy, warm, elegant, party, dramatic, bittersweet
- If orchestra, singer, style, or album are not reasonably inferable, return null
- The four label fields must never be null
"""

USER_TEMPLATE = """Extract Layer 2 fields from this user prompt.

User prompt:
"{prompt}"

Layer 1 regex extraction already found:
{layer1_json}

Catalog context:
{catalog_context}

Return JSON with exactly this schema:
{{
  "orchestra": string or null,
  "singer": string or null,
  "style": "tango" or "vals" or "milonga" or null,
  "album": string or null,
  "bpm_label": "slow" or "moderate" or "fast" or "very fast",
  "danceability_label": "low" or "moderate" or "high",
  "key": string matching ^[A-G](?:b|#)?$ or null,
  "chords_changes_rate": "low" or "moderate" or "high",
  "energy_label": "low" or "moderate" or "high",
  "tags": [5 short descriptive words or short phrases]
}}
"""


# ── Validation ────────────────────────────────────────────────────────────

def _clean_optional_string(value: Any) -> Optional[str]:
    if value is None:
        return None
    value = str(value).strip()
    if not value or value.lower() == "null":
        return None
    return value


def _validate_layer2(payload: dict[str, Any]) -> Layer2Result:
    orchestra = _clean_optional_string(payload.get("orchestra"))
    singer = _clean_optional_string(payload.get("singer"))
    style = _clean_optional_string(payload.get("style"))
    album = _clean_optional_string(payload.get("album"))
    bpm_label = _clean_optional_string(payload.get("bpm_label"))
    danceability_label = _clean_optional_string(payload.get("danceability_label"))
    key = _clean_optional_string(payload.get("key"))
    chords_changes_rate = _clean_optional_string(payload.get("chords_changes_rate"))
    energy_label = _clean_optional_string(payload.get("energy_label"))
    tags = payload.get("tags")

    if style is not None:
        style = style.lower()
    if style not in ALLOWED_STYLE:
        raise ValueError(f"Invalid style: {style}")
    if bpm_label not in ALLOWED_BPM_LABEL:
        raise ValueError(f"Invalid bpm_label: {bpm_label}")
    if danceability_label not in ALLOWED_TRI_LABEL:
        raise ValueError(f"Invalid danceability_label: {danceability_label}")
    if chords_changes_rate not in ALLOWED_TRI_LABEL:
        raise ValueError(f"Invalid chords_changes_rate: {chords_changes_rate}")
    if energy_label not in ALLOWED_TRI_LABEL:
        raise ValueError(f"Invalid energy_label: {energy_label}")
    if key is not None and not KEY_REGEX.fullmatch(key):
        raise ValueError(f"Invalid key format: {key}")
    if not isinstance(tags, list) or len(tags) != 5:
        raise ValueError(f"tags must be a list of exactly 5 items, got: {tags}")
    cleaned_tags = [str(t).strip() for t in tags if str(t).strip()]
    if len(cleaned_tags) != 5:
        raise ValueError("tags contains empty items")

    return Layer2Result(
        orchestra=orchestra, singer=singer, style=style, album=album,
        bpm_label=bpm_label, danceability_label=danceability_label,
        key=key, chords_changes_rate=chords_changes_rate,
        energy_label=energy_label, tags=cleaned_tags,
    )


def _parse_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.startswith("json"):
            text = text[4:].strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON object found in response: {text}")
    return json.loads(text[start: end + 1])


# ── Abstract base translator ──────────────────────────────────────────────

class BaseTranslator:
    def __init__(self, catalog_df: pd.DataFrame) -> None:
        self.df = catalog_df.copy()
        self.catalog_context = _build_catalog_context(self.df)
        # Per-instance cache: SHA-256(prompt + model) → TranslationBundle.
        # Avoids paying the LLM round-trip when the agent replans with the
        # same prompt within a session.
        self._translation_cache: dict[str, "TranslationBundle"] = {}

    def _call_llm(self, user_text: str) -> str:
        raise NotImplementedError

    def _model_name(self) -> str:
        raise NotImplementedError

    def translate(self, prompt: str) -> TranslationBundle:
        cache_key = hashlib.sha256(
            f"{prompt}|{self._model_name()}".encode()
        ).hexdigest()

        if cache_key in self._translation_cache:
            print(f"[prompt_to_features] translation cache hit: {prompt!r:.60}")
            return self._translation_cache[cache_key]

        layer1 = extract_year_decade(prompt)
        user_text = USER_TEMPLATE.format(
            prompt=prompt,
            layer1_json=json.dumps(asdict(layer1), ensure_ascii=False, indent=2),
            catalog_context=self.catalog_context,
        )

        errors: list[str] = []
        last_raw: Optional[str] = None
        layer2: Optional[Layer2Result] = None

        for _ in range(3):
            retry_suffix = ""
            if errors:
                retry_suffix = (
                    "\n\nYour previous answer failed validation:\n"
                    + "\n".join(f"- {e}" for e in errors)
                    + "\nReturn corrected JSON only."
                )
            last_raw = self._call_llm(user_text + retry_suffix)
            try:
                layer2 = _validate_layer2(_parse_json(last_raw))
                break
            except Exception as exc:
                errors.append(str(exc))

        if layer2 is None:
            raise ValueError(
                f"LLM response failed validation after 3 attempts.\n"
                f"Last raw: {last_raw}\nErrors: {errors}"
            )

        merged = {
            "year": layer1.year,
            "decade": layer1.decade,
            "orchestra": layer2.orchestra,
            "singer": layer2.singer,
            "style": layer2.style,
            "album": layer2.album,
            "bpm_label": layer2.bpm_label,
            "danceability_label": layer2.danceability_label,
            "key": layer2.key,
            "chords_changes_rate": layer2.chords_changes_rate,
            "energy_label": layer2.energy_label,
            "tags": layer2.tags,
        }

        bundle = TranslationBundle(
            prompt=prompt, layer1=layer1, layer2=layer2,
            merged=merged, metadata={"model": self._model_name()},
        )
        self._translation_cache[cache_key] = bundle
        return bundle


# ── OpenAI implementation ─────────────────────────────────────────────────

class OpenAITranslator(BaseTranslator):
    def __init__(self, catalog_df: pd.DataFrame, model_name: Optional[str] = None,
                 api_key: Optional[str] = None) -> None:
        super().__init__(catalog_df)
        from openai import OpenAI as _OpenAI
        self._model = model_name or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        key = api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            raise ValueError("Missing OPENAI_API_KEY")
        self._client = _OpenAI(api_key=key)

    def _model_name(self) -> str:
        return self._model

    def _call_llm(self, user_text: str) -> str:
        # Responses API (gpt-5+) or Chat Completions API
        try:
            resp = self._client.responses.create(
                model=self._model,
                instructions=SYSTEM_PROMPT,
                input=user_text,
            )
            return resp.output_text.strip()
        except AttributeError:
            # Fallback to chat completions for older SDK / models
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_text},
                ],
                temperature=0,
            )
            return resp.choices[0].message.content.strip()


# ── Anthropic Claude implementation ───────────────────────────────────────

class ClaudeTranslator(BaseTranslator):
    def __init__(self, catalog_df: pd.DataFrame, model_name: Optional[str] = None,
                 api_key: Optional[str] = None) -> None:
        super().__init__(catalog_df)
        import anthropic
        self._model = model_name or os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
        key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise ValueError("Missing ANTHROPIC_API_KEY")
        self._client = anthropic.Anthropic(api_key=key)

    def _model_name(self) -> str:
        return self._model

    def _call_llm(self, user_text: str) -> str:
        msg = self._client.messages.create(
            model=self._model,
            max_tokens=512,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_text}],
        )
        return msg.content[0].text.strip()


# ── Gemini implementation ─────────────────────────────────────────────────

class GeminiTranslator(BaseTranslator):
    def __init__(self, catalog_df: pd.DataFrame, model_name: Optional[str] = None,
                 api_key: Optional[str] = None) -> None:
        super().__init__(catalog_df)
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import HumanMessage, SystemMessage
        self._HumanMessage = HumanMessage
        self._SystemMessage = SystemMessage
        self._model = model_name or os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        # Original (Nancy) — preserved below; renamed env var to GEMINI_API_KEY
        # for naming consistency with GEMINI_MODEL. The legacy GOOGLE_API_KEY
        # is still honoured as a fallback so existing .env files keep working.
        # key = api_key or os.getenv("GOOGLE_API_KEY")
        # if not key:
        #     raise ValueError("Missing GOOGLE_API_KEY")
        key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not key:
            raise ValueError("Missing GEMINI_API_KEY")
        self._llm = ChatGoogleGenerativeAI(model=self._model, google_api_key=key)

    def _model_name(self) -> str:
        return self._model

    def _call_llm(self, user_text: str) -> str:
        resp = self._llm.invoke([
            self._SystemMessage(content=SYSTEM_PROMPT),
            self._HumanMessage(content=user_text),
        ])
        return resp.content.strip()


# ── Factory ───────────────────────────────────────────────────────────────

def build_translator(
    catalog_df: pd.DataFrame,
    provider: Optional[str] = None,
    **kwargs,
) -> BaseTranslator:
    """
    Return the appropriate translator based on `provider` or the LLM_PROVIDER env var.

    provider options: "openai" | "claude" | "gemini"
    """
    p = (provider or os.getenv("LLM_PROVIDER", "gemini")).lower().strip()
    if p == "openai":
        return OpenAITranslator(catalog_df, **kwargs)
    if p in ("claude", "anthropic"):
        return ClaudeTranslator(catalog_df, **kwargs)
    if p == "gemini":
        return GeminiTranslator(catalog_df, **kwargs)
    raise ValueError(f"Unknown LLM provider: '{p}'. Choose openai, claude, or gemini.")


# Convenience alias used by select_tanda CLI
TwoLayerPromptTranslator = OpenAITranslator   # backward compat for existing imports


# ── CLI ────────────────────────────────────────────────────────────────────

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Two-layer prompt translation for AT-DJ.")
    parser.add_argument("--csv", default="data/reduced_catalog.csv")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--provider", default=None,
                        help="openai | claude | gemini  (overrides LLM_PROVIDER env var)")
    args = parser.parse_args()

    df = load_catalog(args.csv)
    translator = build_translator(df, provider=args.provider)
    bundle = translator.translate(args.prompt)

    print(json.dumps({
        "prompt": bundle.prompt,
        "layer1": asdict(bundle.layer1),
        "layer2": asdict(bundle.layer2),
        "merged": bundle.merged,
        "metadata": bundle.metadata,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
