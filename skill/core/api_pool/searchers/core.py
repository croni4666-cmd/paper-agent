"""CORE searcher — direct HTTP client to api.core.ac.uk v3.

Why hand-roll: CORE has no widely-used Python SDK; the API is straightforward
POST-with-JSON-body, ~150 lines of code is enough.

API reference: https://api.core.ac.uk/docs/v3
Auth: Bearer token via env var CORE_API_KEY (read lazily so missing key
       disables the searcher cleanly).

Rate-limit realities (from CORE docs + community experience, 2026-Q3):
  - 1 RPS for free API key
  - 429 → back off 30-60s

CORE does NOT return a DOI for every hit — some have only a CORE id
("12345"). We:
  - Set Paper.doi = provided DOI when present, else None
  - Fall back to title+year dedup in pool._dedupe (already in place)
  - Use Paper.source = "core" so cross-source merging can be tracked
"""

from __future__ import annotations

import os
import time
from typing import List, Optional

import requests

from ..channel import Paper, RateLimitError, Searcher, SortOrder


_BASE = "https://api.core.ac.uk/v3"
_DEFAULT_FIELDS = (
    "title,authors,yearPublished,abstract,doi,downloadUrl,citationCount,"
    "journals,fullText,id"
)
_USER_AGENT = "PaperAgent/1.0 (mailto:{email})"


def _parse_author_list(items: list) -> list:
    """CORE returns authors as [{name: "..."}, ...]."""
    return [(a or {}).get("name") or "" for a in (items or [])]


def _parse_venue(item: dict) -> tuple:
    """CORE returns journals as [{title: "..."}, ...]."""
    journals = item.get("journals") or []
    if not journals:
        return None, None
    title = (journals[0] or {}).get("title")
    return title, "journal"


def _parse_hit(item: dict) -> Paper:
    venue, venue_type = _parse_venue(item)
    pdf_url = item.get("downloadUrl") or None
    return Paper(
        title=item.get("title", "") or "",
        authors=_parse_author_list(item.get("authors", [])),
        doi=item.get("doi") or None,
        arxiv_id=None,  # CORE does not expose arxiv_id in v3 search response
        year=item.get("yearPublished"),
        abstract=item.get("abstract"),
        venue=venue,
        venue_type=venue_type,
        citation_count=int(item.get("citationCount") or 0),
        pdf_url=pdf_url,
        is_oa=bool(item.get("fullText")) and bool(pdf_url),
        source="core",
    )


class CoreSearcher:
    """CORE.ac.uk v3 search (requires CORE_API_KEY in env)."""

    name = "core"

    def __init__(
        self,
        polite_email: str = "researcher@paper-agent.local",
        api_key: Optional[str] = None,
    ):
        self.polite_email = polite_email
        # Read key lazily so unit-tests don't need a real key
        self.api_key = api_key or os.environ.get("CORE_API_KEY")
        self.enabled = bool(self.api_key)
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": _USER_AGENT.format(email=polite_email),
                "Content-Type": "application/json",
            }
        )

    def search(
        self,
        query: str,
        limit: int = 20,
        sort: SortOrder = SortOrder.RELEVANCE,
        year_from: Optional[int] = None,
    ) -> List[Paper]:
        if not self.enabled:
            return []

        # CORE supports Elasticsearch-style `q`. Compose a year filter into
        # the query when year_from is set. Note: CORE's filter syntax uses
        # `field >= value AND query` (no colon between field and operator);
        # the colon form returns 500. Tested 2026-07-03.
        q = query
        if year_from:
            q = f"({query}) AND yearPublished >= {year_from}"

        body = {
            "q": q,
            "limit": min(limit, 50),  # CORE's v3 cap is 100; be conservative
            "offset": 0,
        }

        # Phase 4 convention: do not raise RateLimitError. 1 RPS is slow;
        # on 429 just back off briefly and return [] so the pool can move
        # to the next searcher.
        for attempt in (1, 2):
            try:
                response = self._session.post(
                    f"{_BASE}/search/works",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=body,
                    timeout=30,
                )
            except requests.RequestException:
                if attempt == 2:
                    return []
                continue

            if response.status_code == 429:
                if attempt == 1:
                    time.sleep(15)
                    continue
                return []
            if response.status_code == 401 or response.status_code == 403:
                # Bad key — disable for this session
                self.enabled = False
                return []
            if not response.ok:
                # Any other non-2xx — graceful exit
                return []
            try:
                data = response.json()
            except ValueError:
                return []
            results = (data or {}).get("results") or []
            return [_parse_hit(item) for item in results if item]
        return []

    def get_by_doi(self, doi: str) -> Optional[Paper]:
        """CORE does not have a direct DOI → record fast-path. Use search."""
        if not self.enabled:
            return None
        # Reuse search with the DOI as query; CORE indexes DOIs in the
        # `doi` field so `doi:"10.xxxx/..."` is a valid Elasticsearch term.
        body = {
            "q": f'doi:"{doi}"',
            "limit": 1,
            "offset": 0,
        }
        try:
            response = self._session.post(
                f"{_BASE}/search/works",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=body,
                timeout=30,
            )
        except requests.RequestException:
            return None
        if not response.ok:
            return None
        try:
            data = response.json()
        except ValueError:
            return None
        results = (data or {}).get("results") or []
        if not results:
            return None
        return _parse_hit(results[0])

    def health_check(self) -> bool:
        if not self.enabled:
            return False
        try:
            r = self._session.get(
                f"{_BASE}/search/works",
                headers={"Authorization": f"Bearer {self.api_key}"},
                params={"q": "test", "limit": 1},
                timeout=10,
            )
            return r.status_code == 200
        except Exception:
            return False
