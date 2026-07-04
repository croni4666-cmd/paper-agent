"""
pa_cli.search — 5-engine academic paper search.

Engines: Crossref, Semantic Scholar, arXiv, OpenAlex, CORE.
Wraps the existing paper-agent v3.1 SearchPool pattern. Falls back gracefully
on per-engine failure.
"""

import json
import os
from typing import List, Dict, Optional, Any
from urllib.parse import quote
import urllib.request as ur
import urllib.error


UA = "paper-agent/3.2 (Mavis; mailto:hello@example.com)"


def http_get_json(url: str, headers: dict = None, timeout: int = 30) -> tuple:
    h = {"User-Agent": UA, "Accept": "application/json"}
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
           f"container-title,published-print,is-referenced-by-count,type")
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
        "type": it.get("type", ""),
        "source": "crossref",
        "abstract": it.get("abstract", "")[:500] if it.get("abstract") else "",
    }


def search_openalex(query: str, year_min: int = None, year_max: int = None,
                    limit: int = 50) -> List[Dict]:
    """OpenAlex: best coverage + has OA flag."""
    f = ""
    if year_min or year_max:
        ymin = year_min or 1900
        ymax = year_max or 2099
        f = f",publication_year:{ymin}-{ymax}"
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
    url += "&fields=title,authors,venue,year,citationCount,externalIds,openAccessPdf,publicationTypes"
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
        results.append({
            "doi": ext.get("DOI", ""),
            "arxiv_id": ext.get("ArXiv", ""),
            "title": it.get("title", ""),
            "authors": [a.get("name", "") for a in (it.get("authors") or [])],
            "venue": it.get("venue", ""),
            "year": it.get("year"),
            "cited_by_count": it.get("citationCount", 0),
            "is_oa": bool(oa.get("url")),
            "oa_url": oa.get("url"),
            "source": "semanticscholar",
            "type": (it.get("publicationTypes") or [""])[0],
        })
    return results


def search_core(query: str, year_min: int = None, year_max: int = None,
                limit: int = 50) -> List[Dict]:
    """CORE.ac.uk v3. Best for legal OA papers."""
    api_key = os.environ.get("CORE_API_KEY")
    if not api_key:
        return []
    url = (f"https://api.core.ac.uk/v3/search/works?q={quote(query)}&limit={min(limit, 100)}")
    if year_min:
        url += f"&yearPublishedFrom={year_min}"
    if year_max:
        url += f"&yearPublishedTo={year_max}"
    s, data = http_get_json(url, headers={"Authorization": f"Bearer {api_key}"})
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
               limit: int = 50, engine: str = "all") -> Dict[str, Any]:
    """Run search across specified engines; returns deduped unified results."""
    engines = (["crossref", "openalex", "arxiv", "semanticscholar", "core"]
               if engine == "all" else [e.strip() for e in engine.split(",")])
    by_engine: Dict[str, List[Dict]] = {}
    funcs = {
        "crossref": search_crossref,
        "openalex": search_openalex,
        "arxiv": search_arxiv,
        "semanticscholar": search_semanticscholar,
        "core": search_core,
    }
    for eng in engines:
        if eng not in funcs:
            continue
        try:
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
                # Merge citation count (prefer highest)
                for c in ("cited_by_count", "is_oa", "oa_url"):
                    if not seen[key].get(c) and p.get(c):
                        seen[key][c] = p[c]

    unified = sorted(seen.values(), key=lambda x: x.get("cited_by_count", 0) or 0, reverse=True)
    return {
        "query": query,
        "year_min": year_min,
        "year_max": year_max,
        "by_engine": {k: len(v) for k, v in by_engine.items()},
        "dedup_count": len(unified),
        "results": unified,
    }