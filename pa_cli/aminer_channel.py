"""pa_cli/aminer_channel.py 鈥?AMiner 7th search engine (v3.9.8.0)

Per ROADMAP [P1-7] (added 2026-07-15, user-decided after B+鈫扐 gap analysis):
  - AMiner 鏅鸿氨瀛︽湳 API 闆嗘垚 (hobbyist budget: 3880 calls 涓€娆℃€т綋楠岄噾)
  - 涓枃 paper 鏀跺綍姣?CNKI 鏇村箍 (3.3 浜?papers, 鍚腑鑻辨枃)
  - 寮曠敤杩借釜 (cited_by_count) 鏄?AMiner 寮洪」
  - 60 澶?token 鏈熼檺 (鐢ㄦ埛鎺у埗鍙拌鐨? 30 澶╂槸榛樿)

**v3.9.8.0 (2026-07-15, 0.1.0 鍒濆瀹炵幇)**:
  - 瀹炵幇鏍稿績 paper/search 绔偣
  - 涓嶅疄鐜?person/search + reference graph (閭ｄ簺鑰?token 澶? 鍚庣画鎸夐渶)
  - 1.2s jitter 閬垮厤瑙﹀彂闄愭祦
  - 澶辫触杩斿洖鍗曞厓绱?error dict (璺?CNKI 妯″紡涓€鑷?

**宸茬煡 limitations** (璇氬疄涓夋璁?:
  - 涓€娆″厤璐瑰寘 3880 calls, 鐢ㄥ畬鍏呭€?Token 鎵嶈兘缁х画 (杩濆弽 Global Rule 闀挎湡鏉℃)
  - 鐢ㄦ埛鏈哄櫒 token 60 澶╁悗杩囨湡, 闇€閲嶆柊鐢熸垚
  - 涓€浜?paper 瀛楁缂哄け: tldr, open_access, abstract (AMiner 璺?S2 涓€鏍峰涓枃 paper 寮?

**鏈潵璺緞**:
  - Day 2-3 璇勪及 cite% 鎻愬崌 鈮?7pp 鎵嶈€冭檻浠樿垂
  - 涓嶄粯璐瑰氨璧?鍏ㄦ枃璺緞" [P1-8] pa fetch
"""
from __future__ import annotations

import os
import json
import time
import urllib.request as ur
import urllib.error
import urllib.parse
from typing import List, Dict, Optional, Any
from pathlib import Path

# AMiner API endpoints
AM_BASE = "https://datacenter.aminer.cn/gateway/open_platform/api"
AM_PAPER_SEARCH = f"{AM_BASE}/paper/search"          # basic, free, title-only
AM_PAPER_SEARCH_PRO = f"{AM_BASE}/paper/search/pro"    # pro, 楼0.01/call, multi-field

# Error codes (璺?CNKI 妯″紡涓€鑷?
E_NO_TOKEN = "aminer_no_token"
E_NETWORK = "aminer_network"
E_AUTH = "aminer_auth"
E_QUOTA = "aminer_quota"
E_EMPTY = "aminer_empty_response"
E_API_ERROR = "aminer_api_error"  # v3.9.25.0: Pro API non-200


def _aminer_token() -> Optional[str]:
    """Read AMiner API token from env. JWT format (from open.aminer.cn control panel)."""
    return os.environ.get("AMINER_API_KEY") or os.environ.get("AM_API_KEY")


def _http_get(url: str, headers: Dict[str, str], timeout: int = 30) -> tuple:
    """Returns (status_code, json_dict or error_string).

    v3.9.13.3: uses pa_cli._http so HTTPS_PROXY env var is honored.
    """
    from ._http import http_get_json as _http_get_json_helper
    return _http_get_json_helper(url, headers=headers, timeout=timeout)

def _title_relevance_score(title: str, query: str) -> float:
    """Score title relevance to full query. Returns 0.0-1.0.

    Used to re-rank AMiner basic search results (which only does phrase
    matching, not full-query relevance). For query "Wilson Disease":
      - "Wilson disease associated with ATP7B" 鈫?high score (both words)
      - "Dr. Wilson's recent work on..."        鈫?low score (only "Wilson")
      - "Cardiovascular disease prevention"      鈫?low score (only "Disease")

    Algorithm: tokenize title + query, compute Jaccard-like overlap of
    word sets. Returns 1.0 for exact match, 0.0 for no overlap.
    """
    import re
    if not title or not query:
        return 0.0
    # Tokenize: lowercase, split on non-alphanumeric (preserves Chinese chars)
    def tokenize(s: str) -> set:
        # For Chinese, use 2-gram split (AMiner Chinese title segmentation is hard)
        # For English, word split
        s_lower = s.lower()
        # Extract words: contiguous ASCII letters/digits OR CJK chars
        words = re.findall(r'[a-z0-9]+|[\u4e00-\u9fff]+', s_lower)
        return set(w for w in words if len(w) >= 2)

    title_words = tokenize(title)
    query_words = tokenize(query)
    if not query_words:
        return 0.0
    # Also include the full query as a phrase check (for "Wilson Disease" 鈫?match)
    query_lower = query.lower().strip()
    phrase_bonus = 0.5 if query_lower in title.lower() else 0.0
    # Jaccard overlap
    intersection = title_words & query_words
    jaccard = len(intersection) / len(query_words) if query_words else 0.0
    # Combined score: phrase bonus + jaccard, capped at 1.0
    return min(1.0, phrase_bonus + jaccard)


def search_aminer_pro(query: str, year_min: int = None, year_max: int = None,
                     limit: int = 20) -> List[Dict]:
    """AMiner Pro search (/paper/search/pro).

    v3.9.25.0: new. Uses the `keyword` parameter which supports multi-word
    queries natively (vs basic search which only does title exact match
    and returns 0 for space-separated queries).

    Pro API differences:
      - Cost: 楼0.01 per call (vs free basic)
      - Returns up to 100 results (vs 20 for basic)
      - Supports filters: keyword, title, abstract, author, org, venue, order
      - The `keyword` field is best for multi-word natural language queries

    When to use:
      - Multi-word English queries (e.g., "Wilson Disease") 鈥?basic returns 0
      - When you need > 20 results
      - When you want semantic search instead of exact title match

    Returns: list of result dicts (paper-agent schema). On failure, returns
    single-element list with "error" key.
    """
    token = _aminer_token()
    if not token:
        return [{"error": E_NO_TOKEN,
                 "message": "AMINER_API_KEY not set",
                 "hint": "Set $env:AMINER_API_KEY = '<your JWT token>'"}]

    if not (query or "").strip():
        return [{"error": E_EMPTY, "message": "Empty query",
                 "hint": "Provide non-empty query string"}]

    # Build query params
    params = {
        "keyword": query.strip(),
        "size": min(limit, 100),
    }
    if year_min:
        params["year_start"] = year_min
    if year_max:
        params["year_end"] = year_max

    url = f"{AM_PAPER_SEARCH_PRO}?{urllib.parse.urlencode(params)}"
    headers = {
        "Authorization": f"{token}",
        "X-Platform": "paper-agent",
        "Accept": "application/json",
    }
    time.sleep(1.2)  # jitter
    status, data = _http_get(url, headers)
    if status != 200 or not isinstance(data, dict):
        return [{"error": E_API_ERROR,
                 "query": query,
                 "status": status,
                 "data": str(data)[:200],
                 "hint": "Pro search costs 楼0.01/call. Check token or quota."}]

    items = data.get("data") or []
    results = []
    for it in items:
        # Pro API may return: id, title, title_zh, doi, year, authors, venue, etc.
        # Field names may differ from basic; normalize
        title_zh = it.get("title_zh") or ""
        title_en = it.get("title") or it.get("title_en") or ""
        title = title_zh if title_zh else title_en

        # Authors
        authors_raw = it.get("authors") or it.get("first_author") or ""
        if isinstance(authors_raw, list):
            authors = [a.get("name", "") if isinstance(a, dict) else str(a) for a in authors_raw]
        else:
            authors = [authors_raw] if authors_raw else []

        # Year
        try:
            year = int(it.get("year")) if it.get("year") else None
        except (ValueError, TypeError):
            year = None

        # Citation
        cited = 0
        for k in ("n_citation", "citation_count", "citations"):
            if it.get(k) is not None:
                try:
                    cited = int(it[k])
                    break
                except (ValueError, TypeError):
                    pass

        results.append({
            "doi": (it.get("doi") or "").replace("https://doi.org/", ""),
            "title": title,
            "authors": authors,
            "venue": it.get("venue") or it.get("venue_name") or "",
            "year": year,
            "cited_by_count": cited,
            "abstract": it.get("abstract") or it.get("abstract_en") or "",
            "is_oa": False,
            "oa_url": None,
            "source": "aminer",
            "type": "journal",
            "aminer_id": it.get("id") or it.get("aminer_id"),
            "matched_phrase": query,
            "match_type": "pro_keyword",  # v3.9.25.0 marker
        })

    # Sort by year desc, then by relevance (cites)
    results.sort(key=lambda r: ((r.get("year") or 0), r.get("cited_by_count") or 0), reverse=True)
    return results[:limit]


def search_aminer(query: str, year_min: int = None, year_max: int = None,
                  limit: int = 20, mode: str = "auto") -> List[Dict]:
    """AMiner paper search 鈥?handles multi-word queries intelligently.

    v3.9.25.0: refactored. Now supports 3 modes:
      - "basic" (free): only basic search with phrase-splitting (legacy behavior)
      - "pro" (楼0.01/call): only Pro search with `keyword` param
      - "auto" (default): pro for multi-word queries, basic for single-word

    The auto mode is the new default behavior. For multi-word English queries
    (e.g., "Wilson Disease"), pro search gives 100x better recall than basic
    because basic only does exact title match and returns 0 for spaces.

    Cost warning: pro mode costs 楼0.01 per call. User has 3880 calls total
    budget. Each multi-word search uses 1 pro call. Monitor usage.

    For "auto" mode, results from both basic and pro are combined, deduped
    by aminer_id, and ranked by:
      1. match_type priority: "pro_keyword" > "phrase:full" > "phrase:split"
      2. year (descending)
      3. cited_by_count (descending)
    """
    if mode == "pro":
        return search_aminer_pro(query, year_min, year_max, limit)
    elif mode == "basic":
        return _search_aminer_basic(query, year_min, year_max, limit)
    elif mode == "auto":
        # Multi-word queries: use pro for better recall
        words = (query or "").split()
        if len(words) >= 2:
            # Use pro first; fall back to basic if pro returns 0 or fails
            pro_results = search_aminer_pro(query, year_min, year_max, limit)
            # If pro returns error or empty, try basic
            if not pro_results or (len(pro_results) == 1 and "error" in pro_results[0]):
                basic_results = _search_aminer_basic(query, year_min, year_max, limit)
                # Mark basic results as fallback
                for r in basic_results:
                    if "match_type" not in r:
                        r["match_type"] = "basic_fallback"
                return _merge_aminer_results(pro_results, basic_results, limit)
            return pro_results
        else:
            # Single word: basic is fine
            return _search_aminer_basic(query, year_min, year_max, limit)
    else:
        # Invalid mode: default to auto
        return search_aminer(query, year_min, year_max, limit, mode="auto")


def _merge_aminer_results(pro: List[Dict], basic: List[Dict], limit: int) -> List[Dict]:
    """Merge pro + basic AMiner results, dedupe by aminer_id, rank.

    Ranking priority:
      1. pro_keyword matches (full query, Pro API)
      2. basic_fallback matches (split query, phrase-by-phrase)
      3. Within each group, by year desc, then by cited_by_count desc
    """
    # Filter errors
    pro_clean = [r for r in pro if "error" not in r]
    basic_clean = [r for r in basic if "error" not in r]

    # Dedupe by aminer_id
    seen = {}
    for r in pro_clean:
        aid = r.get("aminer_id")
        if aid and aid not in seen:
            seen[aid] = r
    for r in basic_clean:
        aid = r.get("aminer_id")
        if aid and aid not in seen:
            seen[aid] = r

    # Sort: pro first, then by year desc, then by cited_by_count desc
    def sort_key(r):
        is_pro = 1 if r.get("match_type") == "pro_keyword" else 0
        year = r.get("year") or 0
        cites = r.get("cited_by_count") or 0
        return (is_pro, year, cites)

    merged = sorted(seen.values(), key=sort_key, reverse=True)
    return merged[:limit]


# v3.9.25.0: extracted basic search as separate function
def _search_aminer_basic(query: str, year_min: int = None, year_max: int = None,
                        limit: int = 20) -> List[Dict]:
    """Basic AMiner search (free, /paper/search endpoint).

    Original v3.9.8.0 behavior: split multi-word query into phrases, search
    each separately, union + dedupe. Limited because:
      - Multi-word queries return 0 results from AMiner (per 2026-07-15 finding)
      - "Disease" alone returns too many irrelevant papers
      - "Wilson" alone matches authors

    Use `search_aminer(query, mode="pro")` or `search_aminer(query, mode="auto")`
    for multi-word English queries.
    """
    # v3.9.25.0: also try the full query as a phrase (might return 0 per legacy
    # behavior, but cheap to try; some AMiner endpoints may have evolved)
    token = _aminer_token()
    if not token:
        return [{"error": E_NO_TOKEN,
                 "message": "AMINER_API_KEY not set",
                 "hint": "Set $env:AMINER_API_KEY = '<your JWT token>'"}]

    # Try full query first as a phrase (might return 0)
    phrases = []
    if (query or "").strip():
        phrases.append(query.strip())
    # Then split into individual words
    split_phrases = [p.strip() for p in (query or "").split() if p.strip()]
    phrases.extend(split_phrases)
    # Dedupe (in case query is single word)
    seen_phrases = []
    for p in phrases:
        if p and p not in seen_phrases:
            seen_phrases.append(p)
    phrases = seen_phrases[:3]  # limit to 3 to save token

    if not phrases:
        return [{"error": E_EMPTY, "message": "Empty query",
                 "hint": "Provide non-empty query string"}]

    size_per_phrase = min(limit * 2, 50)

    # union results by aminer_id
    seen = {}  # aminer_id -> (result dict, phrase matched)
    errors = []
    for ph_idx, ph in enumerate(phrases):
        params = {"title": ph, "page": 1, "size": size_per_phrase}
        url = f"{AM_PAPER_SEARCH}?{urllib.parse.urlencode(params)}"
        headers = {
            "Authorization": f"{token}",
            "X-Platform": "paper-agent",
            "Accept": "application/json",
        }
        time.sleep(1.2)  # jitter
        status, data = _http_get(url, headers)
        if status != 200 or not isinstance(data, dict):
            errors.append({"phrase": ph, "status": status, "data": str(data)[:200]})
            continue
        items = data.get("data") or []
        for it in items:
            aid = it.get("id")
            if not aid or aid in seen:
                continue
            # Tag with which phrase matched
            match_type = "phrase:full" if ph_idx == 0 else f"phrase:{ph}"
            seen[aid] = (it, ph, match_type)
        # Inter-phrase rate limit
        time.sleep(0.5)

    if not seen:
        if errors:
            return [{"error": E_EMPTY,
                     "message": f"All phrases empty/failed (errors: {errors[:2]})",
                     "hint": "Try --aminer-mode pro for multi-word queries"}]
        return [{"error": E_EMPTY,
                 "message": "All phrases returned 0 items",
                 "hint": "AMiner doesn't index this term"}]

    # Build results
    has_cjk = any('\u4e00' <= c <= '\u9fff' for c in (query or ""))
    results = []
    for aid, (it, ph, match_type) in seen.items():
        title_zh = it.get("title_zh") or ""
        title_en = it.get("title") or ""
        if has_cjk and title_zh:
            title = title_zh
        else:
            title = title_en or title_zh

        first_author = (it.get("first_author") or "").strip()
        authors = [first_author] if first_author else []

        try:
            year = int(it.get("year")) if it.get("year") else None
        except (ValueError, TypeError):
            year = None

        bucket = (it.get("n_citation_bucket") or "").strip()
        cited = _bucket_to_cited(bucket)

        venue = (it.get("venue_name") or "").strip()

        # Year filter
        if year_min and (year is None or year < year_min):
            continue
        if year_max and (year is None or year > year_max):
            continue

        # v3.9.25.0: compute title relevance score
        relevance = _title_relevance_score(title, query)

        results.append({
            "doi": (it.get("doi") or "").replace("https://doi.org/", ""),
            "title": title,
            "authors": authors,
            "venue": venue,
            "year": year,
            "cited_by_count": cited,
            "cited_bucket": bucket,
            "abstract": "",
            "is_oa": False,
            "oa_url": None,
            "source": "aminer",
            "type": "journal",
            "aminer_id": aid,
            "matched_phrase": ph,
            "match_type": match_type,
            "title_relevance": relevance,  # v3.9.25.0: 0-1 score
        })

    # v3.9.25.0: sort by relevance (desc) + year (desc)
    # This way, papers with high title-query overlap surface first
    results.sort(key=lambda r: (
        r.get("title_relevance") or 0,
        r.get("year") or 0,
        r.get("cited_by_count") or 0
    ), reverse=True)
    return results[:limit]


# AMiner citation bucket 杞崲 (鍏嶈垂鐗堝彧鏈夋《寮? 娌″叿浣撴暟瀛?
# 鐢ㄦ潵鍋?has_cite"鍒ゆ柇, 涓嶆槸鐪熷疄琚紩鏁?
def _bucket_to_cited(bucket: str) -> int:
    """Convert AMiner n_citation_bucket (e.g. '51-200', '5000+') to int midpoint.
    Returns 0 for empty/'0', bucket midpoint otherwise.
    Note: 杩欏彧鏄矖鐣ヤ及璁? 鐢ㄤ簬杩囨护 + 鎺掑簭, 涓嶄唬琛ㄧ湡瀹炶寮曟暟銆?
    """
    if not bucket or bucket == "0":
        return 0
    # 鑼冨洿 "51-200"
    if "-" in bucket:
        try:
            lo, hi = bucket.split("-", 1)
            return (int(lo) + int(hi)) // 2
        except (ValueError, TypeError):
            return 0
    # "5000+", "1000+"
    if bucket.endswith("+"):
        try:
            return int(bucket[:-1])
        except ValueError:
            return 0
    # 鍗曟暟瀛?
    try:
        return int(bucket)
    except ValueError:
        return 0


def status_report() -> Dict[str, Any]:
    """Return AMiner channel readiness summary (for `pa aminer status` CLI)."""
    token = _aminer_token()
    return {
        "token_set": bool(token),
        "token_prefix": (token[:10] + "...") if token and len(token) > 10 else (token or None),
        "endpoint": AM_PAPER_SEARCH,
        "engine": "aminer",
    }
