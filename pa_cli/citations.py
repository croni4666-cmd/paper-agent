"""pa_cli.citations — Forward + backward citation walk via OpenAlex.

Implements [P1-1] (ROADMAP.md):

  forward  →  papers that cite the given DOI   (via filter=cites:W<id>)
  backward →  papers that the given DOI cites (via referenced_works[])

OpenAlex API:
  - Look up DOI: GET /works/doi:<doi> → {id: "https://openalex.org/W<id>", referenced_works[], ...}
  - Forward: GET /works?filter=cites:W<id>&cursor=<cursor>&per-page=<n>
    Cursor-paginated; meta.next_cursor drives the loop.
  - Backward: each entry in referenced_works[] is "https://openalex.org/W<id>".
    Each requires a separate GET /works/W<id> to fetch metadata. Bounded by --limit.

Note (verified 2026-07-04): OpenAlex `cites` filter accepts ONLY OpenAlex IDs
(W-prefixed), NOT DOIs in any form. Direct DOI URL in filter returns 0 results.

Limits & safety:
  - default cap: 100 forward, 50 backward (per --limit flag override)
  - per-page=200 max for forward (OpenAlex hard cap); default 50 per page
  - 30s timeout per request
  - errors caught per-page (skips to next cursor, logs stderr)
"""

from __future__ import annotations

import logging
import os
from typing import List, Dict, Optional, Any
from urllib.parse import quote

from .search import http_get_json, _normalize_openalex


log = logging.getLogger(__name__)


OPENALEX_BASE = "https://api.openalex.org"


def _api_key_suffix(sep: str = "&") -> str:
    """Append OPENALEX_API_KEY to URL if set in env (free tier: 1 RPS without, faster with).

    sep: '&' when URL already has '?', '?' otherwise.
    """
    key = os.environ.get("OPENALEX_API_KEY")
    if key:
        return f"{sep}api_key={quote(key, safe='')}"
    return ""


def _strip_openalex_url(oa_url: str) -> str:
    """Convert 'https://openalex.org/W123' to 'W123' (for filter=)."""
    return oa_url.replace("https://openalex.org/", "")


def get_work_by_doi(doi: str) -> Optional[dict]:
    """Resolve DOI to OpenAlex work dict.

    Returns dict with `id`, `doi`, `title`, `cited_by_count`, `referenced_works`,
    etc. — or None if not found / 404.
    """
    url = f"{OPENALEX_BASE}/works/doi:{quote(doi, safe='/:')}{_api_key_suffix('?')}"
    status, data = http_get_json(url, timeout=30)
    if status != 200:
        return None
    return data


def get_citing(doi: str, limit: int = 100, per_page: int = 50) -> List[Dict]:
    """Forward citation walk: papers that cite `doi`.

    Cursor-paginated; stops when meta.next_cursor is None or limit reached.
    Returns normalised paper dicts (same shape as `search.run_search` outputs).
    """
    # Step 1: resolve DOI to OpenAlex ID
    work = get_work_by_doi(doi)
    if not work:
        log.warning(f"DOI {doi} not found in OpenAlex; no citations possible")
        return []
    oa_id = work.get("id", "")
    if not oa_id:
        return []
    short_id = _strip_openalex_url(oa_id)

    # Step 2: paginate via cursor
    results: List[Dict] = []
    cursor = "*"  # "*" = initial cursor
    pages = 0
    while cursor and len(results) < limit:
        url = (
            f"{OPENALEX_BASE}/works?filter=cites:{short_id}"
            f"&per-page={per_page}&cursor={quote(cursor, safe='')}"
            f"{_api_key_suffix('&')}"
        )
        status, data = http_get_json(url, timeout=60)
        if status != 200:
            log.warning(f"cites page fetch failed: status={status}, cursor={cursor[:20]}")
            break
        for r in data.get("results", []):
            normalised = _normalize_openalex(r)
            if normalised.get("doi"):
                results.append(normalised)
                if len(results) >= limit:
                    break
        cursor = data.get("meta", {}).get("next_cursor")
        pages += 1
    return results


def get_referenced(doi: str, limit: int = 50) -> List[Dict]:
    """Backward citation walk: papers that `doi` cites.

    Two-step:
      1. GET /works/doi:<doi> → read referenced_works[] (list of OpenAlex URLs)
      2. For each W<id>, GET /works/W<id> → full metadata

    Bounded by --limit (default 50; max ~100 recommended). Higher limits mean
    N+1 API calls — use sparingly.
    """
    # Step 1
    work = get_work_by_doi(doi)
    if not work:
        log.warning(f"DOI {doi} not found in OpenAlex; no references possible")
        return []
    refs = work.get("referenced_works", [])
    if not refs:
        return []
    refs = refs[:limit]

    # Step 2: fetch each
    results: List[Dict] = []
    for oa_url in refs:
        if not oa_url:
            continue
        short_id = _strip_openalex_url(oa_url)
        url = f"{OPENALEX_BASE}/works/{short_id}{_api_key_suffix('?')}"
        status, data = http_get_json(url, timeout=30)
        if status != 200:
            log.warning(f"referenced work fetch failed: id={short_id}, status={status}")
            continue
        normalised = _normalize_openalex(data)
        if normalised.get("doi") or normalised.get("title"):
            results.append(normalised)
    return results


def citation_walk(doi: str, direction: str = "forward", limit: int = 100) -> dict:
    """Top-level citation walk.

    Args:
        doi: target paper DOI
        direction: "forward" (citing) or "backward" (referenced)
        limit: max papers to return (default 100; 50 for backward recommended)

    Returns:
        {
          "doi": input DOI,
          "direction": "forward"|"backward",
          "source_work": <source paper metadata dict>,
          "results": [<normalised paper dict>...],
          "count": int,
          "truncated": bool,  # True if hit limit
        }
    """
    direction = direction.lower()
    if direction not in ("forward", "backward"):
        return {"error": f"unknown direction: {direction!r}",
                "available": ["forward", "backward"]}

    source = get_work_by_doi(doi)
    if not source:
        return {"error": "doi_not_found", "doi": doi}

    src_meta = _normalize_openalex(source)
    src_meta["openalex_id"] = source.get("id", "")

    if direction == "forward":
        papers = get_citing(doi, limit=limit)
    else:
        papers = get_referenced(doi, limit=limit)

    return {
        "doi": doi,
        "direction": direction,
        "source_work": src_meta,
        "results": papers,
        "count": len(papers),
        "truncated": len(papers) >= limit,
    }