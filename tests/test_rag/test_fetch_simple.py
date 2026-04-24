# tests/test_rag/test_fetch_simple.py

from atdj.rag.fetch import fetch_knowledge, _normalize_query_for_lookup


def test_fetch_knowledge_simple_query():
    query = "Who is Carlos Di Sarli?"
    lookup_query = _normalize_query_for_lookup(query)
    result = fetch_knowledge(query)

    print("\n=== SIMPLE FETCH TEST ===")
    print("Original query:", query)
    print("Lookup query:", lookup_query)
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

    # For this test, we mainly want structured output and a sane lookup query
    assert isinstance(lookup_query, str)
    assert len(lookup_query.strip()) > 0