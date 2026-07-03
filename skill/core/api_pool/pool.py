"""SearchPool — unified entry point with cross-searcher fallback + dedupe + cache.

Three responsibilities:
  1. Compose multiple Searcher instances in priority order
  2. Fall back to next searcher on RateLimitError / transient errors
  3. Dedupe results by DOI, merging metadata from multiple sources

Search order (priority for Phase 1):
  1. Crossref (mailto= polite pool, free)
  2. Semantic Scholar (no key, shared pool)
  3. arxiv (no key, infinite)
  4. OpenAlex (only if api_key supplied)
  5. CORE.ac.uk (only if CORE_API_KEY supplied)
"""

from __future__ import annotations

import os
from collections import defaultdict
from typing import List, Optional

from .cache import DiskCache
from .channel import Paper, RateLimitError, SortOrder, Searcher
from .retry import with_retry
from .searchers.core import CoreSearcher
from .searchers.crossref import CrossrefSearcher
from .searchers.openalex import OpenAlexSearcher
from .searchers.semanticscholar import SemanticScholarSearcher
from .searchers.arxiv import ArxivSearcher


class SearchPool:
    """Multi-engine paper search with fallback.

    Usage:
        pool = SearchPool(polite_email="user@example.com")
        papers = pool.search("AI literacy K-12", limit=30)
        long = pool.get_by_doi("10.1145/3313831.3376727")
    """

    def __init__(
        self,
        polite_email: str = "researcher@paper-agent.local",
        openalex_api_key: Optional[str] = None,
        s2_api_key: Optional[str] = None,
        core_api_key: Optional[str] = None,
        cache_dir: str = "./cache/api_pool",
        ttl_days: int = 7,
    ):
        self.searchers: List[Searcher] = [
            CrossrefSearcher(polite_email),  # primary
            SemanticScholarSearcher(polite_email, s2_api_key),  # high-quality
            ArxivSearcher(polite_email),  # preprint / CS
            OpenAlexSearcher(polite_email, openalex_api_key),  # optional
            CoreSearcher(polite_email, core_api_key),  # optional, needs CORE_API_KEY
        ]
        self.cache = DiskCache(cache_dir=cache_dir, ttl_days=ttl_days)
        self.polite_email = polite_email

    def search(
        self,
        query: str,
        limit: int = 20,
        sort: SortOrder = SortOrder.RELEVANCE,
        year_from: Optional[int] = None,
        use_cache: bool = True,
        min_per_source: int = 0,
    ) -> List[Paper]:
        """Cross-searcher search with fallback, dedupe, and cache.

        Phase 4 fix (2026-07-02):
          Added `min_per_source` parameter:
          - 0 (default): stop early once total >= limit (favours Crossref-first
            cheap search)
          - >0: do NOT break early; every searcher is guaranteed to contribute
            >= min_per_source hits (or all hits up to limit). Dedupe output
            is also interleaved so diverse sources survive truncation.
        """
        per_searcher_cap = max(limit, min_per_source) if min_per_source else limit
        cache_key = (
            f"search|{query}|{limit}|{sort.value}|{year_from}|min={min_per_source}"
        )
        if use_cache:
            cached = self.cache.get(cache_key)
            if cached:
                return cached[:limit]

        all_papers: List[Paper] = []
        last_errors: List[str] = []

        for s in self.searchers:
            try:
                papers = with_retry(
                    lambda s=s: s.search(
                        query,
                        limit=per_searcher_cap,
                        sort=sort,
                        year_from=year_from,
                    ),
                    searcher_name=s.name,
                )
                all_papers.extend(papers)
                if min_per_source == 0 and len(all_papers) >= limit:
                    break
            except RateLimitError as e:
                last_errors.append(f"{s.name}:rate-limited({e.retry_after}s)")
                continue
            except Exception as e:
                last_errors.append(f"{s.name}:{type(e).__name__}")
                continue

        deduped = self._dedupe(all_papers)

        # Phase 4 fix (2026-07-03): pure `[:limit]` truncation drops
        # later-iterated sources (Crossref is added first -> OpenAlex papers
        # appended last -> truncated off when limit < total unique). When
        # min_per_source > 0, round-robin to keep diversity.
        if min_per_source > 0 and len(deduped) > limit:
            by_source: dict = defaultdict(list)
            for p in deduped:
                primary = (p.source or "unknown").split("+", 1)[0]
                by_source[primary].append(p)
            result: List[Paper] = []
            order = list(by_source.keys())
            exhausted = set()
            i = 0
            cap = 10 * max(limit, 1)  # defence-in-depth loop bound
            while (
                len(result) < limit
                and len(exhausted) < len(order)
                and i < cap
            ):
                src = order[i % len(order)]
                if src in exhausted or not by_source[src]:
                    exhausted.add(src)
                    i += 1
                    continue
                p = by_source[src].pop(0)
                result.append(p)
                i += 1
            if len(result) < limit:
                for src_papers in by_source.values():
                    for p in src_papers:
                        if len(result) >= limit:
                            break
                        result.append(p)
        else:
            result = deduped[:limit]

        if use_cache and result:
            self.cache.set(cache_key, result)
        return result

    def get_by_doi(self, doi: str, use_cache: bool = True) -> Optional[Paper]:
        """Resolve DOI to Paper by trying each searcher's fast-path method."""
        cache_key = f"doi|{doi}"
        if use_cache:
            cached = self.cache.get(cache_key)
            if cached:
                return cached[0] if cached else None

        for s in self.searchers:
            try:
                paper = with_retry(
                    lambda s=s: s.get_by_doi(doi), searcher_name=s.name
                )
                if paper:
                    if use_cache:
                        self.cache.set(cache_key, [paper])
                    return paper
            except Exception:
                continue
        return None

    def health_summary(self) -> List[bool]:
        return [s.health_check() for s in self.searchers]

    # --- internal ----------------------------------------------------

    @staticmethod
    def _dedupe(papers: List[Paper]) -> List[Paper]:
        """Dedupe by DOI (prefer first, merge metadata from later). Phase 4
        fix (2026-07-03): also dedupe by arxiv_id because arxiv preprints
        in OpenAlex/Crossref get their own DOI (e.g.
        10.48550/arXiv.xxxx.xxxxx) that does NOT match the arxiv-only entry
        from ArxivSearcher.
        """
        by_doi: dict = {}
        by_arxiv: dict = {}
        seen_title_year = set()
        result: List[Paper] = []

        for p in papers:
            if p.arxiv_id:
                if p.arxiv_id in by_arxiv:
                    by_arxiv[p.arxiv_id] = _merge_paper(by_arxiv[p.arxiv_id], p)
                    continue
                by_arxiv[p.arxiv_id] = p
                continue

            if p.doi:
                if p.doi in by_doi:
                    by_doi[p.doi] = _merge_paper(by_doi[p.doi], p)
                else:
                    by_doi[p.doi] = p
            else:
                key = f"{p.title[:60].strip()}|{p.year or 0}"
                if key in seen_title_year:
                    continue
                seen_title_year.add(key)
                result.append(p)

        result = list(by_arxiv.values()) + list(by_doi.values()) + result
        return result


def _merge_paper(a: Paper, b: Paper) -> Paper:
    """Merge metadata from two sources; prefer non-empty / higher counts."""
    return Paper(
        title=a.title or b.title,
        authors=a.authors or b.authors,
        year=a.year or b.year,
        abstract=a.abstract or b.abstract,
        doi=a.doi or b.doi,
        arxiv_id=a.arxiv_id or b.arxiv_id,
        venue=a.venue or b.venue,
        venue_type=a.venue_type or b.venue_type,
        citation_count=max(a.citation_count, b.citation_count),
        references=a.references or b.references,
        is_oa=a.is_oa or b.is_oa,
        pdf_url=a.pdf_url or b.pdf_url,
        source=f"{a.source}+{b.source}",
    )
