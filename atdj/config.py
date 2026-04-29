from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

# --- Project root & data paths ---
ROOT_DIR      = Path(__file__).parent.parent
DATA_DIR      = ROOT_DIR / "data"
RAW_DIR       = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
CORTINAS_DIR  = DATA_DIR / "cortinas"
SAMPLES_DIR   = DATA_DIR / "samples"
CATALOG_PATH     = DATA_DIR / "essentia_newsamp.csv"    # feature catalog (playback, agent)
RAG_CATALOG_PATH = DATA_DIR / "knowledge_base" / "rag_catalog.csv"  # RAG 295-track catalog (ChromaDB ingest)
REDUCED_CATALOG_PATH = DATA_DIR / "reduced_catalog.csv"             # Labeled 295-track catalog (prompt translator + tanda selector)
CHROMA_DIR       = DATA_DIR / "chroma_db"               # ChromaDB store (RAG)
KNOWLEDGE_DIR    = DATA_DIR / "knowledge_base"           # RAG .md domain knowledge files

# --- LLM provider selection (set LLM_PROVIDER in .env) ---
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "claude")  # "gemini" | "claude" | "ollama"

# --- Anthropic / Claude ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL      = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

# --- Google / Gemini ---
# Prefer GEMINI_API_KEY for naming consistency with GEMINI_MODEL; fall back to
# the legacy GOOGLE_API_KEY name so existing .env files keep working.
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


def get_ui_llm():
    """Return a LangChain LLM instance for the provider and key selected in the UI.

    Returns ChatAnthropic for Claude, ChatGoogleGenerativeAI for Gemini.
    Falls back gracefully to .env values when called outside Streamlit.
    """
    provider = get_ui_provider()
    model = get_ui_model()
    api_key = get_ui_api_key()

    if provider == "Claude":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=model, anthropic_api_key=api_key, temperature=0)

    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(model=model, google_api_key=api_key)
