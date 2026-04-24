"""
atdj/rag/fetch.py
-----------------
Query-time knowledge fetching for the AT-DJ RAG system.

This module retrieves background knowledge text for use in the final RAG prompt.

Current source priority
-----------------------
1. Local markdown files in `data/knowledge_base/*.md`
   - preferred when a strong local match exists
   - useful because local files are curated and trustworthy

2. Wikipedia
   - used when local markdown does not provide a meaningful match
   - useful for general musician / orchestra / historical background

3. If both fail
   - return an empty knowledge result and let `query.py` decide whether to use
     an AI-generated fallback answer with a disclaimer

Important design note
---------------------
This file does NOT generate the final user-facing answer.
It only returns structured retrieval results.

The final answer is generated later in `query.py`, which can:
- use the returned content in the prompt
- note whether the answer was based on local markdown or Wikipedia
- fall back to LLM-only background knowledge when no source retrieval succeeded
"""

import re
import requests

from atdj.config import KNOWLEDGE_DIR, GOOGLE_API_KEY, GEMINI_MODEL

REQUEST_TIMEOUT = 5
MAX_WIKI_CHARS = 3000
MIN_WIKI_CHARS = 80


# ── Helper Functions to Extract Keywords from Query ───────────────────────

def _normalize_text(text: str) -> str:
    """Lowercase, remove extra punctuation, normalize spaces/underscores/hyphens."""
    text = text.lower().replace("_", " ").replace("-", " ")
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


def _regex_clean_query(query: str) -> str:
    """
    First-pass rule-based cleanup for lookup.

    Examples:
    - 'Who is Carlos Di Sarli?' -> 'carlos di sarli'
    - 'Tell me about Osvaldo Pugliese' -> 'osvaldo pugliese'
    """
    q = query.strip()

    patterns = [
        r"^\s*who\s+is\s+",
        r"^\s*tell\s+me\s+about\s+",
        r"^\s*what\s+is\s+",
        r"^\s*what\s+are\s+",
        r"^\s*can\s+you\s+tell\s+me\s+about\s+",
        r"^\s*give\s+me\s+background\s+on\s+",
        r"^\s*background\s+on\s+",
        r"^\s*i\s+want\s+to\s+know\s+about\s+",
    ]
    for pat in patterns:
        q = re.sub(pat, "", q, flags=re.IGNORECASE)

    return _normalize_text(q)


def _extract_lookup_query_with_gemini(query: str) -> str:
    """
    Use Gemini to extract a short lookup query for retrieval.

    Intended only for more complex user questions after regex cleanup.
    """
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.messages import HumanMessage

    llm = ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        google_api_key=GOOGLE_API_KEY,
    )

    prompt = f"""You are helping a retrieval system choose a short lookup query.

User question:
{query}

Return ONLY a short lookup query for search.
Rules:
- Prefer a person name, orchestra name, tango term, or very short phrase
- No explanation
- No quotes
- Max 5 words
- Keep it specific and retrieval-friendly

Examples:
Who is Carlos Di Sarli? -> Carlos Di Sarli
Tell me about Osvaldo Pugliese -> Osvaldo Pugliese
What is the difference between tango and vals? -> tango vs vals
Recommend a calm tango for the beginning of the night -> calm opening tango
"""

    response = llm.invoke([HumanMessage(content=prompt)])
    return _normalize_text(response.content)


def _normalize_query_for_lookup(query: str) -> str:
    """
    Convert a natural-language user question into a retrieval-friendly lookup string.

    Policy:
    - First try regex/rule-based cleanup
    - If cleaned query is still longer than 5 words, use Gemini to shorten it
    """
    cleaned = _regex_clean_query(query)

    if not cleaned:
        return ""

    if len(cleaned.split()) <= 5:
        return cleaned

    try:
        llm_query = _extract_lookup_query_with_gemini(query)
        if llm_query:
            return llm_query
    except Exception as exc:
        print(f"[fetch] Gemini query extraction failed for '{query}': {exc}")

    return cleaned


def _meaningful_tokens(text: str) -> list[str]:
    """
    Keep only meaningful tokens for lightweight matching / relevance checks.
    """
    stopwords = {
        "who", "what", "is", "are", "the", "a", "an", "about", "tell", "me",
        "difference", "differences", "between", "and", "or", "for", "of",
        "in", "on", "to", "vs", "versus", "some", "could", "you", "give",
        "background", "social", "dancing"
    }
    tokens = _normalize_text(text).split()
    return [t for t in tokens if len(t) > 2 and t not in stopwords]


# ── Wikipedia ─────────────────────────────────────────────────────────────

def _fetch_wikipedia(query: str) -> dict:
    """
    Fetch a short plain-text Wikipedia extract for the best matching article.

    Returns a structured dict:
    {
        "success": bool,
        "source_type": "wikipedia",
        "source_label": str | None,
        "source_url": str | None,
        "content": str,
    }
    """
    wiki_headers = {
        "User-Agent": "AT-DJ/0.1 (academic project; local development)"
    }

    lookup_query = _normalize_query_for_lookup(query)
    if not lookup_query:
        lookup_query = query.strip()

    try:
        search_url = "https://en.wikipedia.org/w/api.php"

        search_params = {
            "action": "opensearch",
            "search": lookup_query,
            "limit": 1,
            "format": "json",
        }
        resp = requests.get(
            search_url,
            params=search_params,
            headers=wiki_headers,
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()

        results = resp.json()
        titles = results[1]
        urls = results[3] if len(results) > 3 else []

        if not titles:
            return {
                "success": False,
                "source_type": "wikipedia",
                "source_label": None,
                "source_url": None,
                "content": "",
            }

        title = titles[0]
        page_url = urls[0] if urls else None

        # Relevance check on title to avoid clearly bad matches
        query_tokens = _meaningful_tokens(lookup_query)
        title_tokens = set(_normalize_text(title).split())
        overlap = sum(1 for tok in query_tokens if tok in title_tokens)

        # If the lookup query has multiple meaningful tokens, require at least
        # two-token overlap with the title before accepting the page.
        if len(query_tokens) >= 2 and overlap < 2:
            return {
                "success": False,
                "source_type": "wikipedia",
                "source_label": title,
                "source_url": page_url,
                "content": "",
            }

        extract_params = {
            "action": "query",
            "prop": "extracts",
            "exintro": True,
            "explaintext": True,
            "titles": title,
            "format": "json",
        }
        resp2 = requests.get(
            search_url,
            params=extract_params,
            headers=wiki_headers,
            timeout=REQUEST_TIMEOUT,
        )
        resp2.raise_for_status()

        pages = resp2.json().get("query", {}).get("pages", {})
        if not pages:
            return {
                "success": False,
                "source_type": "wikipedia",
                "source_label": title,
                "source_url": page_url,
                "content": "",
            }

        page = next(iter(pages.values()))
        extract = page.get("extract", "").strip()

        if len(extract) < MIN_WIKI_CHARS:
            return {
                "success": False,
                "source_type": "wikipedia",
                "source_label": title,
                "source_url": page_url,
                "content": "",
            }

        return {
            "success": True,
            "source_type": "wikipedia",
            "source_label": title,
            "source_url": page_url,
            "content": extract[:MAX_WIKI_CHARS],
        }

    except Exception as exc:
        print(f"[fetch] Wikipedia failed for '{query}': {exc}")
        return {
            "success": False,
            "source_type": "wikipedia",
            "source_label": None,
            "source_url": None,
            "content": "",
        }


# ── Local markdown fallback / preferred source ────────────────────────────

def _load_local_knowledge(query: str) -> dict:
    """
    Search local markdown files in KNOWLEDGE_DIR for a strict local match.

    Success rule:
    - normalized full query appears in filename, OR
    - normalized full query appears in file content

    This intentionally avoids loose keyword-overlap matching for now,
    so local retrieval is conservative and trustworthy.
    """
    if not KNOWLEDGE_DIR.exists():
        return {
            "success": False,
            "source_type": "local_markdown",
            "source_label": None,
            "source_url": None,
            "content": "",
        }

    md_files = sorted(KNOWLEDGE_DIR.glob("*.md"))
    if not md_files:
        return {
            "success": False,
            "source_type": "local_markdown",
            "source_label": None,
            "source_url": None,
            "content": "",
        }

    query_norm = _normalize_query_for_lookup(query)
    if not query_norm:
        return {
            "success": False,
            "source_type": "local_markdown",
            "source_label": None,
            "source_url": None,
            "content": "",
        }

    # First pass: filename match
    for path in md_files:
        stem_norm = _normalize_text(path.stem)
        if query_norm in stem_norm:
            text = path.read_text(encoding="utf-8").strip()
            if text:
                return {
                    "success": True,
                    "source_type": "local_markdown",
                    "source_label": path.name,
                    "source_url": None,
                    "content": text,
                }

    # Second pass: content phrase match
    for path in md_files:
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            continue

        text_norm = _normalize_text(text)
        if query_norm in text_norm:
            return {
                "success": True,
                "source_type": "local_markdown",
                "source_label": path.name,
                "source_url": None,
                "content": text,
            }

    return {
        "success": False,
        "source_type": "local_markdown",
        "source_label": None,
        "source_url": None,
        "content": "",
    }


# ── Public API ─────────────────────────────────────────────────────────────

def fetch_knowledge(query: str, use_cache: bool = True) -> dict:
    """
    Retrieve background knowledge for a query.

    Priority:
      1. local markdown knowledge
      2. Wikipedia
      3. if both fail, return a structured failure result

    Parameters
    ----------
    query : str
        Natural-language search term
    use_cache : bool
        Reserved for future use; currently unused

    Returns
    -------
    dict
        {
            "success": bool,
            "source_type": "local_markdown" | "wikipedia" | "none",
            "source_label": str | None,
            "source_url": str | None,
            "content": str,
        }
    """
    print(f"[fetch] Fetching knowledge for: '{query}'")

    # 1. Local curated knowledge first
    local_result = _load_local_knowledge(query)
    if local_result["success"]:
        print(f"[fetch] Source: local markdown ({local_result['source_label']}) ✓")
        return local_result

    # 2. Wikipedia second
    wiki_result = _fetch_wikipedia(query)
    if wiki_result["success"]:
        print(f"[fetch] Source: Wikipedia ({wiki_result['source_label']}) ✓")
        return wiki_result

    # 3. Neither source succeeded
    print("[fetch] No useful local markdown or Wikipedia knowledge found.")
    return {
        "success": False,
        "source_type": "none",
        "source_label": None,
        "source_url": None,
        "content": "",
    }