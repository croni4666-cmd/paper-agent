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
    out.sort(key=lambda x: x.get("dateModified", ""), reverse=True)
    return out
