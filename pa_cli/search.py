"""
pa_cli.search — 6+1-engine academic paper search.

Engines: Crossref, Semantic Scholar, arXiv, OpenAlex, AMiner, CNKI (optional).
Wraps the existing paper-agent v3.1 SearchPool pattern. Falls back gracefully
on per-engine failure.

v3.9.8.2 (2026-07-15): CORE removed from default "all" list — OpenAlex already
indexes CORE's repos, so the marginal coverage was <5% but maintenance cost
(buggy key auth path) was real. search_core() function still available via
`pa search --engine core` for explicit use, and now works in no-key mode.

AMiner (added v3.9.8.0): 6th default engine for Chinese papers, gated on
AMINER_API_KEY env var (体验金 3880 calls / 60 days). +10.9pp cite lift
on Chinese queries vs baseline 4 engines.

CNKI (added v3.9.7.3): 7th engine for Chinese papers, gated on cookies file
existence. See pa_cli.cnki_channel for setup details.
"""

import json
import os
import sys
import time
from typing import List, Dict, Optional, Any
from urllib.parse import quote
import urllib.request as ur
import urllib.error


UA = "paper-agent/3.2 (Mavis; mailto:hello@example.com)"
# v3.9.8.0: 用真实 browser UA 避免 Cloudflare/DDoS-Guard 拦截 (CORE API 之前 1010)
UA_BROWSER = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def http_get_json(url: str, headers: dict = None, timeout: int = 30) -> tuple:
    h = {"User-Agent": UA_BROWSER,
         "Accept": "application/json",
         "Accept-Language": "en-US,en;q=0.9",
         "Accept-Encoding": "gzip, deflate, br"}
    if headers:
        h.update(headers)
    req = ur.Request(url, headers=h)
    try:
        with ur.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8", errors="ignore"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8", errors="ignore"))
        except Exception:
            return e.code, {}
    except Exception:
        return 0, {}


# ──────────────────────────────────────────────────────────────────────
# Top-N deep enrichment (v3.9.7.8)
# For papers lacking cite/abstract, do "second-hop" lookups:
#   - If has DOI → query S2 `paper/DOI:...` (returns full tldr/inf_cite)
#   - If no DOI → query Crossref by title (returns DOI + cite)
# Used to lift Chinese-paper cite coverage from 21% (search-only) to ~40-50%.
# ──────────────────────────────────────────────────────────────────────

# Known S2 placeholder strings for tldr filter (same as dedup loop)
S2_TLDR_PLACEHOLDERS = (
    "It's time to dust off the gloves",
    "It\u2019s time to dust off the gloves",
    "It's time to dust off the sledgehammers",
    "It\u2019s time to dust off the sledgehammers",
)


def _s2_lookup_doi(doi: str) -> Optional[Dict]:
    """Semantic Scholar paper/DOI endpoint — returns full metadata for one paper.

    S2 free tier: 1 RPS. Caller must jitter (use 1.0-1.5s between calls).
    """
    if not doi:
        return None
    url = (f"https://api.semanticscholar.org/graph/v1/paper/DOI:{quote(doi, safe='/:')}"
           f"?fields=title,abstract,tldr,citationCount,influentialCitationCount,"
           f"referenceCount,authors,venue,year,externalIds,openAccessPdf,publicationTypes")
    headers = {"User-Agent": UA}
    api_key = os.environ.get("S2_API_KEY")
    if api_key:
        headers["x-api-key"] = api_key
    s, data = http_get_json(url, headers=headers, timeout=15)
    if s != 200 or not data or not data.get("paperId"):
        return None
    # Convert to our normalized result shape (subset)
    ext = data.get("externalIds") or {}
    oa = data.get("openAccessPdf") or {}
    tldr_obj = data.get("tldr") or {}
    tldr_text = tldr_obj.get("text", "") if isinstance(tldr_obj, dict) else ""
    tldr_text = tldr_text or ""  # guard against None
    # Filter known S2 "no tldr" placeholders
    is_placeholder = any(tldr_text.startswith(p) for p in S2_TLDR_PLACEHOLDERS)
    return {
        "doi": ext.get("DOI", doi),
        "title": data.get("title", ""),
        "authors": [a.get("name", "") for a in (data.get("authors") or [])],
        "venue": data.get("venue", ""),
        "year": data.get("year"),
        "abstract": data.get("abstract", ""),
        "tldr": "" if is_placeholder else tldr_text,
        "cited_by_count": data.get("citationCount", 0),
        "influential_cite_count": data.get("influentialCitationCount", 0),
        "reference_count": data.get("referenceCount", 0),
        "is_oa": bool(oa.get("url")),
        "oa_url": oa.get("url"),
        "source": "semanticscholar_doi",
    }


def _crossref_lookup_title(title: str) -> Optional[Dict]:
    """Crossref works?query.bibliographic — finds DOI + cite by title.

    Best-effort: returns top-1 match. Crossref free tier is generous (50 RPS).
    """
    if not title or len(title) < 10:
        return None
    url = (f"https://api.crossref.org/works?query.bibliographic={quote(title)}"
           f"&rows=1&select=DOI,title,author,abstract,container-title,"
           f"is-referenced-by-count,references-count,published-print")
    s, data = http_get_json(url, headers={}, timeout=15)
    if s != 200 or not data.get("message") or not data["message"].get("items"):
        return None
    it = data["message"]["items"][0]
    pub = it.get("published-print") or it.get("published-online") or {}
    parts = pub.get("date-parts", [[None]])[0]
    year = parts[0] if parts else None
    return {
        "doi": it.get("DOI", ""),
        "title": it.get("title", [""])[0] if isinstance(it.get("title"), list) else it.get("title", ""),
        "authors": [f"{a.get('family','')}, {a.get('given','')}".strip(", ")
                    for a in (it.get("author") or [])],
        "venue": (it.get("container-title") or [""])[0] if it.get("container-title") else "",
        "year": year,
        "abstract": it.get("abstract", ""),
        "cited_by_count": it.get("is-referenced-by-count", 0),
        "reference_count": it.get("references-count", 0),
        "source": "crossref_title",
    }


def enrich_top_n(results: List[Dict], n: int = 10, min_cites: int = 1) -> List[Dict]:
    """Top-N deep enrichment (v3.9.7.8; [P1-14] min_cites added 2026-07-16).

    For each result in top-N that lacks cite/abstract, do second-hop lookups:
    1. If has DOI: call S2 paper/DOI for full data (tldr/inf_cite/ref_count)
    2. If no DOI: call Crossref by title to find DOI + cite

    Updates results in-place AND returns them. Adds `_enrichment` field
    per paper documenting which lookups succeeded.

    Jitter: 1.2s between S2 calls (1 RPS free), 0.05s between Crossref calls.

    Args:
        results: list of result dicts (will be sorted by cited_by_count, so
                 top-N is the most-cited papers; closest to "user's interest")
        n: how many top papers to enrich (default 10)
        min_cites: skip S2 lookup for papers with cited_by_count < min_cites
            (default 1 = skip 0-cite papers). Per [P1-14] ROADMAP: when many
            low-cite papers in top-N, S2 often returns shallow entry
            (no tldr/inf_cite) for 0-cite papers, costing ~1.2s × N
            for little gain. Set to 0 to restore v3.9.7.8 behavior (try all).

    Returns: same list (modified in place)
    """
    if n <= 0 or not results:
        return results
    enriched = 0
    skipped_low_cite = 0
    for i, r in enumerate(results[:n]):
        r.setdefault("_enrichment", {})
        has_cite = bool(r.get("cited_by_count"))
        has_abstract = bool(r.get("abstract"))
        # Try S2 by DOI (best — gets tldr, inf_cite, ref_count)
        # [P1-14] skip S2 if paper has cited_by_count < min_cites (saves ~12s/query
        # when many 0-cite papers in top-N; S2 returns shallow entry for 0-cite per
        # v3.9.7.7 lesson learned on Chinese papers)
        if r.get("doi") and (not has_cite or not has_abstract):
            if r.get("cited_by_count", 0) < min_cites:
                r["_enrichment"]["s2_doi_skipped"] = f"cited_by_count<{min_cites}"
                skipped_low_cite += 1
            else:
                s2 = _s2_lookup_doi(r["doi"])
                if s2:
                    for k in ("abstract", "tldr", "cited_by_count", "influential_cite_count",
                              "reference_count", "venue", "authors", "year"):
                        if s2.get(k) and not r.get(k):
                            r[k] = s2[k]
                    r["_enrichment"]["s2_doi"] = True
                    enriched += 1
                time.sleep(1.2)  # S2 free tier: 1 RPS
        # Try Crossref by title (fills missing DOI, gives cite for non-DOI papers)
        if (not r.get("cited_by_count") or not r.get("doi")) and r.get("title"):
            cr = _crossref_lookup_title(r["title"])
            if cr:
                for k in ("doi", "cited_by_count", "reference_count", "abstract",
                          "venue", "year"):
                    if cr.get(k) and not r.get(k):
                        r[k] = cr[k]
                r["_enrichment"]["crossref_title"] = True
                enriched += 1
            time.sleep(0.05)  # Crossref is generous
    # Re-sort by cited_by_count (newly enriched papers may have higher counts)
    results.sort(key=lambda x: x.get("cited_by_count", 0) or 0, reverse=True)
    # [P1-14] print enrichment stats (stdout; CLI can grep/pipe)
    if min_cites > 0 and skipped_low_cite:
        print(f"  [P1-14] enrich_top_n: enriched {enriched}, "
              f"skipped {skipped_low_cite} (cited_by_count<{min_cites}) "
              f"of top-{n}", file=sys.stderr)
    return results


def search_crossref(query: str, year_min: int = None, year_max: int = None,
                    limit: int = 50) -> List[Dict]:
    """Crossref API: best for DOI-rich, peer-reviewed papers."""
    fq = ""
    if year_min or year_max:
        ymin = year_min or 1900
        ymax = year_max or 2099
        fq = f"&filter=from-pub-date:{ymin},until-pub-date:{ymax}"
    url = (f"https://api.crossref.org/works?query.bibliographic={quote(query)}"
           f"&rows={min(limit, 100)}{fq}&select=DOI,title,author,abstract,"
           f"container-title,published-print,is-referenced-by-count,references-count,type")
    s, data = http_get_json(url)
    if s != 200:
        return []
    items = (data.get("message") or {}).get("items", [])
    return [_normalize_crossref(it) for it in items]


def _normalize_crossref(it: dict) -> dict:
    title = (it.get("title") or [""])[0] if it.get("title") else ""
    authors = [f"{a.get('family', '')}, {a.get('given', '')}".strip(", ")
               for a in (it.get("author") or [])]
    pub = it.get("published-print") or it.get("published-online") or {}
    parts = pub.get("date-parts", [[None]])[0]
    year = parts[0] if parts else None
    return {
        "doi": it.get("DOI", ""),
        "title": title,
        "authors": authors,
        "venue": (it.get("container-title") or [""])[0] if it.get("container-title") else "",
        "year": year,
        "cited_by_count": it.get("is-referenced-by-count", 0),
        "reference_count": it.get("references-count", 0),
        "type": it.get("type", ""),
        "source": "crossref",
        "abstract": it.get("abstract", "")[:500] if it.get("abstract") else "",
    }


def search_openalex(query: str, year_min: int = None, year_max: int = None,
                    limit: int = 50, concepts_filter: str = None) -> List[Dict]:
    """OpenAlex: best coverage + has OA flag.

    concepts_filter: optional OpenAlex filter string like
        "concepts.id:C1|C2" (OR) or "concepts.id:C1+concepts.id:C2" (AND).
        Built by pa_cli.concepts.build_concepts_filter.
    """
    f = ""
    if year_min or year_max:
        ymin = year_min or 1900
        ymax = year_max or 2099
        f = f",publication_year:{ymin}-{ymax}"
    if concepts_filter:
        # Add concepts filter; multiple filters joined by comma
        f = f + ("," + concepts_filter if f else concepts_filter)
    url = (f"https://api.openalex.org/works?search={quote(query)}&per_page={min(limit, 100)}"
           f"&filter=type:article{f}")
    api_key = os.environ.get("OPENALEX_API_KEY")
    if api_key:
        url += f"&api_key={api_key}"
    s, data = http_get_json(url)
    if s != 200:
        return []
    results = data.get("results") or []
    return [_normalize_openalex(r) for r in results]


def _normalize_openalex(r: dict) -> dict:
    authors = [a.get("author", {}).get("display_name", "") for a in (r.get("authorships") or [])]
    venue = (r.get("primary_location") or {}).get("source", {}).get("display_name", "") \
        if (r.get("primary_location") or {}).get("source") else ""
    pub_date = r.get("publication_date", "")
    year = int(pub_date[:4]) if pub_date else None
    oa = r.get("open_access") or {}
    return {
        "doi": (r.get("doi") or "").replace("https://doi.org/", ""),
        "title": r.get("title", "") or r.get("display_name", ""),
        "authors": authors,
        "venue": venue,
        "year": year,
        "cited_by_count": r.get("cited_by_count", 0),
        "is_oa": oa.get("is_oa", False),
        "oa_status": oa.get("oa_status"),
        "oa_url": oa.get("oa_url"),
        "source": "openalex",
        "type": r.get("type", ""),
    }


def search_arxiv(query: str, year_min: int = None, year_max: int = None,
                 limit: int = 50) -> List[Dict]:
    """arXiv SDK. Best for preprints."""
    try:
        import arxiv
    except ImportError:
        return []
    s_q = query
    if year_min or year_max:
        ymin = year_min or 1991
        ymax = year_max or 2099
        s_q = f"{query} AND submittedDate:[{ymin}0101 TO {ymax}1231]"
    client = arxiv.Client(page_size=min(limit, 50), delay_seconds=3, num_retries=3)
    search = arxiv.Search(query=s_q, max_results=limit, sort_by=arxiv.SortCriterion.Relevance)
    results = []
    try:
        for r in client.results(search):
            results.append({
                "doi": r.doi or f"arXiv:{r.entry_id.split('/')[-1]}",
                "arxiv_id": r.entry_id.split("/")[-1],
                "title": r.title,
                "authors": [a.name for a in r.authors],
                "venue": "arXiv",
                "year": r.published.year if r.published else None,
                "pdf_url": r.pdf_url,
                "cited_by_count": 0,  # arXiv doesn't track citations
                "source": "arxiv",
                "type": "preprint",
            })
    except Exception:
        pass
    return results


def search_semanticscholar(query: str, year_min: int = None, year_max: int = None,
                           limit: int = 50) -> List[Dict]:
    """Semantic Scholar API. Best for citation-rich data."""
    url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={quote(query)}&limit={min(limit, 100)}"
    if year_min or year_max:
        url += f"&year={year_min or ''}-{year_max or ''}"
    url += "&fields=title,authors,venue,year,citationCount,influentialCitationCount,referenceCount,tldr,externalIds,openAccessPdf,publicationTypes"
    headers = {}
    api_key = os.environ.get("S2_API_KEY")
    if api_key:
        headers["x-api-key"] = api_key
    s, data = http_get_json(url, headers=headers)
    if s != 200:
        return []
    results = []
    for it in (data.get("data") or []):
        ext = it.get("externalIds") or {}
        oa = it.get("openAccessPdf") or {}
        tldr_obj = it.get("tldr") or {}
        results.append({
            "doi": ext.get("DOI", ""),
            "arxiv_id": ext.get("ArXiv", ""),
            "title": it.get("title", ""),
            "authors": [a.get("name", "") for a in (it.get("authors") or [])],
            "venue": it.get("venue", ""),
            "year": it.get("year"),
            "cited_by_count": it.get("citationCount", 0),
            "influential_cite_count": it.get("influentialCitationCount", 0),
            "reference_count": it.get("referenceCount", 0),
            "tldr": tldr_obj.get("text", "") if isinstance(tldr_obj, dict) else "",
            "is_oa": bool(oa.get("url")),
            "oa_url": oa.get("url"),
            "source": "semanticscholar",
            "type": (it.get("publicationTypes") or [""])[0],
        })
    return results


def search_core(query: str, year_min: int = None, year_max: int = None,
                limit: int = 50) -> List[Dict]:
    """CORE.ac.uk v3. Best for legal OA papers (English-heavy repos).

    v3.9.8.2 fix (2026-07-15): CORE v3 API key is OPTIONAL — anonymous
    requests work at a low rate. Earlier we had two bugs:
      1. `if not api_key: return []` skipped CORE entirely when key missing
      2. `Authorization: Bearer ...` header caused timeouts (CORE v3 doesn't
         accept Bearer auth — use `?api_key=` query param instead, or skip key)

    Now we try no-key first, then fall back to key-via-query-param if set.
    Note: this function is NOT in the default "all" engine list (v3.9.8.1+)
    because OpenAlex already indexes CORE's content, but the function is kept
    available via `pa search --engine core` for explicit use.
    """
    api_key = os.environ.get("CORE_API_KEY", "").strip()
    base = f"https://api.core.ac.uk/v3/search/works?q={quote(query)}&limit={min(limit, 100)}"
    if year_min:
        base += f"&yearPublishedFrom={year_min}"
    if year_max:
        base += f"&yearPublishedTo={year_max}"
    # Key as query param (CORE v3 supported format); no Authorization header
    if api_key:
        url = base + f"&api_key={quote(api_key, safe='')}"
    else:
        url = base
    s, data = http_get_json(url)
    if s != 200:
        return []
    results = []
    for it in (data.get("results") or []):
        ext = it.get("externalIdentifiers") or {}
        doi = ""
        if isinstance(ext, dict):
            doi = ext.get("doi", "") or ""
        elif isinstance(ext, list):
            for e in ext:
                if isinstance(e, dict) and e.get("type") == "doi":
                    doi = e.get("value", "")
                    break
        downloads = it.get("sourceFulltextUrls") or []
        results.append({
            "doi": doi,
            "title": it.get("title", ""),
            "authors": [a.get("name", "") for a in (it.get("authors") or [])],
            "venue": (it.get("publisher") or ""),
            "year": it.get("yearPublished"),
            "cited_by_count": it.get("citationCount", 0) or 0,
            "is_oa": True,
            "oa_url": downloads[0] if downloads else None,
            "source": "core",
            "type": it.get("documentType", ""),
        })
    return results


def run_search(query: str, year_min: int = None, year_max: int = None,
               limit: int = 50, engine: str = "all",
               concepts_filter: str = None,
               enrich_top: int = 0,
               enrich_top_min_cites: int = 1) -> Dict[str, Any]:
    """Run search across specified engines; returns deduped unified results.

    concepts_filter: OpenAlex `concepts.id:...` filter string (built by
                     pa_cli.concepts.build_concepts_filter). Only OpenAlex
                     applies it; other engines ignore. Format examples:
                       - OR:  "concepts.id:C1|C2"
                       - AND: "concepts.id:C1+concepts.id:C2"

    enrich_top: if > 0, do second-hop lookups for top-N results lacking
                cite/abstract (S2 by DOI + Crossref by title). See
                enrich_top_n() docs. Adds ~12s for N=10 (S2 1 RPS).
                Default 0 = off (backward compatible).
    enrich_top_min_cites: [P1-14] skip S2 lookup for papers with
                cited_by_count < this threshold (default 1 = skip 0-cite).
                Saves ~12s/query when many low-cite papers in top-N.
                Set to 0 to restore v3.9.7.8 behavior (try all).
    """
    engines = (["crossref", "openalex", "arxiv", "semanticscholar", "aminer", "cnki"]
               if engine == "all" else [e.strip() for e in engine.split(",")])
    # v3.9.8.2 (2026-07-15): CORE is no longer in the default "all" list.
    # OpenAlex already indexes CORE's repos, so marginal coverage is <5%.
    # If user explicitly asks for `--engine core`, route to search_core().
    if engine == "core":
        papers = search_core(query, year_min, year_max, limit)
        return {"results": papers, "by_engine": {"core": papers}, "dedup_count": len(papers)}
    by_engine: Dict[str, List[Dict]] = {}
    funcs = {
        "crossref": search_crossref,
        "openalex": search_openalex,
        "arxiv": search_arxiv,
        "semanticscholar": search_semanticscholar,
    }
    # AMiner is optional — only include if token is set (avoid hard-fail on first run)
    if "aminer" in engines:
        from .aminer_channel import _aminer_token
        if not _aminer_token():
            # Graceful skip: AMiner not configured; engines stays valid
            engines = [e for e in engines if e != "aminer"]
        else:
            from .aminer_channel import search_aminer
            funcs["aminer"] = search_aminer
    # CNKI is optional — only include if cookies exist (avoid hard-fail on first run)
    if "cnki" in engines and not _try_import_cnki():
        # Graceful skip: CNKI not configured yet; engines stays valid
        engines = [e for e in engines if e != "cnki"]
    elif "cnki" in engines:
        from .cnki_channel import search_cnki
        funcs["cnki"] = search_cnki
    for eng in engines:
        if eng not in funcs:
            continue
        try:
            # Pass concepts_filter to OpenAlex; other engines ignore extra args
            if eng == "openalex" and concepts_filter:
                by_engine[eng] = search_openalex(query, year_min, year_max, limit,
                                                concepts_filter=concepts_filter)
            else:
                by_engine[eng] = funcs[eng](query, year_min, year_max, limit)
        except Exception as e:
            by_engine[eng] = [{"error": str(e)[:200]}]

    # Dedup by DOI (or arXiv ID fallback)
    seen = {}
    for eng, papers in by_engine.items():
        for p in papers:
            if "error" in p:
                continue
            key = p.get("doi") or p.get("arxiv_id") or p.get("title", "")[:60]
            if not key:
                continue
            if key not in seen:
                seen[key] = dict(p)
                seen[key]["found_by"] = [eng]
            else:
                if eng not in seen[key]["found_by"]:
                    seen[key]["found_by"].append(eng)
                # Merge citation count + abstract + enrichment fields (prefer non-empty)
                for c in ("cited_by_count", "is_oa", "oa_url", "tldr", "abstract",
                          "venue", "authors", "influential_cite_count", "reference_count",
                          "doi", "arxiv_id"):
                    if not seen[key].get(c) and p.get(c):
                        seen[key][c] = p[c]

    # tldr → abstract fallback: if abstract still empty after merge but tldr present,
    # use tldr — BUT only if it's a real tldr (not S2's "no tldr" placeholder).
    # Known S2 placeholder strings: "It's time to dust off the gloves..."
    S2_TLDR_PLACEHOLDERS = (
        "It's time to dust off the gloves",
        "It\u2019s time to dust off the gloves",
        "It's time to dust off the sledgehammers",
        "It\u2019s time to dust off the sledgehammers",
    )
    for r in seen.values():
        tldr = r.get("tldr") or ""  # guard against None
        if (not r.get("abstract") and tldr
                and not any(tldr.startswith(p) for p in S2_TLDR_PLACEHOLDERS)):
            r["abstract"] = tldr

    unified = sorted(seen.values(), key=lambda x: x.get("cited_by_count", 0) or 0, reverse=True)

    # Top-N deep enrichment (v3.9.7.8): second-hop lookups for top-N results
    # that lack cite/abstract. Off by default (enrich_top=0).
    if enrich_top > 0:
        enrich_top_n(unified, n=enrich_top, min_cites=enrich_top_min_cites)

    return {
        "query": query,
        "year_min": year_min,
        "year_max": year_max,
        "by_engine": {k: len(v) for k, v in by_engine.items()},
        "dedup_count": len(unified),
        "enrich_top": enrich_top,
        "results": unified,
    }


def _try_import_cnki() -> bool:
    """Return True if CNKI channel can be used (cookies + playwright available).

    Per v3.9.7.3 design: CNKI is optional. If cookies file missing OR
    playwright not installed, gracefully skip CNKI from the engine pool
    (downgrade to 5 English engines without raising).
    """
    try:
        from . import cnki_channel
    except ImportError:
        return False
    if not cnki_channel.cookies_exist():
        return False
    try:
        import playwright  # noqa: F401
    except ImportError:
        return False
    # All preconditions met
    return True