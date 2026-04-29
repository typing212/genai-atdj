"""
atdj/rag/query.py
-----------------
Query-time retrieval layer for the AT-DJ RAG system.

This module reads from the local ChromaDB index prepared by `ingest.py`.

It supports three main query patterns:

1. retrieve_tracks()
   Semantic retrieval over the local `"tango_tracks"` collection.

2. answer_question()
   Full RAG pipeline for Q&A.
   It combines:
   - retrieved track context from `"tango_tracks"`
   - retrieved local knowledge chunks from `"domain_knowledge"`
   - optional fetched background knowledge from `fetch.py`
     (local markdown first, Wikipedia second)

3. search_for_planning()
   Retrieval helper for the planning / agent side.
   It applies structured metadata constraints first, then semantic search
   within those constraints.

Important design note
---------------------
This file does NOT build the index. It only queries collections that already
exist in ChromaDB.

Expected local collections
--------------------------
- "tango_tracks"      : built from `rag_catalog.csv`
- "domain_knowledge"  : built from local markdown files in `data/knowledge_base/`

If background retrieval fails, `answer_question()` may still let the LLM answer
from general model knowledge, but it should clearly state that the answer is
AI-generated and not grounded in retrieved external knowledge.
"""

import re

# Original import (hardcoded to config keys):
# from atdj.config import GOOGLE_API_KEY, GEMINI_MODEL, ANTHROPIC_API_KEY, CLAUDE_MODEL
from atdj.config import ANTHROPIC_API_KEY, CLAUDE_MODEL, get_ui_llm
from atdj.rag.store import (
    get_client,
    get_or_create_collection,
    TRACKS_COLLECTION,
    KNOWLEDGE_COLLECTION,
)
from atdj.rag.fetch import fetch_knowledge
from dotenv import load_dotenv
load_dotenv()


# ── Helpers ────────────────────────────────────────────────────────────────

def _get_llm():
    """Return the LLM for the provider/key selected in the UI."""
    # Original implementation (hardcoded to Gemini from config):
    # from langchain_google_genai import ChatGoogleGenerativeAI
    # return ChatGoogleGenerativeAI(
    #     model=GEMINI_MODEL,
    #     google_api_key=GOOGLE_API_KEY,
    # )
    return get_ui_llm()


def _safe_first_nested(results: dict, key: str):
    """
    Safely extract the first nested list from a ChromaDB query result.
    Example:
        {"documents": [["a", "b"]]} -> ["a", "b"]
    """
    value = results.get(key, [])
    if not value:
        return []
    if isinstance(value, list) and len(value) > 0:
        return value[0]
    return []


def _format_track_results(results: dict) -> list[dict]:
    """
    Convert raw ChromaDB query results into a clean list of dicts.

    Each returned dict has:
    - id
    - document
    - metadata
    - distance
    """
    docs = _safe_first_nested(results, "documents")
    metas = _safe_first_nested(results, "metadatas")
    ids = _safe_first_nested(results, "ids")
    distances = _safe_first_nested(results, "distances")

    n = min(len(ids), len(docs), len(metas), len(distances))
    formatted = []

    for i in range(n):
        formatted.append(
            {
                "id": ids[i],
                "document": docs[i],
                "metadata": metas[i],
                "distance": distances[i],
            }
        )

    return formatted


def _format_knowledge_results(results: dict) -> list[dict]:
    """
    Convert raw ChromaDB knowledge query results into a clean list of dicts.

    Each returned dict has:
    - document
    - metadata
    """
    docs = _safe_first_nested(results, "documents")
    metas = _safe_first_nested(results, "metadatas")

    n = min(len(docs), len(metas))
    formatted = []

    for i in range(n):
        formatted.append(
            {
                "document": docs[i],
                "metadata": metas[i],
            }
        )

    return formatted


def _build_track_context(track_hits: list[dict]) -> str:
    """Format retrieved track hits into prompt-ready bullet lines."""
    if not track_hits:
        return "No matching tracks found."

    lines = []
    for t in track_hits:
        meta = t.get("metadata", {})
        title = meta.get("title", "")
        orchestra = meta.get("orchestra", "")
        style = meta.get("style", "")
        decade = meta.get("decade", "")
        distance = t.get("distance", None)

        line = f'- {t["document"]}'
        if title or orchestra or style or decade:
            line += f" [title={title}, orchestra={orchestra}, style={style}, decade={decade}]"
        if distance is not None:
            try:
                line += f" [distance={float(distance):.4f}]"
            except Exception:
                pass
        lines.append(line)

    return "\n".join(lines)


def _build_knowledge_context(knowledge_hits: list[dict]) -> str:
    """Format local knowledge chunks into prompt-ready text."""
    if not knowledge_hits:
        return ""

    blocks = []
    for item in knowledge_hits:
        meta = item.get("metadata", {})
        source = meta.get("source", "unknown")
        topic = meta.get("topic", "unknown")
        text = item.get("document", "")
        blocks.append(f"[Local knowledge chunk | source={source} | topic={topic}]\n{text}")

    return "\n\n".join(blocks)


def _build_fetched_knowledge_block(fetch_result: dict) -> str:
    """
    Convert structured fetch result into prompt-ready text.
    """
    source_type = fetch_result.get("source_type", "none")
    source_label = fetch_result.get("source_label")
    source_url = fetch_result.get("source_url")
    content = fetch_result.get("content", "")

    if source_type == "local_markdown" and content:
        return (
            f"Source: local knowledge base ({source_label})\n"
            f"{content}"
        )

    if source_type == "wikipedia" and content:
        header = f"Source: Wikipedia ({source_label})"
        if source_url:
            header += f"\nURL: {source_url}"
        return f"{header}\n{content}"

    return "No external background knowledge source was successfully retrieved."


def _build_source_policy_note(fetch_result: dict) -> str:
    """
    Tell the LLM how to behave depending on whether external knowledge
    retrieval succeeded.
    """
    source_type = fetch_result.get("source_type", "none")

    if source_type == "none":
        return (
            "No external background source was successfully retrieved. "
            "You may answer using your own general background knowledge, "
            "but you must clearly say that the answer is AI-generated and "
            "not grounded in retrieved external knowledge."
        )

    if source_type == "local_markdown":
        return (
            "Prefer the local curated knowledge base when answering factual "
            "background questions. Mention that the answer is based on the "
            "local knowledge base when appropriate."
        )

    if source_type == "wikipedia":
        return (
            "Use the retrieved Wikipedia background as supporting context. "
            "Mention that the answer is based on Wikipedia when appropriate."
        )

    return (
        "Use the available retrieved context carefully and avoid inventing facts."
    )


def _normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


def _extract_catalog_field_question(question: str) -> tuple[str | None, str | None]:
    """
    Detect simple catalog-field questions like:
    - what is the bpm of Asi Me Gusta A Mi?
    - what year is Milonga Sentimental?
    - what is the key of X?
    """
    q = _normalize_text(question)

    field_patterns = [
        ("bpm", [
            r"what is the bpm of (.+)",
            r"what s the bpm of (.+)",
            r"bpm of (.+)",
        ]),
        ("year", [
            r"what is the year of (.+)",
            r"what s the year of (.+)",
            r"what year is (.+)",
            r"year of (.+)",
        ]),
        ("decade", [
            r"what is the decade of (.+)",
            r"what s the decade of (.+)",
            r"decade of (.+)",
        ]),
        ("style", [
            r"what is the style of (.+)",
            r"what s the style of (.+)",
            r"style of (.+)",
        ]),
        ("orchestra", [
            r"what is the orchestra of (.+)",
            r"what s the orchestra of (.+)",
            r"who plays (.+)",
            r"who performed (.+)",
            r"orchestra of (.+)",
        ]),
        ("singer", [
            r"who sings (.+)",
            r"who sang (.+)",
            r"what is the singer of (.+)",
            r"what s the singer of (.+)",
            r"singer of (.+)",
        ]),
        ("duration_seconds", [
            r"what is the duration of (.+)",
            r"what s the duration of (.+)",
            r"how long is (.+)",
            r"duration of (.+)",
        ]),
        ("key", [
            r"what is the key of (.+)",
            r"what s the key of (.+)",
            r"key of (.+)",
        ]),
        ("energy", [
            r"what is the energy of (.+)",
            r"what s the energy of (.+)",
            r"energy of (.+)",
        ]),
        ("danceability", [
            r"what is the danceability of (.+)",
            r"what s the danceability of (.+)",
            r"danceability of (.+)",
        ]),
    ]

    for field, patterns in field_patterns:
        for pat in patterns:
            m = re.match(pat, q)
            if m:
                title = m.group(1).strip()
                return field, title

    return None, None


def _answer_catalog_field_question(
    question: str,
    chroma_client=None,
) -> str | None:
    """
    Answer direct metadata questions from the track catalog without needing
    background knowledge fetch.
    """
    field, title_query = _extract_catalog_field_question(question)
    if not field or not title_query:
        return None

    if chroma_client is None:
        chroma_client = get_client()

    col = get_or_create_collection(TRACKS_COLLECTION, chroma_client)
    if col.count() == 0:
        return None

    results = col.query(
        query_texts=[title_query],
        n_results=min(5, col.count()),
        include=["documents", "metadatas", "distances"],
    )
    track_hits = _format_track_results(results)

    if not track_hits:
        return None

    # Choose the closest hit
    best = track_hits[0]
    meta = best.get("metadata", {})
    title = meta.get("title", "Unknown")
    value = meta.get(field, None)

    if value is None or value == "":
        return f"I found '{title}', but I could not find its {field} value in the catalog."

    nice_field = {
        "bpm": "BPM",
        "year": "year",
        "decade": "decade",
        "style": "style",
        "orchestra": "orchestra",
        "singer": "singer",
        "duration_seconds": "duration",
        "key": "key",
        "energy": "energy",
        "danceability": "danceability",
    }.get(field, field)

    if field == "duration_seconds":
        try:
            return f"The duration of '{title}' is {float(value):.0f} seconds."
        except Exception:
            return f"The duration of '{title}' is {value}."
    if field == "bpm":
        try:
            return f"The BPM of '{title}' is {float(value):.2f}."
        except Exception:
            return f"The BPM of '{title}' is {value}."

    return f"The {nice_field} of '{title}' is {value}."


# ── 1. retrieve_tracks ─────────────────────────────────────────────────────

def retrieve_tracks(
    question: str,
    chroma_client=None,
    where_filter: dict | None = None,
    n_results: int = 5,
) -> list[dict]:
    """
    Semantic search over the `"tango_tracks"` ChromaDB collection.
    """
    if chroma_client is None:
        chroma_client = get_client()

    col = get_or_create_collection(TRACKS_COLLECTION, chroma_client)

    if col.count() == 0:
        print("[query] WARNING: tango_tracks collection is empty. Run ingest_catalog() first.")
        return []

    query_kwargs = {
        "query_texts": [question],
        "n_results": min(n_results, col.count()),
        "include": ["documents", "metadatas", "distances"],
    }
    if where_filter:
        query_kwargs["where"] = where_filter

    results = col.query(**query_kwargs)
    return _format_track_results(results)


# ── 2. retrieve_local_knowledge ────────────────────────────────────────────

def retrieve_local_knowledge(
    question: str,
    chroma_client=None,
    n_results: int = 3,
) -> list[dict]:
    """
    Semantic search over the local `"domain_knowledge"` collection.
    """
    if chroma_client is None:
        chroma_client = get_client()

    col = get_or_create_collection(KNOWLEDGE_COLLECTION, chroma_client)

    if col.count() == 0:
        return []

    results = col.query(
        query_texts=[question],
        n_results=min(n_results, col.count()),
        include=["documents", "metadatas"],
    )
    return _format_knowledge_results(results)


# ── 3. answer_question ─────────────────────────────────────────────────────

def answer_question(
    question: str,
    chroma_client=None,
    llm=None,
    n_tracks: int = 5,
    n_knowledge_chunks: int = 3,
    include_web_knowledge: bool = True,
) -> str:
    """
    Full RAG pipeline:
    retrieve relevant tracks + retrieve local knowledge + optionally fetch
    background knowledge, then generate an answer.
    """
    from langchain_core.messages import HumanMessage

    if chroma_client is None:
        chroma_client = get_client()

    # Shortcut for direct catalog-field questions
    direct_catalog_answer = _answer_catalog_field_question(
        question=question,
        chroma_client=chroma_client,
    )
    if direct_catalog_answer is not None:
        return direct_catalog_answer

    if llm is None:
        llm = _get_llm()

    # Step 1: retrieve track context
    track_hits = retrieve_tracks(
        question=question,
        chroma_client=chroma_client,
        n_results=n_tracks,
    )

    # Step 2: retrieve local knowledge chunks from Chroma
    knowledge_hits = retrieve_local_knowledge(
        question=question,
        chroma_client=chroma_client,
        n_results=n_knowledge_chunks,
    )

    # Step 3: optionally fetch background knowledge
    fetch_result = {
        "success": False,
        "source_type": "none",
        "source_label": None,
        "source_url": None,
        "content": "",
    }

    if include_web_knowledge:
        try:
            fetch_result = fetch_knowledge(question)
        except Exception as exc:
            print(f"[query] fetch_knowledge failed: {exc}")

    tracks_context = _build_track_context(track_hits)
    knowledge_context = _build_knowledge_context(knowledge_hits)
    fetched_knowledge_block = _build_fetched_knowledge_block(fetch_result)
    source_policy_note = _build_source_policy_note(fetch_result)

    prompt = f"""You are an expert Tango DJ assistant with deep knowledge of Argentine Tango music, orchestras, history, and tanda selection.

Answer the question using the available context below.
Be specific, grounded, and helpful.

Instructions:
- If the question is about tango knowledge, use the local knowledge and fetched background knowledge when relevant.
- If the question asks for recommendations, use the retrieved tracks first and mention orchestra, style, and decade when possible.
- Do not invent facts that are not supported by the context unless explicitly allowed below.
- If the available context is weak or incomplete, say so honestly.
- Keep the answer natural and readable.

Source policy:
{source_policy_note}

## Question
{question}

## Retrieved tracks from local catalog
{tracks_context}

## Retrieved local domain knowledge chunks
{knowledge_context if knowledge_context else "No local domain knowledge chunks retrieved from Chroma."}

## Fetched background knowledge
{fetched_knowledge_block}

## Answer
"""

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
    except Exception as exc:
        print(f"[query] Primary LLM failed: {exc}, trying Claude fallback...")
        import anthropic as _anthropic
        _client = _anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        _msg = _client.messages.create(model=CLAUDE_MODEL, max_tokens=1024,
                                       messages=[{"role": "user", "content": prompt}])
        response = type("R", (), {"content": _msg.content[0].text})()
    return response.content


# ── 4. search_for_planning ─────────────────────────────────────────────────

def search_for_planning(
    style: str,
    energy_min: float,
    energy_max: float,
    decade: str,
    orchestra: str | None = None,
    exclude_ids: list[str] | None = None,
    limit: int = 20,
    chroma_client=None,
) -> list[dict]:
    """
    Structured metadata filter + semantic re-rank for tanda planning.
    """
    if chroma_client is None:
        chroma_client = get_client()
    if exclude_ids is None:
        exclude_ids = []

    col = get_or_create_collection(TRACKS_COLLECTION, chroma_client)
    if col.count() == 0:
        print("[query] WARNING: tango_tracks collection is empty. Run ingest_catalog() first.")
        return []

    style = style.strip().lower()
    decade = decade.strip()

    conditions = [
        {"style": {"$eq": style}},
        {"decade": {"$eq": decade}},
        {"energy": {"$gte": float(energy_min)}},
        {"energy": {"$lte": float(energy_max)}},
    ]
    if orchestra:
        conditions.append({"orchestra": {"$eq": orchestra.strip()}})

    where = {"$and": conditions}

    semantic_query = (
        f"{style} music from the {decade} with energy between "
        f"{energy_min:.2f} and {energy_max:.2f}"
    )
    if orchestra:
        semantic_query += f", orchestra {orchestra}"

    try:
        results = col.query(
            query_texts=[semantic_query],
            n_results=min(limit * 2, col.count()),
            where=where,
            include=["documents", "metadatas", "distances"],
        )
    except Exception as exc:
        print(f"[query] search_for_planning filter returned no results: {exc}")
        return []

    tracks = _format_track_results(results)

    exclude_set = set(exclude_ids)
    tracks = [t for t in tracks if t["id"] not in exclude_set]

    return tracks[:limit]