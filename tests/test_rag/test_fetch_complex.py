# tests/test_rag/test_fetch_complex.py

from atdj.rag.fetch import fetch_knowledge, _normalize_query_for_lookup


def test_fetch_knowledge_complex_query():
    query = "Could you give me some background on the differences between tango and vals for social dancing?"
    lookup_query = _normalize_query_for_lookup(query)
    result = fetch_knowledge(query)

    print("\n=== COMPLEX FETCH TEST ===")
    print("Original query:", query)
    print("Lookup query:", lookup_query)
    print("Lookup word count:", len(lookup_query.split()) if lookup_query else 0)
    print("Source type:", result["source_type"])
    print("Source label:", result["source_label"])
    print("Source URL:", result["source_url"])
    print("Content preview:")
    print(result["content"][:500])

    assert isinstance(result, dict)
    assert "success" in result
    assert "source_type" in result
    assert "source_label" in result
    assert "source_url" in result
    assert "content" in result

    assert isinstance(lookup_query, str)
    assert len(lookup_query.strip()) > 0

    # Since this is the "complex query" path, we expect the final lookup query
    # to be short and retrieval-friendly
    assert len(lookup_query.split()) <= 5