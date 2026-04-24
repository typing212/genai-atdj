"""
atdj/rag/ingest.py
------------------
Builds the local ChromaDB index for the AT-DJ RAG system.

This module prepares two local ChromaDB collections from files stored under
`data/knowledge_base/`:

1. "tango_tracks"
   Built from the cleaned track catalog CSV (`rag_catalog.csv`).
   Each row in the catalog represents one track, and each track is indexed as:
   - one embedding document for semantic retrieval
   - one structured metadata record for filtering and downstream use

   This collection is used for:
   - semantic music search
   - recommendation
   - tanda planning support
   - future integration with the LangGraph agent and UI

2. "domain_knowledge"
   Built from local markdown files in the same `data/knowledge_base/` folder.
   These files can contain tango background knowledge such as:
   - orchestra profiles
   - tango / vals / milonga style notes
   - historical context
   - DJ heuristics or domain notes

   Each markdown file is split into smaller chunks before indexing so retrieval
   can return more focused passages.

Important design note
---------------------
This file only handles LOCAL ingestion.

That means:
- local CSV track data  -> ChromaDB
- local markdown docs   -> ChromaDB

Live web knowledge such as Wikipedia or TodoTango search is handled separately
in `fetch.py` at query time, not here.

Current project expectation
---------------------------
The RAG system is designed to support all three sources together:

1. local track catalog CSV
2. local markdown knowledge files
3. live web retrieval (handled elsewhere)

In this project setup, both the CSV catalog and the markdown knowledge files
are stored inside `data/knowledge_base/`.

Typical usage
-------------
Ingest only tracks:
    python -m atdj.rag.ingest --tracks --reset

Ingest only local markdown knowledge:
    python -m atdj.rag.ingest --knowledge --reset

Ingest both:
    python -m atdj.rag.ingest --all --reset
"""

import re
import uuid
from pathlib import Path

import pandas as pd

from atdj.config import CATALOG_PATH, KNOWLEDGE_DIR
from atdj.rag.store import (
    get_client,
    get_or_create_collection,
    TRACKS_COLLECTION,
    KNOWLEDGE_COLLECTION,
)

CHUNK_SIZE = 400  # approximate characters per knowledge chunk


# ── Helpers ────────────────────────────────────────────────────────────────

def _is_missing(val) -> bool:
    """Return True for None / NaN / empty-string-like values."""
    if val is None:
        return True
    try:
        if pd.isna(val):
            return True
    except Exception:
        pass
    if isinstance(val, str) and val.strip() == "":
        return True
    return False


def _clean_str(val, default: str = "") -> str:
    """Convert a value to a clean string, replacing missing values."""
    if _is_missing(val):
        return default
    return str(val).strip()


def _clean_float(val, default: float = 0.0) -> float:
    """Convert a value to float, using a default on failure."""
    if _is_missing(val):
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _make_stable_track_id(row: dict) -> str:
    """
    Return a stable track ID.

    Priority:
      1. existing catalog 'id'
      2. file_path
      3. album + filename
      4. title + orchestra + year
    """
    existing_id = row.get("id")
    if not _is_missing(existing_id):
        return str(existing_id)

    file_path = _clean_str(row.get("file_path"))
    if file_path:
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, file_path))

    album = _clean_str(row.get("album"))
    filename = _clean_str(row.get("filename"))
    if album or filename:
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{album}|{filename}"))

    title = _clean_str(row.get("title"))
    orchestra = _clean_str(row.get("orchestra"))
    year = _clean_str(row.get("year"))
    fallback_key = f"{title}|{orchestra}|{year}"
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, fallback_key))


# ── Track ingestion ────────────────────────────────────────────────────────

def build_track_document(row: dict) -> str:
    """
    Convert one catalog row into a natural-language document for embeddings.

    The goal is to make semantic search work well for queries like:
    - "romantic Di Sarli tango from the 1940s"
    - "energetic milonga"
    - "smooth vals with moderate energy"
    """
    title = _clean_str(row.get("title"), "Unknown title")
    orchestra = _clean_str(row.get("orchestra"), "Unknown orchestra")
    singer = _clean_str(row.get("singer"))
    style = _clean_str(row.get("style"))
    decade = _clean_str(row.get("decade"))
    year = _clean_str(row.get("year"))
    key = _clean_str(row.get("key"))
    tags = _clean_str(row.get("tags"))
    notes = _clean_str(row.get("notes"))

    bpm = row.get("bpm")
    energy = row.get("energy")
    danceability = row.get("danceability")

    parts = [f'"{title}" by {orchestra}']

    if singer:
        parts.append(f'sung by {singer}')

    if style:
        parts.append(f'It is a {style} track')

    if decade:
        parts.append(f'from the {decade}')
    elif year:
        parts.append(f'from {year}')


    numeric_parts = []
    if not _is_missing(bpm):
        numeric_parts.append(f'BPM {_clean_float(bpm):.2f}')
    if not _is_missing(energy):
        numeric_parts.append(f'energy {_clean_float(energy):.2f}')
    if not _is_missing(danceability):
        numeric_parts.append(f'danceability {_clean_float(danceability):.2f}')

    if numeric_parts:
        parts.append("with " + ", ".join(numeric_parts))


    if key:
        parts.append(f'in key {key}')
    if tags:
        parts.append(f'Tags: {tags}')
    if notes:
        parts.append(f'Notes: {notes}')

    return ". ".join(parts) + "."


def ingest_catalog(
    client=None,
    batch_size: int = 100,
    reset: bool = False,
) -> int:
    """
    Read the catalog CSV and upsert every non-cortina track into the
    "tango_tracks" collection.
    """
    if client is None:
        client = get_client()

    if reset:
        try:
            client.delete_collection(TRACKS_COLLECTION)
            print(f"[ingest] Deleted existing '{TRACKS_COLLECTION}' collection.")
        except Exception:
            pass

    col = get_or_create_collection(TRACKS_COLLECTION, client)

    df = pd.read_csv(CATALOG_PATH)

    if "style" in df.columns:
        df["style"] = df["style"].astype(str).str.strip().str.lower()
        df = df[df["style"] != "cortina"].reset_index(drop=True)

    ids, documents, metadatas = [], [], []

    for _, row in df.iterrows():
        row_dict = row.to_dict()

        track_id = _make_stable_track_id(row_dict)
        doc_text = build_track_document(row_dict)

        meta = {
            "track_id": track_id,
            "title": _clean_str(row_dict.get("title")),
            "orchestra": _clean_str(row_dict.get("orchestra")),
            "singer": _clean_str(row_dict.get("singer")),
            "style": _clean_str(row_dict.get("style")),
            "decade": _clean_str(row_dict.get("decade")),
            "filename": _clean_str(row_dict.get("filename")),
            "file_path": _clean_str(row_dict.get("file_path")),
            "album": _clean_str(row_dict.get("album")),
            "key": _clean_str(row_dict.get("key")),
        }

        for field in ("bpm", "energy", "danceability", "year", "duration_seconds"):
            meta[field] = _clean_float(row_dict.get(field), default=0.0)

        ids.append(track_id)
        documents.append(doc_text)
        metadatas.append(meta)

        if len(ids) >= batch_size:
            col.upsert(ids=ids, documents=documents, metadatas=metadatas)
            ids, documents, metadatas = [], [], []

    if ids:
        col.upsert(ids=ids, documents=documents, metadatas=metadatas)

    total = col.count()
    print(f"[ingest] '{TRACKS_COLLECTION}' collection now has {total} tracks.")
    return total


# ── Knowledge doc ingestion ────────────────────────────────────────────────

def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE) -> list[str]:
    """
    Split text into chunks at paragraph boundaries (~chunk_size chars each).
    Falls back to hard splits if a paragraph is very long.
    """
    paragraphs = re.split(r"\n{2,}", text.strip())
    chunks, current = [], ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(current) + len(para) + 2 < chunk_size:
            current = (current + "\n\n" + para).strip()
        else:
            if current:
                chunks.append(current)

            if len(para) > chunk_size:
                for i in range(0, len(para), chunk_size):
                    chunks.append(para[i:i + chunk_size])
                current = ""
            else:
                current = para

    if current:
        chunks.append(current)

    return chunks


def ingest_knowledge_docs(
    client=None,
    knowledge_dir: Path | None = None,
    reset: bool = False,
) -> int:
    """
    Read all markdown files in the local knowledge base directory and upsert
    their chunks into the "domain_knowledge" collection.

    By default this uses KNOWLEDGE_DIR from config, which should point to:
        data/knowledge_base/
    """
    if client is None:
        client = get_client()
    if knowledge_dir is None:
        knowledge_dir = KNOWLEDGE_DIR

    if reset:
        try:
            client.delete_collection(KNOWLEDGE_COLLECTION)
            print(f"[ingest] Deleted existing '{KNOWLEDGE_COLLECTION}' collection.")
        except Exception:
            pass

    col = get_or_create_collection(KNOWLEDGE_COLLECTION, client)

    md_files = sorted(knowledge_dir.glob("*.md"))
    if not md_files:
        print(f"[ingest] No .md files found in {knowledge_dir}")
        return 0

    ids, documents, metadatas = [], [], []

    for md_path in md_files:
        text = md_path.read_text(encoding="utf-8")
        topic = md_path.stem
        chunks = _chunk_text(text)

        for i, chunk in enumerate(chunks):
            chunk_id = f"knowledge_{topic}_{i}"
            ids.append(chunk_id)
            documents.append(chunk)
            metadatas.append({
                "source": md_path.name,
                "topic": topic,
                "chunk_index": i,
                "chunk_text_len": len(chunk),
            })

    if ids:
        col.upsert(ids=ids, documents=documents, metadatas=metadatas)

    total = col.count()
    print(
        f"[ingest] '{KNOWLEDGE_COLLECTION}' collection now has "
        f"{total} chunks from {len(md_files)} files."
    )
    return total


# ── CLI entry point ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Ingest local track catalog and/or local markdown knowledge docs into ChromaDB."
    )
    parser.add_argument("--tracks", action="store_true", help="Ingest catalog CSV into tango_tracks")
    parser.add_argument("--knowledge", action="store_true", help="Ingest local knowledge_base/*.md into domain_knowledge")
    parser.add_argument("--all", action="store_true", help="Ingest both tracks and knowledge (default)")
    parser.add_argument("--reset", action="store_true", help="Delete collections before ingesting")
    args = parser.parse_args()

    do_all = args.all or (not args.tracks and not args.knowledge)
    client = get_client()

    if do_all or args.tracks:
        ingest_catalog(client=client, reset=args.reset)
    if do_all or args.knowledge:
        ingest_knowledge_docs(client=client, reset=args.reset)