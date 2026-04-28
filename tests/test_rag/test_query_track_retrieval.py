from atdj.rag.query import retrieve_tracks


def test_retrieve_tracks_with_decade_filter():
    results = retrieve_tracks(
        "romantic tango",
        where_filter={"decade": "1930s"},
        n_results=5,
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
        )
        assert r["metadata"].get("decade") == "1930s"