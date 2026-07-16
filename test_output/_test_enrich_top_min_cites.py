"""Unit test: [P1-14] enrich_top_n min_cites filter (v3.9.9.7).

Verifies:
1. min_cites=1 (default): skips S2 for 0-cite papers
2. min_cites=0: tries S2 even for 0-cite papers (v3.9.7.8 compat)
3. min_cites=5: skips S2 for papers with cite < 5
4. _enrichment metadata documents skips
5. Stats are printed to stderr (visible in CLI)

No real network calls; all S2/Crossref lookups are mocked.
"""

import io
import sys
from contextlib import redirect_stderr
from unittest.mock import patch

sys.path.insert(0, ".")

from pa_cli import search


def fake_s2_doi(doi):
    """Fake S2 response: returns shallow data, no tldr/inf_cite."""
    return {
        "doi": doi,
        "abstract": f"Abstract for {doi} (from S2 mock)",
        "cited_by_count": 5,  # bumped
        "venue": "Mock Journal",
    }


def fake_cr_title(title):
    return None  # not used in this test


def test_min_cites_1_skips_zero_cite():
    """min_cites=1 (default) should skip S2 for 0-cite papers."""
    results = [
        {"doi": "10.1/a", "title": "Paper A 0-cite", "cited_by_count": 0, "abstract": ""},
        {"doi": "10.1/b", "title": "Paper B 5-cite", "cited_by_count": 5, "abstract": ""},
        {"doi": "10.1/c", "title": "Paper C 0-cite", "cited_by_count": 0, "abstract": "has abs"},
    ]
    with patch.object(search, "_s2_lookup_doi", side_effect=fake_s2_doi) as s2_mock, \
         patch.object(search, "_crossref_lookup_title", side_effect=fake_cr_title):
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            search.enrich_top_n(results, n=3, min_cites=1)
        # Only paper B (cite=5) should hit S2
        assert s2_mock.call_count == 1, f"expected 1 S2 call, got {s2_mock.call_count}"
        # Use DOI to look up papers (results are re-sorted by cite after enrichment)
        by_doi = {r["doi"]: r for r in results}
        # A and C should have skip metadata
        assert by_doi["10.1/a"]["_enrichment"].get("s2_doi_skipped", "").startswith("cited_by_count<")
        assert by_doi["10.1/c"]["_enrichment"].get("s2_doi_skipped", "").startswith("cited_by_count<")
        # B should have s2_doi enrichment
        assert by_doi["10.1/b"]["_enrichment"].get("s2_doi") is True
        # Stderr should have stats line
        err = stderr.getvalue()
        assert "[P1-14] enrich_top_n" in err
        assert "skipped 2" in err, f"expected 'skipped 2' in stderr, got: {err}"
    print("  [OK] test_min_cites_1_skips_zero_cite passed")


def test_min_cites_0_tries_all():
    """min_cites=0 should try S2 for all papers (v3.9.7.8 backward compat)."""
    results = [
        {"doi": "10.1/a", "title": "Paper A 0-cite", "cited_by_count": 0, "abstract": ""},
        {"doi": "10.1/b", "title": "Paper B 0-cite", "cited_by_count": 0, "abstract": ""},
    ]
    with patch.object(search, "_s2_lookup_doi", side_effect=fake_s2_doi) as s2_mock, \
         patch.object(search, "_crossref_lookup_title", side_effect=fake_cr_title):
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            search.enrich_top_n(results, n=2, min_cites=0)
        # Both papers should hit S2
        assert s2_mock.call_count == 2, f"expected 2 S2 calls, got {s2_mock.call_count}"
        # Both should have s2_doi enrichment (no skips)
        by_doi = {r["doi"]: r for r in results}
        assert by_doi["10.1/a"]["_enrichment"].get("s2_doi") is True
        assert by_doi["10.1/b"]["_enrichment"].get("s2_doi") is True
        # No skip messages in stderr
        err = stderr.getvalue()
        assert "[P1-14] enrich_top_n" not in err, f"expected no P1-14 log, got: {err}"
    print("  [OK] test_min_cites_0_tries_all passed")


def test_min_cites_5_threshold():
    """min_cites=5 should skip S2 for papers with cite < 5."""
    results = [
        {"doi": "10.1/a", "title": "Paper A 3-cite", "cited_by_count": 3, "abstract": ""},
        {"doi": "10.1/b", "title": "Paper B 10-cite", "cited_by_count": 10, "abstract": ""},
        {"doi": "10.1/c", "title": "Paper C 0-cite", "cited_by_count": 0, "abstract": ""},
    ]
    with patch.object(search, "_s2_lookup_doi", side_effect=fake_s2_doi) as s2_mock, \
         patch.object(search, "_crossref_lookup_title", side_effect=fake_cr_title):
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            search.enrich_top_n(results, n=3, min_cites=5)
        # Only paper B (cite=10) should hit S2
        assert s2_mock.call_count == 1, f"expected 1 S2 call, got {s2_mock.call_count}"
        # A and C should be skipped
        by_doi = {r["doi"]: r for r in results}
        assert by_doi["10.1/a"]["_enrichment"].get("s2_doi_skipped", "").startswith("cited_by_count<5")
        assert by_doi["10.1/c"]["_enrichment"].get("s2_doi_skipped", "").startswith("cited_by_count<5")
        # B should be enriched
        assert by_doi["10.1/b"]["_enrichment"].get("s2_doi") is True
        err = stderr.getvalue()
        assert "skipped 2" in err
        assert "cited_by_count<5" in err
    print("  [OK] test_min_cites_5_threshold passed")


def test_no_abstract_no_doi_no_call():
    """Papers with no DOI and no cite shouldn't hit S2 (not enough info)."""
    results = [
        {"title": "No DOI no cite", "cited_by_count": 0, "abstract": ""},
    ]
    with patch.object(search, "_s2_lookup_doi", side_effect=fake_s2_doi) as s2_mock, \
         patch.object(search, "_crossref_lookup_title", side_effect=fake_cr_title):
        search.enrich_top_n(results, n=1, min_cites=1)
        # No DOI, so S2 not called (and no skip msg either — no doi path)
        assert s2_mock.call_count == 0
    print("  [OK] test_no_abstract_no_doi_no_call passed")


def main():
    print("\n=== [P1-14] enrich_top_n min_cites unit tests ===")
    test_min_cites_1_skips_zero_cite()
    test_min_cites_0_tries_all()
    test_min_cites_5_threshold()
    test_no_abstract_no_doi_no_call()
    print("\n=== ALL P1-14 TESTS PASSED ===")


if __name__ == "__main__":
    main()
