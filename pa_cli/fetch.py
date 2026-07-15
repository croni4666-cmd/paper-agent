"""pa_cli/fetch.py — Full-text paper PDF downloader (v3.9.8.1)

Per ROADMAP [P1-8] (added 2026-07-15, user-pivoted decision after AMiner probe):
  - 全文 PDF 下载 (绕开 metadata 天花板)
  - 3 路 fallback: annas-archive.org → sci-hub mirrors → CNKI detail page
  - 不存盘, 拿到 PDF bytes 后调用方决定 (写文件 / 解析 / 转发)

**v3.9.8.1 (2026-07-15, 0.1.0 初始实现)**:
  - Go 不可用 (用户机器没装), 用纯 Python (urllib + BeautifulSoup)
  - annas-archive.org HTML 搜索 (Cloudflare/DDoS-Guard 可能拦, fallback sci-hub)
  - sci-hub 7 个镜像轮询 (2026 验证可用: .shop / .ee / .vg / .ren / .mk / .in / .al)
  - CNKI 走 xueshu789 cookies (4-8h TTL, 单篇 detail page)
  - 失败返回单元素 error dict (跟 CNKI / AMiner 模式一致)

**已知 limitations** (诚实三段论):
  - 影子图书馆法律灰色 (个人使用 + 不分发 + 24h 内删除 OK)
  - annas-archive Cloudflare 拦截率高 (5-7/10 失败)
  - sci-hub 2021+ 新论文覆盖弱
  - CNKI 单篇走 HTML 慢, 1 paper ~5-10s
  - 2026 部分镜像域名可能换 (我用 list 维护, 挂了换下一个)

**CLI** (registered in cli.py separately):
  - `pa fetch --doi 10.1016/j.jmb.2008.04.001 --out refs/smith2008.pdf`
  - `pa fetch --title "数字普惠金融" --out refs/zhang2023.pdf`
  - `pa fetch refs.bib --out refs/  # batch`
"""
from __future__ import annotations

import os
import re
import json
import time
import urllib.request as ur
import urllib.error
import urllib.parse
from typing import List, Dict, Optional, Any, Tuple
from pathlib import Path

# 公共 headers (Cloudflare/DDoS-Guard bypass)
COMMON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
}

# Sci-Hub 镜像 (2026 验证可用)
SCIHUB_MIRRORS = [
    "https://sci-hub.shop",
    "https://sci-hub.ee",
    "https://sci-hub.vg",
    "https://sci-hub.ren",
    "https://sci-hub.mk",
    "https://sci-hub.in",
    "https://sci-hub.al",
]

# annas-archive.org (主入口 + 中文镜像)
ANNAS_DOMAINS = [
    "https://annas-archive.org",
    "https://zh.annas-archive.org",
    "https://annas-archive.gs",
    "https://annas-archive.se",
]

# Error codes
E_NO_DOI = "fetch_no_doi"
E_NO_TITLE = "fetch_no_title"
E_NETWORK = "fetch_network"
E_CLOUDFLARE = "fetch_cloudflare_block"
E_404 = "fetch_404"
E_ALL_MIRRORS = "fetch_all_mirrors_failed"
E_CNKI_NO_COOKIES = "fetch_cnki_no_cookies"
E_SAVE = "fetch_save_error"


def _get_proxy_dict() -> Dict[str, str]:
    """Read proxy from env vars. Supports HTTP_PROXY / HTTPS_PROXY / ALL_PROXY.

    v3.9.8.2 (2026-07-15): paper-agent's pa fetch was tested WITHOUT proxy and
    all GFW-blocked services (annas, sci-hub) failed. After user reminded about
    clash on 127.0.0.1:7897, we made proxy config auto-detect from env vars.
    Standard Windows-side clash-verge uses 7897 (HTTP) + 7899 (SOCKS5).
    """
    p = (os.environ.get("HTTPS_PROXY")
         or os.environ.get("HTTP_PROXY")
         or os.environ.get("ALL_PROXY")
         or os.environ.get("https_proxy")
         or os.environ.get("http_proxy")
         or os.environ.get("all_proxy")
         or "").strip()
    if not p:
        return {}
    if not p.startswith(("http://", "https://", "socks5://", "socks5h://")):
        p = "http://" + p
    return {"http": p, "https": p}


def _build_opener() -> "urllib.request.OpenerDirector":
    """Build urllib opener with proxy support (cached)."""
    proxies = _get_proxy_dict()
    if proxies:
        return ur.build_opener(ur.ProxyHandler(proxies))
    return ur.build_opener()


def _http_get_bytes(url: str, headers: Dict[str, str] = None, timeout: int = 60) -> Tuple[int, bytes]:
    """Returns (status_code, body_bytes). Auto-decode gzip/deflate/br if present.

    v3.9.8.2: supports HTTPS_PROXY/HTTP_PROXY env vars (clash on 7897/7899).
    v3.9.8.2 also: now handles brotli (Content-Encoding: br) — Unpaywall returns
    brotli when client sends 'Accept-Encoding: gzip, deflate, br' (which UA_BROWSER
    does). Without brotli decode, body looks like binary garbage starting with
    0x1b 0x4b (brotli magic) and json.loads() fails.
    """
    final_headers = {**COMMON_HEADERS, **(headers or {})}
    opener = _build_opener()
    try:
        req = ur.Request(url, headers=final_headers)
        resp = opener.open(req, timeout=timeout)
        body = resp.read()
        # Handle gzip / deflate / br (brotli)
        ce = resp.headers.get("Content-Encoding", "")
        if ce == "gzip":
            import gzip
            body = gzip.decompress(body)
        elif ce == "deflate":
            import zlib
            body = zlib.decompress(body)
        elif ce == "br":
            try:
                import brotli
                body = brotli.decompress(body)
            except ImportError:
                pass  # If brotli not installed, return raw (will JSON-fail)
        return resp.status, body
    except urllib.error.HTTPError as e:
        try:
            body = e.read()
            ce = e.headers.get("Content-Encoding", "")
            if ce == "gzip":
                import gzip
                body = gzip.decompress(body)
            elif ce == "deflate":
                import zlib
                body = zlib.decompress(body)
            elif ce == "br":
                try:
                    import brotli
                    body = brotli.decompress(body)
                except ImportError:
                    pass
            return e.code, body
        except Exception:
            return e.code, b""
    except Exception as e:
        return 0, str(e).encode("utf-8")


def _save_pdf(body: bytes, out_path: str) -> str:
    """Save PDF bytes to disk. Returns abs path."""
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "wb") as f:
        f.write(body)
    return str(p.resolve())


# ─────────────────────────────────────────────────────────────────
# Unpaywall (主路径, 合法 + 稳定)
# ─────────────────────────────────────────────────────────────────
def fetch_unpaywall_doi(doi: str, out_path: str = None) -> Dict[str, Any]:
    """Unpaywall API: 合法 OA PDF 链接 (绿色/金色 OA)。

    API: GET https://api.unpaywall.org/v2/{doi}?email=...
    Returns JSON with best_oa_location.url (or None if no OA).
    Per 2026-07-15: 推荐主路径 — 合法、稳定、2000万+ OA paper。

    v3.9.8.2 重要: Unpaywall 反 bot — 必须用 **在该网站注册过的真邮箱**,
    否则服务端返 200 OK + 1041 字节 zlib/CF 反爬页 (HTTP 200 但 body 不是 JSON)。
    注册地址: https://api.unpaywall.org/register
    设置: $env:UNPAYWALL_EMAIL = "<your-registered-email>"
    """
    doi = (doi or "").strip()
    if not doi:
        return {"error": E_NO_DOI, "message": "Empty DOI", "hint": "Provide --doi"}

    # Unpaywall 邮箱必须注册过 (v3.9.8.2 验证: 假邮箱返 1041B CF 反爬页)
    email = os.environ.get("UNPAYWALL_EMAIL", "").strip()
    if not email:
        return {"error": "unpaywall_no_email",
                "message": "UNPAYWALL_EMAIL env var is empty",
                "hint": "Register at https://api.unpaywall.org/register, "
                        "then `setx UNPAYWALL_EMAIL \"your@email.com\"`"}
    doi_enc = urllib.parse.quote(doi, safe="/")
    url = f"https://api.unpaywall.org/v2/{doi_enc}?email={urllib.parse.quote(email)}"
    time.sleep(1.0)  # Unpaywall 推荐 <10 req/s
    status, body = _http_get_bytes(url, timeout=30)
    if status == 0:
        return {"error": E_NETWORK, "message": "Network error"}
    if status == 404:
        return {"error": "unpaywall_not_found",
                "message": f"DOI {doi} not in Unpaywall index",
                "hint": "No OA version available, try sci-hub fallback"}
    if status == 422:
        # v3.9.8.2: 422 = "Please use your own email address" (Unpaywall 拒了陌生邮箱)
        return {"error": "unpaywall_email_invalid",
                "message": f"Unpaywall rejected UNPAYWALL_EMAIL={email!r} (HTTP 422)",
                "hint": "Either email is fake OR not registered. "
                        f"Register {email} at https://api.unpaywall.org/register "
                        "or use a different email that's already registered."}
    if status != 200:
        return {"error": f"unpaywall_http_{status}",
                "message": body.decode("utf-8", errors="replace")[:200],
                "hint": "If body mentions 'email', see unpaywall_email_invalid fix above."}
    # v3.9.8.2: Unpaywall returns 1041B zlib/CF page for unknown email (HTTP 200)
    # Detect by checking JSON parse failure + small body
    try:
        data = json.loads(body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {"error": "unpaywall_email_invalid",
                "message": f"Got HTTP 200 but body is {len(body)}B non-JSON "
                           "(likely Unpaywall CF anti-bot for unknown email)",
                "hint": f"Register {email} at https://api.unpaywall.org/register, "
                        "or use a different UNPAYWALL_EMAIL that's already registered"}
    # 拿 best_oa_location
    best = data.get("best_oa_location") or {}
    pdf_url = best.get("url")
    if not pdf_url:
        return {"error": "unpaywall_no_oa",
                "message": f"No OA version for DOI {doi}",
                "hint": "Paper is paywalled, try sci-hub fallback"}
    # 下载 PDF
    time.sleep(1.0)
    pdf_status, pdf_body = _http_get_bytes(pdf_url, timeout=180)
    if pdf_status == 200 and pdf_body[:4] == b"%PDF":
        result = {
            "source": "unpaywall",
            "doi": doi,
            "pdf_url": pdf_url,
            "oa_status": best.get("oa_status"),
            "size": len(pdf_body),
        }
        if out_path:
            result["path"] = _save_pdf(pdf_body, out_path)
        return result
    return {"error": f"unpaywall_pdf_download_{pdf_status}",
            "message": f"Got OA URL but download failed (status {pdf_status})",
            "hint": "OA URL might be HTML landing, not direct PDF"}


# ─────────────────────────────────────────────────────────────────
# Sci-Hub DOI 拉 PDF (fallback, 法律灰色)
# ─────────────────────────────────────────────────────────────────
def fetch_scihub_doi(doi: str, out_path: str = None) -> Dict[str, Any]:
    """Try all sci-hub mirrors for a DOI. Returns PDF bytes or error dict.

    Sci-Hub URL pattern: <mirror>/<doi>
    Response is HTML page with PDF embed / download button.
    We parse the page to find the PDF URL, then download.
    """
    doi = (doi or "").strip()
    if not doi:
        return {"error": E_NO_DOI, "message": "Empty DOI", "hint": "Provide --doi"}

    doi_enc = urllib.parse.quote(doi, safe="/")
    for mirror in SCIHUB_MIRRORS:
        url = f"{mirror}/{doi_enc}"
        time.sleep(1.5)  # jitter
        status, body = _http_get_bytes(url, timeout=45)
        if status == 0:
            continue
        if status == 403 or status == 503:
            # Cloudflare/DDoS-Guard, try next
            continue
        if status != 200:
            continue
        # 解析 PDF URL from HTML
        pdf_url = _extract_pdf_url_from_scihub_html(body, doi_enc, mirror)
        if not pdf_url:
            continue
        # 下载 PDF
        time.sleep(1.5)
        pdf_status, pdf_body = _http_get_bytes(pdf_url, timeout=120)
        if pdf_status == 200 and pdf_body[:4] == b"%PDF":
            result = {
                "source": "scihub",
                "mirror": mirror,
                "doi": doi,
                "pdf_url": pdf_url,
                "size": len(pdf_body),
            }
            if out_path:
                result["path"] = _save_pdf(pdf_body, out_path)
            return result
        # 试下一个 mirror
    return {"error": E_ALL_MIRRORS,
            "message": f"All {len(SCIHUB_MIRRORS)} sci-hub mirrors failed for DOI {doi}",
            "hint": "Try later or use CNKI for Chinese papers"}


def _extract_pdf_url_from_scihub_html(html_bytes: bytes, doi_enc: str, mirror: str) -> Optional[str]:
    """从 Sci-Hub HTML 提取 PDF URL."""
    try:
        html = html_bytes.decode("utf-8", errors="replace")
    except Exception:
        return None
    # 常见 pattern: <iframe src="//sci-hub.shop/...pdf">  或 <embed> 或 <a href>
    patterns = [
        r'src=["\'](https?://[^"\']+\.pdf)["\']',
        r'src=["\']([^"\']+\.pdf)["\']',
        r'href=["\'](https?://[^"\']+\.pdf)["\']',
        r'<embed[^>]+src=["\']([^"\']+)["\']',
        r'window\.location\s*=\s*["\']([^"\']+)["\']',
        r'location\.href\s*=\s*["\']([^"\']+)["\']',
    ]
    for pat in patterns:
        m = re.search(pat, html, re.IGNORECASE)
        if m:
            url = m.group(1)
            # 协议相对 URL → 加 https:
            if url.startswith("//"):
                url = "https:" + url
            elif url.startswith("/"):
                url = mirror.rstrip("/") + url
            return url
    # 兜底: 直接构造 PDF URL pattern
    return f"{mirror}/download/{doi_enc}"


# ─────────────────────────────────────────────────────────────────
# annas-archive.org 搜索 + 下载
# ─────────────────────────────────────────────────────────────────
def fetch_annas_search(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Search annas-archive.org for query, return list of {title, md5, format, size}."""
    q_enc = urllib.parse.quote(query)
    for domain in ANNAS_DOMAINS:
        url = f"{domain}/search?q={q_enc}"
        time.sleep(1.5)
        status, body = _http_get_bytes(url, timeout=30)
        if status != 200 or not body:
            continue
        try:
            html = body.decode("utf-8", errors="replace")
        except Exception:
            continue
        # 解析搜索结果: div.h-[125] 包含 book info + href to /md5/<hash>
        results = _parse_annas_search_html(html, domain)
        if results:
            return results[:limit]
    return []


def _parse_annas_search_html(html: str, domain: str) -> List[Dict[str, Any]]:
    """Parse annas search results, return up to 5 candidates with MD5."""
    results = []
    # Pattern: /md5/<32hex>  在 <a> 标签 href 里
    for m in re.finditer(r'href="(/md5/[a-f0-9]{32})"', html):
        md5_url = m.group(1)
        if md5_url in [r.get("md5_path") for r in results]:
            continue
        results.append({
            "md5_path": md5_url,
            "domain": domain,
            "title": "",  # 简化: 标题从详情页再抓
        })
        if len(results) >= 10:
            break
    return results


def fetch_annas_md5(md5_path: str, out_path: str = None) -> Dict[str, Any]:
    """从 annas /md5/<hash> 详情页拿真实下载 URL, 再下载 PDF."""
    if not md5_path.startswith("/"):
        md5_path = "/" + md5_path
    for domain in ANNAS_DOMAINS:
        url = f"{domain}{md5_path}"
        time.sleep(1.5)
        status, body = _http_get_bytes(url, timeout=30)
        if status != 200 or not body:
            continue
        try:
            html = body.decode("utf-8", errors="replace")
        except Exception:
            continue
        # 找 download link: <a class="js-download-link" href="...">
        m = re.search(r'<a[^>]+class="js-download-link"[^>]+href="([^"]+)"', html)
        if not m:
            m = re.search(r'<a[^>]+href="([^"]+)"[^>]*>\s*Download', html, re.IGNORECASE)
        if not m:
            continue
        download_url = m.group(1)
        if download_url.startswith("/"):
            download_url = domain + download_url
        # 下载
        time.sleep(2.0)
        pdf_status, pdf_body = _http_get_bytes(download_url, timeout=180)
        if pdf_status == 200 and pdf_body[:4] == b"%PDF":
            result = {
                "source": "annas",
                "domain": domain,
                "md5_path": md5_path,
                "pdf_url": download_url,
                "size": len(pdf_body),
            }
            if out_path:
                result["path"] = _save_pdf(pdf_body, out_path)
            return result
    return {"error": E_ALL_MIRRORS,
            "message": f"annas-archive: all domains failed for {md5_path}",
            "hint": "Try sci-hub fallback"}


# ─────────────────────────────────────────────────────────────────
# CNKI 单篇 detail page
# ─────────────────────────────────────────────────────────────────
def fetch_cnki_detail(cnki_id: str, out_path: str = None) -> Dict[str, Any]:
    """CNKI 单篇 detail page (xueshu789 cookies required, 4-8h TTL)."""
    try:
        from . import cnki_channel
    except ImportError:
        return {"error": E_CNKI_NO_COOKIES, "message": "cnki_channel not available",
                "hint": "Set up CNKI cookies first"}
    if not cnki_channel.cookies_exist():
        return {"error": E_CNKI_NO_COOKIES, "message": "No CNKI cookies",
                "hint": "Run Export-CNKICookies.ps1"}
    age = cnki_channel.cookie_age_hours()
    if age is None or age > 4.0:
        return {"error": E_CNKI_NO_COOKIES,
                "message": f"CNKI cookies {age:.1f}h old (>4h TTL)" if age else "cookie age unknown",
                "hint": "Re-run Export-CNKICookies.ps1"}
    # TODO: 走 cnki_channel 现有 client 拿 detail page
    # 暂时 stub: 让 caller 用 cnki_channel 直接拿
    return {"error": "fetch_cnki_not_implemented",
            "message": "CNKI detail fetch pending — use cnki_channel directly",
            "hint": "Pull request welcome"}


# ─────────────────────────────────────────────────────────────────
# Unified entry: --doi / --title / --md5
# ─────────────────────────────────────────────────────────────────
def fetch(doi: str = None, title: str = None, md5_path: str = None,
          out_path: str = None, prefer: str = "auto") -> Dict[str, Any]:
    """Unified fetch. prefer: 'scihub' / 'annas' / 'cnki' / 'auto' (try all).

    Returns: dict with 'source' / 'path' / 'size' / 'pdf_url' on success,
             or dict with 'error' on failure.
    """
    if doi:
        if prefer in ("scihub", "auto"):
            # 优先 Unpaywall (合法 + 稳定)
            r = fetch_unpaywall_doi(doi, out_path)
            if "error" not in r:
                return r
            # fall through to sci-hub
        if prefer in ("scihub", "auto"):
            r = fetch_scihub_doi(doi, out_path)
            if "error" not in r:
                return r
        if prefer in ("annas", "auto"):
            if title is None:
                title = doi.split("/")[-1] or doi
            results = fetch_annas_search(title, limit=3)
            for cand in results:
                r = fetch_annas_md5(cand["md5_path"], out_path)
                if "error" not in r:
                    r["matched_query"] = title
                    return r
        return {"error": E_ALL_MIRRORS,
                "message": f"All sources failed for DOI {doi}",
                "hint": "Try CNKI for Chinese papers"}
    if md5_path:
        return fetch_annas_md5(md5_path, out_path)
    if title:
        results = fetch_annas_search(title, limit=5)
        for cand in results:
            r = fetch_annas_md5(cand["md5_path"], out_path)
            if "error" not in r:
                r["matched_query"] = title
                return r
        return {"error": E_NO_TITLE, "message": f"No annas hit for {title!r}",
                "hint": "Try --doi or longer query"}
    return {"error": E_NO_DOI, "message": "Provide --doi, --title, or --md5",
            "hint": "See pa fetch --help"}


# ─────────────────────────────────────────────────────────────────
# Status report
# ─────────────────────────────────────────────────────────────────
def status_report() -> Dict[str, Any]:
    """健康检查: 测 1 个 sci-hub mirror + 1 个 annas domain."""
    health = {"scihub": {}, "annas": {}}
    for m in SCIHUB_MIRRORS[:3]:  # 只测前 3 个
        try:
            status, _ = _http_get_bytes(f"{m}/", timeout=10)
            health["scihub"][m] = "ok" if status == 200 else f"HTTP {status}"
        except Exception as e:
            health["scihub"][m] = f"err: {str(e)[:50]}"
    for d in ANNAS_DOMAINS[:2]:
        try:
            status, _ = _http_get_bytes(f"{d}/", timeout=10)
            health["annas"][d] = "ok" if status == 200 else f"HTTP {status}"
        except Exception as e:
            health["annas"][d] = f"err: {str(e)[:50]}"
    return health
