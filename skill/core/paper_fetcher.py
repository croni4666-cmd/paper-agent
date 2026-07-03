"""
Paper Agent Skill - multi-channel paper fetcher (Phase 4 rewrite)

History:
  v3.x — 6-channel hand-roll (urllib + regex)
  v4.0 — Refactor to SearchPool backend (Phase 4: 2026-07-02)

Active backend: skill.core.api_pool (SearchPool + PDFPool).
The v3.x hand-roll implementations are kept in `_legacy_handroll.py`
(legacy module).  This module preserves the v3.x *external* API so
that callers like `pipeline.py` don't have to change.

External API (UNCHANGED):
  fetch_arxiv(query)             → List[Dict]
  fetch_openalex(query, concepts) → List[Dict]
  fetch_semanticscholar(query)   → List[Dict]
  fetch_eric(query)              → List[Dict]  (via OpenAlex Education concepts)
  fetch_doaj(query)              → List[Dict]
  fetch_core(query, api_key)     → List[Dict]
  fetch_all_channels(query, channels) → Dict[channel_name, List[Dict]]
  dedup_papers(papers, by)       → List[Dict]
"""
import urllib.request
import urllib.error
import ssl
import json
import time
import re
import os
from typing import List, Dict, Optional
from pathlib import Path

# Imports from the new api_pool (Phase 4).  Falls back to legacy hand-roll
# if the new module is not importable (e.g. fresh clone before pip install).
try:
    from .api_pool import (
        SearchPool,
        Paper as _Paper,
        SortOrder,
    )
    from .api_pool.searchers.arxiv import ArxivSearcher
    from .api_pool.searchers.openalex import OpenAlexSearcher
    from .api_pool.searchers.semanticscholar import SemanticScholarSearcher
    from .api_pool.searchers.crossref import CrossrefSearcher
    _HAS_SEARCH_POOL = True
except Exception as _e:
    _HAS_SEARCH_POOL = False
    _SEARCH_POOL_ERR = str(_e)

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

UA_OPENALEX = {'User-Agent': 'mailto:researcher@paper-agent.local (Mavis/1.0)'}
UA_BROWSER = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*',
}


# ============================================================
# Phase 4 backend glue: SearchPool ↔ legacy Dict shape
# ============================================================
_POOL_CACHE = {}


def _get_search_pool(api_keys: Optional[Dict] = None) -> 'SearchPool':
    """Return a memoised SearchPool (created on first call)."""
    if 'default' not in _POOL_CACHE:
        if not _HAS_SEARCH_POOL:
            raise RuntimeError(
                f"api_pool not importable: {_SEARCH_POOL_ERR}. "
                "Run: pip install habanero pyalex arxiv"
            )
        openalex_key = (api_keys or {}).get('openalex')
        s2_key = (api_keys or {}).get('s2') or os.environ.get('S2_API_KEY')
        core_key = (api_keys or {}).get('core') or os.environ.get('CORE_API_KEY')
        _POOL_CACHE['default'] = SearchPool(
            polite_email='researcher@paper-agent.local',
            openalex_api_key=openalex_key,
            s2_api_key=s2_key,
            core_api_key=core_key,
            cache_dir='./cache/api_pool',
            ttl_days=7,
        )
    return _POOL_CACHE['default']


def _paper_to_dict(p, source_override: Optional[str] = None) -> Dict:
    """Convert new-style Paper dataclass to the legacy dict shape expected
    by pipeline.py and other callers.
    """
    # Authors: prefer new shape (list[str]), but legacy callers expect list[dict]
    authors_list = []
    for a in (p.authors or []):
        # Authors may be either a string (SearchPool Paper) or dict (legacy)
        if isinstance(a, str):
            authors_list.append({'name': a, 'affiliation': ''})
        elif isinstance(a, dict):
            authors_list.append(a)
        else:
            authors_list.append({'name': str(a), 'affiliation': ''})

    doi = (p.doi or '').lower().strip()
    return {
        'doi': doi,
        'arxiv_id': p.arxiv_id or '',
        'title': p.title or '',
        'abstract': p.abstract or '',
        'authors': authors_list,
        'year': p.year,
        'venue': p.venue or '',
        'cited_by_count': p.citation_count or 0,
        'source': source_override or p.source or '',
        'pdf_url': p.pdf_url or '',
    }


def _http_get(url, headers=None, timeout=30):
    """统一 HTTP GET"""
    h = {**(headers or {})}
    try:
        req = urllib.request.Request(url, headers=h)
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
            return resp.read().decode('utf-8', errors='ignore')
    except Exception as e:
        return None


def restore_abstract(inv):
    """还原 OpenAlex abstract_inverted_index"""
    if not inv or not isinstance(inv, dict):
        return ''
    positions = {}
    for word, locs in inv.items():
        for loc in locs:
            positions[loc] = word
    if not positions:
        return ''
    max_pos = max(positions.keys())
    words = [' '] * (max_pos + 1)
    for pos, word in positions.items():
        if pos < len(words):
            words[pos] = word
    return ' '.join(words).strip()


# ============================================================
# arxiv
# ============================================================
def fetch_arxiv(query: str, max_results: int = 50) -> List[Dict]:
    """arxiv search (Phase 4: backend = ArxivSearcher direct)."""
    if _HAS_SEARCH_POOL:
        try:
            from .api_pool.searchers.arxiv import ArxivSearcher
            s = _get_searcher(ArxivSearcher)
            papers = s.search(query, limit=max_results)
            return [_paper_to_dict(p, source_override='arxiv') for p in papers]
        except Exception:
            pass
    return []


# ============================================================
# semanticscholar
# ============================================================
def fetch_semanticscholar(query: str, max_results: int = 50) -> List[Dict]:
    """Semantic Scholar search (Phase 4: backend = SemanticScholarSearcher)."""
    if _HAS_SEARCH_POOL:
        try:
            from .api_pool.searchers.semanticscholar import SemanticScholarSearcher
            from .api_pool.channel import RateLimitError
            s = _get_searcher(SemanticScholarSearcher)
            papers = s.search(query, limit=max_results)
            if papers:
                return [_paper_to_dict(p, source_override='semanticscholar') for p in papers]
        except RateLimitError:
            pass
        except Exception:
            pass
    return []


# ============================================================
# eric (via OpenAlex Education concept) — convenience wrapper
# ============================================================
def fetch_eric(query: str, max_results: int = 30) -> List[Dict]:
    """ERIC fallback to OpenAlex Education concept filter."""
    return fetch_openalex(query, max_results=max_results,
                          concepts=['C36727532', 'C16443162', 'C120912362', 'C19417346'])


# Lazy searcher cache (separate from pool)
_SEARCHER_CACHE = {}


def _get_searcher(cls):
    """Memoised searcher instance factory."""
    key = cls.__name__
    if key not in _SEARCHER_CACHE:
        polite = 'researcher@paper-agent.local'
        # OpenAlexSearcher takes api_key argument; pass if available
        if cls.__name__ == 'OpenAlexSearcher':
            openalex_key = os.environ.get('OPENALEX_API_KEY')
            _SEARCHER_CACHE[key] = cls(polite_email=polite, api_key=openalex_key)
        else:
            _SEARCHER_CACHE[key] = cls(polite_email=polite)
    return _SEARCHER_CACHE[key]

# ============================================================
# openalex
# ============================================================
def fetch_openalex(query: str, max_results: int = 50, concepts: Optional[List[str]] = None) -> List[Dict]:
    """OpenAlex search.

    Phase 4 backend: OpenAlexSearcher direct. When the SearchPool is disabled
    (no key) or returned zero, falls back to a urllib Polite-pool lookup.
    """
    if _HAS_SEARCH_POOL and concepts is None:
        try:
            from .api_pool.searchers.openalex import OpenAlexSearcher
            s = _get_searcher(OpenAlexSearcher)
            papers = s.search(query, limit=max_results)
            if papers:
                return [_paper_to_dict(p, source_override='openalex') for p in papers]
        except Exception:
            pass
    # Fallback: urllib-based polite lookup (works without API key)
    return _urllib_openalex(query, max_results, concepts)


def _urllib_openalex(query: str, max_results: int, concepts: Optional[List[str]]) -> List[Dict]:
    """Tiny urllib-based OpenAlex fallback for when pyalex is unavailable
    or no key is configured. Best-effort: respects mailto= User-Agent.
    """
    import urllib.request, urllib.parse, json, ssl
    ctx = ssl.create_default_context()
    url = (
        f'https://api.openalex.org/works?search='
        f'{urllib.parse.quote(query)}&per_page={max_results}'
    )
    if concepts:
        url += f"&filter=concepts.id:{'|'.join(concepts)}"
    try:
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'mailto:researcher@paper-agent.local (Mavis/1.0)'},
        )
        with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
            data = json.loads(r.read())
    except Exception:
        return []
    papers = []
    for w in data.get('results', []):
        doi = (w.get('doi') or '').lower().replace('https://doi.org/', '')
        authors = [
            (a.get('author') or {}).get('display_name', '')
            for a in (w.get('authorships') or [])
        ]
        venue = ''
        pl = w.get('primary_location') or {}
        if pl.get('source'):
            venue = (pl['source'] or {}).get('display_name', '')
        papers.append({
            'doi': doi,
            'title': w.get('title') or w.get('display_name') or '',
            'authors': [{'name': a, 'affiliation': ''} for a in authors],
            'year': w.get('publication_year'),
            'venue': venue,
            'cited_by_count': w.get('cited_by_count', 0),
            'source': 'openalex',
        })
    return papers


def dedup_papers(all_papers: List[Dict], by: str = 'doi_or_title') -> List[Dict]:
    """去重论文
    
    by: 'doi' (按 DOI) | 'title' (按 title 前 60 字) | 'doi_or_title' (任一)
    """
    seen_doi = set()
    seen_title = set()
    unique = []
    
    for p in all_papers:
        doi = (p.get('doi') or '').lower().strip()
        title = (p.get('title') or '')[:60].lower().strip()
        
        is_dup = False
        if by in ('doi', 'doi_or_title') and doi:
            if doi in seen_doi:
                is_dup = True
            else:
                seen_doi.add(doi)
        
        if not is_dup and by in ('title', 'doi_or_title'):
            if title and title in seen_title:
                is_dup = True
            elif title:
                seen_title.add(title)
        
        if not is_dup:
            unique.append(p)

    return unique


# ============================================================
# Phase 4: SearchPool-backed unified search (preferred over fetch_all_channels)
# ============================================================

def search_with_searchpool(
    query: str,
    max_per_channel: int = 50,
    openalex_api_key: Optional[str] = None,
    polite_email: str = 'researcher@paper-agent.local',
    use_cache: bool = True,
    min_per_source: int = 0,
) -> Dict[str, List[Dict]]:
    """Search via SearchPool; return channel-keyed dict compatible with the
    legacy fetch_all_channels() shape.

    Each searcher (crossref / semanticscholar / arxiv / openalex) becomes one
    channel entry.  Channels with no results are simply omitted.

    Usage in pipeline.py:
        channel_results = search_with_searchpool(query, max_per_channel=30)
        # channel_results is Dict[channel_name, List[Dict]] — same as fetch_all_channels
    """
    if not _HAS_SEARCH_POOL:
        raise RuntimeError(
            'api_pool unavailable — falling back to fetch_all_channels via caller'
        )
    if 'pool_with_oa' not in _POOL_CACHE:
        _POOL_CACHE['pool_with_oa'] = SearchPool(
            polite_email=polite_email,
            openalex_api_key=openalex_api_key or os.environ.get('OPENALEX_API_KEY'),
            s2_api_key=os.environ.get('S2_API_KEY'),
            core_api_key=os.environ.get('CORE_API_KEY'),
            cache_dir='./cache/api_pool',
            ttl_days=7,
        )
    pool = _POOL_CACHE['pool_with_oa']
    papers = pool.search(
        query, limit=max_per_channel,
        use_cache=use_cache,
        min_per_source=min_per_source,
    )

    # Split by source so legacy Dict shape is preserved
    channel_results: Dict[str, List[Dict]] = {}
    for p in papers:
        ch = p.source or 'unknown'
        channel_results.setdefault(ch, [])
        channel_results[ch].append(_paper_to_dict(p))
    return channel_results


__all__ = [
    'fetch_arxiv',
    'fetch_openalex',
    'fetch_semanticscholar',
    'fetch_eric',
    'fetch_doaj',
    'fetch_core',
    'fetch_all_channels',         # legacy (kept for compatibility)
    'search_with_searchpool',    # Phase 4 preferred
    'dedup_papers',
    '_paper_to_dict',
    'SearchPool',                # re-export
    'PDFPool',                   # re-export (Phase 4)
    'PDFPoolConfig',
    'PDFDownloadResult',
]  # end __all__