"""Global Sample Pool -- user-owned, Mavis-read-only, training-isolated.

Canonical doc: ~/.paper-agent/sample_pool/README.md (cross-platform)
Reference: paper-agent [P3-26] v02 Global Sample Pool (added 2026-08-03)

Three iron rules (enforced at API level):
  1. User-only write: add / label / deprecate require explicit user confirmation
  2. Mavis read-only: list / get / stats / count / query / export work for any session
  3. Training-isolated: export writes to OUT path, pool.sqlite is never mutated
                       by training scripts (they must re-export every time)

This module exposes the cmd_* functions for use from cli.py. The CLI
subcommands are defined in cli.py (sample_pool_cmd group).

Read paths (any Mavis session may call):
  - cmd_list / cmd_get / cmd_stats / cmd_count / cmd_query / cmd_export

Write paths (require explicit user confirmation, e.g. terminal y/n):
  - cmd_add / cmd_label / cmd_deprecate

Propose path (Mavis may call, no write):
  - cmd_suggest
"""

import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ----- Constants -----

# Default location: ~/.paper-agent/sample_pool/ (cross-Mavis-session, NOT in git)
POOL_DIR = Path.home() / ".paper-agent" / "sample_pool"
POOL_DB = POOL_DIR / "pool.sqlite"
SCHEMA_SQL = POOL_DIR / "schema.sql"
README = POOL_DIR / "README.md"
EXAMPLE = POOL_DIR / "example_entry.json"
AUDIT_LOG = POOL_DIR / "audit.log"  # flat file (DB audit_log is in-DB)

ALLOWED_DOMAINS = ("econ", "cs_ai", "medical", "legal", "social", "other")
ALLOWED_DIFFICULTY = ("easy", "medium", "hard")
ALLOWED_LABEL = (0, 1, 2, 3)
ALLOWED_SOURCE = (
    "manual-pa-search",
    "manual-pa-citations",
    "manual-pa-judge",
    "manual-other",
)
ALLOWED_EXPORT_FORMATS = ("ltr", "moe", "cross-encoder", "json")
LABEL_LEGEND = {
    0: "irrelevant (not relevant at all)",
    1: "marginal (peripheral mention)",
    2: "relevant (substantively addresses query)",
    3: "highly relevant (directly answers query)",
}


# ----- Connection helpers -----


def get_connection(readonly: bool = True) -> sqlite3.Connection:
    """Open SQLite connection. readonly=True uses immutable mode.

    Raises FileNotFoundError if pool.sqlite does not exist.
    """
    if not POOL_DB.exists():
        raise FileNotFoundError(
            f"Pool not found: {POOL_DB}\n"
            f"Run `pa sample-pool init` first to create schema."
        )
    if readonly:
        # SQLite URI: mode=ro is read-only
        uri = f"file:{POOL_DB.as_posix()}?mode=ro"
        return sqlite3.connect(uri, uri=True)
    return sqlite3.connect(POOL_DB)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ----- Init / verification -----


def cmd_init(force: bool = False) -> Dict[str, Any]:
    """Initialize pool.sqlite from schema.sql. Idempotent unless force=True.

    On existing DB, also runs any pending migrations (e.g. v1 -> v2 for nullable label).
    """
    POOL_DIR.mkdir(parents=True, exist_ok=True)
    if POOL_DB.exists() and not force:
        # Run any pending migrations
        mig = cmd_migrate()
        return {"status": "exists", "path": str(POOL_DB), "migrations": mig}
    if not SCHEMA_SQL.exists():
        raise FileNotFoundError(f"schema.sql not found at {SCHEMA_SQL}")
    schema_sql = SCHEMA_SQL.read_text(encoding="utf-8")
    conn = sqlite3.connect(POOL_DB)
    try:
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()
    return {"status": "created", "path": str(POOL_DB)}


def cmd_migrate() -> List[str]:
    """Run pending schema migrations. Returns list of applied migrations.

    Migrations are version-tracked in the `schema_version` table. Each migration
    is keyed by a version string (v1, v2, ...). When pool.sqlite exists with
    older versions, this runs the upgrade.

    v1 -> v2: Make relevance_labels.label nullable. SQLite cannot ALTER NOT NULL,
              so we drop and recreate the table. pool_entries is preserved.
              Any pre-existing labels are LOST (acceptable because pool is still
              in cold start; this migration runs once at v3.9.11.4).
    """
    if not POOL_DB.exists():
        return []
    applied: List[str] = []
    conn = sqlite3.connect(POOL_DB)
    try:
        # What versions are present?
        cur = conn.execute("SELECT version FROM schema_version ORDER BY version")
        have = {r[0] for r in cur.fetchall()}
        if "v2" not in have and "v1" in have:
            # v1 -> v2 migration
            # Save existing labels (if any), drop, recreate, reinsert with NULL allowed
            existing_labels = conn.execute(
                "SELECT qid, candidate_key, rank, label, labeled_at, labeled_by, notes "
                "FROM relevance_labels"
            ).fetchall()
            conn.execute("DROP TABLE IF EXISTS relevance_labels")
            # Recreate with v2 schema (nullable label, labeled_at, labeled_by)
            conn.executescript("""
                CREATE TABLE relevance_labels (
                  qid             TEXT NOT NULL,
                  candidate_key   TEXT NOT NULL,
                  rank            INTEGER NOT NULL CHECK (rank > 0 AND rank <= 50),
                  label           INTEGER CHECK (label IS NULL OR label IN (0, 1, 2, 3)),
                  labeled_at      TEXT,
                  labeled_by      TEXT CHECK (labeled_by IS NULL OR labeled_by IN ('user', 'mavis-suggested')),
                  notes           TEXT,
                  PRIMARY KEY (qid, candidate_key),
                  FOREIGN KEY (qid) REFERENCES pool_entries(qid) ON DELETE RESTRICT
                );
                CREATE INDEX idx_labels_qid ON relevance_labels(qid);
                CREATE INDEX idx_labels_label ON relevance_labels(label);
                CREATE INDEX idx_labels_unlabeled ON relevance_labels(qid) WHERE label IS NULL;
            """)
            # Reinsert existing labels (preserve data, even if label is set)
            for r in existing_labels:
                conn.execute(
                    "INSERT INTO relevance_labels "
                    "(qid, candidate_key, rank, label, labeled_at, labeled_by, notes) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    r,
                )
            n_lost_unlabeled = sum(1 for r in existing_labels if r[3] is None)
            # Mark v2 as applied
            conn.execute(
                "INSERT OR IGNORE INTO schema_version (version, applied_at, notes) "
                "VALUES (?, ?, ?)",
                (
                    "v2",
                    now_iso(),
                    f"Made label nullable. preserved={len(existing_labels)} labels, "
                    f"of which {n_lost_unlabeled} were NULL (acceptable; "
                    f"re-label via `pa sample-pool label` if needed)",
                ),
            )
            conn.commit()
            applied.append("v1->v2 (relevance_labels.label nullable)")
    finally:
        conn.close()
    return applied


def cmd_verify() -> Dict[str, Any]:
    """Verify pool integrity: schema version, tables present, gate status sane."""
    conn = get_connection(readonly=True)
    try:
        out: Dict[str, Any] = {"pool_db": str(POOL_DB), "exists": True}
        # schema version
        rows = conn.execute("SELECT version, applied_at, notes FROM schema_version").fetchall()
        out["schema_versions"] = [
            {"version": r[0], "applied_at": r[1], "notes": r[2]} for r in rows
        ]
        # tables present
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view') ORDER BY type, name"
        ).fetchall()
        out["objects"] = [r[0] for r in rows]
        # row counts
        out["n_entries_total"] = conn.execute(
            "SELECT COUNT(*) FROM pool_entries"
        ).fetchone()[0]
        out["n_entries_active"] = conn.execute(
            "SELECT COUNT(*) FROM v_active_entries"
        ).fetchone()[0]
        out["n_labels"] = conn.execute("SELECT COUNT(*) FROM relevance_labels").fetchone()[0]
        return out
    finally:
        conn.close()


# ----- Read paths (Mavis may call) -----


def cmd_list(
    domain: Optional[str] = None,
    project: Optional[str] = None,
    difficulty: Optional[str] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """List active entries with optional filters."""
    conn = get_connection(readonly=True)
    try:
        q = (
            "SELECT qid, query, domain, difficulty, project, n_candidates, "
            "added_at, source FROM v_active_entries WHERE 1=1"
        )
        params: List[Any] = []
        if domain:
            q += " AND domain = ?"
            params.append(domain)
        if project:
            q += " AND project = ?"
            params.append(project)
        if difficulty:
            q += " AND difficulty = ?"
            params.append(difficulty)
        q += " ORDER BY added_at DESC LIMIT ?"
        params.append(limit)
        cols = ["qid", "query", "domain", "difficulty", "project", "n_candidates", "added_at", "source"]
        rows = conn.execute(q, params).fetchall()
        return [dict(zip(cols, r)) for r in rows]
    finally:
        conn.close()


def cmd_get(qid: str) -> Optional[Dict[str, Any]]:
    """Get full entry (including all labels). Returns None if not found or deprecated."""
    conn = get_connection(readonly=True)
    try:
        row = conn.execute(
            "SELECT * FROM v_active_entries WHERE qid = ?", (qid,)
        ).fetchone()
        if not row:
            return None
        cols = [d[0] for d in conn.execute("SELECT * FROM pool_entries").description]
        # Only include columns that exist in pool_entries (views select subset)
        full_cols = [d[0] for d in conn.execute("SELECT * FROM pool_entries WHERE qid = ?", (qid,)).description]
        full_row = conn.execute("SELECT * FROM pool_entries WHERE qid = ?", (qid,)).fetchone()
        entry = dict(zip(full_cols, full_row))
        # filter out deprecated
        label_rows = conn.execute(
            "SELECT * FROM relevance_labels WHERE qid = ? ORDER BY rank", (qid,)
        ).fetchall()
        lcols = [d[0] for d in conn.execute("SELECT * FROM relevance_labels").description]
        entry["labels"] = [dict(zip(lcols, lr)) for lr in label_rows]
        # summary
        n_labeled = sum(1 for l in entry["labels"] if l.get("label") is not None)
        entry["n_labeled"] = n_labeled
        entry["n_unlabeled"] = entry.get("n_candidates", 0) - n_labeled
        return entry
    finally:
        conn.close()


def cmd_stats() -> Dict[str, Any]:
    """Aggregate stats + gate status."""
    conn = get_connection(readonly=True)
    try:
        stats: Dict[str, Any] = {}
        # pool summary (v_pool_stats has fixed columns: n_entries, n_labels_total, n_label_0..3)
        row = conn.execute("SELECT * FROM v_pool_stats").fetchone()
        if row is None:
            # pool is empty / no entries
            stats["pool"] = {
                "n_entries": 0, "n_labels_total": 0,
                "n_label_0": 0, "n_label_1": 0, "n_label_2": 0, "n_label_3": 0,
            }
        else:
            cols = [d[0] for d in conn.execute("SELECT * FROM v_pool_stats").description]
            stats["pool"] = {k: (0 if v is None else v) for k, v in zip(cols, row)}
        # by domain
        rows = conn.execute("SELECT domain, n_entries, n_labels FROM v_by_domain").fetchall()
        stats["by_domain"] = {r[0]: {"n_entries": r[1], "n_labels": r[2]} for r in rows}
        # by project
        rows = conn.execute("SELECT project, n_entries, n_labels FROM v_by_project").fetchall()
        stats["by_project"] = {r[0]: {"n_entries": r[1], "n_labels": r[2]} for r in rows}
        # by difficulty
        rows = conn.execute("SELECT difficulty, n_entries FROM v_by_difficulty").fetchall()
        stats["by_difficulty"] = {r[0]: r[1] for r in rows}
        # gates
        rows = conn.execute(
            "SELECT gate_name, threshold_n, threshold_other, current_n, unlocked, unlocked_at "
            "FROM gate_status ORDER BY threshold_n"
        ).fetchall()
        stats["gates"] = [
            {
                "gate_name": r[0],
                "threshold_n": r[1],
                "threshold_other": r[2],
                "current_n": r[3],
                "unlocked": bool(r[4]),
                "unlocked_at": r[5],
            }
            for r in rows
        ]
        return stats
    finally:
        conn.close()


def cmd_count(by: str = "domain") -> List[Dict[str, Any]]:
    """Count entries grouped by dimension (domain|project|difficulty)."""
    if by not in ("domain", "project", "difficulty"):
        raise ValueError(f"by must be one of (domain, project, difficulty), got {by!r}")
    view = f"v_by_{by}"
    conn = get_connection(readonly=True)
    try:
        rows = conn.execute(f"SELECT * FROM {view}").fetchall()
        cols = [d[0] for d in conn.execute(f"SELECT * FROM {view}").description]
        return [dict(zip(cols, r)) for r in rows]
    finally:
        conn.close()


def cmd_query(sql: str, params: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
    """Run a SELECT/WITH query. Validates no DML/DDL keywords.

    Iron Rule 5.2 enforcement: even read paths must not allow INSERT/UPDATE/DELETE/etc.
    """
    sql_stripped = sql.strip().rstrip(";").strip()
    sql_lower = sql_stripped.lower()
    if not (sql_lower.startswith("select") or sql_lower.startswith("with")):
        raise ValueError(
            f"Only SELECT/WITH queries allowed. Got: {sql_stripped[:50]!r}..."
        )
    forbidden = (
        "insert", "update", "delete", "drop", "alter", "create", "replace",
        "attach", "detach", "vacuum", "pragma", "truncate",
    )
    for kw in forbidden:
        if re.search(r"\b" + kw + r"\b", sql_lower):
            raise ValueError(
                f"Query contains forbidden keyword: {kw!r}. "
                f"Read paths cannot modify pool. Use add/label/deprecate subcommands."
            )
    conn = get_connection(readonly=True)
    try:
        cur = conn.execute(sql_stripped, params or [])
        cols = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchall()
        return [dict(zip(cols, r)) for r in rows]
    finally:
        conn.close()


# ----- Validation helpers -----


def _validate_entry(entry: Dict[str, Any]) -> Optional[str]:
    """Validate entry dict. Returns error string or None."""
    required = ("qid", "query", "domain", "difficulty", "added_at",
                "added_by", "source", "n_candidates")
    for k in required:
        if k not in entry:
            return f"Missing required field: {k}"
    if entry["domain"] not in ALLOWED_DOMAINS:
        return f"domain must be one of {ALLOWED_DOMAINS}, got {entry['domain']!r}"
    if entry["difficulty"] not in ALLOWED_DIFFICULTY:
        return f"difficulty must be one of {ALLOWED_DIFFICULTY}, got {entry['difficulty']!r}"
    if entry["added_by"] not in ("user", "mavis-suggested"):
        return f"added_by must be 'user' or 'mavis-suggested', got {entry['added_by']!r}"
    if entry["source"] not in ALLOWED_SOURCE:
        return f"source must be one of {ALLOWED_SOURCE}, got {entry['source']!r}"
    n = entry["n_candidates"]
    if not isinstance(n, int) or n < 1 or n > 50:
        return f"n_candidates must be int 1-50, got {n!r}"
    # qid format: ASCII slug (per memory discipline)
    if not re.match(r"^[a-z0-9][a-z0-9\-]{1,62}$", entry["qid"]):
        return (
            f"qid must be ASCII slug (lowercase letters, digits, hyphens; "
            f"3-63 chars; start with letter/digit), got {entry['qid']!r}"
        )
    return None


# ----- Propose path (Mavis may call, no write) -----


def cmd_suggest(
    query: str,
    domain: str,
    difficulty: str,
    project: str = "global",
    notes: str = "",
    source: str = "manual-pa-search",
    n_candidates: int = 30,
    candidates: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Propose a new entry. Returns a dict (NOT written to pool).

    Used by Mavis to show user a preview before they run `pa sample-pool add`.
    Mavis may call this freely. The returned dict is for the user to review.
    """
    return {
        "qid": None,  # user must provide
        "query": query,
        "domain": domain,
        "difficulty": difficulty,
        "project": project,
        "notes": notes,
        "added_at": now_iso(),
        "added_by": "mavis-suggested",
        "source": source,
        "n_candidates": n_candidates,
        "candidates": candidates or [],
        "_hint": (
            "This is a SUGGESTION, not written to pool. "
            "Review fields above. To commit, run `pa sample-pool add` with these values "
            "(or save to a JSON file and use --from-file)."
        ),
    }


# ----- Write paths (require user confirmation) -----


def cmd_add(
    entry: Dict[str, Any],
    confirm: bool = False,
    session_id: str = "cli",
) -> Dict[str, Any]:
    """INSERT new entry. Iron Rule 5.1: requires confirm=True.

    Re-validates entry before writing. Writes in-DB audit log row.
    Returns {qid, status, n_candidates, n_labeled}.

    Raises PermissionError if confirm=False (Mavis cannot bypass).
    """
    if not confirm:
        raise PermissionError(
            "Mavis / script cannot directly add entries. "
            "Iron Rule 5.1: only user-written entries go in. "
            "Use the CLI's interactive prompt (no --confirm-y) or pass confirm=True "
            "from a user-invoked script."
        )
    err = _validate_entry(entry)
    if err:
        raise ValueError(f"Invalid entry: {err}")
    # 5.1: reject mavis-added entries unless user_approved explicitly set
    if entry.get("added_by") == "mavis-suggested" and not entry.get("user_approved"):
        raise PermissionError(
            "Entry added_by='mavis-suggested' but no user_approved flag. "
            "Mavis suggestions must be reviewed by user before INSERT."
        )
    conn = get_connection(readonly=False)
    try:
        existing = conn.execute(
            "SELECT 1 FROM pool_entries WHERE qid = ?", (entry["qid"],)
        ).fetchone()
        if existing:
            return {"qid": entry["qid"], "status": "exists", "action": "skipped"}
        # defaults
        project = entry.get("project") or "global"
        schema_version = entry.get("schema_version") or "v1"
        notes = entry.get("notes")
        cols = (
            "qid", "query", "domain", "difficulty", "project", "notes",
            "added_at", "added_by", "source", "n_candidates", "schema_version",
        )
        values = (
            entry["qid"], entry["query"], entry["domain"], entry["difficulty"],
            project, notes, entry["added_at"], entry["added_by"],
            entry["source"], entry["n_candidates"], schema_version,
        )
        conn.execute(
            f"INSERT INTO pool_entries ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
            values,
        )
        # Insert candidates with optional labels
        n_labeled = 0
        candidates = entry.get("candidates", [])
        for c in candidates:
            label = c.get("label")
            if label is not None and label not in ALLOWED_LABEL:
                raise ValueError(
                    f"candidate {c.get('candidate_key', '?')!r}: label must be one of "
                    f"{ALLOWED_LABEL}, got {label!r}"
                )
            rank = c.get("rank")
            if rank is None or not (1 <= rank <= 50):
                raise ValueError(
                    f"candidate {c.get('candidate_key', '?')!r}: rank must be 1-50, got {rank!r}"
                )
            labeled_at = c.get("labeled_at") or now_iso()
            labeled_by = c.get("labeled_by", "user")
            label_notes = c.get("label_notes") or c.get("notes")
            conn.execute(
                "INSERT OR REPLACE INTO relevance_labels "
                "(qid, candidate_key, rank, label, labeled_at, labeled_by, notes) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (entry["qid"], c["candidate_key"], rank, label, labeled_at, labeled_by, label_notes),
            )
            if label is not None:
                n_labeled += 1
        # update gate current_n
        n_total = conn.execute("SELECT COUNT(*) FROM v_active_entries").fetchone()[0]
        conn.execute(
            "UPDATE gate_status SET current_n = ? WHERE threshold_n <= ? AND unlocked = 0",
            (n_total, n_total),
        )
        # audit
        _audit_db(conn, "INSERT", entry["qid"], session_id, {
            "n_candidates": len(candidates),
            "n_labeled": n_labeled,
            "domain": entry["domain"],
            "project": project,
        })
        conn.commit()
        return {
            "qid": entry["qid"],
            "status": "inserted",
            "n_candidates": len(candidates),
            "n_labeled": n_labeled,
        }
    finally:
        conn.close()


def cmd_label(
    qid: str,
    candidate_key: str,
    label: int,
    notes: Optional[str] = None,
    confirm: bool = False,
    session_id: str = "cli",
) -> Dict[str, Any]:
    """Add or update a single relevance label. Iron Rule 5.1: requires confirm=True.

    Refuses if qid is deprecated. Refuses if candidate_key is not registered
    (use `pa sample-pool add` to register candidates first).
    """
    if not confirm:
        raise PermissionError(
            "Mavis / script cannot directly label. Iron Rule 5.1: user-only write. "
            "Use the CLI's interactive prompt or pass confirm=True."
        )
    if label not in ALLOWED_LABEL:
        raise ValueError(f"label must be one of {ALLOWED_LABEL}, got {label!r}")
    conn = get_connection(readonly=False)
    try:
        row = conn.execute(
            "SELECT deprecated FROM pool_entries WHERE qid = ?", (qid,)
        ).fetchone()
        if not row:
            raise ValueError(f"qid {qid!r} not found")
        if row[0]:
            raise ValueError(f"qid {qid!r} is deprecated, cannot label")
        existing = conn.execute(
            "SELECT 1 FROM relevance_labels WHERE qid = ? AND candidate_key = ?",
            (qid, candidate_key),
        ).fetchone()
        if not existing:
            raise ValueError(
                f"candidate_key {candidate_key!r} not registered under qid {qid!r}. "
                f"Use `pa sample-pool add` (or update the source entry) to register "
                f"this candidate first, then label it."
            )
        ts = now_iso()
        conn.execute(
            "UPDATE relevance_labels SET label = ?, labeled_at = ?, labeled_by = 'user', notes = ? "
            "WHERE qid = ? AND candidate_key = ?",
            (label, ts, notes, qid, candidate_key),
        )
        _audit_db(conn, "UPDATE", qid, session_id, {
            "candidate_key": candidate_key, "label": label,
        })
        conn.commit()
        return {"qid": qid, "candidate_key": candidate_key, "label": label, "op": "UPDATE"}
    finally:
        conn.close()


def cmd_deprecate(
    qid: str,
    reason: str,
    confirm: bool = False,
    session_id: str = "cli",
) -> Dict[str, Any]:
    """Mark entry as deprecated (NOT delete). Iron Rule 5.1: requires confirm=True."""
    if not confirm:
        raise PermissionError(
            "Mavis / script cannot directly deprecate. Iron Rule 5.1: user-only write. "
            "Use the CLI's interactive prompt or pass confirm=True."
        )
    if not reason or len(reason.strip()) < 3:
        raise ValueError("reason is required (min 3 chars)")
    conn = get_connection(readonly=False)
    try:
        ts = now_iso()
        cur = conn.execute(
            "UPDATE pool_entries SET deprecated = 1, deprecate_reason = ?, deprecated_at = ? "
            "WHERE qid = ?",
            (reason.strip(), ts, qid),
        )
        if cur.rowcount == 0:
            return {"qid": qid, "status": "not_found"}
        _audit_db(conn, "DEPRECATE", qid, session_id, {"reason": reason.strip()})
        conn.commit()
        return {"qid": qid, "status": "deprecated", "reason": reason.strip()}
    finally:
        conn.close()


# ----- Export (isolated working copy) -----


def cmd_export(
    format_name: str,
    out_path: str,
    min_n_labeled: int = 1,
    session_id: str = "cli",
) -> Dict[str, Any]:
    """Export pool to working/ in given format. Reads from pool (immutable).

    Iron Rule 5.3: writes only to out_path, never touches pool.sqlite.
    """
    if format_name not in ALLOWED_EXPORT_FORMATS:
        raise ValueError(
            f"format must be one of {ALLOWED_EXPORT_FORMATS}, got {format_name!r}"
        )
    out = Path(out_path)
    if not out.is_absolute():
        # Convention: relative paths go under bench/v02/working/ of paper-agent
        # (user can override with absolute path)
        out = (Path.cwd() / out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection(readonly=True)
    try:
        entries_rows = conn.execute(
            "SELECT qid, query, domain, difficulty, project, n_candidates, added_at, source "
            "FROM v_active_entries ORDER BY added_at"
        ).fetchall()
        cols = ["qid", "query", "domain", "difficulty", "project", "n_candidates", "added_at", "source"]
        export_data: List[Dict[str, Any]] = []
        for row in entries_rows:
            e = dict(zip(cols, row))
            labels = conn.execute(
                "SELECT candidate_key, rank, label, notes FROM relevance_labels "
                "WHERE qid = ? ORDER BY rank",
                (e["qid"],),
            ).fetchall()
            n_labeled = sum(1 for l in labels if l[2] is not None)
            if n_labeled < min_n_labeled:
                continue
            e["labels"] = [
                {"candidate_key": l[0], "rank": l[1], "label": l[2], "notes": l[3]}
                for l in labels
            ]
            e["n_labeled"] = n_labeled
            export_data.append(e)

        if format_name == "json":
            payload: Any = export_data
        elif format_name == "ltr":
            payload = {
                "_format": "ltr",
                "_note": "X / y / group are placeholders. Training script must extract features.",
                "n_entries": len(export_data),
                "queries": [
                    {
                        "qid": e["qid"],
                        "query": e["query"],
                        "domain": e["domain"],
                        "difficulty": e["difficulty"],
                        "candidates": [
                            {"candidate_key": l["candidate_key"], "rank": l["rank"], "label": l["label"]}
                            for l in e["labels"]
                        ],
                    }
                    for e in export_data
                ],
            }
        elif format_name == "moe":
            payload = {
                "_format": "moe",
                "_note": "Each query has candidates with engine-agnostic label. Training script maps to engine-specific features.",
                "n_entries": len(export_data),
                "queries": [
                    {
                        "qid": e["qid"],
                        "query": e["query"],
                        "domain": e["domain"],
                        "difficulty": e["difficulty"],
                        "candidates": e["labels"],
                    }
                    for e in export_data
                ],
            }
        elif format_name == "cross-encoder":
            payload = {
                "_format": "cross-encoder",
                "_note": "Flattened (query, candidate) pairs for fine-tuning. label 0/1/2/3.",
                "n_entries": len(export_data),
                "n_pairs": sum(len(e["labels"]) for e in export_data),
                "pairs": [
                    {
                        "qid": e["qid"],
                        "query": e["query"],
                        "domain": e["domain"],
                        "candidate_key": l["candidate_key"],
                        "rank": l["rank"],
                        "label": l["label"],
                    }
                    for e in export_data
                    for l in e["labels"]
                ],
            }

        out.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        # Note: EXPORT does NOT write to in-DB audit_log (pool is read-only here).
        # Only the flat audit.log file gets the entry, for cross-process visibility.
        _audit_flat(session_id, format_name, str(out), len(export_data))
        return {
            "format": format_name,
            "out": str(out),
            "n_entries": len(export_data),
            "min_n_labeled": min_n_labeled,
        }
    finally:
        conn.close()


# ----- Audit -----


def _audit_db(
    conn: sqlite3.Connection,
    op: str,
    target: Optional[str],
    session_id: str,
    details: Dict[str, Any],
) -> None:
    conn.execute(
        "INSERT INTO audit_log (ts, op, target, source_session, details) "
        "VALUES (?, ?, ?, ?, ?)",
        (now_iso(), op, target, session_id, json.dumps(details, ensure_ascii=False)),
    )


def _audit_flat(
    session_id: str,
    format_name: str,
    out_path: str,
    n_entries: int,
) -> None:
    """Append a line to flat audit.log (separate from in-DB log, for cross-process visibility)."""
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(
        {
            "ts": now_iso(),
            "op": "EXPORT",
            "target": None,
            "source_session": session_id,
            "details": {
                "format": format_name,
                "out": out_path,
                "n_entries": n_entries,
            },
        },
        ensure_ascii=False,
    )
    with AUDIT_LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def cmd_audit(limit: int = 50) -> List[Dict[str, Any]]:
    """Show recent audit log entries (read-only)."""
    conn = get_connection(readonly=True)
    try:
        rows = conn.execute(
            "SELECT ts, op, target, source_session, details FROM audit_log "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        cols = ["ts", "op", "target", "source_session", "details"]
        out = []
        for r in rows:
            d = dict(zip(cols, r))
            # parse details JSON
            try:
                d["details"] = json.loads(d["details"]) if d["details"] else {}
            except (json.JSONDecodeError, TypeError):
                pass
            out.append(d)
        return out
    finally:
        conn.close()
