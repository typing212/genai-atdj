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
KNOWLEDGE_DIR = ROOT_DIR / "data" / "knowledge_base"
CATALOG_PATH = KNOWLEDGE_DIR / "rag_catalog.csv"
CHROMA_DIR = ROOT_DIR / "data" / "chroma_db"

# --- LLM provider selection (set LLM_PROVIDER in .env) ---
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "claude")  # "gemini" | "claude" | "ollama"

# --- Anthropic / Claude ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL      = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

# --- Google / Gemini ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL   = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")
