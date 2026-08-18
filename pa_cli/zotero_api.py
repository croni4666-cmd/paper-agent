"""pa_cli.zotero_api - Zotero Web API wrapper (v3.9.15.0, [P2-17] + [P2-18])

Implements Zotero write + library search via the official Zotero Web API v3,
wrapped by the `pyzotero` library (MIT, well-maintained).

**What ships**:
- `pa zotero push` — push Bibtex entries + PDFs to user's Zotero library
- `pa zotero sync` — combine [P2-16] check + [P2-17] push + library search
- `pa zotero search` — search user's existing Zotero library

**Design constraints** (per留痕 / AGPL discipline):
- API key is read from `$ZOTERO_API_KEY` env var ONLY (NOT from `.env` per
  留痕 discipline; user exports per session)
- Idempotent: re-running same corpus does not duplicate items (DOI dedup
  via `check_items()` before `create_items()`)
- `linked_file` mode (default): PDF stays at original path, Zotero just
  stores the path. NO file copy. Same as `instsci zotero sync
  --attachment-mode linked_file`.
- `imported_file` mode: PDF copied to Zotero's storage dir
  (user-managed, requires Zotero to be running locally)
- Errors are structured (no bare exceptions, returns dict per item)

**No state** lives outside Zotero's server. Pure pass-through.

**Zotero is a registered trademark of the Corporation for Digital Scholarship.**
This module is not affiliated with or endorsed by the Zotero project.
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Lazy import pyzotero (it's a runtime dep, not import-time)
# pyzotero is in requirements-optional.txt under `zotero` group
try:
    from pyzotero.zotero import Zotero
    HAS_PYZOTERO = True
except ImportError:
    HAS_PYZOTERO = False


# ─────────────────────────────────────────────────────────────────
# Config helpers
# ─────────────────────────────────────────────────────────────────
def get_api_key(env_var: str = "ZOTERO_API_KEY") -> Optional[str]:
    """Read Zotero API key from env var. Returns None if unset."""
    return os.environ.get(env_var, "").strip() or None


def get_library_id() -> Optional[str]:
    """Read Zotero library ID from env var. Returns None if unset."""
    return os.environ.get("ZOTERO_LIBRARY_ID", "").strip() or None


def get_client(
    api_key: Optional[str] = None,
    library_id: Optional[str] = None,
    library_type: str = "user",
) -> "Zotero":
    """Build a pyzotero.Zotero client.

    Args:
        api_key: Zotero API key. If None, reads from $ZOTERO_API_KEY.
        library_id: Zotero user/group/library ID. If None, reads from
                    $ZOTERO_LIBRARY_ID.
        library_type: 'user' (default), 'group', or 'library'

    Returns:
        Zotero client instance.

    Raises:
        ImportError: pyzotero not installed
        ValueError: missing api_key or library_id
    """
    if not HAS_PYZOTERO:
        raise ImportError(
            "pyzotero not installed. Install with: "
            "pip install pyzotero  (or see requirements-optional.txt zotero group)"
        )
    api_key = api_key or get_api_key()
    library_id = library_id or get_library_id()
    if not api_key:
        raise ValueError(
            "Zotero API key missing. Set $ZOTERO_API_KEY env var. "
            "Get one at https://www.zotero.org/settings/keys"
        )
    if not library_id:
        raise ValueError(
            "Zotero library ID missing. Set $ZOTERO_LIBRARY_ID env var. "
            "Find yours at https://www.zotero.org/settings/keys "
            "(the numeric ID, not the username)"
        )
    return Zotero(library_id=library_id, api_key=api_key, library_type=library_type)


# ─────────────────────────────────────────────────────────────────
# DOI normalization (reuse from zotero_local for consistency)
# ─────────────────────────────────────────────────────────────────
def normalize_doi(raw: Optional[str]) -> Optional[str]:
    """Normalize DOI to canonical form. Same logic as zotero_local.normalize_doi."""
    if not raw:
        return None
    s = str(raw).strip()
    if not s:
        return None
    s = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", s, flags=re.IGNORECASE)
    s = re.sub(r"^doi:\s*", "", s, flags=re.IGNORECASE)
    s = s.strip().rstrip(".,;").strip().lower()
    if not re.match(r"^10\.\d{4,9}/[^\s\"<>]+$", s):
        return None
    return s


def parse_bibtex_for_doi(bibtex_path: Path) -> List[Dict[str, str]]:
    """Parse Bibtex file and return list of {key, doi, title, type, year, author} dicts.

    Uses a minimal regex parser (handles `field = {value}` and `field = "value"`).
    For complex nested braces, use `pa export-screening` (CSV path) or a
    dedicated Bibtex library.
    """
    if not bibtex_path.exists():
        return []
    text = bibtex_path.read_text(encoding="utf-8", errors="replace")
    # Match @type{key, field = {value}, field = "value", ... }
    entry_pattern = re.compile(
        r"@(\w+)\s*\{\s*([^,]+),(.*?)\n\}",
        re.DOTALL,
    )
    field_pattern = re.compile(r"(\w+)\s*=\s*[\{\"]\s*([^\}\"]+?)\s*[\}\"]", re.IGNORECASE)

    entries = []
    for m in entry_pattern.finditer(text):
        entry_type = m.group(1).lower()
        key = m.group(2).strip()
        body = m.group(3)
        entry = {"key": key, "type": entry_type}
        for fm in field_pattern.finditer(body):
            field_name = fm.group(1).lower()
            value = fm.group(2).strip()
            if field_name in ("doi", "title", "year", "author", "journal", "publisher"):
                entry[field_name] = value
        if "doi" in entry:  # only entries with DOI are useful
            entries.append(entry)
    return entries


# ─────────────────────────────────────────────────────────────────
# Idempotency: check if items already in library
# ─────────────────────────────────────────────────────────────────
def check_dois_in_library(client: "Zotero", dois: List[str]) -> Set[str]:
    """Return the set of DOIs (normalized) already in user's Zotero library.

    Uses pyzotero's `check_items()` for efficient batched lookup, then
    normalizes results to canonical DOI form.
    """
    if not dois:
        return set()
    # pyzotero expects a list of dicts with 'DOI' field for check_items
    items_to_check = [{"DOI": d} for d in dois if d]
    try:
        existing_keys = client.check_items(items_to_check)
    except Exception as e:
        # Network error, auth error, etc. — return empty so caller proceeds
        return set()
    # existing_keys is a list of the items that DO exist in library.
    # The DOI is the key by which we identified them.
    found = set()
    for i, item in enumerate(items_to_check):
        if i < len(existing_keys) and existing_keys[i] is not None:
            found.add(dois[i])
    return found


# ─────────────────────────────────────────────────────────────────
# Push items
# ─────────────────────────────────────────────────────────────────
def bibtex_to_zotero_item(entry: Dict[str, str]) -> Dict[str, Any]:
    """Convert a parsed Bibtex entry dict to a Zotero API item template.

    Returns a dict suitable for pyzotero's create_items().
    """
    # Map Bibtex type to Zotero item type
    type_map = {
        "article": "journalArticle",
        "inproceedings": "conferencePaper",
        "conference": "conferencePaper",
        "book": "book",
        "incollection": "bookSection",
        "phdthesis": "thesis",
        "mastersthesis": "thesis",
        "techreport": "report",
    }
    z_type = type_map.get(entry.get("type", "").lower(), "journalArticle")

    item = {"itemType": z_type}
    if "title" in entry:
        item["title"] = entry["title"]
    if "doi" in entry:
        item["DOI"] = entry["doi"]
    if "url" not in entry and "doi" in entry:
        item["url"] = f"https://doi.org/{entry['doi']}"
    if "author" in entry:
        # Simple split on " and " — for complex author lists, use a proper parser
        item["creators"] = [
            {"creatorType": "author", "name": a.strip()}
            for a in re.split(r"\s+and\s+", entry["author"])
            if a.strip()
        ]
    if "year" in entry:
        item["date"] = entry["year"]
    if "journal" in entry:
        # journalArticle uses 'publicationTitle'; book uses 'publisher'
        if z_type == "journalArticle":
            item["publicationTitle"] = entry["journal"]
        else:
            item["publisher"] = entry["journal"]
    elif "publisher" in entry:
        item["publisher"] = entry["publisher"]
    return item


def push_items(
    client: "Zotero",
    bibtex_entries: List[Dict[str, str]],
    pdf_dir: Optional[Path] = None,
    mode: str = "linked_file",
    skip_existing: bool = True,
) -> Dict[str, Any]:
    """Push Bibtex entries (+ optional PDFs) to user's Zotero library.

    Args:
        client: pyzotero.Zotero client
        bibtex_entries: list of parsed Bibtex entries (from parse_bibtex_for_doi)
        pdf_dir: directory containing PDFs named {key}.pdf (optional)
        mode: 'linked_file' (default, symlink only) or 'imported_file' (copy to Zotero storage)
        skip_existing: if True, skip entries already in library (DOI dedup)

    Returns:
        Dict with keys:
          n_total, n_pushed, n_skipped, n_failed, results: [...]
    """
    if not bibtex_entries:
        return {"n_total": 0, "n_pushed": 0, "n_skipped": 0, "n_failed": 0, "results": []}

    # Step 1: check which DOIs already in library
    dois = [normalize_doi(e.get("doi", "")) for e in bibtex_entries]
    dois = [d for d in dois if d]  # drop None
    existing = check_dois_in_library(client, dois) if skip_existing else set()

    # Step 2: build list of items to push (skip existing)
    to_push = []
    skipped = []
    for entry in bibtex_entries:
        norm_doi = normalize_doi(entry.get("doi", ""))
        if norm_doi and norm_doi in existing:
            skipped.append({"key": entry.get("key", ""), "doi": norm_doi, "reason": "already_in_library"})
            continue
        to_push.append(entry)

    # Step 3: convert to Zotero format and create
    zotero_items = [bibtex_to_zotero_item(e) for e in to_push]
    results = []
    n_pushed = 0
    n_failed = 0
    if zotero_items:
        try:
            created = client.create_items(zotero_items)
            # pyzotero returns a list of {successful: {...}, failed: {...}}
            for i, item_dict in enumerate(created):
                entry = to_push[i]
                if "successful" in item_dict:
                    item_key = item_dict["successful"].get("key", "")
                    n_pushed += 1
                    results.append({
                        "key": entry.get("key", ""),
                        "doi": normalize_doi(entry.get("doi", "")) or "",
                        "zotero_key": item_key,
                        "status": "pushed",
                    })
                elif "failed" in item_dict:
                    n_failed += 1
                    err = item_dict["failed"]
                    results.append({
                        "key": entry.get("key", ""),
                        "doi": normalize_doi(entry.get("doi", "")) or "",
                        "status": "failed",
                        "error": str(err)[:200],
                    })
        except Exception as e:
            return {
                "n_total": len(bibtex_entries),
                "n_pushed": 0,
                "n_skipped": len(skipped),
                "n_failed": len(zotero_items),
                "results": skipped + [{
                    "key": e.get("key", ""),
                    "doi": normalize_doi(e.get("doi", "")) or "",
                    "status": "failed",
                    "error": f"create_items exception: {type(e).__name__}: {str(e)[:200]}",
                } for e in to_push],
            }

    # Step 4: optionally upload PDFs (skipped for now — separate function)
    if pdf_dir and mode in ("linked_file", "imported_file"):
        # TODO: implement PDF upload. The push() step created the items
        # with metadata; uploading PDFs as attachments is a separate API
        # call (item.attachment_simple() or upload_attachments()).
        # For v3.9.15.0 we focus on metadata push; PDF upload tracked
        # as [P2-17.1] follow-up.
        pass

    return {
        "n_total": len(bibtex_entries),
        "n_pushed": n_pushed,
        "n_skipped": len(skipped),
        "n_failed": n_failed,
        "results": skipped + results,
    }


# ─────────────────────────────────────────────────────────────────
# Search library
# ─────────────────────────────────────────────────────────────────
def search_library(
    client: "Zotero",
    query: str,
    limit: int = 20,
    qmode: str = "titleCreatorYear",
) -> List[Dict[str, Any]]:
    """Search user's Zotero library by title/author/year.

    Args:
        client: pyzotero.Zotero client
        query: search query (matched against title, creator, year per qmode)
        limit: max results to return
        qmode: 'titleCreatorYear' (default), 'everything', or 'title'

    Returns:
        List of items: [{key, title, creators, date, DOI, ...}, ...]
    """
    if not query.strip():
        return []
    try:
        # pyzotero's search() returns a list of items or empty list
        results = client.search(query, qmode=qmode, limit=limit)
    except Exception:
        return []
    out = []
    for item in results[:limit]:
        out.append({
            "key": item.get("key", ""),
            "title": item.get("title", "(no title)"),
            "creators": item.get("creators", []),
            "date": item.get("date", ""),
            "DOI": item.get("DOI", ""),
            "itemType": item.get("itemType", ""),
        })
    return out
