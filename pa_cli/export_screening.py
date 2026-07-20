"""pa_cli.export_screening — Bibtex (+ optional pa judge) to systematic-review CSV.

Per ROADMAP [P2-8] (added 2026-07-15, shipped 2026-07-20 in v3.9.10.4):
  Exports a Bibtex (and optional pa judge data) to a screening CSV ready for
  Notion / Excel / RevMan / Covidence. Columns:
    - paper_key    : bib entry key (e.g. 'smith2023ai')
    - query        : pa judge query (empty if no judgements for this paper)
    - relevance    : 0/1/2 (empty if no judgements)
    - reason       : pa judge reason (empty if no judgements)
    - source       : pa judge source ('manual' / 'auto' / 'bulk-import')
    - title        : bib title
    - authors      : bib authors (joined with '; ')
    - year         : bib year (int)
    - venue        : bib journal/booktitle
    - doi          : bib doi
    - abstract     : bib abstract (may be empty)
    - type         : bib type (@article / @inproceedings / etc.)
    - bib_url      : doi.org URL if doi present, else None

Use case: after running pa judge on a query, export the full corpus to CSV,
then import into Notion/Excel for systematic review with title/abstract screening.

Usage from CLI:
  pa export-screening refs.bib --out screening.csv
  pa export-screening refs.bib --judges db.sqlite --query "AI literacy" --out screening.csv
  pa export-screening refs.bib --judges db.sqlite --query "..." --include-unrated --out screening.csv
"""
from __future__ import annotations

import csv
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .scaffold import parse_bibtex, load_bibtex


# ──────────────────────────────────────────────────────────────────────
# Bibtex screening dict
# ──────────────────────────────────────────────────────────────────────

def build_screening_dict(bib_path: Path) -> Dict[str, Dict[str, str]]:
    """Build per-paper screening dict from Bibtex.

    Returns dict {paper_key: {title, authors, year, venue, doi, abstract, type}}.
    """
    entries = load_bibtex(bib_path)
    out = {}
    for e in entries:
        key = e.get('key')
        if not key:
            continue
        # Authors field in bibtex is comma-separated "Last, First and Last2, First2"
        # Normalize: replace " and " with "; " for CSV friendliness
        authors = e.get('author', '').replace(' and ', '; ')
        out[key] = {
            'paper_key': key,
            'title': e.get('title', ''),
            'authors': authors,
            'year': e.get('year', ''),
            'venue': e.get('journal', '') or e.get('booktitle', '') or e.get('publisher', ''),
            'doi': e.get('doi', ''),
            'abstract': e.get('abstract', ''),
            'type': e.get('type', 'misc'),
            'bib_url': f"https://doi.org/{e['doi']}" if e.get('doi') else '',
        }
    return out


# ──────────────────────────────────────────────────────────────────────
# pa judge join
# ──────────────────────────────────────────────────────────────────────

def load_judgements(
    db_path: Path,
    query: Optional[str] = None,
    include_unrated: bool = True,
) -> List[Dict[str, str]]:
    """Load pa judge data from sqlite, optionally filtered to one query.

    Returns list of {paper_key, query, relevance, reason, source, paper_title}
    sorted by (query, relevance desc, paper_key).

    If include_unrated=True (default), also adds an "unrated" row for every
    bib paper_key that has NO judgements in the db, so the CSV is complete
    (relevance='' and reason='' for unrated).

    NOTE: This function takes a bib_path so it can include unrated rows for
    every bib key. The function is split into two for clarity:
      - load_judgements_only(db_path, query): returns just judge rows
      - merge_with_bib: merges with bib dict to add unrated rows
    """
    if not db_path.exists():
        # No judge db yet — return empty list
        return []

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        if query:
            cur.execute(
                "SELECT paper_key, query, relevance, reason, source, paper_title "
                "FROM judgements WHERE query = ? ORDER BY relevance DESC, paper_key",
                (query,)
            )
        else:
            cur.execute(
                "SELECT paper_key, query, relevance, reason, source, paper_title "
                "FROM judgements ORDER BY query, relevance DESC, paper_key"
            )
        rows = [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()
    return rows


def merge_with_bib(
    bib_dict: Dict[str, Dict[str, str]],
    judge_rows: List[Dict[str, str]],
    include_unrated: bool = True,
) -> List[Dict[str, str]]:
    """Merge bib dict with judge rows.

    If include_unrated=True, every bib paper_key with no judge row gets a
    placeholder row (relevance='', reason='', source='', query='').
    """
    # Index judge rows by (query, paper_key) for uniqueness
    by_qk: Dict[Tuple[str, str], Dict] = {(r['query'], r['paper_key']): r for r in judge_rows}
    seen_paper_keys: set = {r['paper_key'] for r in judge_rows}

    out = []
    for r in judge_rows:
        bib = bib_dict.get(r['paper_key'], {})
        out.append({
            'paper_key': r['paper_key'],
            'query': r['query'],
            'relevance': r['relevance'],
            'reason': r.get('reason', ''),
            'source': r.get('source', ''),
            'title': bib.get('title', r.get('paper_title', '')),
            'authors': bib.get('authors', ''),
            'year': bib.get('year', ''),
            'venue': bib.get('venue', ''),
            'doi': bib.get('doi', ''),
            'abstract': bib.get('abstract', ''),
            'type': bib.get('type', ''),
            'bib_url': bib.get('bib_url', ''),
        })

    if include_unrated:
        for key, bib in bib_dict.items():
            if key not in seen_paper_keys:
                out.append({
                    'paper_key': key,
                    'query': '',
                    'relevance': '',
                    'reason': '',
                    'source': '',
                    'title': bib['title'],
                    'authors': bib['authors'],
                    'year': bib['year'],
                    'venue': bib['venue'],
                    'doi': bib['doi'],
                    'abstract': bib['abstract'],
                    'type': bib['type'],
                    'bib_url': bib['bib_url'],
                })
    return out


# ──────────────────────────────────────────────────────────────────────
# CSV writer
# ──────────────────────────────────────────────────────────────────────

CSV_COLUMNS = [
    'paper_key', 'query', 'relevance', 'reason', 'source',
    'title', 'authors', 'year', 'venue', 'doi', 'abstract', 'type', 'bib_url',
]


def write_csv(rows: List[Dict[str, str]], out_path: Path) -> int:
    """Write screening rows to CSV. Returns number of data rows written.

    Handles:
    - Quoting (csv.QUOTE_MINIMAL)
    - UTF-8 encoding (with BOM for Excel compatibility)
    - Empty values for unrated rows
    - Multiline fields (abstract) properly quoted
    """
    n = 0
    with open(out_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        for row in rows:
            # Convert all values to string (None → '')
            row_clean = {k: ('' if v is None else str(v)) for k, v in row.items()}
            writer.writerow(row_clean)
            n += 1
    return n


# ──────────────────────────────────────────────────────────────────────
# Main pipeline
# ──────────────────────────────────────────────────────────────────────

def run_export_screening(
    bib_path: Path,
    out_path: Path,
    judges_db: Optional[Path] = None,
    query: Optional[str] = None,
    include_unrated: bool = True,
) -> Dict:
    """Full pipeline. Returns dict with summary stats."""
    bib_dict = build_screening_dict(bib_path)

    judge_rows: List[Dict[str, str]] = []
    if judges_db is not None:
        judge_rows = load_judgements(judges_db, query=query, include_unrated=False)

    rows = merge_with_bib(bib_dict, judge_rows, include_unrated=include_unrated)
    n_written = write_csv(rows, out_path)

    return {
        'n_bib_papers': len(bib_dict),
        'n_judge_rows': len(judge_rows),
        'n_csv_rows': n_written,
        'n_unrated': n_written - len(judge_rows) if include_unrated else 0,
        'out_path': str(out_path),
        'bib_path': str(bib_path),
        'judges_db': str(judges_db) if judges_db else None,
        'query': query,
    }
