"""pa_cli/aminer_channel.py — AMiner 7th search engine (v3.9.8.0)

Per ROADMAP [P1-7] (added 2026-07-15, user-decided after B+→A gap analysis):
  - AMiner 智谱学术 API 集成 (hobbyist budget: 3880 calls 一次性体验金)
  - 中文 paper 收录比 CNKI 更广 (3.3 亿 papers, 含中英文)
  - 引用追踪 (cited_by_count) 是 AMiner 强项
  - 60 天 token 期限 (用户控制台设的, 30 天是默认)

**v3.9.8.0 (2026-07-15, 0.1.0 初始实现)**:
  - 实现核心 paper/search 端点
  - 不实现 person/search + reference graph (那些耗 token 多, 后续按需)
  - 1.2s jitter 避免触发限流
  - 失败返回单元素 error dict (跟 CNKI 模式一致)

**已知 limitations** (诚实三段论):
  - 一次免费包 3880 calls, 用完充值 Token 才能继续 (违反 Global Rule 长期条款)
  - 用户机器 token 60 天后过期, 需重新生成
  - 一些 paper 字段缺失: tldr, open_access, abstract (AMiner 跟 S2 一样对中文 paper 弱)

**未来路径**:
  - Day 2-3 评估 cite% 提升 ≥ 7pp 才考虑付费
  - 不付费就走"全文路径" [P1-8] pa fetch
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

# AMiner API endpoint
AM_BASE = "https://datacenter.aminer.cn/gateway/open_platform/api"
AM_PAPER_SEARCH = f"{AM_BASE}/paper/search"

# Error codes (跟 CNKI 模式一致)
E_NO_TOKEN = "aminer_no_token"
E_NETWORK = "aminer_network"
E_AUTH = "aminer_auth"
E_QUOTA = "aminer_quota"
E_EMPTY = "aminer_empty_response"


def _aminer_token() -> Optional[str]:
    """Read AMiner API token from env. JWT format (from open.aminer.cn control panel)."""
    return os.environ.get("AMINER_API_KEY") or os.environ.get("AM_API_KEY")


def _http_get(url: str, headers: Dict[str, str], timeout: int = 30) -> tuple:
    """Returns (status_code, json_dict or error_string)."""
    try:
        req = ur.Request(url, headers=headers)
        resp = ur.urlopen(req, timeout=timeout)
        body = resp.read().decode("utf-8", errors="replace")
        try:
            return resp.status, json.loads(body)
        except json.JSONDecodeError:
            return resp.status, body[:500]
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8", errors="replace")
            try:
                return e.code, json.loads(err_body)
            except json.JSONDecodeError:
                return e.code, err_body[:500]
        except Exception:
            return e.code, str(e)
    except Exception as e:
        return 0, str(e)[:300]


def search_aminer(query: str, year_min: int = None, year_max: int = None,
                  limit: int = 20) -> List[Dict]:
    """AMiner paper search — handles multi-word queries by splitting + unioning.

    Per v3.9.8.0 finding (2026-07-15):
      AMiner 不支持复合 multi-word query (空格分词 = 0 结果)
      但单短语 query 召回极强 (e.g. "数字普惠金融" → 1915 papers)
    Strategy: split query on whitespace, run each phrase separately,
              union + dedupe by aminer_id, return top `limit` by year desc.

    Returns: list of result dicts (normalized to paper-agent schema).
             On failure (no token / network / auth / quota / parse),
             returns single-element list with "error" key.
    """
    token = _aminer_token()
    if not token:
        return [{"error": E_NO_TOKEN,
                 "message": "AMINER_API_KEY not set",
                 "hint": "Set $env:AMINER_API_KEY = '<your JWT token>'"}]

    # 拆 query: AMiner 单短语最强, 多词 = 0 结果
    phrases = [p.strip() for p in (query or "").split() if p.strip()]
    if not phrases:
        return [{"error": E_EMPTY, "message": "Empty query",
                 "hint": "Provide non-empty query string"}]
    # 如果就 1 个短语, 直接跑; 多个就 union
    # 限制最多 3 个短语 (省 token)
    phrases = phrases[:3]
    # size 限制: 每个短语最多取 limit*2 给 union 留 dedup 余量
    size_per_phrase = min(limit * 2, 50)

    # union results by aminer_id
    seen = {}  # aminer_id -> result dict
    errors = []
    for ph in phrases:
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
            # 用 ph 作为 phrase 标签
            seen[aid] = (it, ph)
        # 每个短语之间再加 1s (避免 rate limit)
        time.sleep(0.5)

    if not seen:
        # 全失败 / 全空
        if errors:
            return [{"error": E_EMPTY,
                     "message": f"All phrases empty/failed (errors: {errors[:2]})",
                     "hint": "Try shorter / single-phrase query"}]
        return [{"error": E_EMPTY,
                 "message": "All phrases returned 0 items",
                 "hint": "AMiner doesn't index this term"}]

    # 合并 → 转 paper-agent schema
    # AMiner 真实响应结构 (实测 v3.9.8.0 2026-07-15):
    #   {
    #     "code": 200, "success": true, "msg": "",
    #     "data": [ {doi, first_author, id, n_citation_bucket, title, title_zh, venue_name, year} ],
    #     "total": 12345,
    #     "log_id": "..."
    #   }
    # 关键: 引用是桶式 (n_citation_bucket, e.g. "51-200", "5000+"), 抽象是空, 作者只有 first_author
    has_cjk = any('一' <= c <= '鿿' for c in (query or ""))
    results = []
    for aid, (it, ph) in seen.items():
        # 标题: 中文 query 优先 title_zh
        title_zh = it.get("title_zh") or ""
        title_en = it.get("title") or ""
        if has_cjk and title_zh:
            title = title_zh
        else:
            title = title_en or title_zh

        # 作者: 包装成 list (AMiner 只给 first_author)
        first_author = (it.get("first_author") or "").strip()
        authors = [first_author] if first_author else []

        # 年份
        try:
            year = int(it.get("year")) if it.get("year") else None
        except (ValueError, TypeError):
            year = None

        # 引用数: n_citation_bucket 桶式字符串
        bucket = (it.get("n_citation_bucket") or "").strip()
        cited = _bucket_to_cited(bucket)

        # 期刊/会议
        venue = (it.get("venue_name") or "").strip()

        # 客户端 year filter
        if year_min and (year is None or year < year_min):
            continue
        if year_max and (year is None or year > year_max):
            continue

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
        })

    # 按年份降序排, 取 limit
    results.sort(key=lambda r: r.get("year") or 0, reverse=True)
    return results[:limit]


# AMiner citation bucket 转换 (免费版只有桶式, 没具体数字)
# 用来做"has_cite"判断, 不是真实被引数
def _bucket_to_cited(bucket: str) -> int:
    """Convert AMiner n_citation_bucket (e.g. '51-200', '5000+') to int midpoint.
    Returns 0 for empty/'0', bucket midpoint otherwise.
    Note: 这只是粗略估计, 用于过滤 + 排序, 不代表真实被引数。
    """
    if not bucket or bucket == "0":
        return 0
    # 范围 "51-200"
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
    # 单数字
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
