"""Semantic Scholar searcher — direct HTTP client.

Why hand-roll: S2 has no official Python SDK.
Reference: allenai/s2-folks (278 stars) community space provides examples.

Rate-limit realities (from https://www.semanticscholar.org/product/api):
  - "Most endpoints are available without authentication"
  - "rate-limited to 1000 RPS shared among all unauthenticated users"
  - "API key intro rate: 1 RPS on all endpoints"  (so key is worse for raw RPS!)
  - "Requests may also be further throttled during periods of heavy use"

Phase 6 update (2026-07-03): S2 API key integration. Two modes:
  - No key: shared pool (heavily throttled, default behavior in v3.0.1)
  - With key: 1 RPS dedicated pool (consistent, no shared-pool noise).
  Key path: S2_API_KEY env var, read lazily.
"""

from __future__ import annotations

import os
import time
from typing import List, Optional

import requests

from ..channel import Paper, RateLimitError, Searcher, SortOrder


_BASE = "https://api.semanticscholar.org/graph/v1"
_DEFAULT_FIELDS = (
    "title,authors,year,abstract,venue,citationCount,externalIds,"
    "openAccessPdf,journal,publicationTypes,publicationDate"
)
_USER_AGENT = "PaperAgent/1.0 (mailto:{email})"


def _parse_author_list(items: list) -> list:
    return [(a or {}).get("name") or "" for a in (items or [])]


def _parse_hit(item: dict) -> Paper:
    ext = item.get("externalIds") or {}
    pdf = item.get("openAccessPdf") or {}
    return Paper(
        title=item.get("title", "") or "",
        authors=_parse_author_list(item.get("authors", [])),
        doi=ext.get("DOI"),
        arxiv_id=ext.get("ArXiv"),
        year=item.get("year"),
        abstract=item.get("abstract"),
        venue=item.get("venue"),
        citation_count=int(item.get("citationCount") or 0),
        pdf_url=pdf.get("url"),
        is_oa=bool(pdf.get("url")),
        source="semanticscholar",
    )


class SemanticScholarSearcher:
    """S2 search — paper abstract search.

    Two modes:
      - No key: shared anonymous pool (1 RPS shared across all users, often
        throttled in practice — see v3.0.1 Phase 4 fix).
      - With key: 1 RPS dedicated pool (consistent, predictable).
    """

    name = "semanticscholar"

    def __init__(
        self,
        polite_email: str = "researcher@paper-agent.local",
        api_key: Optional[str] = None,
    ):
        self.polite_email = polite_email
        # Read key lazily so unit tests / no-key setups don't fail
        self.api_key = api_key or os.environ.get("S2_API_KEY")
        self._session = requests.Session()
        headers = {"User-Agent": _USER_AGENT.format(email=polite_email)}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        self._session.headers.update(headers)

    def search(
        self,
        query: str,
        limit: int = 20,
        sort: SortOrder = SortOrder.RELEVANCE,
        year_from: Optional[int] = None,
    ) -> List[Paper]:
        # Phase 6 fix (2026-07-03): S2 with key still throttles — diagnostic
        # showed 1 RPS is *sustained* not burst; a 4s follow-up still 429s.
        # Bump backoff 15s → 30s and add a 3rd retry (60s) so the searcher
        # gives S2 real recovery time on warm-up / heavy-load windows.
        # Total worst case: 30s + 60s = 90s before giving up cleanly.
        # Still returns [] (not raise) so SearchPool moves on to other engines.
        params = {
            "query": query,
            "limit": min(limit, 100),
            "fields": _DEFAULT_FIELDS,
        }
        if year_from:
            params["year"] = f"{year_from}-2099"

        backoffs = (30, 60)  # 1st retry waits 30s, 2nd waits 60s
        for attempt in range(3):  # initial + 2 retries
            try:
                response = self._session.get(
                    f"{_BASE}/paper/search", params=params, timeout=30
                )
            except requests.RequestException:
                if attempt >= 2:
                    return []
                time.sleep(backoffs[attempt])
                continue

            if response.status_code == 429:
                if attempt < 2:
                    time.sleep(backoffs[attempt])
                    continue
                return []
            response.raise_for_status()
            data = response.json().get("data", []) or []
            return [_parse_hit(item) for item in data if item]
        return []

    def get_by_doi(self, doi: str) -> Optional[Paper]:
        url = f"{_BASE}/paper/DOI:{doi}"
        params = {"fields": _DEFAULT_FIELDS}
        try:
            response = self._session.get(url, params=params, timeout=30)
        except requests.RequestException:
            return None
        if response.status_code == 404:
            return None
        if response.status_code == 429:
            raise RateLimitError(self.name, 60, "by-DOI throttle")
        response.raise_for_status()
        json_data = response.json()
        if not json_data.get("paperId"):
            return None
        return _parse_hit(json_data)

    def health_check(self) -> bool:
        try:
            r = self._session.get(
                f"{_BASE}/paper/search",
                params={"query": "test", "limit": 1, "fields": "paperId,title"},
                timeout=10,
            )
            if r.status_code != 200:
                return False
            data = r.json().get("data", [])
            return isinstance(data, list)
        except Exception:
            return False
