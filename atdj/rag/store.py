"""
atdj/rag/store.py
-----------------
ChromaDB connection layer.

Responsibilities:
- Create / return a persistent ChromaDB client pointed at data/chroma_db/
- Provide get_or_create_collection() so every other module gets
  the same collection object without re-initialising the DB.

Two collections are used across the project:
  "tango_tracks"     – one document per track in catalog.csv
  "domain_knowledge" – chunked markdown knowledge docs (orchestra bios, etc.)
"""

import chromadb
from chromadb.config import Settings
from atdj.config import CHROMA_DIR
from typing import Optional

# ── Collection names (single source of truth) ──────────────────────────────
TRACKS_COLLECTION     = "tango_tracks"
KNOWLEDGE_COLLECTION  = "domain_knowledge"


# ── Singleton client — avoids reloading sentence-transformers on every rerun ──
# Original (Nancy): _chroma_client: chromadb.PersistentClient | None = None
# chromadb 1.5.8 exposes PersistentClient as a function; PEP 604 `func | None` at module level → TypeError.
_chroma_client: Optional[chromadb.PersistentClient] = None


def get_client() -> chromadb.PersistentClient:
    """
    Return a singleton ChromaDB PersistentClient.

    Created once per process and reused — avoids reloading sentence-transformers
    on every Streamlit rerun. Data is stored in data/chroma_db/.
    """
    # Original implementation (created a new client on every call):
    # CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    # return chromadb.PersistentClient(
    #     path=str(CHROMA_DIR),
    #     settings=Settings(anonymized_telemetry=False),
    # )

    global _chroma_client
    if _chroma_client is None:
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(
            path=str(CHROMA_DIR),
            settings=Settings(anonymized_telemetry=False),
        )
    return _chroma_client


def get_or_create_collection(
    name: str,
    client: Optional[chromadb.PersistentClient] = None,
    ) -> chromadb.Collection:
    """
    Return a ChromaDB collection, creating it if it doesn't exist yet.

    Parameters
    ----------
    name   : collection name — use TRACKS_COLLECTION or KNOWLEDGE_COLLECTION
    client : optional existing client; creates a new one if omitted

    Usage
    -----
    >>> col = get_or_create_collection(TRACKS_COLLECTION)
    >>> col.count()   # number of documents currently in the collection
    """
    if client is None:
        client = get_client()

    # get_or_create_collection is idempotent — safe to call on every startup
    return client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},   # cosine similarity for semantic search
    )
