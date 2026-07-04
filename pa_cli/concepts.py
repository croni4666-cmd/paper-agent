"""pa_cli.concepts — OpenAlex concept lookup + work filter helpers.

[ P1-2 ] (ROADMAP.md): semantic filtering for pa search.

Three entry points:
  - search_concepts(query, limit) — text→list of {id, name, level, works_count}
  - resolve_concept_ids(names_or_ids) — mixed input: IDs pass through, names
    are looked up. Returns canonical list of OpenAlex C<id> strings.
  - build_concepts_filter(ids, mode) — produces the OpenAlex filter string
    for use in `pa search` URL construction.

Concept search uses OpenAlex's `/concepts?search=<text>` endpoint. The
endpoint does full-text search across concept names + descriptions, with
multi-word queries returning more matches than single-word (verified
2026-07-04: "higher education"→11 results, "AI literacy"→0 results since
"AI literacy" isn't a registered OpenAlex concept).
"""

from __future__ import annotations

import logging
import os
import re
from typing import List, Dict, Optional, Tuple
from urllib.parse import quote

from .search import http_get_json


log = logging.getLogger(__name__)

OPENALEX_BASE = "https://api.openalex.org"
CONCEPT_ID_PATTERN = re.compile(r"^C\d+$", re.IGNORECASE)


def _api_key_suffix(sep: str = "&") -> str:
    """Append OPENALEX_API_KEY to URL (faster rate limit when set)."""
    key = os.environ.get("OPENALEX_API_KEY")
    if key:
        return f"{sep}api_key={quote(key, safe='')}"
    return ""


def search_concepts(query: str, limit: int = 5) -> List[Dict]:
    """Search OpenAlex concepts by text query.

    Returns list of dicts: [{id, display_name, level, works_count}, ...]
    sorted by works_count desc (most-used first).

    Note: short/specific terms may return 0 (e.g. "AI literacy" not in
    OpenAlex concept vocabulary). User can supply IDs directly instead.
    """
    if not query or not query.strip():
        return []
    url = f"{OPENALEX_BASE}/concepts?search={quote(query.strip())}&per-page={min(limit, 50)}"
    url += _api_key_suffix("&")
    status, data = http_get_json(url, timeout=20)
    if status != 200:
        log.warning(f"concept search failed: status={status}")
        return []
    results = data.get("results", [])
    normalised = []
    for r in results:
        normalised.append({
            "id": r.get("id", ""),  # e.g. "https://openalex.org/C154945302"
            "concept_id": _short_id(r.get("id", "")),  # e.g. "C154945302"
            "display_name": r.get("display_name", ""),
            "level": r.get("level"),
            "works_count": r.get("works_count", 0) or 0,
        })
    # Sort by works_count desc (most useful first)
    normalised.sort(key=lambda x: x["works_count"], reverse=True)
    return normalised[:limit]


def _short_id(oa_url: str) -> str:
    """Convert 'https://openalex.org/C123' to 'C123'."""
    return oa_url.replace("https://openalex.org/", "")


def is_concept_id(s: str) -> bool:
    """True if s looks like an OpenAlex concept ID (C<digits>)."""
    if not s:
        return False
    return bool(CONCEPT_ID_PATTERN.match(s.strip()))


def resolve_concept_ids(names_or_ids: List[str]) -> Tuple[List[str], List[Dict]]:
    """Resolve a mixed list of concept IDs + names to canonical C<id> list.

    Args:
        names_or_ids: list of strings; each is either a C<id> (passes through)
                       or a free-text name (looked up via search_concepts)

    Returns:
        (canonical_ids, unresolved_warnings)
        - canonical_ids: list of "C<digits>" strings (deduplicated, in input order)
        - unresolved_warnings: list of {input, reason} dicts for inputs that
          didn't resolve (name with 0 results)
    """
    canonical: List[str] = []
    seen = set()
    warnings: List[Dict] = []

    for raw in names_or_ids:
        s = (raw or "").strip()
        if not s:
            continue
        if is_concept_id(s):
            if s.upper() not in seen:
                canonical.append(s.upper())
                seen.add(s.upper())
            continue
        # Treat as name; look up
        results = search_concepts(s, limit=1)
        if not results:
            warnings.append({"input": s, "reason": "no_concept_match"})
            continue
        cid = results[0]["concept_id"]
        if cid and cid not in seen:
            canonical.append(cid)
            seen.add(cid)
    return canonical, warnings


def build_concepts_filter(concept_ids: List[str], mode: str = "or") -> str:
    """Build OpenAlex filter string for concept filtering.

    Args:
        concept_ids: list of "C<digits>" strings (already resolved + canonical)
        mode: "or" (default) or "and"
            - or:  concepts.id:C1|C2|C3 (work has any of the concepts)
            - and: concepts.id:C1+concepts.id:C2 (work has all of the concepts)

    Returns:
        The complete filter value to pass to OpenAlex's `filter=` param.
        Returns empty string if concept_ids is empty.
    """
    if not concept_ids:
        return ""
    if mode not in ("or", "and"):
        raise ValueError(f"mode must be 'or' or 'and', got {mode!r}")
    if mode == "or":
        # OR syntax: pipe-separated IDs in a single concepts.id filter
        return f"concepts.id:{'|'.join(concept_ids)}"
    # AND: separate concepts.id filter expressions joined with +
    # Note: OpenAlex uses + for AND between filter expressions, encoded as %2B
    # in URLs, but urllib handles this if we pass `+` literal then encode.
    return "+".join(f"concepts.id:{c}" for c in concept_ids)


def fetch_concept_metadata(concept_id: str) -> Optional[Dict]:
    """Look up a single concept by ID. Returns dict or None."""
    cid = concept_id.strip()
    if not is_concept_id(cid):
        return None
    url = f"{OPENALEX_BASE}/concepts/{cid}{_api_key_suffix('?')}"
    status, data = http_get_json(url, timeout=20)
    if status != 200:
        return None
    return {
        "concept_id": _short_id(data.get("id", "")),
        "display_name": data.get("display_name", ""),
        "level": data.get("level"),
        "works_count": data.get("works_count", 0) or 0,
        "description": (data.get("description") or "")[:200],
    }
