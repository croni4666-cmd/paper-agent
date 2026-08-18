"""pa_cli.corpus_stats - aggregate stats for a pa project's Bibtex corpus.

v3.9.20 [P2-19] - per-project corpus analytics.

Computes summary statistics from a pa project's refs.bib:
- n_papers (total, with-DOI, without-DOI)
- year distribution (min, max, median, by-decade histogram)
- top authors (top N by paper count, splitting "Lastname, Firstname and ...")
- top venues (top N by paper count, from journal/publisher fields)
- type distribution (article/inproceedings/book/etc.)

Pure stdlib + the existing `load_bibtex` from pa_cli.scaffold. No
new external deps.
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Optional, Tuple


def _split_authors(author_str: str) -> List[str]:
    """Split a Bibtex author field into a list of authors.

    Handles "Lastname, Firstname and Lastname, Firstname" format.
    """
    if not author_str:
        return []
    return [a.strip() for a in re.split(r"\s+and\s+", str(author_str)) if a.strip()]


def _author_short(author: str) -> str:
    """Shorten "Lastname, Firstname" to "Lastname" for display.

    For org authors (no comma), use as-is.
    """
    if not author:
        return ""
    if "," in author:
        return author.split(",", 1)[0].strip()
    return author.strip()


def _year_from_entry(entry: Dict[str, Any]) -> Optional[int]:
    """Extract a 4-digit year from a Bibtex entry's year field."""
    y = entry.get("year")
    if not y:
        return None
    y_str = str(y).strip()
    m = re.match(r"^(\d{4})", y_str)
    if m:
        try:
            return int(m.group(1))
        except (ValueError, TypeError):
            return None
    return None


def compute_corpus_stats(refs_bib_path: Path, top_n: int = 10) -> Dict[str, Any]:
    """Compute summary statistics from a Bibtex file.

    Args:
        refs_bib_path: path to refs.bib
        top_n: number of top authors / venues to return (default 10)

    Returns:
        Dict with:
        - n_papers: total
        - n_with_doi: count with DOI
        - n_without_doi: count without DOI
        - by_type: {type_name: count} e.g. {"article": 18, "inproceedings": 2}
        - year_min, year_max, year_median: int or None
        - year_histogram: {decade: count} e.g. {"2020s": 12, "2010s": 5}
        - top_authors: [{"name": "Smith, A", "count": 3}, ...]  (top N, desc)
        - top_venues: [{"name": "J Health Econ", "count": 5}, ...]  (top N, desc)
        - bibtex_path: absolute path of the source file

    Missing file: returns all-zero dict (does NOT raise).
    """
    out: Dict[str, Any] = {
        "n_papers": 0,
        "n_with_doi": 0,
        "n_without_doi": 0,
        "by_type": {},
        "year_min": None,
        "year_max": None,
        "year_median": None,
        "year_histogram": {},
        "top_authors": [],
        "top_venues": [],
        "bibtex_path": str(refs_bib_path),
    }

    refs_bib_path = Path(refs_bib_path)
    if not refs_bib_path.exists():
        return out

    from .scaffold import load_bibtex
    try:
        entries = load_bibtex(refs_bib_path)
    except Exception:
        return out

    out["n_papers"] = len(entries)

    # Type + DOI counts
    type_counter: Counter = Counter()
    n_with_doi = 0
    for e in entries:
        t = e.get("type", "misc") or "misc"
        type_counter[t] += 1
        if e.get("doi"):
            n_with_doi += 1
    out["n_with_doi"] = n_with_doi
    out["n_without_doi"] = len(entries) - n_with_doi
    out["by_type"] = dict(type_counter.most_common())

    # Year stats
    years: List[int] = []
    for e in entries:
        y = _year_from_entry(e)
        if y is not None:
            years.append(y)
    if years:
        out["year_min"] = min(years)
        out["year_max"] = max(years)
        out["year_median"] = int(median(years))
        # Decade histogram: bucket by 10-year decade
        decade_counter: Counter = Counter()
        for y in years:
            decade = f"{(y // 10) * 10}s"
            decade_counter[decade] += 1
        out["year_histogram"] = dict(
            sorted(decade_counter.items(), key=lambda x: x[0])
        )

    # Top authors (split on " and ", dedup by short name)
    author_counter: Counter = Counter()
    for e in entries:
        for a in _split_authors(e.get("author", "")):
            short = _author_short(a)
            if short:
                author_counter[short] += 1
    out["top_authors"] = [
        {"name": name, "count": count}
        for name, count in author_counter.most_common(top_n)
    ]

    # Top venues (from journal or publisher or booktitle)
    venue_counter: Counter = Counter()
    for e in entries:
        v = e.get("journal") or e.get("publisher") or e.get("booktitle") or ""
        v = str(v).strip()
        if v:
            venue_counter[v] += 1
    out["top_venues"] = [
        {"name": name, "count": count}
        for name, count in venue_counter.most_common(top_n)
    ]

    return out


def format_corpus_stats_human(stats: Dict[str, Any]) -> str:
    """Format corpus stats as a human-readable string."""
    lines = []
    lines.append(f"[corpus-stats] {stats['bibtex_path']}")
    lines.append(f"  total:         {stats['n_papers']} papers")
    lines.append(f"  with DOI:      {stats['n_with_doi']}")
    lines.append(f"  without DOI:   {stats['n_without_doi']}")
    if stats["by_type"]:
        type_str = ", ".join(f"{k}={v}" for k, v in stats["by_type"].items())
        lines.append(f"  by type:       {type_str}")
    if stats["year_min"] is not None:
        lines.append(
            f"  year range:    {stats['year_min']} - {stats['year_max']} "
            f"(median {stats['year_median']})"
        )
    if stats["year_histogram"]:
        hist_str = ", ".join(
            f"{k}={v}" for k, v in stats["year_histogram"].items()
        )
        lines.append(f"  by decade:     {hist_str}")
    if stats["top_authors"]:
        authors_str = ", ".join(
            f"{a['name']}({a['count']})" for a in stats["top_authors"][:5]
        )
        lines.append(f"  top authors:   {authors_str}")
    if stats["top_venues"]:
        venues_str = ", ".join(
            f"{v['name']}({v['count']})" for v in stats["top_venues"][:5]
        )
        lines.append(f"  top venues:    {venues_str}")
    return "\n".join(lines)
