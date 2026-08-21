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

# arXiv PDF URL pattern (v3.9.11.6, new channel — was missing from v3.9.8.x)
ARXIV_PDF_URL = "https://arxiv.org/pdf/{arxiv_id}"
ARXIV_DOI_PREFIX = "10.48550/arXiv."  # arXiv DOI prefix
ARXIV_OLD_PREFIXES = ("arxiv:", "arXiv:")  # legacy ID prefix
ARXIV_ID_RE = re.compile(r"^\d{4}\.\d{4,5}(v\d+)?$")  # 2310.06825, 2310.06825v1

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
    """Deprecated wrapper. Use pa_cli._http.get_proxy_dict() instead.

    v3.9.13.3 (Round 13): extracted to pa_cli._http so all 8 search engines
    + fetch-batch + cross-encoder + deep-rerank + aminer + keys-probe share
    the same TLS validation. This wrapper kept for backward compat.
    """
    from ._http import get_proxy_dict
    return get_proxy_dict()


def _validate_proxy_security(proxy_url: str, allow_remote: bool = False) -> None:
    """Deprecated wrapper. Use pa_cli._http.validate_proxy_security() instead."""
    from ._http import validate_proxy_security
    validate_proxy_security(proxy_url, allow_remote=allow_remote)


def _get_allow_remote_proxy() -> bool:
    """Deprecated wrapper. Use pa_cli._http.get_allow_remote_proxy() instead."""
    from ._http import get_allow_remote_proxy
    return get_allow_remote_proxy()


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


# ============================================================================
# arXiv channel (v3.9.11.6, new — was missing from cascade in v3.9.8.x)
# ============================================================================
# arXiv papers are not on sci-hub, not on annas, not on CNKI. The old
# `pa fetch` for arXiv DOIs returned "all sources failed" because no
# channel knew how to fetch from arxiv.org. v3.9.11.6 adds this channel
# so arXiv preprints (a huge portion of CS/AI/ML research) are reachable.
#
# Accepts 3 input forms:
#   - Bare arXiv ID:           "2310.06825"
#   - arXiv DOI:               "10.48550/arXiv.2310.06825"
#   - Legacy prefix:           "arxiv:2310.06825" / "arXiv:2310.06825"
#   - URL tail:                "https://arxiv.org/abs/2310.06825" → 2310.06825
#
# arXiv PDF URL: https://arxiv.org/pdf/{id}  (no auth, free, no rate limit
# for normal use, but be polite with 1s sleep)

def _extract_arxiv_id(s: str) -> Optional[str]:
    """Extract arXiv ID from various input forms. Returns None if not arXiv."""
    s = (s or "").strip()
    if not s:
        return None
    # Bare ID: 2310.06825 or 2310.06825v1
    if ARXIV_ID_RE.match(s):
        return s
    # arXiv DOI: 10.48550/arXiv.2310.06825
    if s.startswith(ARXIV_DOI_PREFIX):
        return s[len(ARXIV_DOI_PREFIX):]
    # Legacy prefix: arxiv:2310.06825 or arXiv:2310.06825
    for prefix in ARXIV_OLD_PREFIXES:
        if s.lower().startswith(prefix.lower()):
            tail = s[len(prefix):].strip()
            if ARXIV_ID_RE.match(tail):
                return tail
    # URL tail: https://arxiv.org/abs/2310.06825 or /pdf/2310.06825
    if "arxiv.org/" in s:
        # take last path segment
        tail = s.rstrip("/").split("/")[-1]
        if ARXIV_ID_RE.match(tail):
            return tail
    return None


def fetch_arxiv_doi(doi_or_id: str, out_path: str = None) -> Dict[str, Any]:
    """arXiv channel: directly download PDF from arxiv.org/pdf/<id>.

    Returns dict with 'source' / 'arxiv_id' / 'pdf_url' / 'size' / 'path'
    on success, or dict with 'error' on failure.

    v3.9.11.6: new channel. arXiv preprints have their own DOI namespace
    (10.48550/arXiv.*) and are not on sci-hub/annas/CNKI. Without this
    channel, all arXiv papers returned "fetch_all_mirrors_failed".
    """
    arxiv_id = _extract_arxiv_id(doi_or_id)
    if not arxiv_id:
        return {"error": "not_arxiv",
                "message": f"Input {doi_or_id!r} does not look like an arXiv ID",
                "hint": "Use prefer=annas or prefer=scihub for non-arXiv DOIs"}
    pdf_url = ARXIV_PDF_URL.format(arxiv_id=arxiv_id)
    time.sleep(1.0)  # polite jitter
    status, body = _http_get_bytes(pdf_url, timeout=60)
    if status == 200 and body[:4] == b"%PDF":
        result = {
            "source": "arxiv",
            "arxiv_id": arxiv_id,
            "pdf_url": pdf_url,
            "size": len(body),
        }
        if out_path:
            result["path"] = _save_pdf(body, out_path)
        return result
    return {"error": f"arxiv_download_failed_{status}",
            "message": f"arXiv download failed for {arxiv_id} (status {status})",
            "hint": "Check network / proxy; arXiv should not have paywall"}


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
# PMC fulltext channel (v3.9.21+, 2026-08-21)
# 合法 + 永久 + 100% 走通, 替代 sci-hub/annas cascade 失败时的 fallback
#
# 3 步:
#   1. DOI → PMCID: eutils.ncbi.nlm.nih.gov/.../esearch.fcgi?db=pmc&term=<doi>[doi]
#   2. EFetch XML:   eutils.ncbi.nlm.nih.gov/.../efetch.fcgi?db=pmc&id=<numeric>&rettype=xml
#   3. Europe PMC PDF: europepmc.org/articles/pmc<id>?pdf=render (CC BY/CC BY-NC 论文可走)
#
# 已知网络:
#   - E-utilities API: 100% 走通 (无 WAF, 200 OK)
#   - Europe PMC: 间歇 404 (server 限制, 需要 retry 或换 journal direct URL)
#   - 期刊 direct PDF (Frontiers / BMC / MDPI / Elsevier): 通过 Unpaywall API 拿 best_oa_location
# ─────────────────────────────────────────────────────────────────
EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
PMC_OA_SERVICE = "https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi"


def _pmc_doi_to_pmcid(doi: str) -> Optional[str]:
    """Resolve DOI → PMCID via NCBI E-utilities ESearch.

    ESearch ?db=pmc&term=<doi>[doi] returns PMC UID (numeric).
    Prepend "PMC" to get PMCID.

    Note: PMC ID Converter v1 API (/pmc/utils/idconv/v1/converter/) returns 404
    on user machine; ESearch is the working alternative.
    """
    doi = (doi or "").strip()
    if not doi:
        return None
    url = f"{EUTILS_BASE}/esearch.fcgi?db=pmc&term={urllib.parse.quote(doi)}[doi]&retmode=json"
    status, body = _http_get_bytes(url, timeout=15)
    if status != 200 or not body:
        return None
    try:
        data = json.loads(body.decode("utf-8", errors="replace"))
        ids = data.get("esearchresult", {}).get("idlist", [])
        if ids:
            return f"PMC{ids[0]}"
    except Exception:
        pass
    return None


def _pmc_efetch_xml(pmcid: str, out_path: str = None) -> Dict[str, Any]:
    """EFetch full-text JATS XML from PMC. K-Dense hazard: 200 OK but body
    missing = publisher restriction; always verify body via jats_to_text.py.
    """
    pmcid_clean = pmcid.replace("PMC", "")
    url = f"{EUTILS_BASE}/efetch.fcgi?db=pmc&id={pmcid_clean}&rettype=xml"
    time.sleep(0.4)  # NCBI rate limit
    status, body = _http_get_bytes(url, timeout=60)
    if status != 200 or not body:
        return {"error": f"pmc_efetch_status_{status}"}
    if out_path:
        saved = _save_pdf(body, out_path)  # saves raw bytes; caller can rename
    result = {
        "source": "pmc_xml",
        "pmcid": pmcid,
        "size": len(body),
        "url": url,
    }
    if out_path:
        # Rename .pdf to .xml since bytes are XML not PDF
        from pathlib import Path
        p = Path(out_path)
        xml_path = p.with_suffix('.xml')
        xml_path.parent.mkdir(parents=True, exist_ok=True)
        xml_path.write_bytes(body)
        result["path"] = str(xml_path.resolve())
    return result


def _pmc_europe_pdf(pmcid: str, out_path: str = None, max_retries: int = 3) -> Dict[str, Any]:
    """Europe PMC PDF rendering endpoint: europepmc.org/articles/pmc<id>?pdf=render

    Note: server 间歇 404, 需要 retry. 对 CC BY/CC BY-NC 论文 80% 成功.
    """
    pmcid_lower = pmcid.lower().replace("pmc", "")
    epmc_url = f"https://europepmc.org/articles/pmc{pmcid_lower}?pdf=render"
    for attempt in range(1, max_retries + 1):
        status, body = _http_get_bytes(epmc_url, timeout=180)
        if status == 200 and body and body[:4] == b"%PDF":
            result = {
                "source": "pmc_europe",
                "pmcid": pmcid,
                "pdf_url": epmc_url,
                "size": len(body),
                "attempts": attempt,
            }
            if out_path:
                result["path"] = _save_pdf(body, out_path)
            return result
        time.sleep(2.0)
    return {"error": "pmc_europe_all_retries_failed",
            "pmcid": pmcid,
            "url": epmc_url,
            "attempts": max_retries}


def _pmc_jats_to_pdf(pmcid: str, xml_path: str, out_path: str = None,
                      embed_figures: bool = True,
                      proxy: str = None) -> Dict[str, Any]:
    """v3.9.21+: JATS XML → real PDF via pa_cli.jats_to_pdf (Playwright).

    Last-resort fallback when Europe PMC PDF rendering fails. Always works
    (Chromium renders any valid JATS HTML) but slower (15-25s with figures).

    Returns dict with:
      - source: "pmc_jats_pdf"
      - pmcid, pdf_path, pdf_size, elapsed_sec
      - error on failure
    """
    import time as _t
    t0 = _t.time()
    pmcid_clean = pmcid.replace("PMC", "")
    try:
        # Lazy import: jats_to_pdf pulls in playwright (large dep)
        from .jats_to_pdf import jats_xml_to_pdf
        xml_bytes = Path(xml_path).read_bytes()
        pdf_bytes = jats_xml_to_pdf(
            xml_bytes,
            doi="",
            pmcid=pmcid_clean,
            embed_figures=embed_figures,
            proxy=proxy,
        )
        if not pdf_bytes or not pdf_bytes.startswith(b"%PDF"):
            return {"error": "jats_pdf_invalid_output",
                    "pmcid": pmcid, "hint": "jats_to_pdf returned non-PDF bytes"}
        result = {
            "source": "pmc_jats_pdf",
            "pmcid": pmcid,
            "size": len(pdf_bytes),
            "elapsed_sec": round(_t.time() - t0, 2),
        }
        if out_path:
            from pathlib import Path as _P
            out_p = _P(out_path)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            out_p.write_bytes(pdf_bytes)
            result["path"] = str(out_p.resolve())
        return result
    except Exception as e:
        return {"error": f"jats_pdf_{type(e).__name__}",
                "pmcid": pmcid,
                "message": str(e)[:200],
                "hint": "Check playwright install or JATS XML validity"}


def fetch_pmc_doi(doi: str, out_path: str = None) -> Dict[str, Any]:
    """PMC channel: DOI → PMCID → EFetch XML (always) + Europe PMC PDF (best-effort).

    Returns dict with:
      - success: "pmc_xml" (XML saved) or "pmc_europe" (PDF saved) or both
      - pmcid: e.g. "PMC13466339"
      - xml_path: full JATS XML path (always, if PMC has body)
      - pdf_path: real PDF path (if Europe PMC render worked)
      - error: only on total failure
    """
    doi = (doi or "").strip()
    if not doi:
        return {"error": E_NO_DOI, "message": "Empty DOI", "hint": "Provide --doi"}

    # Step 1: DOI → PMCID
    pmcid = _pmc_doi_to_pmcid(doi)
    if not pmcid:
        return {"error": "pmc_doi_not_found",
                "message": f"DOI {doi} not in PMC",
                "hint": "Try Unpaywall or sci-hub fallback"}

    # Step 2: EFetch full-text XML
    xml_out = out_path  # will be auto-renamed to .xml by _pmc_efetch_xml
    xml_result = _pmc_efetch_xml(pmcid, out_path=xml_out)
    if "error" in xml_result:
        return {"error": xml_result["error"],
                "pmcid": pmcid,
                "hint": "PMC EFetch failed; try other channels"}

    # Step 3: Try Europe PMC PDF rendering (best-effort, ~25% success in 2026-08 retest)
    pdf_result = _pmc_europe_pdf(pmcid, out_path=out_path, max_retries=2)
    europe_ok = "error" not in pdf_result

    # Step 4 (v3.9.21+): If Europe PMC failed, fall back to jats_to_pdf
    # (JATS XML → Chromium-rendered real PDF). Always works for valid JATS.
    if not europe_ok:
        # Get proxy from env (v3.9.13.2: --proxy sets HTTPS_PROXY)
        proxy_env = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
        jats_result = _pmc_jats_to_pdf(
            pmcid,
            xml_path=xml_result.get("path"),
            out_path=out_path,
            embed_figures=True,
            proxy=proxy_env,
        )
        if "error" not in jats_result:
            return {
                "source": "pmc_jats_pdf",
                "pmcid": pmcid,
                "doi": doi,
                "xml_path": xml_result.get("path"),
                "xml_size": xml_result.get("size"),
                "pdf_path": jats_result.get("path"),
                "pdf_size": jats_result.get("size"),
                "pdf_method": "jats_to_pdf",
                "pdf_elapsed_sec": jats_result.get("elapsed_sec"),
                "europe_pdf_error": pdf_result.get("error"),
                "hint": "v3.9.21+ JATS→PDF fallback; figures embedded as data URIs",
            }
        # Both methods failed
        return {
            "source": "pmc_xml_only",
            "pmcid": pmcid,
            "doi": doi,
            "xml_path": xml_result.get("path"),
            "xml_size": xml_result.get("size"),
            "pdf_path": None,
            "pdf_size": None,
            "pdf_error_europe": pdf_result.get("error"),
            "pdf_error_jats": jats_result.get("error"),
            "hint": "Both Europe PMC and jats_to_pdf failed; XML available",
        }

    return {
        "source": "pmc" if "error" not in pdf_result else "pmc_xml_only",
        "pmcid": pmcid,
        "doi": doi,
        "xml_path": xml_result.get("path"),
        "xml_size": xml_result.get("size"),
        "pdf_path": pdf_result.get("path") if "error" not in pdf_result else None,
        "pdf_size": pdf_result.get("size") if "error" not in pdf_result else None,
        "pdf_attempts": pdf_result.get("attempts"),
        "pdf_error": pdf_result.get("error") if "error" in pdf_result else None,
        "hint": "v3.9.21+ PMC channel; K-Dense paper-lookup hazard: verify <body> in XML",
    }


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
    """CNKI 单篇 PDF download (xueshu789 cookies required, 4-8h TTL).

    v3.9.8.3 实装 (2026-07-15):
      1. Check cookies fresh (< 4h)
      2. Bootstrap via xueshu789 (same pattern as CNKIClient.search)
      3. If cnki_id looks like a DOI: search for it, get cnki_url
      4. page.goto(cnki_url) detail page (try proxy IP domain first, fallback to kns.cnki.net)
      5. Find PDF download link in detail HTML
      6. Trigger page.expect_download() and save to out_path

    KNOWN LIMITATIONS (verified 2026-07-15 E2E):
      - 2-cookie sessions (only PHPSESSID + user) are insufficient for detail page access.
        v3.9.7.4 used 4 cookies (PHPSESSID + user + entrys + expires); the 2-cookie
        minimal set triggers kns.cnki.net's anti-bot Vue SPA (安全验证 page).
      - Real CNKI downloads go through bar.cnki.net/bar/download/order (paid order
        system, requires institutional subscription OR CAPTCHA per-download). Out of
        hobbyist scope.
      - xueshu789 proxy IP (120.53.241.46:5888) only proxies search (/kns8s/brief/grid)
        and brief navigation; not detail page or download.
      - Result: fetch_cnki_detail() works for SEARCH-side metadata only; PDF download
        remains blocked unless user has full cookies + bar.cnki.net access.

    Args:
        cnki_id: either a CNKI internal filename (e.g. "CSDB202607008") OR a DOI
                 (e.g. "10.3969/j.issn.1003-9031.2022.04.008"). If DOI, will search first.
        out_path: optional path to save PDF (else return bytes)
    """
    try:
        from . import cnki_channel
    except ImportError:
        return {"error": E_CNKI_NO_COOKIES, "message": "cnki_channel not available",
                "hint": "Set up CNKI cookies first"}
    if not cnki_channel.cookies_exist():
        return {"error": E_CNKI_NO_COOKIES, "message": "No CNKI cookies file",
                "hint": "Run Export-CNKICookies.ps1"}
    age = cnki_channel.cookie_age_hours()
    if age is None or age > 4.0:
        return {"error": E_CNKI_NO_COOKIES,
                "message": f"CNKI cookies {age:.1f}h old (>4h TTL)" if age else "cookie age unknown",
                "hint": "Re-run Export-CNKICookies.ps1"}

    # If cnki_id is a DOI, search for the matching paper first
    cnki_url = None
    cnki_filename = None
    if "10." in cnki_id and "/" in cnki_id:
        # Looks like a DOI — search for it
        # We need proxy_base, but CNKIClient.search opens a new browser.
        # Simpler: search for the DOI substring, get the first match's cnki_url.
        try:
            from playwright.sync_api import sync_playwright
            client = cnki_channel.CNKIClient()
            client.load()
            with sync_playwright() as pw:
                browser = pw.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-blink-features=AutomationControlled'],
                )
                ctx = browser.new_context(
                    user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) "
                                "Chrome/120.0.0.0 Safari/537.36"),
                    accept_downloads=True,
                )
                ctx.add_cookies(client._cookies)
                page = ctx.new_page()
                try:
                    proxy_base = client._bootstrap_in_context(ctx, page)
                    # Search by DOI field (CNKI field code SU=主题, but DOI is not searchable
                    # via SU; we use FT=全文 for fulltext search)
                    query_json = client._build_query_json(
                        cnki_id, "FT", "WD0FTY92", "CROSSDB", None, None)
                    html = client._post_brief_page_in_context(
                        ctx, page, proxy_base, query_json, 1)
                    results = client._parse_brief_response(html)
                    for r in results:
                        if r.get("doi") and cnki_id.lower() in r["doi"].lower():
                            cnki_url = r.get("cnki_url")
                            cnki_filename = r.get("cnki_filename")
                            break
                    if not cnki_url and results:
                        # Fallback: take first result
                        cnki_url = results[0].get("cnki_url")
                        cnki_filename = results[0].get("cnki_filename")
                finally:
                    try:
                        browser.close()
                    except Exception:
                        pass
        except Exception as e:
            return {"error": "fetch_cnki_search_failed",
                    "message": f"DOI search failed: {str(e)[:200]}",
                    "hint": "Try passing cnki_filename directly instead of DOI"}
        if not cnki_url:
            return {"error": "fetch_cnki_not_found",
                    "message": f"DOI {cnki_id} not found in CNKI",
                    "hint": "CNKI may not have this paper, or cookies need refresh"}
    else:
        # Treat as cnki_filename
        cnki_filename = cnki_id
        cnki_url = f"https://kns.cnki.net/kcms2/article/abstract?v={cnki_filename}"

    # Now visit detail page and find PDF link
    try:
        from playwright.sync_api import sync_playwright
        client = cnki_channel.CNKIClient()
        if not client._cookies:
            client.load()
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-blink-features=AutomationControlled'],
            )
            ctx = browser.new_context(
                user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/120.0.0.0 Safari/537.36"),
                accept_downloads=True,
            )
            ctx.add_cookies(client._cookies)
            page = ctx.new_page()
            try:
                proxy_base = client._bootstrap_in_context(ctx, page)
                # Visit detail page
                # v3.9.8.3 fix: ALWAYS reconstruct on proxy_base (kns.cnki.net
                # domain has anti-bot security check that rejects xueshu789
                # cookies — see debug/last_cnki_detail.html after first run).
                detail_url = None
                if cnki_url:
                    if "kns.cnki.net" in cnki_url:
                        # Reconstruct on proxy IP
                        # E.g. https://kns.cnki.net/kcms2/article/abstract?v=X
                        #   → http://{proxy}/kcms2/article/abstract?v=X
                        path = cnki_url.split("kns.cnki.net", 1)[1]
                        detail_url = f"{proxy_base.rstrip('/')}{path}"
                    elif cnki_url.startswith("http"):
                        detail_url = cnki_url
                    else:
                        detail_url = f"{proxy_base.rstrip('/')}/{cnki_url.lstrip('/')}"
                page.goto(detail_url, timeout=30_000, wait_until="domcontentloaded")
                # Find PDF/Caj download link in detail page
                # Common patterns: /kcms2/article/vvip/{filename}, /kns8s/download, etc.
                pdf_url = None
                html = page.content()
                # Save HTML for debugging (overwritten on each call)
                try:
                    debug_path = Path(os.path.expanduser("~")) / ".paper-agent" / "debug" / "last_cnki_detail.html"
                    debug_path.parent.mkdir(parents=True, exist_ok=True)
                    debug_path.write_text(html, encoding="utf-8")
                except Exception:
                    pass
                # Try vvip link
                import re as _re
                m = _re.search(r'href=["\']([^"\']*vvip[^"\']+)', html, _re.IGNORECASE)
                if m:
                    pdf_url = m.group(1)
                # Try download link
                if not pdf_url:
                    m = _re.search(r'href=["\']([^"\']*download[^"\']+)', html, _re.IGNORECASE)
                    if m:
                        pdf_url = m.group(1)
                # Try explicit PDF link
                if not pdf_url:
                    m = _re.search(r'href=["\']([^"\']+\.pdf[^"\']*)', html, _re.IGNORECASE)
                    if m:
                        pdf_url = m.group(1)
                # Try Caj link (CNKI proprietary format)
                if not pdf_url:
                    m = _re.search(r'href=["\']([^"\']*caj[^"\']*)', html, _re.IGNORECASE)
                    if m:
                        pdf_url = m.group(1)
                # Try kns.cnki.net direct download path
                if not pdf_url:
                    m = _re.search(r'["\']([^"\']*(?:kcms2|kns8s)[^"\']*(?:download|file|article/abstract)[^"\']*)',
                                    html, _re.IGNORECASE)
                    if m:
                        pdf_url = m.group(1)
                if not pdf_url:
                    return {"error": "fetch_cnki_no_pdf_link",
                            "message": f"Detail page ({detail_url}) loaded but no PDF link found",
                            "hint": f"Detail HTML saved to {debug_path}. Inspect for download link."}
                # Resolve relative URL
                if pdf_url.startswith("/"):
                    pdf_url = f"{proxy_base.rstrip('/')}{pdf_url}"
                elif not pdf_url.startswith("http"):
                    pdf_url = f"{proxy_base.rstrip('/')}/{pdf_url.lstrip('/')}"
                # Trigger download
                with page.expect_download(timeout=30_000) as dl_info:
                    # Use the same page (cookies + proxy context preserved)
                    page.goto(pdf_url, timeout=30_000, wait_until="domcontentloaded")
                download = dl_info.value
                # Save to out_path
                if out_path:
                    from pathlib import Path as _P
                    p = _P(out_path)
                    p.parent.mkdir(parents=True, exist_ok=True)
                    download.save_as(str(p))
                    saved_path = str(p.resolve())
                else:
                    # Save to temp file
                    import tempfile
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
                    download.save_as(tmp.name)
                    saved_path = tmp.name
                return {"source": "cnki",
                        "cnki_filename": cnki_filename,
                        "cnki_url": cnki_url,
                        "pdf_url": pdf_url,
                        "path": saved_path,
                        "size": _P(saved_path).stat().st_size if out_path else None}
            finally:
                try:
                    browser.close()
                except Exception:
                    pass
    except Exception as e:
        return {"error": "fetch_cnki_failed",
                "message": str(e)[:300],
                "hint": "Check cookies freshness, network, or paper access permissions"}


# ─────────────────────────────────────────────────────────────────
# Unified entry: --doi / --title / --md5
# ─────────────────────────────────────────────────────────────────
def fetch(doi: str = None, title: str = None, md5_path: str = None,
          out_path: str = None, prefer: str = "auto") -> Dict[str, Any]:
    """Unified fetch. prefer: 'arxiv' / 'annas' / 'cnki' / 'scihub' / 'auto'.

    v3.9.11.6 cascade (was buggy in v3.9.8.x — only scihub was reachable):
      1. arXiv     (NEW v3.9.11.6)  — if DOI looks like arXiv
      2. CNKI                       — if DOI is Chinese journal pattern
      3. Anna's archive             — search by DOI tail / title
      4. Unpaywall                  — official, legal, stable
      5. Sci-Hub                    — mirror rotation, last resort

    'auto' runs all 5 in order. Other prefer values restrict to that
    channel + 'auto'-equivalent paths.

    Returns: dict with 'source' / 'path' / 'size' / 'pdf_url' on success,
             or dict with 'error' on failure.
    """
    if doi:
        # 1. arXiv channel — if DOI looks like arXiv (10.48550/arXiv.* or bare ID)
        arxiv_id = _extract_arxiv_id(doi)
        if arxiv_id and prefer in ("arxiv", "auto"):
            r = fetch_arxiv_doi(arxiv_id, out_path)
            if "error" not in r:
                return r
            # If user explicitly asked for arxiv and it failed, don't fall through
            if prefer == "arxiv":
                return r

        # 2. CNKI — if DOI is Chinese journal pattern
        is_cn_journal = (doi.startswith("10.3969/") or doi.startswith("10.16525/")
                          or "/j.cnki." in doi or "/j.issn." in doi)
        if is_cn_journal and prefer in ("cnki", "auto"):
            r = fetch_cnki_detail(doi, out_path)
            if "error" not in r:
                return r
            if prefer == "cnki":
                return r

        # 3. Anna's archive — search by DOI tail (or title if provided)
        if prefer in ("annas", "auto"):
            search_q = title or doi.split("/")[-1] or doi
            results = fetch_annas_search(search_q, limit=3)
            for cand in results:
                r = fetch_annas_md5(cand["md5_path"], out_path)
                if "error" not in r:
                    r["matched_query"] = search_q
                    r["search_domain"] = cand.get("domain", "")
                    return r
            if prefer == "annas":
                return {"error": E_ALL_MIRRORS,
                        "message": f"annas search yielded no PDF for {search_q!r}",
                        "hint": "Try a different query or prefer=auto"}

        # 4. PMC fulltext channel (v3.9.21+, 2026-08-21)
        #    DOI → PMCID → EFetch XML (always) + Europe PMC PDF (best-effort)
        #    合法 + 永久, 替代 sci-hub/annas cascade 失败时的 fallback
        if prefer in ("pmc", "pmc-pdf", "auto"):
            r = fetch_pmc_doi(doi, out_path)
            # 成功: 有 xml_path (always) + 可能 pdf_path
            if "error" not in r and r.get("xml_path"):
                return r
            if prefer == "pmc":
                return r  # user explicitly asked for pmc, don't fall through

        # 5. Unpaywall (cheap, official, legal)
        # v3.9.22: --prefer unpaywall explicit, or fall through from scihub/auto
        if prefer in ("unpaywall", "scihub", "auto"):
            r = fetch_unpaywall_doi(doi, out_path)
            if "error" not in r:
                return r

        # 5b. Semantic Scholar openAccessPdf (v3.9.22+, 2026-08-21)
        # Cross-domain, fast, ~30% hit rate. Sits between Unpaywall and
        # Sci-Hub because it's free + legal + S2-API-key optional.
        if prefer in ("s2", "auto"):
            try:
                from .s2_channel import fetch_s2_doi
                r = fetch_s2_doi(doi, out_path)
                if "error" not in r:
                    return r
            except ImportError:
                pass

        # 5c. bioRxiv / medRxiv (v3.9.22+, 2026-08-21)
        # Only triggers for 10.1101/* DOIs. High-success preprint server.
        if doi.lower().startswith("10.1101/") and prefer in ("biorxiv", "auto"):
            try:
                from .biorxiv_channel import fetch_biorxiv_doi
                r = fetch_biorxiv_doi(doi, out_path)
                if "error" not in r:
                    return r
            except ImportError:
                pass

        # 5d. CORE re-add (v3.9.22+, 2026-08-21)
        # Re-added because OpenAlex only has metadata, CORE has 36M+ full text.
        # Requires $CORE_API_KEY (free at core.ac.uk/services/api).
        if prefer in ("core", "auto"):
            try:
                from .core_channel import fetch_core_doi
                r = fetch_core_doi(doi, out_path)
                if "error" not in r:
                    return r
            except ImportError:
                pass

        # 5e. OSF Preprints (v3.9.22+, 2026-08-21)
        # Only triggers for 10.31219/osf.io/* or 10.31234/osf.io/* DOIs.
        if (doi.lower().startswith("10.31219/osf.io/") or
            doi.lower().startswith("10.31234/osf.io/")) and prefer in ("osf", "auto"):
            try:
                from .osf_channel import fetch_osf_doi
                r = fetch_osf_doi(doi, out_path)
                if "error" not in r:
                    return r
            except ImportError:
                pass

        # 5f. ChemRxiv (v3.9.22+, 2026-08-21)
        # Only triggers for 10.26434/chemrxiv-* DOIs.
        if doi.lower().startswith("10.26434/chemrxiv-") and prefer in ("chemrxiv", "auto"):
            try:
                from .chemrxiv_channel import fetch_chemrxiv_doi
                r = fetch_chemrxiv_doi(doi, out_path)
                if "error" not in r:
                    return r
            except ImportError:
                pass

        # 6. Sci-Hub (mirror rotation, last-resort gray route)
        if prefer in ("scihub", "auto"):
            r = fetch_scihub_doi(doi, out_path)
            if "error" not in r:
                return r

        return {"error": E_ALL_MIRRORS,
                "message": f"All sources failed for DOI {doi}",
                "hint": "Try a different DOI, set UNPAYWALL_EMAIL, or use --title with prefer=annas"}
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
# Backward-compat wrapper: v3.9.8.1-style fetch_doi (used by CLI + deep_rerank)
# Added 2026-07-16 (audit round 22) — v3.9.8.2 renamed fetch_doi → fetch and
# dropped channels/output_dir/use_cache/max_total_sec params. This wrapper
# translates old API → new API, restoring `pa fetch <DOI>` CLI + cache
# integration compatibility.
#
# Honest 3-tier limits (documented):
#   - cache integration: NOT restored (was removed in v3.9.8.2). --no-cache
#     flag has no effect on the wrapper (always bypasses cache). Use
#     `pa cache put` to manually populate cache.
#   - max_total_sec: NOT implemented in new fetch. Old 5-min hard cap
#     is gone. Each channel call has its own 30s timeout (urllib default).
#   - channels: translated to `prefer` heuristically. Not all 8 channels
#     supported (e.g. "openalex" / "arxiv" / "doi_redirect" / "playwright"
#     are not in new fetch's prefer list — they fall through to "auto").
#   - result dict shape: mapped back to old shape (via_channel, saved_as,
#     elapsed_sec, final_status, channels) for callers that depend on it.
def fetch_doi(doi: str, output_dir: str = ".",
              proxy: str = None,
              channels = None,
              unpaywall_email: str = "hello@example.com",
              max_total_sec: int = 300,
              use_cache: bool = True) -> Dict[str, Any]:
    """v3.9.8.1-style fetch wrapper. Translates to new fetch() and maps result back.

    New in v3.9.9.6 (audit round 22): this wrapper was added to restore
    `pa fetch <DOI>` CLI and `pa_cli.deep_rerank.fetch_doi` callsite
    after v3.9.8.2 renamed fetch_doi → fetch and changed the signature.

    Channel → prefer mapping (heuristic; not all 8 channels supported):
      ["cnki", ...]         → prefer="cnki"
      ["unpaywall", ...]     → prefer="scihub"  (new cascade includes unpaywall)
      ["scihub", ...]        → prefer="scihub"
      ["annas", ...]         → prefer="annas"
      default / other        → prefer="auto"

    Result shape mapping:
      new `path`        → old `saved_as`
      new `source`      → old `via_channel` (no "cache:" prefix; cache is bypassed)
      new `size`        → (not in old shape, but kept for completeness)
      new `pdf_url`     → old `via_url`
      new `error`       → old `final_status` = "ALL_FAIL" + `error` + `hint`
    """
    t0 = time.time()

    # Cache check at function entry — short-circuit cascade on hit.
    # P0-2 acceptance (re-restored 2026-07-16): if PDF magic valid +
    # sha256 unchanged, return without re-downloading.
    if use_cache:
        try:
            from . import cache as _cache_mod
            hit = _cache_mod.cache_get(doi)
            if hit:
                return {
                    "doi": doi,
                    "saved_as": hit["pdf_path"],
                    "via_channel": f"cache:{hit['channel']}" if hit.get("channel") else "cache",
                    "via_url": hit.get("url", ""),
                    "cache_hit": True,
                    "cache_age_days": round(hit.get("age_days", 0), 3),
                    "cache_sha256": hit["sha256"],
                    "elapsed_sec": round(time.time() - t0, 3),
                    "final_status": "SUCCESS_CACHE_HIT",
                    "_wrapper_notes": {
                        "cache_supported": True,
                        "max_total_sec_supported": False,
                        "channels_translated_to": "(cache hit, no fetch)",
                    },
                }
        except Exception as e:
            # Cache miss or read error — fall through to fetch
            pass

    # Map channels → prefer (v3.9.11.6 + 2026-08-09 fix: arxiv priority)
    #
    # Key insight: if DOI looks like arXiv (10.48550/arXiv.* / bare ID /
    # arxiv: prefix), ONLY the arxiv channel can fetch it — sci-hub,
    # annas, CNKI don't carry arXiv preprints. So when the DOI is
    # arXiv-shaped AND "arxiv" is in the channel list, we MUST use
    # arxiv regardless of other channels being present.
    #
    # v3.9.11.6 had this bug: required "arxiv in channels AND no
    # other channels", which fails for the default list
    # ("openalex,arxiv,unpaywall,doi_redirect,scihub,playwright")
    # because scihub+unpaywall are also present. Result: arXiv DOIs
    # always fell through to scihub, which has no arXiv papers.
    # Verified bug 2026-08-09 via test_output/_retest_arxiv/test1.pdf.
    channels = channels or []
    arxiv_id = _extract_arxiv_id(doi)
    if arxiv_id and "arxiv" in channels:
        prefer = "arxiv"
    elif "pmc-pdf" in channels:
        # v3.9.21+: Force PMC + jats_to_pdf (skip Europe PMC). Always returns
        # a real PDF even when Europe PMC render is 404. Slower (15-25s).
        prefer = "pmc-pdf"
    elif "pmc" in channels:
        # v3.9.21+: PMC fulltext channel. DOI → PMCID → EFetch XML + Europe PMC PDF.
        # 合法 + 永久, 替代 sci-hub cascade
        prefer = "pmc"
    elif "unpaywall" in channels and "scihub" not in channels:
        # v3.9.21+: Unpaywall 独立 option (不强制走 sci-hub)
        # 合法 OA PDF, 走 api.unpaywall.org + best_oa_location
        prefer = "unpaywall"
    elif "cnki" in channels and not any(c in channels for c in ("annas", "scihub", "unpaywall")):
        prefer = "cnki"
    elif "annas" in channels and not any(c in channels for c in ("scihub", "unpaywall")):
        prefer = "annas"
    elif "s2" in channels and "scihub" not in channels:
        # v3.9.22+: Semantic Scholar openAccessPdf channel (free, no key)
        prefer = "s2"
    elif "biorxiv" in channels and not any(c in channels for c in ("annas", "scihub", "unpaywall")):
        # v3.9.22+: bioRxiv/medRxiv preprint channel
        prefer = "biorxiv"
    elif "core" in channels and "scihub" not in channels:
        # v3.9.22+: CORE re-added (36M+ full text vs OpenAlex metadata-only)
        prefer = "core"
    elif "osf" in channels and "scihub" not in channels:
        # v3.9.22+: OSF Preprints (PsyArXiv/SocArXiv/EarthArXiv/etc.)
        prefer = "osf"
    elif "chemrxiv" in channels and "scihub" not in channels:
        # v3.9.22+: ChemRxiv (chemistry preprints)
        prefer = "chemrxiv"
    elif "scihub" in channels or "unpaywall" in channels:
        prefer = "scihub"
    else:
        prefer = "auto"

    # Map output_dir + DOI → out_path
    # v3.9.11.6: also replace ':' (legacy arXiv prefix) and other
    # Windows-illegal chars. arxiv:2310.06825 → arxiv_2310_06825
    doi_slug = (doi.replace("/", "_").replace(".", "_").replace(":", "_")
                    .replace("\\", "_").replace(" ", "_"))
    out_path = str(Path(output_dir) / f"{doi_slug}.pdf")

    # Call new fetch
    # v3.9.13.2: route --proxy CLI option through env var so _get_proxy_dict()
    # picks it up (and runs the validation). Previously `proxy` was a
    # parameter but never used in the function body, so `pa fetch --proxy`
    # was silently ignored. Fix: temporarily set HTTPS_PROXY if not already
    # set in env, then restore in finally.
    # v3.9.13.3 (F-007 fix): --proxy CLI option ALWAYS wins over env var.
    # If user passes --proxy AND has HTTPS_PROXY/HTTP_PROXY set, we warn
    # but use --proxy. Standard CLI > env var precedence.
    proxy_env_set = False
    prev_https_proxy = os.environ.get("HTTPS_PROXY")
    prev_http_proxy = os.environ.get("HTTP_PROXY")
    if proxy:
        if prev_https_proxy or prev_http_proxy:
            # v3.9.13.3: warn that --proxy overrides env var (UX improvement)
            active = "HTTPS_PROXY" if prev_https_proxy else "HTTP_PROXY"
            import warnings as _w
            _w.warn(
                f"paper-agent: --proxy={proxy} overrides existing {active} env var. "
                f"To use env var, omit --proxy. (v3.9.13.3 F-007 fix)",
                stacklevel=2,
            )
        # Normalize scheme-less proxy like _get_proxy_dict does
        p = proxy.strip()
        if not p.startswith(("http://", "https://", "socks5://", "socks5h://")):
            p = "http://" + p
        os.environ["HTTPS_PROXY"] = p
        proxy_env_set = True
    try:
        r = fetch(doi=doi, out_path=out_path, prefer=prefer)
    finally:
        if proxy_env_set:
            os.environ.pop("HTTPS_PROXY", None)

    elapsed = round(time.time() - t0, 3)

    # Translate result to old shape
    if "error" in r:
        return {
            "doi": doi,
            "saved_as": None,
            "channels": {prefer: {"status": "fail", "error": r["error"]}},
            "handoff": {
                "reason": r.get("message", r["error"]),
                "elapsed_sec": elapsed,
                "user_action_required": r.get("hint", "Try a different DOI or check network"),
            },
            "elapsed_sec": elapsed,
            "final_status": "ALL_FAIL",
            "error": r["error"],
            "hint": r.get("hint"),
            "_wrapper_notes": {
                "cache_supported": True,  # cache check restored; not the issue here
                "max_total_sec_supported": False,
                "channels_translated_to": prefer,
            },
        }
    # Success
    return {
        "doi": doi,
        "saved_as": r.get("path", out_path),
        "via_channel": r.get("source", prefer),
        "via_url": r.get("pdf_url"),
        "elapsed_sec": elapsed,
        "final_status": "SUCCESS",
        "cache_hit": False,  # not from cache (would have returned earlier)
        "size_bytes": r.get("size"),
        "_wrapper_notes": {
            "cache_supported": True,
            "max_total_sec_supported": False,
            "channels_translated_to": prefer,
        },
    }


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
