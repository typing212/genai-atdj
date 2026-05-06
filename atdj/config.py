from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

ROOT_DIR      = Path(__file__).parent.parent
DATA_DIR      = ROOT_DIR / "data"
RAW_DIR       = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
CORTINAS_DIR  = DATA_DIR / "cortinas"
SAMPLES_DIR   = DATA_DIR / "samples"
CATALOG_PATH         = DATA_DIR / "essentia_newsamp.csv"
RAG_CATALOG_PATH     = DATA_DIR / "knowledge_base" / "rag_catalog.csv"
REDUCED_CATALOG_PATH = DATA_DIR / "reduced_catalog.csv"
CHROMA_DIR           = DATA_DIR / "chroma_db"
KNOWLEDGE_DIR        = DATA_DIR / "knowledge_base"

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "claude")  # "claude" | "gemini"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL      = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

# GOOGLE_API_KEY is honoured as a fallback so older .env files keep working.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL   = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


def _get_ui_state() -> dict:
    """Safely read UI session state. Returns empty dict outside Streamlit."""
    try:
        import streamlit as st
        return dict(st.session_state)
    except Exception:
        return {}


def get_ui_provider() -> str:
    """Return the provider selected in the UI ('Claude', 'Gemini', 'Ollama')."""
    state = _get_ui_state()
    return state.get("s_provider", "") or ("Claude" if LLM_PROVIDER == "claude" else "Gemini")


def get_ui_api_key() -> str:
    """Return the API key entered in the UI, falling back to .env."""
    state = _get_ui_state()
    key = state.get("s_api_key", "")
    if key:
        return key
    provider = get_ui_provider()
    return ANTHROPIC_API_KEY if provider == "Claude" else GEMINI_API_KEY


def get_ui_model() -> str:
    """Return the model selected in the UI, falling back to .env defaults."""
    state = _get_ui_state()
    model = state.get("s_model", "")
    if model:
        return model
    provider = get_ui_provider()
    return CLAUDE_MODEL if provider == "Claude" else GEMINI_MODEL


# Module-level memo for LLM clients. Keyed on (provider, model, api_key) so a
# sidebar change still produces a fresh client. Each call to a chat workflow
# would otherwise re-construct the LangChain client (TLS handshake on first
# request, ~0.5-2s); caching it amortises that across the session.
_llm_client_cache: dict[tuple[str, str, str], object] = {}


def get_ui_llm():
    """Return a LangChain LLM instance for the provider and key selected in the UI.

    Returns ChatAnthropic for Claude, ChatGoogleGenerativeAI for Gemini.
    Falls back gracefully to .env values when called outside Streamlit.
    Memoised on (provider, model, api_key) — see `_llm_client_cache`.
    """
    provider = get_ui_provider()
    model = get_ui_model()
    api_key = get_ui_api_key()

    cache_key = (provider, model, api_key)
    cached = _llm_client_cache.get(cache_key)
    if cached is not None:
        return cached

    if provider == "Claude":
        from langchain_anthropic import ChatAnthropic
        client = ChatAnthropic(model=model, anthropic_api_key=api_key, temperature=0)
    else:
        from langchain_google_genai import ChatGoogleGenerativeAI
        client = ChatGoogleGenerativeAI(model=model, google_api_key=api_key)

    _llm_client_cache[cache_key] = client
    return client
