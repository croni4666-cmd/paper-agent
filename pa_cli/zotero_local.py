"""pa_cli.zotero_local - Read-only Zotero local SQLite utilities (v3.9.14.0).

Implements [P2-16] pa zotero check (read-only, no API key, no network).

Use case: after `pa fetch-pdf-batch` returns N papers, check which DOIs
are already in the user's Zotero library to avoid re-reading PDFs and
to prioritize new papers in the lit review.

**Design constraints (per留痕 / AGPL discipline)**:
- Read-only access: SQLite opened in `mode=ro` URI mode, writes are
  impossible even by accident
- No API key, no network, no cloud: only reads local zotero.sqlite
- No persistent state in paper-agent: each call is independent
- Path auto-detection for macOS / Linux / Windows

**Zotero 6+ schema** (from `~/Zotero/zotero.sqlite`):
- `items(itemID, itemTypeID, key)` — one row per Zotero item
- `itemData(itemID, fieldID, valueID)` — links items to values
- `itemDataValues(valueID, value)` — actual value strings
- `fields(fieldID, fieldName)` — DOI is field 1 (constant across versions)

Public API:
    find_zotero_db() -> Optional[Path]
        Auto-detect Zotero local DB path. None if not installed.
    get_library_dois(db_path=None) -> set[str]
        Return the set of normalized DOIs in user's Zotero library.
    check_corpus(corpus_dois, library_dois=None) -> dict
        Compare corpus DOIs against library. Returns 4-bucket result.
    normalize_doi(s) -> Optional[str]
        Strip doi.org URL prefix, lowercase, validate shape.

Zotero is a registered trademark of the Corporation for Digital Scholarship.
This module is not affiliated with or endorsed by the Zotero project.
"""

from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set


# Field IDs in Zotero's `fields` table. DOI is fieldID=59 in Zotero 6+
# (verified 2026-08-18 against local install). We look it up by name at
# runtime so the code survives schema changes across Zotero versions.
_ZOTERO_DOI_FIELD_NAME = "doi"

# Item types to exclude from DOI extraction (we only want user-facing items,
# not notes / annotations / attachments). Looked up by name at runtime
# because Zotero 6 renumbered these (note was itemTypeID=1 in 2015 schema,
# now annotation=1, note=28, attachment=3).
_EXCLUDED_ITEM_TYPES = {"annotation", "attachment", "note"}

# DOI regex per Crossref recommended format: starts with 10., prefix/suffix
# separated by /.  Allow common URL prefixes.
_DOI_RE = re.compile(r"^10\.\d{4,9}/[^\s\"<>]+$", re.IGNORECASE)

# doi.org URL prefix patterns (case-insensitive)
_DOI_URL_PATTERNS = [
    re.compile(r"^https?://(?:dx\.)?doi\.org/", re.IGNORECASE),
    re.compile(r"^doi:\s*", re.IGNORECASE),
]

# Default search paths for Zotero local DB, in priority order.
# macOS / Linux: ~/Zotero/zotero.sqlite
# Windows: ~/Zotero/Profiles/<random>/zotero.sqlite (Firefox profile pattern)
_DEFAULT_DB_PATHS: List[Path] = [
    Path.home() / "Zotero" / "zotero.sqlite",                          # macOS / Linux
    Path.home() / "Zotero" / "Profiles" / "default" / "zotero.sqlite",  # Win typical
    Path.home() / "Zotero" / "Profiles" / "Default" / "zotero.sqlite",  # Win variant
]


# ─────────────────────────────────────────────────────────────────
# Path auto-detection
# ─────────────────────────────────────────────────────────────────
def find_zotero_db(env_var: str = "ZOTERO_LOCAL_DB") -> Optional[Path]:
    """Auto-detect Zotero local SQLite DB. Returns None if not found.

    Search order:
        1. Environment variable override ($ZOTERO_LOCAL_DB)
        2. macOS / Linux: ~/Zotero/zotero.sqlite
        3. Windows: ~/Zotero/Profiles/*/zotero.sqlite (first match)
        4. $HOME/Zotero/zotero.sqlite (fallback for custom install)

    **Read-only probe**: this function only checks `Path.exists()` and
    does not open the DB. The actual open happens in `get_library_dois()`.
    """
    # 1. Env var override
    env_path = os.environ.get(env_var, "").strip()
    if env_path:
        p = Path(env_path)
        if p.exists() and p.is_file():
            return p
        return None  # explicit override that doesn't exist — don't fall through

    # 2-3. Default paths
    for p in _DEFAULT_DB_PATHS:
        if p.exists() and p.is_file():
            return p

    # 4. Windows Profile glob fallback (in case profile name is non-default)
    win_glob = Path.home() / "Zotero" / "Profiles"
    if win_glob.exists() and win_glob.is_dir():
        for p in win_glob.glob("*/zotero.sqlite"):
            if p.is_file():
                return p

    return None


# ─────────────────────────────────────────────────────────────────
# DOI normalization
# ─────────────────────────────────────────────────────────────────
def normalize_doi(raw: Optional[str]) -> Optional[str]:
    """Normalize a DOI string to canonical form (10.PREFIX/SUFFIX lowercase).

    Returns None if input is empty, malformed, or unparseable.

    Handles:
        - `10.1234/foo.bar` (raw DOI) → `10.1234/foo.bar`
        - `https://doi.org/10.1234/foo.bar` → `10.1234/foo.bar`
        - `http://dx.doi.org/10.1234/foo.bar` → `10.1234/foo.bar`
        - `doi:10.1234/foo.bar` → `10.1234/foo.bar`
        - `DOI: 10.1234/foo.bar` (whitespace) → `10.1234/foo.bar`

    Trims trailing punctuation: `.` `,` `;` (common in Bibtex entries)
    Lowercases (DOIs are case-insensitive per Crossref)
    """
    if not raw:
        return None
    s = str(raw).strip()
    if not s:
        return None

    # Strip URL prefixes
    for pat in _DOI_URL_PATTERNS:
        s = pat.sub("", s)
    s = s.strip()

    # Trim trailing punctuation that's usually not part of the DOI itself
    s = s.rstrip(".,;")
    s = s.strip()

    if not s:
        return None
    s = s.lower()
    if not _DOI_RE.match(s):
        return None
    return s


# ─────────────────────────────────────────────────────────────────
# Library DOI extraction
# ─────────────────────────────────────────────────────────────────
def _lookup_field_id(conn, field_name: str) -> Optional[int]:
    """Return the fieldID for a given field name (case-insensitive).

    Returns None if the field doesn't exist. Looks up at runtime so we
    survive Zotero schema changes (DOI was fieldID=1 in old schema, 59 in Zotero 6+).
    """
    cur = conn.cursor()
    cur.execute(
        "SELECT fieldID FROM fields WHERE LOWER(fieldName) = LOWER(?)",
        (field_name,),
    )
    row = cur.fetchone()
    return row[0] if row else None


def _lookup_excluded_item_type_ids(conn) -> List[int]:
    """Return itemTypeIDs for item types we want to exclude (note, attachment, annotation).

    Looked up by name (case-insensitive). Zotero 6 changed the numbering
    (annotation=1, note=28, attachment=3) vs older schemas.
    """
    cur = conn.cursor()
    placeholders = ",".join("?" for _ in _EXCLUDED_ITEM_TYPES)
    cur.execute(
        f"SELECT itemTypeID FROM itemTypes WHERE LOWER(typeName) IN ({placeholders})",
        tuple(t.lower() for t in _EXCLUDED_ITEM_TYPES),
    )
    return [row[0] for row in cur.fetchall()]


def get_library_dois(db_path: Optional[Path] = None) -> Set[str]:
    """Read Zotero's local SQLite DB, return set of normalized DOIs.

    **Read-only**: DB is opened with `mode=ro` URI, writes are impossible.
    Safe to call while Zotero is running.

    **Schema** (Zotero 6+, also works with older schemas since we look up
    field/itemType IDs by name at runtime):
        items JOIN itemData JOIN itemDataValues WHERE fieldID=(doi-field-id)
        Returns the `value` column for each match, then normalize.

    Returns empty set if:
        - DB not found (db_path is None)
        - DB exists but has no DOI entries
        - DB schema doesn't have a DOI field (very old Zotero, corrupted, etc.)
    """
    if db_path is None:
        db_path = find_zotero_db()
    if db_path is None or not db_path.exists():
        return set()

    # Open read-only via URI (SQLite OPEN_READONLY flag).
    # This is a hard guarantee: no writes possible even on bug.
    uri = f"file:{db_path}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True, timeout=5)
        try:
            cur = conn.cursor()
            # 1. Look up DOI field ID by name (case-insensitive)
            doi_field_id = _lookup_field_id(conn, _ZOTERO_DOI_FIELD_NAME)
            if doi_field_id is None:
                return set()  # No DOI field in schema

            # 2. Look up excluded item type IDs (note/annotation/attachment)
            excluded_ids = _lookup_excluded_item_type_ids(conn)

            # 3. Build the query
            if excluded_ids:
                placeholders = ",".join("?" for _ in excluded_ids)
                query = f"""
                    SELECT DISTINCT idv.value
                    FROM items i
                    JOIN itemData id ON id.itemID = i.itemID
                    JOIN itemDataValues idv ON idv.valueID = id.valueID
                    WHERE id.fieldID = ?
                      AND i.itemTypeID NOT IN ({placeholders})
                """
                params: tuple = (doi_field_id,) + tuple(excluded_ids)
            else:
                query = """
                    SELECT DISTINCT idv.value
                    FROM items i
                    JOIN itemData id ON id.itemID = i.itemID
                    JOIN itemDataValues idv ON idv.valueID = id.valueID
                    WHERE id.fieldID = ?
                """
                params = (doi_field_id,)

            cur.execute(query, params)
            dois: Set[str] = set()
            for (raw,) in cur:
                n = normalize_doi(raw)
                if n:
                    dois.add(n)
            return dois
        finally:
            conn.close()
    except sqlite3.Error:
        # Schema mismatch, corrupted DB, locked, etc.
        # Returning empty set is the right behavior — caller treats as
        # "library has no DOIs" and proceeds with not_in_library=N.
        return set()


# ─────────────────────────────────────────────────────────────────
# Corpus checking
# ─────────────────────────────────────────────────────────────────
def check_corpus(
    corpus_dois: Iterable[str],
    library_dois: Optional[Set[str]] = None,
    db_path: Optional[Path] = None,
) -> Dict[str, List[str]]:
    """Compare corpus DOIs against Zotero library. Returns 4 buckets.

    Returns dict with keys:
        - in_library: list of normalized DOIs that exist in library
        - not_in_library: list of normalized DOIs that don't exist
        - invalid_doi: list of raw inputs that couldn't be normalized
        - duplicates_in_corpus: list of normalized DOIs that appear >1x
                               in the corpus (after normalization)

    Args:
        corpus_dois: iterable of DOI strings (raw, mixed format OK)
        library_dois: optional pre-loaded set (skip DB read if provided)
        db_path: optional explicit DB path (else auto-detect)
    """
    if library_dois is None:
        library_dois = get_library_dois(db_path=db_path)

    in_library: List[str] = []
    not_in_library: List[str] = []
    invalid_doi: List[str] = []
    seen: Dict[str, int] = {}  # normalized_doi → count for dup detection

    for raw in corpus_dois:
        norm = normalize_doi(raw)
        if norm is None:
            invalid_doi.append(raw)
            continue
        seen[norm] = seen.get(norm, 0) + 1
        if norm in library_dois:
            in_library.append(norm)
        else:
            not_in_library.append(norm)

    # Dedupe the in/out lists (same DOI may appear multiple times in corpus)
    in_library = sorted(set(in_library))
    not_in_library = sorted(set(not_in_library))
    duplicates_in_corpus = sorted(d for d, c in seen.items() if c > 1)

    return {
        "in_library": in_library,
        "not_in_library": not_in_library,
        "invalid_doi": invalid_doi,
        "duplicates_in_corpus": duplicates_in_corpus,
    }


# ─────────────────────────────────────────────────────────────────
# Bibtex parsing
# ─────────────────────────────────────────────────────────────────
def extract_dois_from_bibtex(bibtex_path: Path) -> List[str]:
    """Extract DOI field from a Bibtex file. Returns list of raw DOI strings.

    Uses simple regex on `doi = {...}` and `doi = "..."` lines.
    Handles Bibtex entries with `doi`, `DOI`, `Doi` (case-insensitive).
    Handles values wrapped in `{}` or `"..."` (with optional leading
    `https://doi.org/` prefix).

    Note: This is a deliberately minimal Bibtex parser — it does NOT
    handle nested braces, comments, or `@string` macros. Zotero's CSV
    export + manual import is the more robust path; this is just for
    the `pa zotero check --corpus refs.bib` convenience.
    """
    if not bibtex_path.exists() or not bibtex_path.is_file():
        return []
    text = bibtex_path.read_text(encoding="utf-8", errors="replace")
    # Match: doi\s*=\s*[{"]([^}"]+)[}"]
    # Captures group 1 = the value (anything until the closing brace or quote)
    pattern = re.compile(r"doi\s*=\s*[\{\"]\s*([^\}\"]+?)\s*[\}\"]", re.IGNORECASE)
    return [m.group(1) for m in pattern.finditer(text)]
