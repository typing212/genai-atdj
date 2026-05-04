"""ChromaDB connection layer.

Provides a persistent ChromaDB client at data/chroma_db/ and a collection
accessor. Two collections live in the DB:
  "tango_tracks"     – one document per track in catalog.csv
  "domain_knowledge" – chunked markdown knowledge docs (orchestra bios, etc.)
"""

import chromadb
from chromadb.config import Settings
from atdj.config import CHROMA_DIR
from typing import Optional

TRACKS_COLLECTION     = "tango_tracks"
KNOWLEDGE_COLLECTION  = "domain_knowledge"


# Singleton client so sentence-transformers isn't reloaded on every Streamlit rerun.
# chromadb 1.5.8 exposes PersistentClient as a function, so the type annotation
# uses Optional[...] rather than `func | None` (which would TypeError at module level).
_chroma_client: Optional[chromadb.PersistentClient] = None


def get_client() -> chromadb.PersistentClient:
    """Return the singleton ChromaDB PersistentClient (created on first call)."""
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
    """Return a ChromaDB collection, creating it if it doesn't exist yet."""
    if client is None:
        client = get_client()
    return client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )
