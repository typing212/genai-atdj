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
RAG_CATALOG_PATH = DATA_DIR / "knowledge_base" / "rag_catalog.csv"  # RAG 295-track catalog
CHROMA_DIR       = DATA_DIR / "chroma_db"               # ChromaDB store (RAG)
KNOWLEDGE_DIR    = DATA_DIR / "knowledge_base"           # RAG .md domain knowledge files

# --- LLM provider selection (set LLM_PROVIDER in .env) ---
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "claude")  # "gemini" | "claude" | "ollama"

# --- Anthropic / Claude ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL      = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

# --- Google / Gemini ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL   = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
