"""
pa_cli.judge — relevance judgement collection for ML/DL rerank.

Per [P3-1] ROADMAP "Tier 5 long-term" (post-v3.9.7.9, revised per user
pushback 2026-07-15):
  v3.9.7.0-7.2 ML/DL local rerank failed at n=50 (data problem, not absolute).
  User's 2026-07-15 pushback: "ML/DL 本地不是不可行, 是数据太少".
  Corrected verdict: re-probe when n>=500.

This module is the data-collection track. Stores judgements in a local
SQLite DB so we can accumulate labels opportunistically over time and
re-train / re-evaluate ML/DL rerankers when n is large enough.

Relevance scale (matches existing bench/v01/labels.json rubric):
  0 = irrelevant  (off-topic, or wrong level+topic)
  1 = marginal    (topic adjacent, OR level wrong, OR scope right but topic wrong)
  2 = relevant    (matches query topic + level + scope)

Usage from CLI:
  pa judge add --query "AI literacy higher education" --key doi:10.1186/s41239-023-00411-8 \\
               --relevance 2 --reason "Direct hit on AI + higher ed + K-12"
  pa judge bulk refs.bib --query "数字普惠金融 家庭消费" --relevance 1
  pa judge list
  pa judge list --query "AI literacy" --relevance 2
  pa judge stats
  pa judge stats --query "AI literacy"
  pa judge export bench_labels.json
  pa judge import bench/v01/labels.json
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

# ---------- Storage ----------

# Default DB path: ~/.paper-agent/judgements.sqlite
# Honours PA_JUDGE_DB env var override.
DEFAULT_DB = Path(
    os.environ.get("PA_JUDGE_DB")
    or (Path.home() / ".paper-agent" / "judgements.sqlite")
)


# ---------- Schema ----------

# 3-level relevance scale (matches existing bench/v01 rubric)
RELEVANCE_LABELS = {
    0: "irrelevant",
    1: "marginal",
    2: "relevant",
}
# Inverse for validation / display
RELEVANCE_NAMES = RELEVANCE_LABELS  # alias

SCHEMA = """
CREATE TABLE IF NOT EXISTS judgements (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    query        TEXT    NOT NULL,
    paper_key    TEXT    NOT NULL,
    paper_title  TEXT,
    relevance    INTEGER NOT NULL CHECK (relevance IN (0, 1, 2)),
    reason       TEXT,
    source       TEXT    NOT NULL DEFAULT 'manual',
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(query, paper_key)
);
CREATE INDEX IF NOT EXISTS idx_judgements_query ON judgements(query);
CREATE INDEX IF NOT EXISTS idx_judgements_paper ON judgements(paper_key);
CREATE INDEX IF NOT EXISTS idx_judgements_rel   ON judgements(relevance);
"""


@contextmanager
def _connect(db_path: Path = None) -> Iterator[sqlite3.Connection]:
    """Context manager: yields sqlite3 connection, auto-commits, closes."""
    db_path = Path(db_path or DEFAULT_DB)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)
        conn.commit()
        yield conn
        conn.commit()
    finally:
        conn.close()


# ---------- Core operations ----------

def add(
    query: str,
    paper_key: str,
    relevance: int,
    paper_title: Optional[str] = None,
    reason: Optional[str] = None,
    source: str = "manual",
    db_path: Optional[Path] = None,
    overwrite: bool = True,
) -> int:
    """Add or update a single judgement. Returns the row id.

    Args:
        query: query string or query_id (e.g. "AI literacy" or "q001")
        paper_key: paper identifier (DOI, bibtex key, or OpenAlex ID)
        relevance: 0=irrelevant, 1=marginal, 2=relevant
        paper_title: optional human-readable title for display
        reason: optional annotation
        source: 'manual' | 'bulk-bibtex' | 'mavis-auto' | 'import'
        db_path: override DEFAULT_DB
        overwrite: if True, update existing (query, paper_key) row; else raise
    """
    if relevance not in RELEVANCE_LABELS:
        raise ValueError(
            f"relevance must be 0/1/2 (irrelevant/marginal/relevant), got {relevance!r}"
        )
    if not query or not query.strip():
        raise ValueError("query must be non-empty")
    if not paper_key or not paper_key.strip():
        raise ValueError("paper_key must be non-empty")

    with _connect(db_path) as conn:
        cur = conn.execute(
            "SELECT id FROM judgements WHERE query = ? AND paper_key = ?",
            (query.strip(), paper_key.strip()),
        )
        existing = cur.fetchone()
        if existing and not overwrite:
            raise ValueError(
                f"Judgement already exists for ({query!r}, {paper_key!r}); "
                f"pass overwrite=True to update"
            )
        if existing:
            conn.execute(
                """UPDATE judgements
                   SET relevance = ?, paper_title = ?, reason = ?,
                       source = ?, updated_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (relevance, paper_title, reason, source, existing["id"]),
            )
            return existing["id"]
        cur = conn.execute(
            """INSERT INTO judgements
               (query, paper_key, paper_title, relevance, reason, source)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (query.strip(), paper_key.strip(), paper_title,
             relevance, reason, source),
        )
        return cur.lastrowid


def add_bulk(
    query: str,
    items: List[Tuple[str, Optional[str], int, Optional[str]]],
    source: str = "bulk-bibtex",
    db_path: Optional[Path] = None,
) -> Tuple[int, int, int]:
    """Bulk add judgements. Each item is (paper_key, paper_title, relevance, reason).

    Returns (n_added, n_updated, n_skipped).
    """
    n_added = n_updated = n_skipped = 0
    with _connect(db_path) as conn:
        for paper_key, paper_title, relevance, reason in items:
            try:
                cur = conn.execute(
                    "SELECT id FROM judgements WHERE query = ? AND paper_key = ?",
                    (query.strip(), paper_key.strip()),
                )
                existing = cur.fetchone()
                if existing:
                    conn.execute(
                        """UPDATE judgements
                           SET relevance = ?, paper_title = ?, reason = ?,
                               source = ?, updated_at = CURRENT_TIMESTAMP
                           WHERE id = ?""",
                        (relevance, paper_title, reason, source, existing["id"]),
                    )
                    n_updated += 1
                else:
                    conn.execute(
                        """INSERT INTO judgements
                           (query, paper_key, paper_title, relevance, reason, source)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (query.strip(), paper_key.strip(), paper_title,
                         relevance, reason, source),
                    )
                    n_added += 1
            except sqlite3.Error as e:
                n_skipped += 1
                print(f"[pa judge] skip {paper_key!r}: {e}", file=sys.stderr)
    return n_added, n_updated, n_skipped


def list_judgements(
    query: Optional[str] = None,
    relevance: Optional[int] = None,
    limit: int = 200,
    db_path: Optional[Path] = None,
) -> List[sqlite3.Row]:
    """List judgements, optionally filtered by query and/or relevance."""
    with _connect(db_path) as conn:
        sql = "SELECT * FROM judgements WHERE 1=1"
        params: list = []
        if query:
            sql += " AND query = ?"
            params.append(query)
        if relevance is not None:
            sql += " AND relevance = ?"
            params.append(relevance)
        sql += " ORDER BY updated_at DESC, id DESC LIMIT ?"
        params.append(limit)
        return list(conn.execute(sql, params))


def stats(
    query: Optional[str] = None, db_path: Optional[Path] = None
) -> dict:
    """Return aggregate counts.

    Returns:
        {
            "n_total": int,
            "n_irrelevant": int,
            "n_marginal": int,
            "n_relevant": int,
            "n_queries": int,
            "queries": [(query, n), ...] sorted by n desc, top 20,
        }
    """
    with _connect(db_path) as conn:
        if query:
            row = conn.execute(
                """SELECT
                     COUNT(*) AS n_total,
                     SUM(CASE WHEN relevance = 0 THEN 1 ELSE 0 END) AS n_irrelevant,
                     SUM(CASE WHEN relevance = 1 THEN 1 ELSE 0 END) AS n_marginal,
                     SUM(CASE WHEN relevance = 2 THEN 1 ELSE 0 END) AS n_relevant
                   FROM judgements WHERE query = ?""",
                (query,),
            ).fetchone()
            return {
                "n_total": row["n_total"] or 0,
                "n_irrelevant": row["n_irrelevant"] or 0,
                "n_marginal": row["n_marginal"] or 0,
                "n_relevant": row["n_relevant"] or 0,
                "n_queries": 1,
                "queries": [(query, row["n_total"] or 0)],
            }
        # All queries
        rows = conn.execute(
            """SELECT query,
                     COUNT(*) AS n,
                     SUM(CASE WHEN relevance = 0 THEN 1 ELSE 0 END) AS n0,
                     SUM(CASE WHEN relevance = 1 THEN 1 ELSE 0 END) AS n1,
                     SUM(CASE WHEN relevance = 2 THEN 1 ELSE 0 END) AS n2
               FROM judgements
               GROUP BY query
               ORDER BY n DESC"""
        ).fetchall()
        n_total = sum(r["n"] for r in rows)
        return {
            "n_total": n_total,
            "n_irrelevant": sum(r["n0"] or 0 for r in rows),
            "n_marginal": sum(r["n1"] or 0 for r in rows),
            "n_relevant": sum(r["n2"] or 0 for r in rows),
            "n_queries": len(rows),
            "queries": [(r["query"], r["n"]) for r in rows[:20]],
        }


# ---------- Import / Export ----------

def export_jsonl(
    output_path: Path, db_path: Optional[Path] = None
) -> int:
    """Export all judgements to JSONL (one judgement per line). Returns n_rows."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with _connect(db_path) as conn, open(output_path, "w", encoding="utf-8") as f:
        for row in conn.execute("SELECT * FROM judgements ORDER BY id"):
            d = dict(row)
            d["relevance_name"] = RELEVANCE_LABELS.get(d["relevance"], "?")
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
            n += 1
    return n


def export_bench_format(
    output_path: Path, db_path: Optional[Path] = None
) -> int:
    """Export in the bench/v01/labels.json format (query-keyed, {key: {label, reason}}).

    Useful for compatibility with the existing LTR pipeline that reads
    bench/v01/labels.json.

    Returns the number of queries exported.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(db_path) as conn:
        # Group by query, preserving relevance+reason
        out = {
            "_meta": {
                "version": "exported-from-sqlite",
                "labeled_by": "various (see source column)",
                "method": "Exported from pa judge SQLite DB",
                "rubric": (
                    "0=irrelevant (off-topic, or wrong level+topic); "
                    "1=marginal (topic adjacent OR level wrong OR scope right but topic wrong); "
                    "2=relevant (matches query topic + level + scope)"
                ),
                "queries_covered": [],
            },
            "labels": {},
        }
        for row in conn.execute(
            "SELECT query, paper_key, relevance, reason, source, updated_at "
            "FROM judgements ORDER BY query, id"
        ):
            q = row["query"]
            if q not in out["labels"]:
                out["labels"][q] = {}
                out["_meta"]["queries_covered"].append(q)
            out["labels"][q][row["paper_key"]] = {
                "label": row["relevance"],
                "reason": row["reason"] or f"source={row['source']}",
            }
        output_path.write_text(
            json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return len(out["_meta"]["queries_covered"])


def import_bench_format(
    input_path: Path,
    db_path: Optional[Path] = None,
    default_source: str = "import",
) -> Tuple[int, int, int]:
    """Import from bench/v01/labels.json format.

    Returns (n_added, n_updated, n_skipped).
    """
    input_path = Path(input_path)
    data = json.loads(input_path.read_text(encoding="utf-8"))
    labels = data.get("labels", {})
    n_added = n_updated = n_skipped = 0
    with _connect(db_path) as conn:
        for query, papers in labels.items():
            items = []
            for paper_key, info in papers.items():
                rel = info.get("label")
                reason = info.get("reason", "")
                if rel not in RELEVANCE_LABELS:
                    n_skipped += 1
                    continue
                items.append((paper_key, None, rel, reason))
            n_a, n_u, n_s = _add_items_bulk(conn, query, items, default_source)
            n_added += n_a
            n_updated += n_u
            n_skipped += n_s
    return n_added, n_updated, n_skipped


def _add_items_bulk(
    conn: sqlite3.Connection,
    query: str,
    items: List[Tuple[str, Optional[str], int, Optional[str]]],
    source: str,
) -> Tuple[int, int, int]:
    """Internal bulk-add helper that uses an existing connection."""
    n_added = n_updated = n_skipped = 0
    for paper_key, paper_title, relevance, reason in items:
        try:
            cur = conn.execute(
                "SELECT id FROM judgements WHERE query = ? AND paper_key = ?",
                (query.strip(), paper_key.strip()),
            )
            existing = cur.fetchone()
            if existing:
                conn.execute(
                    """UPDATE judgements
                       SET relevance = ?, paper_title = ?, reason = ?,
                           source = ?, updated_at = CURRENT_TIMESTAMP
                       WHERE id = ?""",
                    (relevance, paper_title, reason, source, existing["id"]),
                )
                n_updated += 1
            else:
                conn.execute(
                    """INSERT INTO judgements
                       (query, paper_key, paper_title, relevance, reason, source)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (query.strip(), paper_key.strip(), paper_title,
                     relevance, reason, source),
                )
                n_added += 1
        except sqlite3.Error:
            n_skipped += 1
    return n_added, n_updated, n_skipped
