"""Unit test: [P1-18] max_age_years year-aware enrichment skip (v3.9.9.10).

Verifies:
1. Old paper (>10y): all enrichment skipped, _enrichment.enrichment_skipped set
2. New paper (<=10y): enrichment proceeds normally
3. None year: enrichment proceeds (can't determine age)
4. max_age_years=0: disables age-based skip
5. max_age_years=5: tighter threshold (5 years)
6. S2 not called for old papers
7. Crossref not called for old papers
8. OpenAlex fallback not called for old papers
9. Stats line includes skipped_old count
10. max_age_years boundary: 2016 paper in 2026 = exactly 10y old = NOT skipped

current_year is hardcoded to 2026 in enrich_top_n; tests use that.
"""

import sys
import io
from contextlib import redirect_stderr
from unittest.mock import patch

sys.path.insert(0, ".")

from pa_cli import search


# current_year hardcoded in enrich_top_n is 2026
CURRENT_YEAR = 2026


def test_old_paper_skipped():
    """Paper from 2010 (16 years old in 2026) should be skipped."""
    results = [
        {"doi": "10.1/old", "title": "Old paper", "year": 2010,
         "cited_by_count": 5, "abstract": ""},
    ]
    with patch.object(search, "_s2_lookup_doi", side_effect=AssertionError("S2 should NOT be called")) as s2_mock, \
         patch.object(search, "_crossref_lookup_title", side_effect=AssertionError("Crossref should NOT be called")) as cr_mock, \
         patch.object(search, "_openalex_lookup_title", side_effect=AssertionError("OpenAlex should NOT be called")) as oa_mock:
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            search.enrich_top_n(results, n=1, min_cites=0, max_age_years=10)
        # No S2/Crossref/OpenAlex calls
        # No enrichment fields set
        assert results[0]["_enrichment"].get("s2_doi") is None
        assert results[0]["_enrichment"].get("crossref_title") is None
        assert results[0]["_enrichment"].get("openalex_title") is None
        # Skip reason recorded
        assert results[0]["_enrichment"].get("enrichment_skipped", "").startswith("year<")
        # Stats line mentions skipped_old
        assert "skipped_old" in stderr.getvalue(), f"expected 'skipped_old' in stderr, got: {stderr.getvalue()}"
    print("  [OK] test_old_paper_skipped passed")


def test_new_paper_enriched():
    """Paper from 2024 (2 years old in 2026) should be enriched normally."""
    results = [
        {"doi": "10.1/new", "title": "New paper", "year": 2024,
         "cited_by_count": 5, "abstract": ""},
    ]
    def fake_s2(doi):
        return {"doi": doi, "cited_by_count": 50, "abstract": "from S2"}
    with patch.object(search, "_s2_lookup_doi", side_effect=fake_s2), \
         patch.object(search, "_crossref_lookup_title", return_value=None):
        search.enrich_top_n(results, n=1, min_cites=0, max_age_years=10)
        assert results[0]["_enrichment"].get("s2_doi") is True
        assert results[0]["_enrichment"].get("enrichment_skipped") is None
        # abstract was empty, should be filled
        assert results[0]["abstract"] == "from S2"
    print("  [OK] test_new_paper_enriched passed")


def test_none_year_proceeds():
    """Paper with no year (None) should be enriched (can't determine age)."""
    results = [
        {"doi": "10.1/noyear", "title": "No year paper", "year": None,
         "cited_by_count": 5, "abstract": ""},
    ]
    def fake_s2(doi):
        return {"doi": doi, "cited_by_count": 50, "abstract": "from S2"}
    with patch.object(search, "_s2_lookup_doi", side_effect=fake_s2), \
         patch.object(search, "_crossref_lookup_title", return_value=None):
        search.enrich_top_n(results, n=1, min_cites=0, max_age_years=10)
        assert results[0]["_enrichment"].get("s2_doi") is True
        assert results[0]["_enrichment"].get("enrichment_skipped") is None
    print("  [OK] test_none_year_proceeds passed")


def test_max_age_zero_disables_skip():
    """max_age_years=0 should disable age-based skip (enrich all)."""
    # Paper from 1990 should be enriched when max_age_years=0
    results = [
        {"doi": "10.1/veryold", "title": "Very old paper", "year": 1990,
         "cited_by_count": 5, "abstract": ""},
    ]
    def fake_s2(doi):
        return {"doi": doi, "cited_by_count": 50, "abstract": "from S2"}
    with patch.object(search, "_s2_lookup_doi", side_effect=fake_s2), \
         patch.object(search, "_crossref_lookup_title", return_value=None):
        search.enrich_top_n(results, n=1, min_cites=0, max_age_years=0)
        assert results[0]["_enrichment"].get("s2_doi") is True
        assert results[0]["_enrichment"].get("enrichment_skipped") is None
        # abstract was empty, should be filled
        assert results[0]["abstract"] == "from S2"
    print("  [OK] test_max_age_zero_disables_skip passed")


def test_tighter_threshold_5_years():
    """max_age_years=5 means skip papers >5 years old."""
    # 2018 paper is 8 years old in 2026; should be skipped with max_age_years=5
    results = [
        {"doi": "10.1/2018", "title": "2018 paper", "year": 2018,
         "cited_by_count": 5, "abstract": ""},
    ]
    with patch.object(search, "_s2_lookup_doi", side_effect=AssertionError("S2 should NOT be called")):
        search.enrich_top_n(results, n=1, min_cites=0, max_age_years=5)
        assert results[0]["_enrichment"].get("enrichment_skipped", "").startswith("year<2021")
    print("  [OK] test_tighter_threshold_5_years passed")


def test_boundary_exactly_10_years_not_skipped():
    """Paper from 2016 (exactly 10 years old in 2026) should NOT be skipped
    because condition is '> max_age_years' (strict greater-than)."""
    # 2026 - 2016 = 10, not > 10, so NOT skipped
    results = [
        {"doi": "10.1/2016", "title": "2016 paper", "year": 2016,
         "cited_by_count": 5, "abstract": ""},
    ]
    def fake_s2(doi):
        return {"doi": doi, "cited_by_count": 50, "abstract": "from S2"}
    with patch.object(search, "_s2_lookup_doi", side_effect=fake_s2), \
         patch.object(search, "_crossref_lookup_title", return_value=None):
        search.enrich_top_n(results, n=1, min_cites=0, max_age_years=10)
        # Should be enriched (not strictly older than 10 years)
        assert results[0]["_enrichment"].get("s2_doi") is True
        assert results[0]["_enrichment"].get("enrichment_skipped") is None
    print("  [OK] test_boundary_exactly_10_years_not_skipped passed")


def test_mixed_old_and_new():
    """Mix of old and new papers: old skipped, new enriched."""
    results = [
        {"doi": "10.1/old", "title": "Old paper", "year": 2000, "cited_by_count": 5, "abstract": ""},
        {"doi": "10.1/new", "title": "New paper", "year": 2024, "cited_by_count": 5, "abstract": ""},
        {"doi": "10.1/medium", "title": "2015 paper", "year": 2015, "cited_by_count": 5, "abstract": ""},
    ]
    def fake_s2(doi):
        return {"doi": doi, "cited_by_count": 50, "abstract": "from S2"}
    with patch.object(search, "_s2_lookup_doi", side_effect=fake_s2), \
         patch.object(search, "_crossref_lookup_title", return_value=None):
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            search.enrich_top_n(results, n=3, min_cites=0, max_age_years=10)
        by_doi = {r["doi"]: r for r in results}
        # 2000 (26y) and 2015 (11y) should be skipped; 2024 (2y) should be enriched
        assert by_doi["10.1/old"]["_enrichment"].get("enrichment_skipped") is not None
        assert by_doi["10.1/medium"]["_enrichment"].get("enrichment_skipped") is not None
        assert by_doi["10.1/new"]["_enrichment"].get("s2_doi") is True
        # Stats line
        err = stderr.getvalue()
        assert "skipped_old 2" in err, f"expected 'skipped_old 2' in stderr, got: {err}"
    print("  [OK] test_mixed_old_and_new passed")


def test_max_age_with_min_cites_combination():
    """Verify max_age_years and min_cites work together correctly.
    Old paper with 0 cite: should be skipped for BOTH reasons (age takes priority)."""
    results = [
        {"doi": "10.1/old0", "title": "Old 0-cite", "year": 2010,
         "cited_by_count": 0, "abstract": ""},
    ]
    with patch.object(search, "_s2_lookup_doi", side_effect=AssertionError("should not be called")):
        search.enrich_top_n(results, n=1, min_cites=1, max_age_years=10)
        # The age check happens first, so enrichment_skipped is set, NOT s2_doi_skipped
        assert results[0]["_enrichment"].get("enrichment_skipped") is not None
        assert results[0]["_enrichment"].get("s2_doi_skipped") is None
    print("  [OK] test_max_age_with_min_cites_combination passed")


def main():
    print("\n=== [P1-18] max_age_years unit tests ===")
    test_old_paper_skipped()
    test_new_paper_enriched()
    test_none_year_proceeds()
    test_max_age_zero_disables_skip()
    test_tighter_threshold_5_years()
    test_boundary_exactly_10_years_not_skipped()
    test_mixed_old_and_new()
    test_max_age_with_min_cites_combination()
    print("\n=== ALL P1-18 TESTS PASSED ===")


if __name__ == "__main__":
    main()
