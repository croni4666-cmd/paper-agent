"""pa_cli.zotero_api - Zotero Web API wrapper (v3.9.16, [P2-17] + [P2-18] + [P3-28])

Implements Zotero write + library search + collection-as-project
management via the official Zotero Web API v3, wrapped by the `pyzotero`
library (MIT, well-maintained).

**What ships**:

*`pa zotero push` ([P2-17], v3.9.15.0)*:
- Push Bibtex entries + PDFs to user's Zotero library

*`pa zotero search` ([P2-18], v3.9.15.0)*:
- Search user's existing Zotero library

*`pa zotero sync` ([P2-18], v3.9.15.0)*:
- Combine [P2-16] check + [P2-17] push + library search

*`pa zotero project` ([P3-28], v3.9.16) -- NEW*:
- `create` / `list` / `status` / `note` -- collection-as-research-project
- `search` -- cross-collection search
- per-project master note attached to collection

**Design constraints** (per留痕 / AGPL discipline):
- API key is read from `$ZOTERO_API_KEY` env var ONLY (NOT from `.env` per
  留痕 discipline; user exports per session)
- Idempotent: re-running same corpus does not duplicate items (DOI dedup
  via `check_items()` before `create_items()`)
- `create_collection` is idempotent by name (case-insensitive)
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
from datetime import datetime
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
        # Network error, auth error, etc. --?return empty so caller proceeds
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
        # Simple split on " and " --?for complex author lists, use a proper parser
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

    # Step 4: optionally upload PDFs (v3.9.17.1 [P2-17.1] --?was no-op in v3.9.15.0)
    n_pdf_uploaded = 0
    n_pdf_failed = 0
    pdf_results = []
    if pdf_dir and mode in ("linked_file", "imported_file"):
        # For each successfully pushed item, look for a matching PDF
        # at {pdf_dir}/{key}.pdf and queue for upload
        uploads = []
        for r in results:
            if r.get("status") != "pushed":
                continue
            key = r.get("key", "")
            parent_key = r.get("zotero_key", "")
            if not key or not parent_key:
                continue
            pdf_path = Path(pdf_dir) / f"{key}.pdf"
            if pdf_path.exists():
                uploads.append({
                    "pdf_path": str(pdf_path),
                    "parent_key": parent_key,
                    "title": f"{key}.pdf",
                })
        if uploads:
            upload_result = upload_pdfs(client, uploads, mode=mode)
            n_pdf_uploaded = upload_result["n_uploaded"]
            n_pdf_failed = upload_result["n_failed"]
            pdf_results = upload_result["results"]
            # Add per-pdf results to the main results list
            for pr in pdf_results:
                results.append({
                    "key": pr.get("pdf_path", ""),
                    "doi": "",
                    "status": "pdf_" + pr.get("status", "unknown"),
                    "zotero_key": pr.get("zotero_key", ""),
                    "parent_key": pr.get("parent_key", ""),
                    "mode": pr.get("mode", ""),
                    "error": pr.get("error", ""),
                })

    return {
        "n_total": len(bibtex_entries),
        "n_pushed": n_pushed,
        "n_skipped": len(skipped),
        "n_failed": n_failed,
        "n_pdf_uploaded": n_pdf_uploaded,
        "n_pdf_failed": n_pdf_failed,
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


# ─────────────────────────────────────────────────────────────────
# Collections (project-as-collection) --?v3.9.16 [P3-28]
# ─────────────────────────────────────────────────────────────────
def list_collections(client: "Zotero", top_only: bool = True) -> List[Dict[str, Any]]:
    """List collections (= research projects) in user's Zotero library.

    Args:
        client: pyzotero.Zotero client
        top_only: if True, return only top-level collections (skip sub-collections)

    Returns:
        List of {key, name, parentCollection, numItems, numCollections, version}
        dicts. Sorted by name (case-insensitive).
    """
    try:
        if top_only:
            raw = client.collections_top()
        else:
            raw = client.collections()
    except Exception:
        return []
    out = []
    for c in raw:
        data = c.get("data", c)  # pyzotero sometimes wraps in 'data'
        out.append({
            "key": data.get("key", ""),
            "name": data.get("name", ""),
            "parentCollection": data.get("parentCollection", False),
            "numItems": data.get("numItems", 0),
            "numCollections": data.get("numCollections", 0),
            "version": data.get("version", 0),
        })
    out.sort(key=lambda x: x["name"].lower())
    return out


def find_collection_by_name(
    client: "Zotero",
    name: str,
    parent_key: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Find a top-level collection by exact name. Returns the collection dict
    or None if not found.

    Case-insensitive match. For nested collections, pass parent_key to scope
    the search to a specific parent.
    """
    if not name.strip():
        return None
    needle = name.strip().lower()
    for coll in list_collections(client, top_only=False):
        if coll["name"].lower() == needle:
            if parent_key is None or coll.get("parentCollection") == parent_key:
                return coll
    return None


def create_collection(
    client: "Zotero",
    name: str,
    parent_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new Zotero collection (= research project).

    Args:
        client: pyzotero.Zotero client
        name: collection name (will be used as the project topic name)
        parent_key: optional parent collection key (for nested projects)

    Returns:
        Dict with {status, key, name, error?}:
          - status='created' on success with key
          - status='exists' if collection with same name already exists
          - status='error' on API error

    **Idempotency**: returns status='exists' if a collection with the
    same name already exists (at the same level). Safe to re-run.
    """
    name = (name or "").strip()
    if not name:
        return {"status": "error", "error": "empty collection name", "name": ""}

    # Check if already exists (idempotent)
    existing = find_collection_by_name(client, name, parent_key)
    if existing is not None:
        return {
            "status": "exists",
            "key": existing["key"],
            "name": existing["name"],
            "numItems": existing["numItems"],
        }

    payload = [{"name": name}]
    if parent_key:
        payload[0]["parentCollection"] = parent_key
    try:
        result = client.create_collections(payload)
        # pyzotero returns [{"successful": {"key": ..., "data": {...}}}] or
        # [{"failed": {...}}]
        if not result:
            return {"status": "error", "error": "empty response from create_collections", "name": name}
        first = result[0]
        if "successful" in first:
            return {
                "status": "created",
                "key": first["successful"].get("key", ""),
                "name": name,
            }
        elif "failed" in first:
            err = first["failed"]
            return {
                "status": "error",
                "error": str(err)[:300],
                "name": name,
            }
        else:
            return {"status": "error", "error": f"unexpected response: {str(first)[:300]}", "name": name}
    except Exception as e:
        return {
            "status": "error",
            "error": f"{type(e).__name__}: {str(e)[:200]}",
            "name": name,
        }


def get_collection_items(client: "Zotero", collection_key: str) -> List[Dict[str, Any]]:
    """Get all items in a Zotero collection.

    Args:
        client: pyzotero.Zotero client
        collection_key: the collection's Zotero key

    Returns:
        List of {key, title, creators, date, DOI, itemType} dicts.
        Sorted by date (descending), then title.
    """
    if not collection_key:
        return []
    try:
        raw = client.collection_items(collection_key)
    except Exception:
        return []
    out = []
    for item in raw:
        data = item.get("data", item)
        # Filter out attachments/notes (we only want top-level bibliographic items)
        if data.get("itemType") in ("attachment", "note"):
            continue
        out.append({
            "key": data.get("key", ""),
            "title": data.get("title", "(no title)"),
            "creators": data.get("creators", []),
            "date": data.get("date", ""),
            "DOI": data.get("DOI", ""),
            "itemType": data.get("itemType", ""),
        })
    # Sort by date desc, then title
    out.sort(key=lambda x: (x.get("date", ""), x.get("title", "").lower()), reverse=True)
    return out


def add_items_to_collection(
    client: "Zotero",
    item_keys: List[str],
    collection_key: str,
) -> Dict[str, Any]:
    """Add existing Zotero items to a collection.

    Args:
        client: pyzotero.Zotero client
        item_keys: list of Zotero item keys to add
        collection_key: target collection key

    Returns:
        Dict with {n_added, n_failed, results: [...]}
    """
    if not item_keys or not collection_key:
        return {"n_added": 0, "n_failed": 0, "results": []}
    results = []
    n_added = 0
    n_failed = 0
    # pyzotero doesn't have a direct "add to collection" method; we update
    # each item's collections field
    for k in item_keys:
        try:
            item = client.item(k)
            data = item.get("data", item)
            existing = set(data.get("collections", []))
            existing.add(collection_key)
            data["collections"] = list(existing)
            client.update_item(item)
            n_added += 1
            results.append({"key": k, "status": "added"})
        except Exception as e:
            n_failed += 1
            results.append({"key": k, "status": "failed", "error": str(e)[:200]})
    return {"n_added": n_added, "n_failed": n_failed, "results": results}


def create_collection_note(
    client: "Zotero",
    collection_key: str,
    title: str,
    content: str,
) -> Dict[str, Any]:
    """Create a note attached to a Zotero collection (= project master note).

    In Zotero, collection-level notes are 'note' items with
    itemType='note' and the collection in their 'collections' field.

    Args:
        client: pyzotero.Zotero client
        collection_key: target collection key
        title: note title (e.g. "long-term care --?research note")
        content: note content (HTML or plain text --?Zotero stores HTML)

    Returns:
        Dict with {status, key, title, error?}
    """
    if not collection_key or not title:
        return {"status": "error", "error": "missing collection_key or title"}
    # Zotero notes use HTML
    if not content.lstrip().startswith("<"):
        # Plain text �?wrap in <pre> for whitespace preservation
        body = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        content = f"<h1>{title}</h1>\n<pre>{body}</pre>"
    payload = [{
        "itemType": "note",
        "title": title,
        "note": content,
        "collections": [collection_key],
        "tags": [{"tag": "paper-agent-project-note"}],
    }]
    try:
        result = client.create_items(payload)
        if not result:
            return {"status": "error", "error": "empty response"}
        first = result[0]
        if "successful" in first:
            return {
                "status": "created",
                "key": first["successful"].get("key", ""),
                "title": title,
            }
        elif "failed" in first:
            return {"status": "error", "error": str(first["failed"])[:300], "title": title}
        return {"status": "error", "error": f"unexpected: {str(first)[:300]}", "title": title}
    except Exception as e:
        return {
            "status": "error",
            "error": f"{type(e).__name__}: {str(e)[:200]}",
            "title": title,
        }


def list_collection_notes(
    client: "Zotero",
    collection_key: str,
) -> List[Dict[str, Any]]:
    """List all notes attached to a Zotero collection.

    Returns:
        List of {key, title, note (HTML), version, dateModified}
    """
    if not collection_key:
        return []
    try:
        items = client.collection_items(collection_key)
    except Exception:
        return []
    out = []
    for item in items:
        data = item.get("data", item)
        if data.get("itemType") == "note":
            out.append({
                "key": data.get("key", ""),
                "title": data.get("title", ""),
                "note": data.get("note", ""),
                "dateModified": data.get("dateModified", ""),
                "version": data.get("version", 0),
            })
    out.sort(key=lambda x: x.get("dateModified", ""), reverse=True)
    return out


# ─────────────────────────────────────────────────────────────────
# PDF upload (v3.9.17.1 [P2-17.1]) -- attachment via pyzotero API
# ─────────────────────────────────────────────────────────────────
def upload_pdfs(
    client: "Zotero",
    uploads: List[Dict[str, str]],
    mode: str = "linked_file",
) -> Dict[str, Any]:
    """Upload PDFs as attachments to existing Zotero items.

    Args:
        client: pyzotero.Zotero client
        uploads: list of {pdf_path, parent_key, [title]} dicts
        mode: 'linked_file' (default, symlink only --?original PDF
              stays at pdf_path, Zotero just stores the reference)
              or 'imported_file' (copy to Zotero storage dir; uses
              quota --?free tier ~300MB)

    Returns:
        Dict with keys:
          n_uploaded, n_failed, results: [...]

    **Two implementation paths** (matches v3.9.15.0 push semantics):
        - `linked_file`: uses `item_template("attachment", linkmode="linked_file")`
          + `create_items([template], parentid=parent_key)`. The PDF
          stays at its original location; Zotero stores the absolute
          path. No file copy, no quota usage.
        - `imported_file`: uses `attachment_simple([file_path], parentid=parent_key)`.
          pyzotero uploads the file to Zotero's storage dir. Counts
          against user's Zotero file quota.

    **Auth**: inherits from client (env-var-only, per 留痕 discipline).
    """
    if not uploads:
        return {"n_uploaded": 0, "n_failed": 0, "results": []}

    n_uploaded = 0
    n_failed = 0
    results = []

    for upload in uploads:
        pdf_path = upload.get("pdf_path", "")
        parent_key = upload.get("parent_key", "")
        title = upload.get("title") or Path(pdf_path).name

        # Validation
        if not pdf_path or not parent_key:
            n_failed += 1
            results.append({
                "pdf_path": pdf_path, "parent_key": parent_key,
                "status": "failed", "error": "missing pdf_path or parent_key",
            })
            continue
        path_obj = Path(pdf_path)
        if not path_obj.exists():
            n_failed += 1
            results.append({
                "pdf_path": pdf_path, "parent_key": parent_key,
                "status": "failed", "error": "file not found",
            })
            continue

        # Resolve to absolute path (Zotero requires absolute paths for linked_file)
        abs_path = str(path_obj.resolve())

        try:
            if mode == "linked_file":
                # Use create_items with linkmode=linked_file + absolute path
                template = client.item_template("attachment", linkmode="linked_file")
                template["title"] = title
                template["path"] = abs_path
                created = client.create_items([template], parentid=parent_key)
                if not created:
                    n_failed += 1
                    results.append({
                        "pdf_path": pdf_path, "parent_key": parent_key,
                        "status": "failed", "error": "empty response from create_items",
                    })
                    continue
                first = created[0] if created else {}
                if "successful" in first:
                    n_uploaded += 1
                    results.append({
                        "pdf_path": pdf_path, "parent_key": parent_key,
                        "zotero_key": first["successful"].get("key", ""),
                        "mode": "linked_file", "status": "uploaded",
                    })
                elif "failed" in first:
                    n_failed += 1
                    results.append({
                        "pdf_path": pdf_path, "parent_key": parent_key,
                        "status": "failed",
                        "error": str(first["failed"])[:200],
                    })
                else:
                    n_failed += 1
                    results.append({
                        "pdf_path": pdf_path, "parent_key": parent_key,
                        "status": "failed",
                        "error": f"unexpected response: {str(first)[:200]}",
                    })
            else:  # imported_file
                # Use attachment_simple --?pyzotero handles upload
                uploaded = client.attachment_simple([abs_path], parentid=parent_key)
                if not uploaded:
                    n_failed += 1
                    results.append({
                        "pdf_path": pdf_path, "parent_key": parent_key,
                        "status": "failed", "error": "empty response from attachment_simple",
                    })
                    continue
                first = uploaded[0] if uploaded else {}
                if "successful" in first:
                    n_uploaded += 1
                    results.append({
                        "pdf_path": pdf_path, "parent_key": parent_key,
                        "zotero_key": first["successful"].get("key", ""),
                        "mode": "imported_file", "status": "uploaded",
                    })
                elif "failed" in first:
                    n_failed += 1
                    results.append({
                        "pdf_path": pdf_path, "parent_key": parent_key,
                        "status": "failed",
                        "error": str(first["failed"])[:200],
                    })
                else:
                    n_failed += 1
                    results.append({
                        "pdf_path": pdf_path, "parent_key": parent_key,
                        "status": "failed",
                        "error": f"unexpected response: {str(first)[:200]}",
                    })
        except Exception as e:
            n_failed += 1
            results.append({
                "pdf_path": pdf_path, "parent_key": parent_key,
                "status": "failed",
                "error": f"{type(e).__name__}: {str(e)[:200]}",
            })

    return {
        "n_uploaded": n_uploaded,
        "n_failed": n_failed,
        "results": results,
    }


# ─────────────────────────────────────────────────────────────────
# Pull / export-bib (v3.9.18 [P3-28.2]) -- bidirectional Zotero <-> local pa project
# ─────────────────────────────────────────────────────────────────
_ZOTERO_TYPE_TO_BIBTEX_TYPE = {
    "journalArticle": "article",
    "book": "book",
    "bookSection": "incollection",
    "conferencePaper": "inproceedings",
    "thesis": "phdthesis",  # default; will check ThesisType for mastersthesis
    "report": "techreport",
    "preprint": "misc",
    "manuscript": "unpublished",
    "document": "misc",
    "webpage": "misc",
    "encyclopediaArticle": "incollection",
    "dictionaryEntry": "incollection",
    "magazineArticle": "article",
    "newspaperArticle": "article",
    "blogPost": "misc",
    "forumPost": "misc",
    "presentation": "misc",
    "dataset": "misc",
    "software": "misc",
    "interview": "misc",
    "letter": "misc",
    "podcast": "misc",
    "radioBroadcast": "misc",
    "tvBroadcast": "misc",
    "videoRecording": "misc",
    "audioRecording": "misc",
    "patent": "patent",
}


def _zotero_type_to_bibtex_type(z_type: str, extra: Optional[Dict[str, Any]] = None) -> str:
    """Map a Zotero itemType to a Bibtex entry type.

    Unknown types fall back to @misc. Thesis subtype is auto-detected
    from extra['thesisType']: 'Master's Thesis' -> 'mastersthesis'.
    """
    base = _ZOTERO_TYPE_TO_BIBTEX_TYPE.get(z_type, "misc")
    if z_type == "thesis" and extra:
        tt = (extra.get("thesisType") or "").lower()
        if "master" in tt:
            return "mastersthesis"
    return base


def _zotero_creators_to_bibtex_author(creators: List[Dict[str, Any]]) -> str:
    """Convert Zotero creators list to Bibtex author field value.

    Zotero creator = {"creatorType": "author", "firstName": "...", "lastName": "..."}
                  or {"creatorType": "author", "name": "..."}  (single-field for orgs)
    Bibtex format: "Lastname, Firstname and Lastname, Firstname"
    For single-name (organizations): pass through.

    **Only `author` creatorType is included** (editors / translators
    go in their own Bibtex fields, not in `author`).
    """
    if not creators:
        return ""
    parts = []
    for c in creators:
        ctype = c.get("creatorType")
        if ctype and ctype != "author":
            continue  # skip editor/translator/contributor/etc.
        last = (c.get("lastName") or "").strip()
        first = (c.get("firstName") or "").strip()
        name = (c.get("name") or "").strip()
        if last and first:
            parts.append(f"{last}, {first}")
        elif last:
            parts.append(last)
        elif name:
            parts.append(name)
    return " and ".join(parts)


def _sanitize_bibtex_key(s: str, fallback: str = "ref") -> str:
    """Make a string into a valid Bibtex cite-key.

    Strips non-ASCII, replaces runs of non-alphanumeric with single '_',
    trims to 40 chars. Returns 'fallback' if input is empty.
    """
    if not s:
        return fallback
    # Lowercase + replace any non [a-z0-9] with '_'
    out = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_").lower()
    if not out:
        return fallback
    return out[:40]


def zotero_item_to_bibtex(item: Dict[str, Any]) -> Optional[str]:
    """Convert a single Zotero item dict to a Bibtex entry string.

    Args:
        item: a single item from `client.collection_items()` (or any
              pyzotero item response). Accepts both bare items and
              {"data": {...}} wrapped items.

    Returns:
        A complete Bibtex entry string (e.g. "@article{key,\n  ...\n}"),
        or None if the item has no title (skipped) or unsupported shape.
    """
    data = item.get("data", item) if isinstance(item, dict) else {}
    if not data:
        return None
    title = (data.get("title") or "").strip()
    if not title:
        return None

    z_type = data.get("itemType", "journalArticle")
    bib_type = _zotero_type_to_bibtex_type(z_type, data)

    # Cite-key: prefer DOI (URL-stripped, last path segment), else first-author-surname + year
    doi = normalize_doi(data.get("DOI", "")) or ""
    if doi:
        # Use last path component of DOI as cite-key base
        key_base = doi.split("/")[-1]
    else:
        creators = data.get("creators") or []
        last_name = ""
        org_name = ""
        for c in creators:
            if c.get("lastName"):
                last_name = c["lastName"]
                break
            if not org_name and c.get("name"):
                # Use first word of org name for cite-key
                org_name = c["name"].split()[0] if c.get("name") else ""
        year = (data.get("date") or "")[:4]
        if last_name and year:
            key_base = f"{last_name}{year}"
        elif last_name:
            key_base = f"{last_name}{year}" if year else last_name
        elif org_name:
            key_base = f"{org_name}{year}" if year else org_name
        elif title:
            # Use first significant word of title (skip "the", "a", etc.)
            for w in re.split(r"\s+", title):
                wl = w.lower().strip(".,;:")
                if wl and wl not in ("the", "a", "an", "of", "on", "in"):
                    key_base = w + (year or "")
                    break
            else:
                key_base = title
        else:
            key_base = "ref"
    cite_key = _sanitize_bibtex_key(key_base, fallback="ref")

    # Build fields
    fields = []
    fields.append(("title", title))
    authors = _zotero_creators_to_bibtex_author(data.get("creators") or [])
    if authors:
        fields.append(("author", authors))
    date = (data.get("date") or "").strip()
    if date:
        # Bibtex year is YYYY; Zotero date may be 'YYYY-MM-DD' or 'YYYY'
        year = date[:4] if date[:4].isdigit() else ""
        if year:
            fields.append(("year", year))
    if doi:
        fields.append(("doi", doi))
        fields.append(("url", f"https://doi.org/{doi}"))
    pub_title = (data.get("publicationTitle") or "").strip()
    if pub_title:
        fields.append(("journal", pub_title))
    publisher = (data.get("publisher") or "").strip()
    if publisher:
        fields.append(("publisher", publisher))
    volume = (data.get("volume") or "").strip()
    if volume:
        fields.append(("volume", volume))
    issue = (data.get("issue") or "").strip()
    if issue:
        fields.append(("number", issue))
    pages = (data.get("pages") or "").strip()
    if pages:
        fields.append(("pages", pages))
    # For bookSection: book title goes into 'booktitle'
    book_title = (data.get("bookTitle") or "").strip()
    if book_title and bib_type == "incollection":
        fields.append(("booktitle", book_title))
    # For thesis: thesisType stays in 'type' sub-field
    thesis_type = (data.get("thesisType") or "").strip()
    if thesis_type and bib_type in ("phdthesis", "mastersthesis"):
        fields.append(("type", thesis_type))
    # Place / institution for thesis
    place = (data.get("place") or "").strip()
    if place and bib_type in ("phdthesis", "mastersthesis"):
        fields.append(("address", place))
    institution = (data.get("institution") or "").strip()
    if institution and bib_type in ("phdthesis", "mastersthesis", "techreport"):
        fields.append(("school" if bib_type in ("phdthesis", "mastersthesis") else "institution", institution))
    abstract = (data.get("abstractNote") or "").strip()
    if abstract:
        # Truncate very long abstracts to keep file readable
        if len(abstract) > 4000:
            abstract = abstract[:4000] + "..."
        fields.append(("abstract", abstract))
    # Zotero key (for round-trip back to push)
    z_key = (data.get("key") or "").strip()
    if z_key:
        fields.append(("zotero_key", z_key))

    # Serialize
    body_lines = ["@" + bib_type + "{" + cite_key + ","]
    for k, v in fields:
        # Escape braces / backslashes in value
        v_esc = v.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
        body_lines.append(f"  {k:<12s} = {{{v_esc}}},")
    body_lines.append("}")
    return "\n".join(body_lines)


def collection_items_to_bibtex(
    client: "Zotero",
    collection_key: str,
    out_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Convert all items in a Zotero collection to Bibtex format.

    Args:
        client: pyzotero.Zotero client
        collection_key: the collection's Zotero key
        out_path: optional .bib file to write. If None, returns Bibtex string.

    Returns:
        Dict with {n_total, n_converted, n_skipped, n_failed, bibtex_str, out_path?}.
        Failed items (e.g. attachments or unsupported types) are skipped, not raised.
    """
    if not collection_key:
        return {"n_total": 0, "n_converted": 0, "n_skipped": 0, "n_failed": 0,
                "bibtex_str": "", "results": []}

    items = get_collection_items(client, collection_key)
    n_total = len(items)

    bibtex_entries: List[str] = []
    n_converted = 0
    n_skipped = 0
    n_failed = 0
    results: List[Dict[str, Any]] = []
    seen_keys: Set[str] = set()  # dedup by cite-key

    for item in items:
        try:
            bib_str = zotero_item_to_bibtex(item)
        except Exception as e:
            n_failed += 1
            results.append({"key": item.get("key", ""), "title": item.get("title", ""),
                            "status": "failed", "error": f"{type(e).__name__}: {str(e)[:200]}"})
            continue
        if bib_str is None:
            n_skipped += 1
            results.append({"key": item.get("key", ""), "title": item.get("title", ""),
                            "status": "skipped", "error": "no title or unsupported"})
            continue
        # Extract cite-key (first line "@type{key,") for dedup
        try:
            first_line = bib_str.split("\n", 1)[0]
            cite_key = first_line.split("{", 1)[1].rstrip(",")
        except (IndexError, ValueError):
            cite_key = ""
        if cite_key and cite_key in seen_keys:
            # Append a suffix to make unique
            i = 2
            while f"{cite_key}_{i}" in seen_keys:
                i += 1
            new_key = f"{cite_key}_{i}"
            # Replace old cite-key with new in the first line
            first_line, rest = bib_str.split("\n", 1)
            first_line = first_line.replace("{" + cite_key + ",", "{" + new_key + ",")
            bib_str = first_line + "\n" + rest
            cite_key = new_key
        if cite_key:
            seen_keys.add(cite_key)
        bibtex_entries.append(bib_str)
        n_converted += 1
        results.append({"key": item.get("key", ""), "title": item.get("title", ""),
                        "cite_key": cite_key, "status": "converted"})

    bibtex_str = "\n\n".join(bibtex_entries) + ("\n" if bibtex_entries else "")

    written_path: Optional[str] = None
    if out_path is not None:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(bibtex_str, encoding="utf-8")
        written_path = str(out_path)

    return {
        "n_total": n_total,
        "n_converted": n_converted,
        "n_skipped": n_skipped,
        "n_failed": n_failed,
        "bibtex_str": bibtex_str,
        "out_path": written_path,
        "results": results,
    }


def pull_collection_to_project(
    client: "Zotero",
    collection_name: str,
    project_slug: Optional[str] = None,
    project_root: Optional[Path] = None,
    overwrite: bool = False,
) -> Dict[str, Any]:
    """Pull a Zotero collection into a local pa project (refs.bib + meta.json).

    Creates a new pa project at <project_root>/<project_slug>/ with:
    - meta.json: {slug, title, description, created_at, updated_at,
                  zotero_collection_key, zotero_collection_name,
                  zotero_collection_version, source: "zotero-pull"}
    - refs.bib: all bibliographic items from the collection (Bibtex format)
    - judges.sqlite: empty judge table (matches local pa project layout)

    Args:
        client: pyzotero.Zotero client
        collection_name: Zotero collection name to pull
        project_slug: project slug (default: derived from name)
        project_root: project root (default: ~/.paper-agent/projects/)
        overwrite: if True, replace existing project. If False, refuse if exists.

    Returns:
        Dict with {status, project_path, project_slug, n_items, n_converted,
                  n_skipped, n_failed, refs_path, meta_path, zotero_key,
                  zotero_collection_name, error?}.
    """
    # Lazy import to avoid circular dep at module import
    from .project import (
        DEFAULT_ROOT as PA_DEFAULT_ROOT,
        init_project,
        project_dir,
        project_files,
        save_meta,
    )

    if not collection_name or not collection_name.strip():
        return {"status": "error", "error": "empty collection name",
                "collection_name": ""}

    coll = find_collection_by_name(client, collection_name)
    if coll is None:
        return {"status": "error", "error": f"collection not found: {collection_name!r}",
                "collection_name": collection_name}

    # Slug: derived from name if not provided
    if not project_slug:
        project_slug = re.sub(r"[^A-Za-z0-9._-]+", "-", collection_name.strip()).strip("-").lower() or "zotero-project"

    # Project root
    root = Path(project_root) if project_root else PA_DEFAULT_ROOT

    # Refuse if exists (unless overwrite)
    pdir = project_dir(project_slug, root)
    if pdir.exists() and not overwrite:
        return {"status": "error",
                "error": f"project already exists at {pdir} (use --overwrite to replace)",
                "project_slug": project_slug, "project_path": str(pdir),
                "collection_name": collection_name}

    if pdir.exists() and overwrite:
        import shutil
        shutil.rmtree(pdir)

    # Init project (creates meta.json + empty refs.bib + empty judges.sqlite)
    try:
        meta = init_project(
            slug=project_slug,
            title=collection_name,
            description=f"Pulled from Zotero collection '{collection_name}' (key={coll['key']})",
            root=root,
        )
    except FileExistsError as e:
        return {"status": "error", "error": str(e), "project_slug": project_slug}

    # Augment meta.json with Zotero-specific fields
    meta["zotero_collection_key"] = coll["key"]
    meta["zotero_collection_name"] = coll["name"]
    meta["zotero_collection_version"] = coll.get("version", 0)
    meta["source"] = "zotero-pull"
    meta["updated_at"] = datetime.now().isoformat(timespec="seconds")
    save_meta(project_slug, meta, root)

    # Convert collection items to Bibtex and write to refs.bib
    refs_path = project_files(project_slug, root)["refs"]
    conv = collection_items_to_bibtex(client, coll["key"], out_path=refs_path)

    return {
        "status": "created" if not overwrite else "overwritten",
        "project_path": str(pdir),
        "project_slug": project_slug,
        "zotero_key": coll["key"],
        "zotero_collection_name": coll["name"],
        "n_total": conv["n_total"],
        "n_converted": conv["n_converted"],
        "n_skipped": conv["n_skipped"],
        "n_failed": conv["n_failed"],
        "refs_path": str(refs_path),
        "meta_path": str(project_files(project_slug, root)["meta"]),
        "judges_path": str(project_files(project_slug, root)["judges"]),
    }


# ─────────────────────────────────────────────────────────────────
# Diff / sync (v3.9.19 [P3-28.3]) -- incremental Zotero -> local updates
# ─────────────────────────────────────────────────────────────────
def _parse_refs_bib_dois(refs_bib_path: Path) -> Dict[str, str]:
    """Parse a local refs.bib and return {normalized_doi: bibtex_key}.

    Uses `parse_bibtex_for_doi()` (the same parser used by `push_items`).
    Returns empty dict if the file doesn't exist or has no DOIs.

    Bibtex entries without DOI are ignored for diff purposes (Zotero
    items are matched by DOI; without DOI, we can't reliably
    deduplicate across systems).
    """
    if not refs_bib_path.exists():
        return {}
    out: Dict[str, str] = {}
    for entry in parse_bibtex_for_doi(refs_bib_path):
        doi = normalize_doi(entry.get("doi", ""))
        if doi:
            out[doi] = entry.get("key", "")
    return out


def diff_collection_to_local(
    client: "Zotero",
    collection_key: str,
    local_refs_bib_path: Path,
) -> Dict[str, Any]:
    """Compare a Zotero collection against a local refs.bib file.

    Items are matched by normalized DOI. Returns:
    - `new_dois`: DOIs in Zotero but NOT in local refs.bib (Zotero
      has new items that the local copy doesn't)
    - `removed_dois`: DOIs in local refs.bib but NOT in Zotero
      (Zotero has removed items that are still in local; we DON'T
      auto-delete locally)
    - `new_items`: full Zotero data for the new DOIs (for use by
      `sync_collection_to_local` to append to refs.bib)
    - `zotero_n_items`: total top-level bibliographic items in Zotero
    - `local_n_dois`: total DOIs found in local refs.bib
    - `unchanged_n`: count of DOIs in both (matched)

    **No "updated" detection** in v3.9.19: we don't track per-item
    versions locally, so we can't reliably tell if a Zotero item was
    edited after pull. The pull command in v3.9.18.0 set
    `zotero_collection_version` (collection-level, not per-item).
    Use `pa zotero project pull --overwrite` to fully refresh if
    item-level updates are needed.

    Args:
        client: pyzotero.Zotero client
        collection_key: the collection's Zotero key
        local_refs_bib_path: path to local refs.bib

    Returns:
        Dict with {new_dois, removed_dois, new_items, zotero_n_items,
        local_n_dois, unchanged_n}.
    """
    # Local DOIs
    local_dois = _parse_refs_bib_dois(Path(local_refs_bib_path))

    # Zotero items (top-level only, not attachments/notes)
    zotero_items = get_collection_items(client, collection_key)

    zotero_doi_to_item: Dict[str, Dict[str, Any]] = {}
    for item in zotero_items:
        doi = normalize_doi(item.get("DOI", ""))
        if doi:
            zotero_doi_to_item[doi] = item

    new_dois = sorted(d for d in zotero_doi_to_item if d not in local_dois)
    removed_dois = sorted(d for d in local_dois if d not in zotero_doi_to_item)
    unchanged_n = len(set(local_dois) & set(zotero_doi_to_item))
    new_items = [zotero_doi_to_item[d] for d in new_dois]

    return {
        "new_dois": new_dois,
        "removed_dois": removed_dois,
        "new_items": new_items,
        "zotero_n_items": len(zotero_items),
        "local_n_dois": len(local_dois),
        "unchanged_n": unchanged_n,
    }


def sync_collection_to_local(
    client: "Zotero",
    collection_name: str,
    project_slug: Optional[str] = None,
    project_root: Optional[Path] = None,
    dry_run: bool = True,
) -> Dict[str, Any]:
    """Incrementally sync a Zotero collection into a local pa project.

    Compares Zotero collection against the local refs.bib, optionally
    appending new items to refs.bib. Default is `dry_run=True` (just
    reports the diff without changing anything).

    **Behavior**:
    - **NEW** items in Zotero (DOI not in local): appended to refs.bib
      in Bibtex format
    - **REMOVED** items in Zotero (DOI in local but not in Zotero):
      NOT deleted from local refs.bib (safety); recorded in
      `meta.json` under `removed_from_zotero: [dois]` for the user
      to decide
    - **UNCHANGED** items: no action
    - **`meta.json`** updated with:
      - `zotero_collection_version` (refresh)
      - `zotero_last_sync_at` (ISO timestamp)
      - `n_items` (refresh)
      - `removed_from_zotero` (list of DOIs no longer in Zotero)

    Args:
        client: pyzotero.Zotero client
        collection_name: Zotero collection name
        project_slug: local project slug (default: derived from name)
        project_root: project root (default: ~/.paper-agent/projects/)
        dry_run: if True (default), only report diff without writing
                 any file. Pass `dry_run=False` to actually apply.

    Returns:
        Dict with {status, project_slug, dry_run, n_new, n_removed,
        n_unchanged, new_dois, removed_dois, refs_path, meta_path,
        n_items, applied: bool}.
    """
    from .project import (
        DEFAULT_ROOT as PA_DEFAULT_ROOT,
        project_dir,
        project_files,
        load_meta,
        save_meta,
    )

    coll = find_collection_by_name(client, collection_name)
    if coll is None:
        return {"status": "error",
                "error": f"collection not found: {collection_name!r}",
                "collection_name": collection_name}

    if not project_slug:
        project_slug = re.sub(r"[^A-Za-z0-9._-]+", "-", collection_name.strip()).strip("-").lower() or "zotero-project"
    root = Path(project_root) if project_root else PA_DEFAULT_ROOT
    pdir = project_dir(project_slug, root)
    if not pdir.exists():
        return {"status": "error",
                "error": f"local project not found: {pdir} (run `pa zotero project pull --name {collection_name!r}` first)",
                "project_slug": project_slug, "project_path": str(pdir)}
    refs_path = project_files(project_slug, root)["refs"]
    meta_path = project_files(project_slug, root)["meta"]

    diff = diff_collection_to_local(client, coll["key"], refs_path)

    result = {
        "status": "ok",
        "project_slug": project_slug,
        "project_path": str(pdir),
        "dry_run": dry_run,
        "zotero_collection_name": coll["name"],
        "zotero_key": coll["key"],
        "zotero_n_items": diff["zotero_n_items"],
        "local_n_dois": diff["local_n_dois"],
        "n_new": len(diff["new_dois"]),
        "n_removed": len(diff["removed_dois"]),
        "n_unchanged": diff["unchanged_n"],
        "new_dois": diff["new_dois"],
        "removed_dois": diff["removed_dois"],
        "refs_path": str(refs_path),
        "meta_path": str(meta_path),
        "applied": False,
    }

    if dry_run:
        result["status"] = "ok_dry_run"
        return result

    # Apply: append new items to refs.bib
    if diff["new_items"]:
        new_bibtex_entries: List[str] = []
        seen_keys: Set[str] = set()
        for item in diff["new_items"]:
            try:
                bib_str = zotero_item_to_bibtex(item)
            except Exception:
                continue
            if bib_str is None:
                continue
            # Extract cite-key for dedup
            try:
                first_line = bib_str.split("\n", 1)[0]
                cite_key = first_line.split("{", 1)[1].rstrip(",")
            except (IndexError, ValueError):
                cite_key = ""
            if cite_key and cite_key in seen_keys:
                i = 2
                while f"{cite_key}_{i}" in seen_keys:
                    i += 1
                first_line, rest = bib_str.split("\n", 1)
                first_line = first_line.replace("{" + cite_key + ",", "{" + cite_key + f"_{i},")
                bib_str = first_line + "\n" + rest
                cite_key = f"{cite_key}_{i}"
            if cite_key:
                seen_keys.add(cite_key)
            new_bibtex_entries.append(bib_str)

        # Append to refs.bib (preserve existing content)
        existing = refs_path.read_text(encoding="utf-8") if refs_path.exists() else ""
        # Ensure there's a blank line separator
        if existing and not existing.endswith("\n\n"):
            existing = existing.rstrip("\n") + "\n\n"
        appended = "\n\n".join(new_bibtex_entries) + "\n"
        refs_path.write_text(existing + appended, encoding="utf-8")

    # Update meta.json
    meta = load_meta(project_slug, root)
    if not meta:
        meta = {"slug": project_slug, "title": collection_name}
    meta["zotero_collection_version"] = coll.get("version", 0)
    meta["zotero_last_sync_at"] = datetime.now().isoformat(timespec="seconds")
    meta["n_items"] = diff["local_n_dois"] + len(diff["new_dois"])
    if diff["removed_dois"]:
        existing_removed = meta.get("removed_from_zotero", [])
        meta["removed_from_zotero"] = sorted(set(existing_removed) | set(diff["removed_dois"]))
    meta["updated_at"] = datetime.now().isoformat(timespec="seconds")
    save_meta(project_slug, meta, root)

    result["applied"] = True
    result["n_items"] = meta["n_items"]
    return result

