from atdj.rag.query import search_for_planning


def test_search_for_planning_returns_1930s_tango():
    results = search_for_planning(
        style="tango",
        energy_min=0.0,
        energy_max=1.0,
        decade="1930s",
        limit=5,
    )

    assert isinstance(results, list)
    assert len(results) > 0

    for r in results[:5]:
        print(
            r["metadata"].get("title"),
            "|",
            r["metadata"].get("orchestra"),
            "|",
            r["metadata"].get("style"),
            "|",
            r["metadata"].get("decade"),
            "|",
            r["metadata"].get("energy"),
        )
        assert r["metadata"].get("style") == "tango"
        assert r["metadata"].get("decade") == "1930s"