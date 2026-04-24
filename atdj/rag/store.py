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


def get_client() -> chromadb.PersistentClient:
    """
    Return a ChromaDB PersistentClient.

    Data is stored in data/chroma_db/ so it survives restarts.
    ChromaDB uses its own built-in embedding model (all-MiniLM-L6-v2)
    by default — no API key needed.

    Usage
    -----
    >>> client = get_client()
    """
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(
        path=str(CHROMA_DIR),
        settings=Settings(anonymized_telemetry=False),
    )


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
