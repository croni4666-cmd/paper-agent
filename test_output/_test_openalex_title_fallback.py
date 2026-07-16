"""Unit test: [P1-15] OpenAlex-by-title fallback (v3.9.9.7).

Verifies:
1. Crossref hit: openalex_title NOT used
2. Crossref 0-hit + OpenAlex hit: openalex_title used, fields filled
3. Both 0-hit: nothing happens (no exception, no _enrichment.openalex_title)
4. _openalex_lookup_title: returns normalized dict from OpenAlex /works
5. _openalex_lookup_title: returns None on 0 results
6. _openalex_lookup_title: returns None on short titles (<10 chars)

No real network calls; all S2/Crossref/OpenAlex lookups mocked.
"""

import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, ".")

from pa_cli import search


def fake_crossref_0hit(title):
    """Crossref returns 0 hits."""
    return None


def fake_crossref_hit(title):
    """Crossref returns a hit."""
    return {
        "doi": "10.1234/cr-hit",
        "cited_by_count": 5,
        "venue": "CR Journal",
        "year": 2020,
        "source": "crossref_title",
    }


def fake_openalex_hit(title):
    """OpenAlex returns a hit."""
    return {
        "doi": "10.1234/oa-hit",
        "cited_by_count": 12,
        "venue": "OA Journal",
        "year": 2021,
        "is_oa": True,
        "oa_url": "http://example.com/oa.pdf",
        "source": "openalex",
    }


def fake_openalex_0hit(title):
    return None


def test_crossref_hit_skips_openalex():
    """When Crossref returns a hit, OpenAlex is not called."""
    results = [
        {"doi": "", "title": "Some paper", "cited_by_count": 0, "abstract": ""},
    ]
    with patch.object(search, "_s2_lookup_doi", return_value=None), \
         patch.object(search, "_crossref_lookup_title", side_effect=fake_crossref_hit), \
         patch.object(search, "_openalex_lookup_title",
                      side_effect=AssertionError("openalex should NOT be called")) as oa_mock:
        search.enrich_top_n(results, n=1, min_cites=0)
        assert results[0]["_enrichment"].get("crossref_title") is True
        assert results[0]["_enrichment"].get("openalex_title") is None
        assert results[0]["doi"] == "10.1234/cr-hit"
    print("  [OK] test_crossref_hit_skips_openalex passed")


def test_crossref_0hit_uses_openalex():
    """When Crossref returns 0-hit, OpenAlex is called as fallback."""
    results = [
        {"doi": "", "title": "Chinese paper that Crossref misses", "cited_by_count": 0,
         "abstract": ""},
    ]
    with patch.object(search, "_s2_lookup_doi", return_value=None), \
         patch.object(search, "_crossref_lookup_title", side_effect=fake_crossref_0hit), \
         patch.object(search, "_openalex_lookup_title", side_effect=fake_openalex_hit) as oa_mock:
        search.enrich_top_n(results, n=1, min_cites=0)
        assert oa_mock.call_count == 1, f"expected 1 OpenAlex call, got {oa_mock.call_count}"
        assert results[0]["_enrichment"].get("openalex_title") is True
        assert results[0]["doi"] == "10.1234/oa-hit"
        assert results[0]["cited_by_count"] == 12
        assert results[0]["year"] == 2021
        assert results[0]["venue"] == "OA Journal"
    print("  [OK] test_crossref_0hit_uses_openalex passed")


def test_both_0hit_no_enrichment():
    """When both Crossref and OpenAlex return 0-hit, no enrichment happens."""
    results = [
        {"doi": "", "title": "Obscure paper that neither finds", "cited_by_count": 0,
         "abstract": ""},
    ]
    with patch.object(search, "_s2_lookup_doi", return_value=None), \
         patch.object(search, "_crossref_lookup_title", side_effect=fake_crossref_0hit), \
         patch.object(search, "_openalex_lookup_title", side_effect=fake_openalex_0hit) as oa_mock:
        search.enrich_top_n(results, n=1, min_cites=0)
        assert oa_mock.call_count == 1
        assert results[0]["_enrichment"].get("crossref_title") is None
        assert results[0]["_enrichment"].get("openalex_title") is None
        assert results[0]["doi"] == ""  # unfilled
        assert results[0]["cited_by_count"] == 0
    print("  [OK] test_both_0hit_no_enrichment passed")


def test_openalex_fills_only_missing_fields():
    """If paper already has some fields, OpenAlex shouldn't overwrite."""
    results = [
        {"doi": "", "title": "Already has venue", "cited_by_count": 0,
         "abstract": "user-supplied abstract", "venue": "Original Venue"},
    ]
    with patch.object(search, "_s2_lookup_doi", return_value=None), \
         patch.object(search, "_crossref_lookup_title", side_effect=fake_crossref_0hit), \
         patch.object(search, "_openalex_lookup_title", side_effect=fake_openalex_hit):
        search.enrich_top_n(results, n=1, min_cites=0)
        # Venue was already set; OpenAlex should NOT overwrite
        assert results[0]["venue"] == "Original Venue"
        # But doi/cited_by_count/year should be filled
        assert results[0]["doi"] == "10.1234/oa-hit"
        assert results[0]["cited_by_count"] == 12
        assert results[0]["year"] == 2021
        # abstract was already set; OpenAlex should not overwrite
        assert results[0]["abstract"] == "user-supplied abstract"
    print("  [OK] test_openalex_fills_only_missing_fields passed")


def test_openalex_lookup_title_returns_normalized():
    """_openalex_lookup_title should call OpenAlex API and return _normalize result."""
    with patch.object(search, "http_get_json") as http_mock:
        http_mock.return_value = (200, {
            "results": [{
                "doi": "https://doi.org/10.1234/normalized",
                "title": "Test paper",
                "publication_date": "2022-05-15",
                "cited_by_count": 7,
                "authorships": [{"author": {"display_name": "Alice"}}],
                "primary_location": {"source": {"display_name": "Journal X"}},
                "open_access": {"is_oa": True, "oa_url": "http://x.com/oa.pdf"},
                "type": "article",
            }]
        })
        result = search._openalex_lookup_title("Test paper for normalization")
        assert result is not None
        assert result["doi"] == "10.1234/normalized", f"DOI should strip prefix, got: {result['doi']}"
        assert result["cited_by_count"] == 7
        assert result["year"] == 2022
        assert result["is_oa"] is True
        assert result["oa_url"] == "http://x.com/oa.pdf"
    print("  [OK] test_openalex_lookup_title_returns_normalized passed")


def test_openalex_lookup_title_0results():
    """_openalex_lookup_title should return None when results list is empty."""
    with patch.object(search, "http_get_json") as http_mock:
        http_mock.return_value = (200, {"results": []})
        result = search._openalex_lookup_title("Nonexistent paper xyz123")
        assert result is None
    print("  [OK] test_openalex_lookup_title_0results passed")


def test_openalex_lookup_title_short_title():
    """_openalex_lookup_title should return None for titles < 10 chars."""
    result = search._openalex_lookup_title("Short")
    assert result is None, f"expected None for short title, got: {result}"
    result = search._openalex_lookup_title("")
    assert result is None
    print("  [OK] test_openalex_lookup_title_short_title passed")


def test_openalex_lookup_title_http_error():
    """_openalex_lookup_title should return None on non-200 response."""
    with patch.object(search, "http_get_json") as http_mock:
        http_mock.return_value = (500, {})
        result = search._openalex_lookup_title("Test paper for http error")
        assert result is None
    print("  [OK] test_openalex_lookup_title_http_error passed")


def main():
    print("\n=== [P1-15] OpenAlex-by-title fallback unit tests ===")
    test_crossref_hit_skips_openalex()
    test_crossref_0hit_uses_openalex()
    test_both_0hit_no_enrichment()
    test_openalex_fills_only_missing_fields()
    test_openalex_lookup_title_returns_normalized()
    test_openalex_lookup_title_0results()
    test_openalex_lookup_title_short_title()
    test_openalex_lookup_title_http_error()
    print("\n=== ALL P1-15 TESTS PASSED ===")


if __name__ == "__main__":
    main()
