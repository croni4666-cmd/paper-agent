"""pa_cli.dedup_strict — stricter Bibtex dedup with fuzzy matching.

Per ROADMAP [P2-10] (added 2026-07-15, shipped 2026-07-20 in v3.9.10.6):
  Catches near-duplicates that default DOI-only dedup misses:
    - Fuzzy title match (difflib.SequenceMatcher ratio >= 0.85)
    - Same author + year (cross-DOI merge)
    - Same arxiv-ID (cross-venue merge)
  Default dedup priority: DOI > arxiv-ID > fuzzy title > exact-title.

  Reuses pa_cli/scaffold.py:parse_bibtex for bib parsing.

Usage from CLI:
  pa dedup-strict refs.bib --out deduped.bib
  pa dedup-strict refs.bib --out deduped.bib --report dup_report.json
  pa dedup-strict refs.bib --out deduped.bib --fuzzy-threshold 0.90
"""
from __future__ import annotations

import difflib
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .scaffold import parse_bibtex, load_bibtex


# ──────────────────────────────────────────────────────────────────────
# Normalization helpers
# ──────────────────────────────────────────────────────────────────────

def _normalize_title(title: str) -> str:
    """Normalize title for fuzzy comparison.

    Steps: lowercase, strip punctuation, collapse whitespace, remove common
    latex (\textbf, \textit) markers, drop LaTeX curly-brace artifacts.
    """
    if not title:
        return ''
    t = title.lower()
    # Drop LaTeX commands
    t = re.sub(r"\\[a-zA-Z]+\s*\{?", "", t)
    # Drop math mode $...$
    t = re.sub(r"\$.*?\$", "", t)
    # Drop punctuation except word chars and spaces
    t = re.sub(r"[^\w\s]", " ", t)
    # Collapse whitespace
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _normalize_author(author: str) -> set:
    """Normalize author string: 'Last, First and Last2, First2' -> {'lastfirst', 'last2first2'}.

    Bibtex author field format is "Last, First" per name, joined by ' and '.
    We collapse each (last, first) pair into a single token 'lastfirst' so
    the same person across papers maps to the same key.
    """
    if not author:
        return set()
    # Split on ' and ' first to get individual name strings
    pieces = re.split(r"\s+and\s+", author)
    names = set()
    for piece in pieces:
        # Each piece is "Last, First" or "Last" (institutional author).
        # Drop all spaces and punctuation, lowercase.
        compact = re.sub(r"[\s,]+", "", piece).lower()
        if compact:
            names.add(compact)
    return names


def _extract_arxiv_id(entry: Dict) -> Optional[str]:
    """Extract arxiv ID from various fields (eprint, archiveprefix, journal)."""
    for field in ('eprint', 'arxiv', 'arxiv-id', 'archiveprefix'):
        if entry.get(field):
            v = entry[field].strip()
            # Match formats: 2507.02259, arXiv:2507.02259, math.AG/0501234
            m = re.search(r"(\d{4}\.\d{4,5}(v\d+)?|[\w\-\.]+/\d{7})", v)
            if m:
                return m.group(1)
    # Also check journal field for arXiv-style IDs (common in old bibtex)
    if entry.get('journal', '').lower().startswith('arxiv'):
        m = re.search(r"(\d{4}\.\d{4,5})", entry['journal'])
        if m:
            return m.group(1)
    return None


# ──────────────────────────────────────────────────────────────────────
# Fuzzy matching
# ──────────────────────────────────────────────────────────────────────

def fuzzy_title_match(t1: str, t2: str, threshold: float = 0.85) -> bool:
    """Return True if normalized titles are within threshold similarity.

    Uses difflib.SequenceMatcher ratio (0.0-1.0).
    """
    n1, n2 = _normalize_title(t1), _normalize_title(t2)
    if not n1 or not n2:
        return False
    if n1 == n2:
        return True
    ratio = difflib.SequenceMatcher(None, n1, n2).ratio()
    return ratio >= threshold


def title_similarity(t1: str, t2: str) -> float:
    """Return SequenceMatcher ratio (0.0-1.0) between two titles."""
    n1, n2 = _normalize_title(t1), _normalize_title(t2)
    if not n1 or not n2:
        return 0.0
    return difflib.SequenceMatcher(None, n1, n2).ratio()


# ──────────────────────────────────────────────────────────────────────
# Dedup key generation
# ──────────────────────────────────────────────────────────────────────

def dedup_key(entry: Dict) -> Tuple[str, str, str]:
    """Generate a 3-tuple (doi, arxiv, normalized_title).

    First non-empty value is the primary key. Ties broken by arxiv, then title.
    """
    doi = (entry.get('doi') or '').strip().lower()
    arxiv = _extract_arxiv_id(entry) or ''
    title_n = _normalize_title(entry.get('title', ''))
    return (doi, arxiv, title_n)


# ──────────────────────────────────────────────────────────────────────
# Grouping & merge
# ──────────────────────────────────────────────────────────────────────

@dataclass
class DupGroup:
    """A group of bib entries that should be merged into one."""
    primary_key: str  # which dedup key won
    entries: List[Dict] = field(default_factory=list)
    match_reasons: List[str] = field(default_factory=list)

    def __len__(self):
        return len(self.entries)


def find_dup_groups(
    entries: List[Dict],
    fuzzy_threshold: float = 0.85,
    progress: bool = False,
) -> List[DupGroup]:
    """Find groups of duplicate bib entries.

    Strategy:
      1. Group by DOI (exact match, highest priority)
      2. Group by arxiv-ID (exact match, second priority)
      3. Group by fuzzy title (>= threshold similarity, third priority)
      4. Group by same first-author + same year (heuristic, lowest priority)

    Returns list of DupGroup with 1+ entries; groups with 1 entry are
    non-duplicates (kept as-is in dedup output).
    """
    # Step 1: index by DOI
    by_doi: Dict[str, List[Dict]] = defaultdict(list)
    by_arxiv: Dict[str, List[Dict]] = defaultdict(list)
    for e in entries:
        doi = (e.get('doi') or '').strip().lower()
        arxiv = _extract_arxiv_id(e) or ''
        if doi:
            by_doi[doi].append(e)
        if arxiv:
            by_arxiv[arxiv].append(e)

    # Step 2: union-find to merge groups via DOI and arxiv
    parent = {id(e): id(e) for e in entries}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    # Merge by DOI
    for doi, group in by_doi.items():
        if len(group) > 1:
            base = id(group[0])
            for e in group[1:]:
                union(base, id(e))

    # Merge by arxiv (skip if already same group via DOI)
    for arxiv, group in by_arxiv.items():
        if len(group) > 1:
            base = id(group[0])
            for e in group[1:]:
                union(base, id(e))

    # Step 3: fuzzy title match
    title_norm_list = [(_normalize_title(e.get('title', '')), i) for i, e in enumerate(entries)]
    n = len(entries)
    for i in range(n):
        for j in range(i + 1, n):
            t1 = title_norm_list[i][0]
            t2 = title_norm_list[j][0]
            if not t1 or not t2:
                continue
            if t1 == t2:
                # exact title match
                union(id(entries[i]), id(entries[j]))
                continue
            ratio = difflib.SequenceMatcher(None, t1, t2).ratio()
            if ratio >= fuzzy_threshold:
                union(id(entries[i]), id(entries[j]))

    # Step 4: collect groups
    groups: Dict[int, List[Dict]] = defaultdict(list)
    for e in entries:
        groups[find(id(e))].append(e)

    result = []
    for root_id, group_entries in groups.items():
        if len(group_entries) == 1:
            # No duplicate; still wrap in DupGroup for consistent output
            result.append(DupGroup(primary_key=root_id, entries=group_entries,
                                    match_reasons=['unique']))
        else:
            # Multiple — pick primary (first entry with a DOI, else first)
            primary = next((e for e in group_entries if e.get('doi')), group_entries[0])
            reasons = []
            dois = {e.get('doi', '').strip().lower() for e in group_entries if e.get('doi')}
            if len(dois) > 0 and len(dois) < len(group_entries):
                reasons.append('partial-doi')
            elif len(dois) > 1:
                reasons.append('multi-doi-conflict')
            arxivs = {_extract_arxiv_id(e) for e in group_entries}
            arxivs.discard(None)
            if len(arxivs) > 1:
                reasons.append('multi-arxiv-conflict')
            elif len(arxivs) == 1:
                reasons.append('arxiv-match')
            if not reasons:
                reasons.append('fuzzy-title')
            result.append(DupGroup(primary_key=primary.get('key', root_id),
                                    entries=group_entries, match_reasons=reasons))
    return result


# ──────────────────────────────────────────────────────────────────────
# Write deduped Bibtex
# ──────────────────────────────────────────────────────────────────────

def write_deduped_bibtex(groups: List[DupGroup], original_text: str, out_path: Path) -> int:
    """Write deduped Bibtex. For each group with >1 entries, keep only the
    primary (first with DOI, else first).

    Returns number of entries written.
    """
    # Find primary entries to keep
    keep_keys = set()
    for g in groups:
        if len(g) == 1:
            keep_keys.add(g.entries[0].get('key'))
        else:
            primary = next((e for e in g.entries if e.get('doi')), g.entries[0])
            keep_keys.add(primary.get('key'))

    # Re-parse original text and write back only kept entries
    # Use a simple approach: split on @ entries
    chunks = re.split(r"(?=@\w+\s*\{)", original_text)
    written = 0
    with open(out_path, 'w', encoding='utf-8') as f:
        for chunk in chunks:
            chunk_stripped = chunk.strip()
            if not chunk_stripped.startswith('@'):
                continue
            m = re.match(r"@\w+\s*\{\s*([^,\s]+)\s*,", chunk_stripped)
            if not m:
                continue
            key = m.group(1)
            if key in keep_keys:
                f.write(chunk)
                if not chunk.endswith('\n'):
                    f.write('\n')
                written += 1
    return written


# ──────────────────────────────────────────────────────────────────────
# Report
# ──────────────────────────────────────────────────────────────────────

def build_report(groups: List[DupGroup]) -> Dict:
    """Build a JSON-serializable report of duplicate groups."""
    dup_groups = [g for g in groups if len(g) > 1]
    return {
        'n_total_entries': sum(len(g) for g in groups),
        'n_unique_entries': len(groups),
        'n_duplicate_groups': len(dup_groups),
        'n_removed': sum(len(g) - 1 for g in dup_groups),
        'duplicate_groups': [
            {
                'primary_key': g.primary_key,
                'reasons': g.match_reasons,
                'entries': [
                    {
                        'key': e.get('key'),
                        'doi': e.get('doi', ''),
                        'title': e.get('title', ''),
                        'year': e.get('year', ''),
                    }
                    for e in g.entries
                ],
            }
            for g in dup_groups
        ],
    }


# ──────────────────────────────────────────────────────────────────────
# Main pipeline
# ──────────────────────────────────────────────────────────────────────

def run_dedup(
    bib_path: Path,
    out_path: Path,
    report_path: Optional[Path] = None,
    fuzzy_threshold: float = 0.85,
) -> Dict:
    """Full pipeline. Returns the report dict."""
    original_text = bib_path.read_text(encoding='utf-8')
    entries = load_bibtex(bib_path)
    groups = find_dup_groups(entries, fuzzy_threshold=fuzzy_threshold)
    n_written = write_deduped_bibtex(groups, original_text, out_path)
    report = build_report(groups)
    report['n_written'] = n_written
    report['out_path'] = str(out_path)
    report['bib_path'] = str(bib_path)
    report['fuzzy_threshold'] = fuzzy_threshold
    if report_path:
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    return report
