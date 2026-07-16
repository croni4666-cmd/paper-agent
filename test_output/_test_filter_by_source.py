"""Unit test: [P1-17] --source post-filter (v3.9.9.9).

Verifies:
1. No filter (None): returns all results
2. No filter (empty list): returns all results
3. Single source "openalex": only matches openalex results
4. Multiple sources "openalex,cnki": matches both
5. Prefix matching: "openalex" also matches "openalex_title" (P1-15 fallback)
6. Prefix matching: "crossref" matches both "crossref" and "crossref_title"
7. Case-insensitive: "OpenAlex" works
8. Unknown source: returns empty list (no match)

No network calls.
"""

import sys
import io
from contextlib import redirect_stderr
from unittest.mock import patch

sys.path.insert(0, ".")

from pa_cli import search


def test_no_filter_returns_all():
    results = [
        {"title": "A", "source": "openalex"},
        {"title": "B", "source": "cnki"},
        {"title": "C", "source": "crossref"},
    ]
    out = search.filter_by_source(results, source_filter=None)
    assert len(out) == 3
    out2 = search.filter_by_source(results, source_filter=[])
    assert len(out2) == 3
    print("  [OK] test_no_filter_returns_all passed")


def test_single_source():
    results = [
        {"title": "A", "source": "openalex"},
        {"title": "B", "source": "cnki"},
        {"title": "C", "source": "crossref"},
    ]
    out = search.filter_by_source(results, source_filter=["openalex"])
    assert len(out) == 1
    assert out[0]["title"] == "A"
    print("  [OK] test_single_source passed")


def test_multiple_sources():
    results = [
        {"title": "A", "source": "openalex"},
        {"title": "B", "source": "cnki"},
        {"title": "C", "source": "crossref"},
        {"title": "D", "source": "arxiv"},
    ]
    out = search.filter_by_source(results, source_filter=["openalex", "cnki"])
    titles = [r["title"] for r in out]
    assert sorted(titles) == ["A", "B"]
    print("  [OK] test_multiple_sources passed")


def test_prefix_matching_openalex():
    """'openalex' should match 'openalex' AND 'openalex_title' (P1-15 fallback)."""
    results = [
        {"title": "A", "source": "openalex"},
        {"title": "B", "source": "openalex_title"},  # from P1-15 fallback
        {"title": "C", "source": "cnki"},
    ]
    out = search.filter_by_source(results, source_filter=["openalex"])
    titles = [r["title"] for r in out]
    assert sorted(titles) == ["A", "B"], f"expected A,B, got {titles}"
    print("  [OK] test_prefix_matching_openalex passed")


def test_prefix_matching_crossref():
    """'crossref' should match 'crossref' AND 'crossref_title'."""
    results = [
        {"title": "A", "source": "crossref"},
        {"title": "B", "source": "crossref_title"},
        {"title": "C", "source": "openalex"},
    ]
    out = search.filter_by_source(results, source_filter=["crossref"])
    titles = [r["title"] for r in out]
    assert sorted(titles) == ["A", "B"]
    print("  [OK] test_prefix_matching_crossref passed")


def test_case_insensitive():
    results = [
        {"title": "A", "source": "OpenAlex"},  # mixed case source
        {"title": "B", "source": "openalex"},
    ]
    out = search.filter_by_source(results, source_filter=["openalex"])
    titles = [r["title"] for r in out]
    assert sorted(titles) == ["A", "B"], f"case-insensitive match failed, got {titles}"
    print("  [OK] test_case_insensitive passed")


def test_unknown_source_returns_empty():
    results = [
        {"title": "A", "source": "openalex"},
        {"title": "B", "source": "cnki"},
    ]
    out = search.filter_by_source(results, source_filter=["nonexistent_engine"])
    assert out == []
    print("  [OK] test_unknown_source_returns_empty passed")


def test_strips_whitespace_in_filter():
    """Filter 'openalex, cnki' (with space) should still work."""
    results = [
        {"title": "A", "source": "openalex"},
        {"title": "B", "source": "cnki"},
        {"title": "C", "source": "arxiv"},
    ]
    out = search.filter_by_source(results, source_filter=["openalex, cnki"])  # NOT split; passed as one
    # This is the helper's behavior; CLI is responsible for splitting
    assert len(out) == 0  # no source starts with "openalex, cnki"
    # Now test with list of stripped strings (CLI does this)
    out2 = search.filter_by_source(results, source_filter=[" openalex ", " cnki "])
    titles = [r["title"] for r in out2]
    assert sorted(titles) == ["A", "B"]
    print("  [OK] test_strips_whitespace_in_filter passed")


def test_returns_new_list_not_mutating():
    """filter_by_source should not mutate input."""
    results = [
        {"title": "A", "source": "openalex"},
        {"title": "B", "source": "cnki"},
    ]
    original_ids = [id(r) for r in results]
    out = search.filter_by_source(results, source_filter=["openalex"])
    assert len(results) == 2  # input unchanged
    assert [id(r) for r in results] == original_ids  # same objects
    assert len(out) == 1
    assert out[0]["title"] == "A"
    print("  [OK] test_returns_new_list_not_mutating passed")


def main():
    print("\n=== [P1-17] filter_by_source unit tests ===")
    test_no_filter_returns_all()
    test_single_source()
    test_multiple_sources()
    test_prefix_matching_openalex()
    test_prefix_matching_crossref()
    test_case_insensitive()
    test_unknown_source_returns_empty()
    test_strips_whitespace_in_filter()
    test_returns_new_list_not_mutating()
    print("\n=== ALL P1-17 TESTS PASSED ===")


if __name__ == "__main__":
    main()
