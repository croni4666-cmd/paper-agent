"""
pa_cli.search 鈥?academic paper search across multiple engines.

Default engines: Crossref, OpenAlex, arXiv, AMiner, PubMed, ClinicalTrials.gov.
Wraps the existing paper-agent v3.1 SearchPool pattern. Falls back gracefully
on per-engine failure.

CORE engine is isolated to a local-only file (pa_cli/_engines_local/core.py,
gitignored). Public repo does not include the functional CORE engine. To use
CORE: `python tools/install_core.py` once after clone, then `pa search
--engine core "..."`. See tools/install_core.py for rationale.

v3.9.8.2 (2026-07-15): CORE removed from default "all" list 鈥?OpenAlex already
indexes CORE's repos, so the marginal coverage was <5% but maintenance cost
(buggy key auth path) was real. search_core() function still available via
`pa search --engine core` for explicit use, and now works in no-key mode.

v3.9.11.1 (2026-07-23): CORE engine code moved to pa_cli/_engines_local/core.py
(local-only, gitignored). Public `pa search --engine core` raises "not installed"
error; user runs `python tools/install_core.py` to enable. This separates the
CORE engine from the rest of the package 鈥?see tools/install_core.py for the
isolation rationale and trade-offs.

AMiner (added v3.9.8.0): 6th default engine for Chinese papers, gated on
AMINER_API_KEY env var (浣撻獙閲?3880 calls / 60 days). +10.9pp cite lift
on Chinese queries vs baseline 4 engines.

"""

import json
import gzip
import io
import logging
import os
import sys
import threading
import time
from pathlib import Path
from typing import List, Dict, Optional, Any, Callable
from urllib.parse import quote
import urllib.request as ur
import urllib.error
import xml.etree.ElementTree as ET


logger = logging.getLogger(__name__)


class EngineRateLimitError(RuntimeError):
    """An upstream engine rejected the request because its rate limit was hit."""


def _load_dotenv(path: Optional[Path] = None) -> None:
    """Minimal .env loader (no python-dotenv dep). Sets keys into os.environ
    only if not already set (so shell env wins).

    Searches: --env-file CLI arg > $PAPER_AGENT_ENV_FILE > ./pa.env > ./.env
    > <repo>/pa.env > <repo>/.env (whichever exists first).
    """
    if path is None:
        for cand in (
            os.environ.get("PAPER_AGENT_ENV_FILE"),
            "pa.env", ".env",
            str(Path(__file__).resolve().parents[1] / "pa.env"),
            str(Path(__file__).resolve().parents[1] / ".env"),
        ):
            if cand and Path(cand).is_file():
                path = Path(cand)
                break
    if path is None or not path.is_file():
        return
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            # Don't overwrite shell env
            os.environ.setdefault(k, v)
    except Exception:
        pass


_load_dotenv()


UA = "paper-agent/3.2 (Mavis; mailto:hello@example.com)"
# v3.9.8.0: 鐢ㄧ湡瀹?browser UA 閬垮厤 Cloudflare/DDoS-Guard 鎷︽埅 (CORE API 涔嬪墠 1010)
UA_BROWSER = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def http_get_json(url: str, headers: dict = None, timeout: int = 30) -> tuple:
    """v3.9.13.3: now goes through pa_cli._http so HTTPS_PROXY env var is honored.

    Returns (status_code, parsed_dict_or_bytes_or_error_dict).
    """
    from ._http import http_get_json as _http_get_json_helper
    return _http_get_json_helper(url, headers=headers, timeout=timeout)
def _crossref_lookup_title(title: str) -> Optional[Dict]:
    """Crossref works?query.bibliographic 鈥?finds DOI + cite by title.

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
    parts = (pub.get("date-parts") or [[None]])[0]
    year = parts[0] if parts else None
    return {
        "doi": it.get("DOI", ""),
        "title": it.get("title", [""])[0] if isinstance(it.get("title"), list) else it.get("title", ""),
        "authors": [f"{a.get('family','')}, {a.get('given','')}".strip(", ")
                    for a in (it.get("author") or [])],
        "venue": (it.get("container-title") or [""])[0] if it.get("container-title") else "",
        "year": year,
        "abstract": it.get("abstract", ""),
        "cited_by_count": (it.get("is-referenced-by-count") or 0),
        "reference_count": it.get("references-count", 0),
        "source": "crossref_title",
    }


def _openalex_lookup_title(title: str) -> Optional[Dict]:
    """[P1-15] OpenAlex works?search={title} 鈥?fallback for Crossref-by-title
    0-hit case. Better Chinese coverage than Crossref per v3.9.7.5 lessons.

    Returns same shape as _crossref_lookup_title() so the caller can use
    either result interchangeably.

    Best-effort: returns top-1 match. OpenAlex free tier is generous (no
    rate limit when no api_key; 5 RPS with polite pool key).

    Note: OpenAlex uses `cited_by_count` natively (not is-referenced-by-count
    like Crossref) so the field is consistent with the rest of the codebase.
    """
    if not title or len(title) < 10:
        return None
    url = (f"https://api.openalex.org/works?search={quote(title)}&per_page=1"
           f"&filter=type:article")
    api_key = os.environ.get("OPENALEX_API_KEY")
    if api_key:
        url += f"&api_key={api_key}"
    s, data = http_get_json(url, headers={}, timeout=15)
    if s != 200 or not data.get("results"):
        return None
    return _normalize_openalex(data["results"][0])


def enrich_top_n(results: List[Dict], n: int = 10,
                 resort_by: str = "cite", max_age_years: int = 10) -> List[Dict]:
    """Fill missing metadata for the top results from Crossref and OpenAlex."""
    if n <= 0 or not results:
        return results
    enriched = 0
    skipped_old = 0
    current_year = 2026
    for result in results[:n]:
        result.setdefault("_enrichment", {})
        year = result.get("year")
        if max_age_years > 0 and year and current_year - year > max_age_years:
            result["_enrichment"]["enrichment_skipped"] = f"year<{current_year - max_age_years}"
            skipped_old += 1
            continue
        if (not result.get("cited_by_count") or not result.get("doi")) and result.get("title"):
            enrichment = _crossref_lookup_title(result["title"]) or _openalex_lookup_title(result["title"])
            if enrichment:
                for key in ("doi", "cited_by_count", "reference_count", "abstract", "venue", "year"):
                    if enrichment.get(key) and not result.get(key):
                        result[key] = enrichment[key]
                result["_enrichment"][enrichment.get("source", "metadata")] = True
                enriched += 1
            time.sleep(0.05)
    if resort_by == "cite":
        results.sort(key=lambda item: item.get("cited_by_count", 0) or 0, reverse=True)
    elif resort_by == "year":
        results.sort(key=lambda item: item.get("year") or 0, reverse=True)
    if skipped_old:
        print(f"  [enrich] enriched {enriched}; skipped_old {skipped_old} of top-{n}", file=sys.stderr)
    return results

def sort_results(results: List[Dict], sort_by: str = "cite") -> List[Dict]:
    """[P1-16] Sort unified results by user-selected criterion.

    cite (default): cited_by_count desc 鈥?v3.9.7.8 backward compat.
    year: year desc (newest first; None/0 at end).
    relevance: keep natural engine order (no sort) 鈥?preserves the
              per-engine relevance ranking each engine returned.

    Returns: NEW list (does not mutate input).
    """
    if sort_by == "cite":
        return sorted(results, key=lambda x: x.get("cited_by_count", 0) or 0, reverse=True)
    elif sort_by == "year":
        return sorted(results, key=lambda x: x.get("year") or 0, reverse=True)
    else:  # "relevance" or unknown
        return list(results)


def filter_by_source(results: List[Dict], source_filter: List[str] = None) -> List[Dict]:
    """[P1-17] Post-filter unified results to only show those from specified
    engines. Use case: query many engines, but only display certain ones
    (for example, to compare OpenAlex and AMiner coverage).

    source_filter: list of base engine names like
        ["openalex", "crossref", "arxiv", "aminer", "pubmed", "clinicaltrials", "core"]
        If None or empty, no filter (all results returned).
    Matching: a result matches if its `source` field starts with any filter
        entry. So "openalex" matches both "openalex" and "openalex_title"
        (the [P1-15] fallback). "crossref" matches "crossref" and "crossref_title".

    Returns: NEW list (does not mutate input).
    """
    if not source_filter:
        return list(results)
    sf = [s.strip().lower() for s in source_filter if s.strip()]
    if not sf:
        return list(results)
    return [r for r in results if any(
        (r.get("source") or "").lower().startswith(prefix) for prefix in sf
    )]


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
    if s != 200 or not isinstance(data, dict):
        raise RuntimeError(f"OpenAlex request failed with HTTP status {s}")
    if data.get("error"):
        raise RuntimeError(f"OpenAlex response error: {data['error']}")
    items = (data.get("message") or {}).get("items", [])
    return [_normalize_crossref(it) for it in items]


def _normalize_crossref(it: dict) -> dict:
    title = (it.get("title") or [""])[0] if it.get("title") else ""
    authors = [f"{a.get('family', '')}, {a.get('given', '')}".strip(", ")
               for a in (it.get("author") or [])]
    pub = it.get("published-print") or it.get("published-online") or {}
    parts = (pub.get("date-parts") or [[None]])[0]
    year = parts[0] if parts else None
    return {
        "doi": it.get("DOI", ""),
        "title": title,
        "authors": authors,
        "venue": (it.get("container-title") or [""])[0] if it.get("container-title") else "",
        "year": year,
        "cited_by_count": (it.get("is-referenced-by-count") or 0),
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
    authors = [(a.get("author") or {}).get("display_name", "") for a in (r.get("authorships") or [])]
    venue = (r.get("primary_location") or {}).get("source", {}).get("display_name", "") \
        if (r.get("primary_location") or {}).get("source") else ""
    pub_date = r.get("publication_date", "")
    year = int(pub_date[:4]) if pub_date and pub_date[:4].isdigit() else None
    oa = r.get("open_access") or {}
    return {
        "doi": (r.get("doi") or "").replace("https://doi.org/", ""),
        "title": r.get("title", "") or r.get("display_name", ""),
        "authors": authors,
        "venue": venue,
        "year": year,
        "cited_by_count": (r.get("cited_by_count") or 0),
        "is_oa": oa.get("is_oa", False),
        "oa_status": oa.get("oa_status"),
        "oa_url": oa.get("oa_url"),
        "source": "openalex",
        "type": r.get("type", ""),
    }


def search_arxiv(query: str, year_min: int = None, year_max: int = None,
                 limit: int = 50) -> List[Dict]:
    """arXiv SDK. Best for preprints.

    v3.9.24.0: added post-filter on r.published.year. arXiv's
    `submittedDate:[X TO Y]` filter is on the API level but the SDK
    sometimes returns papers where r.published is outside the range
    (e.g. when sorted by Relevance and the API soft-relaxes the filter).
    We post-filter to enforce the year range.
    """
    try:
        import arxiv
    except ImportError as exc:
        raise RuntimeError("arxiv dependency is not installed") from exc
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
    except Exception as exc:
        raise RuntimeError(f"arXiv search failed: {exc}") from exc

    # v3.9.24.0: post-filter on year to handle API filter relaxation
    if year_min or year_max:
        ymin = year_min or 1991
        ymax = year_max or 2099
        pre_filter_count = len(results)
        results = [
            r for r in results
            if r.get("year") and ymin <= int(r["year"]) <= ymax
        ]
        if pre_filter_count > 0 and len(results) < pre_filter_count:
            logger.debug(
                f"arxiv year post-filter: {pre_filter_count} -> {len(results)} "
                f"(API submittedDate filter was relaxed; applied {ymin}-{ymax} "
                f"client-side)"
            )

    return results


# v3.9.11.1 (2026-07-23): CORE engine isolated to local-only file.
# The public repo's `pa search --engine core` raises a clear "not installed"
# error until the user runs `python tools/install_core.py` once after clone.
# See tools/install_core.py for the install step + isolation rationale.
def _search_core_unavailable(*args, **kwargs):
    raise RuntimeError(
        "CORE engine not installed locally. "
        "Run: python tools/install_core.py"
    )


# v3.9.11.8 (2026-08-09): PubMed engine (NCBI E-utilities).
# First medical-specific search engine. ~36M biomedical citations.
# Free public API, no auth required (API key raises rate limit from 3 to 10 RPS).
# Returns: PMID, title, journal, year, authors, DOI, publication types.
# Adds best-effort abstracts and MeSH terms through batched EFetch XML.
# 2 calls per search: esearch (PMID list) + esummary (metadata). 1s polite sleep between.
_PUBMED_LAST_CALL_TS = [0.0]  # module-level throttle

def _pubmed_throttle(min_interval: float = 0.4) -> None:
    """NCBI etiquette: 3 RPS without API key, 10 RPS with key.
    Default 0.4s = 2.5 RPS = safely under both limits and polite to NCBI.
    """
    elapsed = time.time() - _PUBMED_LAST_CALL_TS[0]
    if elapsed < min_interval:
        time.sleep(min_interval - elapsed)
    _PUBMED_LAST_CALL_TS[0] = time.time()


def _parse_pubmed_details(xml_bytes: bytes) -> Dict[str, Dict[str, Any]]:
    """Extract abstract sections and MeSH descriptors from PubMed EFetch XML."""
    details: Dict[str, Dict[str, Any]] = {}
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return details
    for article in root.findall(".//PubmedArticle"):
        pmid = (article.findtext("./MedlineCitation/PMID") or "").strip()
        if not pmid:
            continue
        abstract_parts = []
        for item in article.findall("./MedlineCitation/Article/Abstract/AbstractText"):
            text = " ".join("".join(item.itertext()).split())
            if text:
                label = (item.get("Label") or "").strip()
                abstract_parts.append(f"{label}: {text}" if label else text)
        mesh_terms = []
        for item in article.findall("./MedlineCitation/MeshHeadingList/MeshHeading/DescriptorName"):
            text = " ".join("".join(item.itertext()).split())
            if text:
                mesh_terms.append(text)
        details[pmid] = {
            "abstract": " ".join(abstract_parts),
            "mesh_terms": mesh_terms,
        }
    return details


def _fetch_pubmed_details(pmids: List[str], tool: str, email: str,
                          api_key: str) -> Dict[str, Dict[str, Any]]:
    """Best-effort EFetch enrichment; failure leaves ESummary results usable."""
    if not pmids:
        return {}
    from ._http import http_get
    details: Dict[str, Dict[str, Any]] = {}
    for i in range(0, len(pmids), 100):
        _pubmed_throttle()
        ids = ",".join(pmids[i:i + 100])
        url = (
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
            f"?db=pubmed&id={ids}&retmode=xml&tool={tool}&email={quote(email)}"
        )
        if api_key:
            url += f"&api_key={quote(api_key)}"
        try:
            details.update(_parse_pubmed_details(http_get(url, timeout=45)))
        except Exception:
            continue
    return details

def search_pubmed(query: str, year_min: int = None, year_max: int = None,
                  limit: int = 50) -> List[Dict]:
    """PubMed (NCBI E-utilities): ~36M biomedical/biomedical-adjacent citations.

    Free public API, no key required. To raise rate limit from 3 to 10 RPS,
    set env var NCBI_API_KEY (free at https://www.ncbi.nlm.nih.gov/account/settings/).

    v3.9.11.8: initial release. Returns: PMID, title, journal, year,
    authors (max 5 + et al.), DOI (if available), publication types.
    Abstract and MeSH enrichment is best effort and never blocks search results.
    """
    # NCBI E-utilities requires email + tool parameters per their etiquette
    tool = "paper-agent"
    email = os.environ.get("NCBI_EMAIL", "paper-agent@example.com")
    api_key = os.environ.get("NCBI_API_KEY", "").strip()

    # 鈹€鈹€ 1. esearch: get PMIDs matching query 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
    _pubmed_throttle()
    date_filter = ""
    if year_min or year_max:
        ymin = year_min or 1900
        ymax = year_max or 2099
        date_filter = f"&mindate={ymin}/01/01&maxdate={ymax}/12/31&datetype=pdat"
    esearch_url = (
        f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        f"?db=pubmed&term={quote(query)}&retmode=json"
        f"&retmax={min(limit, 200)}{date_filter}"
        f"&tool={tool}&email={email}"
    )
    if api_key:
        esearch_url += f"&api_key={quote(api_key)}"

    s, data = http_get_json(esearch_url, timeout=30)
    if s != 200 or not data:
        return []
    pmids = (data.get("esearchresult") or {}).get("idlist") or []
    if not pmids:
        return []

    # 鈹€鈹€ 2. esummary: get metadata for PMIDs 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
    # NCBI limits to 200 IDs per esummary call. If we got more, chunk.
    results: List[Dict] = []
    for i in range(0, len(pmids), 100):
        chunk = pmids[i:i + 100]
        _pubmed_throttle()
        ids_str = ",".join(chunk)
        esummary_url = (
            f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
            f"?db=pubmed&id={ids_str}&retmode=json"
            f"&tool={tool}&email={email}"
        )
        if api_key:
            esummary_url += f"&api_key={quote(api_key)}"

        s2, data2 = http_get_json(esummary_url, timeout=30)
        if s2 != 200 or not data2:
            continue
        result_root = data2.get("result") or {}
        uids = result_root.get("uids") or []
        for uid in uids:
            r = result_root.get(uid) or {}
            if not r or r.get("error"):
                continue
            results.append(_normalize_pubmed(r))

    # 3. EFetch: add abstracts and controlled MeSH terms in batches.
    # An EFetch outage must not discard usable ESummary metadata.
    pubmed_details = _fetch_pubmed_details(pmids, tool, email, api_key)
    for paper in results:
        detail = pubmed_details.get(paper.get("pmid"), {})
        if detail.get("abstract"):
            paper["abstract"] = detail["abstract"]
        if detail.get("mesh_terms"):
            paper["mesh_terms"] = detail["mesh_terms"]
    # Post-filter by year (v3.9.11.8 hotfix)
    #
    # esearch's `datetype=pdat` filter is on ONLINE publication date (epub
    # ahead of print), but `_normalize_pubmed` extracts `year` from
    # `pubdate` (print pubdate). For papers with epub ahead of print, the
    # two can differ by 1-2 years. Re-filter to ensure `year` falls in
    # [year_min, year_max] so the user gets semantically correct results.
    #
    # Trade-off: post-filter may reduce the result count below `limit`.
    # Acceptable 鈥?user wants correct year filter, not full limit.
    if year_min or year_max:
        ymin = year_min or 1900
        ymax = year_max or 2099
        results = [
            r for r in results
            if r.get("year") and ymin <= int(r["year"]) <= ymax
        ]

    return results


def _normalize_pubmed(r: dict) -> dict:
    """Convert PubMed esummary record to paper-agent unified schema."""
    # Authors: list of {name, authtype, clusterid}
    authors_raw = r.get("authors") or []
    authors = [a.get("name", "") for a in authors_raw if a.get("name")]

    # DOI from articleids list
    doi = ""
    for aid in (r.get("articleids") or []):
        if aid.get("idtype") == "doi":
            doi = aid.get("value", "")
            break

    # Publication year from pubdate (e.g. "2025 Mar 15" -> 2025)
    pubdate = r.get("pubdate", "") or ""
    year = None
    for part in pubdate.split():
        if part.isdigit() and len(part) == 4:
            year = int(part)
            break
    if not year and (r.get("epubdate") or ""):
        for part in r["epubdate"].split():
            if part.isdigit() and len(part) == 4:
                year = int(part)
                break

    # Publication types
    pub_types = r.get("pubtype") or []

    # Volume / issue / pages
    volume = r.get("volume", "")
    issue = r.get("issue", "")
    pages = r.get("pages", "")

    return {
        "doi": doi,
        "pmid": r.get("uid", ""),
        "title": r.get("title", ""),
        "authors": authors,
        "venue": r.get("fulljournalname") or r.get("source") or "",
        "year": year,
        "volume": volume,
        "issue": issue,
        "pages": pages,
        "pub_types": pub_types,
        "issn": r.get("issn", ""),
        "abstract": "",
        "mesh_terms": [],
        "source": "pubmed",
        # cited_by_count: PubMed doesn't have a direct cite count.
        # Leave 0; downstream engines (S2/OpenAlex dedup) can fill it in.
        "cited_by_count": 0,
    }


# v3.9.12.0 (2026-08-10): ClinicalTrials.gov engine
# Free public API, no auth, JSON-based, returns clinical trial registry
# records (NOT papers 鈥?different content type from PubMed/PEDro).
# Use case: "is anyone currently running a trial for this intervention?"
# See: https://clinicaltrials.gov/api/v2
def search_clinicaltrials(query: str, year_min: int = None, year_max: int = None,
                          limit: int = 50) -> List[Dict]:
    """ClinicalTrials.gov v2 API: 500K+ registered clinical trials.

    Free public API, no auth, no key, ~3 req/s rate limit. Returns trial
    registry records (not published papers 鈥?different content type from
    PubMed/PEDro/etc.).

    v3.9.12.0: initial release. Returns: nct_id, title, status, conditions,
    interventions, phase, enrollment, start_date, related_pub_refs.

    Args:
        query: free-text search (CT.gov searches title/condition/intervention
               fields with simple relevance ranking).
        year_min / year_max: filter by trial START year. CT.gov uses
               YYYY-MM-DD date format with dateFilter via filter.advanced.
        limit: max results to return. CT.gov accepts pageSize up to 1000,
               we cap at 100 internally.
    """
    import urllib.parse as _up

    base = "https://clinicaltrials.gov/api/v2/studies"
    params = {
        "query.term": query,
        "format": "json",
        "pageSize": str(min(limit, 100)),
    }
    if year_min or year_max:
        # dateFilter syntax via filter.advanced: AREA[StartDate]RANGE[YYYY-MM-DD, YYYY-MM-DD]
        ymin = f"{year_min or 1900}-01-01"
        ymax = f"{year_max or 2099}-12-31"
        params["filter.advanced"] = f"AREA[StartDate]RANGE[{ymin},{ymax}]"

    url = base + "?" + _up.urlencode(params)
    _pubmed_throttle(0.4)  # ~2.5 RPS, polite to CT.gov

    s, data = http_get_json(url, timeout=30)
    if s != 200 or not data:
        return []

    studies = data.get("studies") or []
    results: List[Dict] = []
    for study in studies:
        norm = _normalize_clinicaltrial(study)
        if norm:
            results.append(norm)

    # CT.gov date filter is precise (exact start date in range), so
    # post-filter is optional. We trust it. (No v3.9.11.9-style post-filter
    # needed because CT.gov API does proper date filtering, unlike NCBI
    # esearch which uses pdat vs print date.)
    return results


def _normalize_clinicaltrial(s: dict) -> dict:
    """Normalize CT.gov study to paper-agent unified schema.

    CT.gov study shape:
      {
        "protocolSection": {
          "identificationModule": {nctId, briefTitle, officialTitle, ...},
          "statusModule": {overallStatus, startDateStruct, ...},
          "designModule": {phases, enrollmentInfo, ...},
          "conditionsModule": {conditions: [{name, ...}]},
          "armsInterventionsModule": {interventions: [{type, name, ...}]},
          "referencesModule": {references: [{citation, pmid, ...}]}
        }
      }
    """
    proto = s.get("protocolSection") or {}
    if not proto:
        return None

    ident = proto.get("identificationModule") or {}
    status = proto.get("statusModule") or {}
    design = proto.get("designModule") or {}
    cond_mod = proto.get("conditionsModule") or {}
    arms = proto.get("armsInterventionsModule") or {}
    refs_mod = proto.get("referencesModule") or {}

    # Conditions: list of strings or list of dicts depending on CT.gov version
    cond_raw = cond_mod.get("conditions") or []
    if cond_raw and isinstance(cond_raw[0], dict):
        conditions = [c.get("name", "?") for c in cond_raw if c.get("name")]
    else:
        conditions = list(cond_raw)

    # Interventions
    interv_raw = arms.get("interventions") or []
    interventions = []
    for i in interv_raw:
        if isinstance(i, dict):
            interventions.append(i.get("name", "?"))
        else:
            interventions.append(str(i))

    # Start year from YYYY-MM-DD or YYYY-MM or YYYY
    start_struct = status.get("startDateStruct") or {}
    start_date = start_struct.get("date", "")
    year = None
    if start_date:
        try:
            year = int(start_date.split("-")[0])
        except (ValueError, IndexError):
            year = None

    # Phase
    phases = design.get("phases") or []
    phase = ", ".join(phases) if phases else ""

    # Enrollment
    enroll = design.get("enrollmentInfo") or {}
    enrollment = enroll.get("count")

    # Related published refs (citations to papers from this trial)
    related_pubs = []
    for r in (refs_mod.get("references") or [])[:5]:
        cite = r.get("citation")
        pmid = r.get("pmid")
        if cite:
            related_pubs.append({"citation": cite, "pmid": pmid})

    nct_id = ident.get("nctId", "")
    return {
        "doi": "",  # trials don't have DOI
        "nct_id": nct_id,  # ClinicalTrials.gov unique ID
        "title": ident.get("briefTitle") or ident.get("officialTitle") or "",
        "authors": [],  # trials have no authors per se (PI is "sponsor")
        "venue": f"ClinicalTrials.gov ({nct_id})",
        "year": year,
        "phase": phase,
        "enrollment": enrollment,
        "status": status.get("overallStatus", ""),
        "start_date": start_date,
        "conditions": conditions,
        "interventions": interventions,
        "related_pubs": related_pubs,
        "source": "clinicaltrials",
        "cited_by_count": 0,  # trials don't have cite count
    }


try:
    from pa_cli._engines_local.core import search_core  # noqa: F401
except ImportError:
    search_core = _search_core_unavailable


DEFAULT_ENGINE_TIMEOUT_SECONDS = 30.0


def _run_engine_with_timeout(callback: Callable[[], List[Dict]], timeout: float) -> List[Dict]:
    """Run one engine without allowing a stalled network call to block others."""
    if timeout <= 0:
        raise ValueError("engine timeout must be greater than zero")

    outcome: Dict[str, Any] = {}
    completed = threading.Event()

    def invoke() -> None:
        try:
            outcome["value"] = callback()
        except Exception as exc:
            outcome["error"] = exc
        finally:
            completed.set()

    threading.Thread(target=invoke, daemon=True).start()
    if not completed.wait(timeout):
        raise TimeoutError(f"search timed out after {timeout:g}s")
    if "error" in outcome:
        raise outcome["error"]
    return outcome["value"]

def run_search(query: str, year_min: int = None, year_max: int = None,
               limit: int = 50, engine: str = "all",
               concepts_filter: str = None,
               enrich_top: int = 0,
               sort_by: str = "cite",
               source_filter: List[str] = None,
               enrich_max_age_years: int = 10,
               aminer_mode: str = "auto",
               engine_timeout: float = DEFAULT_ENGINE_TIMEOUT_SECONDS) -> Dict[str, Any]:
    """Run search across specified engines; returns deduped unified results.

    concepts_filter: OpenAlex `concepts.id:...` filter string (built by
                     pa_cli.concepts.build_concepts_filter). Only OpenAlex
                     applies it; other engines ignore. Format examples:
                       - OR:  "concepts.id:C1|C2"
                       - AND: "concepts.id:C1+concepts.id:C2"

    enrich_top: if > 0, do second-hop lookups for top-N results lacking
                cite/abstract (Crossref or OpenAlex by title). See
                enrich_top_n() docs.
                Default 0 = off (backward compatible).
    sort_by: [P1-16] sort criterion for unified results.
             "cite" (default), "year", or "relevance". See sort_results().
    source_filter: [P1-17] post-filter results to only show those from
             specified engines (e.g. ["openalex", "aminer"]). None/empty =
             no filter (default). See filter_by_source() for matching
             semantics. Use case: query many engines, display subset.
    enrich_max_age_years: skip enrichment for papers older than this many years; set 0 to disable.
    engine_timeout: maximum seconds for one engine before its result is
             marked as an error and the remaining engines continue.
    """
    engines = (["crossref", "openalex", "arxiv", "aminer", "pubmed", "clinicaltrials"]
               if engine == "all" else [e.strip() for e in engine.split(",")])
    # v3.9.8.2 (2026-07-15): CORE is no longer in the default "all" list.
    # OpenAlex already indexes CORE's repos, so marginal coverage is <5%.
    # If user explicitly asks for `--engine core`, route to search_core().
    if engine == "core":
        papers = search_core(query, year_min, year_max, limit)
        return {
            "results": papers,
            "by_engine": {"core": papers},
            "engine_status": {"core": {"status": "ok", "count": len(papers)}},
            "dedup_count": len(papers),
        }
    by_engine: Dict[str, List[Dict]] = {}
    engine_status: Dict[str, Dict[str, Any]] = {}
    funcs = {
        "crossref": search_crossref,
        "openalex": search_openalex,
        "arxiv": search_arxiv,
        # v3.9.11.8 (2026-08-09): PubMed medical engine, no auth required.
        "pubmed": search_pubmed,
        # v3.9.12.0 (2026-08-10): ClinicalTrials.gov, no auth, JSON API.
        # Note: returns trial registry records (NOT papers). Different
        # content type from PubMed/PEDro. Will appear as source='clinicaltrials'.
        "clinicaltrials": search_clinicaltrials,
    }
    # AMiner is optional 鈥?only include if token is set (avoid hard-fail on first run)
    if "aminer" in engines:
        from .aminer_channel import _aminer_token
        if not _aminer_token():
            # Surface an unavailable optional engine instead of silently hiding it.
            by_engine["aminer"] = []
            engine_status["aminer"] = {"status": "skipped", "count": 0,
                                        "message": "AMiner API token is not configured"}
            engines = [e for e in engines if e != "aminer"]
        else:
            from .aminer_channel import search_aminer
            funcs["aminer"] = search_aminer
    for eng in engines:
        if eng not in funcs:
            by_engine[eng] = []
            engine_status[eng] = {"status": "unsupported", "count": 0,
                                  "message": f"Unsupported search engine: {eng}"}
            continue
        try:
            # Pass concepts_filter to OpenAlex; other engines ignore extra args.
            if eng == "openalex" and concepts_filter:
                invoke = lambda search_func=search_openalex: search_func(
                    query, year_min, year_max, limit, concepts_filter=concepts_filter
                )
            elif eng == "aminer":
                invoke = lambda search_func=funcs[eng]: search_func(
                    query, year_min, year_max, limit, mode=aminer_mode
                )
            else:
                invoke = lambda search_func=funcs[eng]: search_func(
                    query, year_min, year_max, limit
                )
            by_engine[eng] = _run_engine_with_timeout(invoke, engine_timeout)
            engine_status[eng] = {"status": "ok", "count": len(by_engine[eng])}
        except EngineRateLimitError as e:
            by_engine[eng] = []
            engine_status[eng] = {"status": "rate_limited", "count": 0,
                                  "message": str(e)[:200]}
        except Exception as e:
            by_engine[eng] = []
            engine_status[eng] = {"status": "error", "count": 0,
                                  "message": str(e)[:200]}

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

    # Use a provider summary as an abstract only when no abstract is present.
    for r in seen.values():
        if not r.get("abstract") and r.get("tldr"):
            r["abstract"] = r["tldr"]

    unified = sort_results(list(seen.values()), sort_by=sort_by)

    # Top-N deep enrichment (v3.9.7.8): second-hop lookups for top-N results
    # that lack cite/abstract. Off by default (enrich_top=0).
    if enrich_top > 0:
        enrich_top_n(unified, n=enrich_top,
                     resort_by=sort_by, max_age_years=enrich_max_age_years)
    elif sort_by != "cite":
        # Even without enrichment, ensure final sort matches user request
        unified = sort_results(unified, sort_by=sort_by)

    # [P1-17] Post-filter by source if requested (after sort + dedup, before return)
    if source_filter:
        pre_count = len(unified)
        unified = filter_by_source(unified, source_filter=source_filter)
        post_count = len(unified)
        if pre_count != post_count:
            print(f"  [P1-17] filter_by_source: {pre_count} -> {post_count} "
                  f"(kept only: {','.join(source_filter)})", file=sys.stderr)

    return {
        "query": query,
        "year_min": year_min,
        "year_max": year_max,
        "by_engine": {k: len(v) for k, v in by_engine.items()},
        "engine_status": engine_status,
        "dedup_count": len(unified),
        "enrich_top": enrich_top,
        "results": unified,
    }
