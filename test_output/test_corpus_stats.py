"""Tests for pa_cli.corpus_stats (v3.9.20 [P2-19]).

Computes aggregate stats from a pa project's refs.bib: n_papers,
by-type, year distribution, top authors, top venues.

Pure stdlib + existing load_bibtex. No new deps.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pa_cli import corpus_stats
from pa_cli.corpus_stats import (
    _split_authors,
    _author_short,
    _year_from_entry,
    compute_corpus_stats,
    format_corpus_stats_human,
)


def _write_refs_bib(path, entries):
    """Write a minimal refs.bib from a list of (key, fields_dict) tuples."""
    lines = []
    for key, fields in entries:
        lines.append("@article{" + key + ",")
        for k, v in fields.items():
            lines.append(f"  {k:<8s} = {{{v}}},")
        lines.append("}")
    path.write_text("\n\n".join(lines) + "\n", encoding="utf-8")


# ─────────────────────────────────────────────────────────────────
# TestSplitAuthors
# ─────────────────────────────────────────────────────────────────
class TestSplitAuthors:
    def test_empty(self):
        assert _split_authors("") == []

    def test_single(self):
        assert _split_authors("Smith, A") == ["Smith, A"]

    def test_multi(self):
        assert _split_authors("Smith, A and Jones, B") == ["Smith, A", "Jones, B"]

    def test_three(self):
        assert _split_authors("A, X and B, Y and C, Z") == ["A, X", "B, Y", "C, Z"]


# ─────────────────────────────────────────────────────────────────
# TestAuthorShort
# ─────────────────────────────────────────────────────────────────
class TestAuthorShort:
    def test_with_comma(self):
        assert _author_short("Smith, Alice") == "Smith"

    def test_without_comma(self):
        assert _author_short("World Health Organization") == "World Health Organization"

    def test_empty(self):
        assert _author_short("") == ""


# ─────────────────────────────────────────────────────────────────
# TestYearFromEntry
# ─────────────────────────────────────────────────────────────────
class TestYearFromEntry:
    def test_full_year(self):
        assert _year_from_entry({"year": "2024"}) == 2024

    def test_year_month_day(self):
        assert _year_from_entry({"year": "2023-06-15"}) == 2023

    def test_no_year(self):
        assert _year_from_entry({}) is None

    def test_invalid_year(self):
        assert _year_from_entry({"year": "abc"}) is None

    def test_year_with_garbage(self):
        assert _year_from_entry({"year": "20x4"}) is None


# ─────────────────────────────────────────────────────────────────
# TestComputeCorpusStats
# ─────────────────────────────────────────────────────────────────
class TestComputeCorpusStats:
    def test_empty_file(self, tmp_path):
        path = tmp_path / "refs.bib"
        # Non-existent file
        stats = compute_corpus_stats(path)
        assert stats["n_papers"] == 0
        assert stats["n_with_doi"] == 0
        assert stats["year_min"] is None
        assert stats["top_authors"] == []

    def test_missing_file(self, tmp_path):
        path = tmp_path / "nope.bib"
        stats = compute_corpus_stats(path)
        assert stats["n_papers"] == 0

    def test_simple(self, tmp_path):
        path = tmp_path / "refs.bib"
        _write_refs_bib(path, [
            ("a1", {"title": "T1", "author": "Smith, A", "journal": "J Health", "year": "2024", "doi": "10.1/a"}),
            ("a2", {"title": "T2", "author": "Jones, B", "journal": "J Health", "year": "2023", "doi": "10.1/b"}),
        ])
        stats = compute_corpus_stats(path)
        assert stats["n_papers"] == 2
        assert stats["n_with_doi"] == 2
        assert stats["n_without_doi"] == 0
        assert stats["year_min"] == 2023
        assert stats["year_max"] == 2024
        assert stats["year_median"] == 2023  # median of [2023, 2024]
        assert stats["by_type"] == {"article": 2}
        assert stats["year_histogram"] == {"2020s": 2}
        # Top authors
        assert stats["top_authors"][0]["name"] == "Smith"
        assert stats["top_authors"][0]["count"] == 1
        # Top venues
        assert stats["top_venues"][0]["name"] == "J Health"
        assert stats["top_venues"][0]["count"] == 2

    def test_without_doi(self, tmp_path):
        path = tmp_path / "refs.bib"
        _write_refs_bib(path, [
            ("a1", {"title": "T1", "author": "X, Y", "journal": "J", "year": "2020"}),  # no DOI
        ])
        stats = compute_corpus_stats(path)
        assert stats["n_papers"] == 1
        assert stats["n_with_doi"] == 0
        assert stats["n_without_doi"] == 1

    def test_multi_author_split(self, tmp_path):
        path = tmp_path / "refs.bib"
        _write_refs_bib(path, [
            ("a1", {"title": "T1", "author": "Smith, A and Jones, B", "journal": "J", "year": "2024", "doi": "10.1/a"}),
            ("a2", {"title": "T2", "author": "Smith, A", "journal": "J", "year": "2023", "doi": "10.1/b"}),
            ("a3", {"title": "T3", "author": "Smith, A and Lee, C", "journal": "K", "year": "2022", "doi": "10.1/c"}),
        ])
        stats = compute_corpus_stats(path)
        # Smith should be top with 3 papers
        assert stats["top_authors"][0]["name"] == "Smith"
        assert stats["top_authors"][0]["count"] == 3
        # Year histogram
        assert stats["year_histogram"] == {"2020s": 3}

    def test_top_n_limit(self, tmp_path):
        path = tmp_path / "refs.bib"
        entries = []
        for i in range(15):
            entries.append((f"k{i}", {"title": f"T{i}", "author": f"Author{i}, X", "journal": f"J{i}", "year": "2024", "doi": f"10.1/{i}"}))
        _write_refs_bib(path, entries)
        stats = compute_corpus_stats(path, top_n=3)
        # Only top 3 authors returned
        assert len(stats["top_authors"]) == 3
        assert len(stats["top_venues"]) == 3

    def test_venue_fallback(self, tmp_path):
        # No journal field, but booktitle for inproceedings
        path = tmp_path / "refs.bib"
        path.write_text(
            "@inproceedings{k1,\n  title={T1},\n  author={X, Y},\n"
            "  booktitle={Proc ICML},\n  year={2024},\n  doi={10.1/a}\n}\n",
            encoding="utf-8",
        )
        stats = compute_corpus_stats(path)
        assert stats["by_type"] == {"inproceedings": 1}
        assert stats["top_venues"][0]["name"] == "Proc ICML"


# ─────────────────────────────────────────────────────────────────
# TestFormatCorpusStatsHuman
# ─────────────────────────────────────────────────────────────────
class TestFormatCorpusStatsHuman:
    def test_empty(self, tmp_path):
        path = tmp_path / "refs.bib"
        stats = compute_corpus_stats(path)
        out = format_corpus_stats_human(stats)
        assert "total:" in out
        assert "0 papers" in out

    def test_with_data(self, tmp_path):
        path = tmp_path / "refs.bib"
        _write_refs_bib(path, [
            ("a1", {"title": "T1", "author": "Smith, A", "journal": "J", "year": "2024", "doi": "10.1/a"}),
        ])
        stats = compute_corpus_stats(path)
        out = format_corpus_stats_human(stats)
        assert "1 papers" in out
        assert "year range:    2024 - 2024" in out
        assert "top authors:" in out
        assert "Smith(1)" in out


# ─────────────────────────────────────────────────────────────────
# TestCliCorpusStats (smoke)
# ─────────────────────────────────────────────────────────────────
class TestCliCorpusStats:
    def test_help(self):
        from click.testing import CliRunner
        from pa_cli import cli
        result = CliRunner().invoke(cli.main, ["project", "corpus-stats", "--help"])
        assert result.exit_code == 0
        assert "--json" in result.output
        assert "--top" in result.output
        assert "[P2-19]" in result.output
