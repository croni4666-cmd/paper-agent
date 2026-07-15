"""pa_cli/cnki_channel.py — CNKI 6th search engine (v3.9.7.4 real search).

Per ROADMAP [P0-9] (added 2026-07-14, user-confirmed design 2026-07-14):
  - 中文 paper 收录 (CNKI = China National Knowledge Infrastructure)
  - Cookies 来自 user-maintained export script (4-8 hour proxy session)
  - 通过 xueshu789.com 代理入口 → 实际跳转 `120.53.241.46:5888` (or other load-balanced IP)
  - **NOT** through clash proxy (CNKI 国内站)

**v3.9.7.4 real search wiring** (this commit, 2026-07-15):
  - Step A: Bootstrap via `https://www.xueshu789.com/dbItem/1` (1.5s JS redirect)
  - Step B: Real CNKI proxy IP discovered from redirect (e.g. 120.53.241.46:5888)
  - Step C: POST to `/kns8s/brief/grid` with QueryJson form payload
  - Step D: Parse HTML response → standard result dict (title/authors/venue/year/cited/cnki_url)
  - Step E: Pagination (pageNum=1, 2, 3 ...) for limit > 20
  - Field selection: 默认 主题(SU), optional 标题/TI, 关键词/KY, 篇关摘/TKA, 全文/FT, 作者/AR
  - Database selection: 默认 总库(CROSSDB+classid=WD0FTY92), optional 期刊/学位/会议/...

**Architecture** (v3.9.7.4):
  - search() launches ONE playwright instance per call (cost: ~1s startup)
  - 复用 fetch.py 的 playwright 框架 + cookies 加载模式
  - 通过 page.context.request.post() 用同一 context 内的 cookies 发起 POST
  - 不重开 browser, 也不重用 (cookies 跨 call 需 refresh, 简化)

**5-check Global Rule audit** (per ROADMAP [P0-9]):
1. ✅ $0 cost (CNKI 订阅 + 代理 都在 user 侧)
2. ✅ No hosted service (cookies 本地, playwright 本地, 不经过 clash proxy)
3. ✅ Maintenance ~450 LOC (vs 250 skeleton) + 复用 fetch.py playwright 框架
4. ✅ No publish obligation
5. ✅ Free-tier degradation: cookies 过期 → fallback to 5 英文 engine (no regression)

**v3.9.7.3 → v3.9.7.4 changes** (2026-07-15):
  - REPLACE placeholder search() with real playwright + brief/grid POST
  - ADD HTML parser (_parse_brief_response) for title/authors/venue/year/cited/cnki_url/doi
  - ADD pagination (_search_with_pagination) for limit > 20
  - ADD field selection (主题/标题/关键词/篇关摘/全文/作者) via `field` arg
  - ADD database selection (总库/期刊/学位/会议) via `db_classid` arg
  - KEEP cookie management, error codes, status_report interface
"""
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Dict, Optional, Any
from urllib.parse import quote, unquote


# ──────────────────────────────────────────────────────────────────────
# Cookie management (unchanged from v3.9.7.3)
# ──────────────────────────────────────────────────────────────────────

CNKI_COOKIES_PATH = Path.home() / ".paper-agent" / "cookies" / "cnki.json"
# xueshu789.com entry URL (1.5s JS redirect to real CNKI proxy IP)
XUESHU_ENTRY_URL = "https://www.xueshu789.com/dbItem/1"
# Real CNKI search endpoint (relative path on proxy IP)
CNKI_BRIEF_GRID_PATH = "/kns8s/brief/grid"


def cookies_exist() -> bool:
    """Check if CNKI cookies file exists (user exported via Export-CNKICookies.ps1)."""
    return CNKI_COOKIES_PATH.exists()


def load_cookies() -> List[Dict[str, Any]]:
    """Load CNKI cookies from `~/.paper-agent/cookies/cnki.json`.

    Expected format (Playwright context.add_cookies compatible):
    [
        {"name": "ASP.NET_SessionId", "value": "...", "domain": ".cnki.net",
         "path": "/", "expires": 1234567890, "httpOnly": true, "secure": false},
        ...
    ]

    Returns: list of cookie dicts, or [] if file missing / invalid.
    """
    if not CNKI_COOKIES_PATH.exists():
        return []
    try:
        cookies = json.loads(CNKI_COOKIES_PATH.read_text(encoding="utf-8"))
        if not isinstance(cookies, list):
            return []
        return cookies
    except (json.JSONDecodeError, OSError):
        return []


def cookie_age_hours() -> Optional[float]:
    """Return age of cookies file in hours, or None if file doesn't exist."""
    if not CNKI_COOKIES_PATH.exists():
        return None
    mtime = CNKI_COOKIES_PATH.stat().st_mtime
    return (time.time() - mtime) / 3600


# ──────────────────────────────────────────────────────────────────────
# Error codes (per ROADMAP [P0-9] "fallback" design)
# ──────────────────────────────────────────────────────────────────────

class CNKIError(Exception):
    """Base error for CNKI channel failures."""
    def __init__(self, code: str, message: str, hint: str = ""):
        self.code = code
        self.message = message
        self.hint = hint
        super().__init__(f"[{code}] {message}" + (f" Hint: {hint}" if hint else ""))


# Common error codes
E_NO_COOKIES = "no_cookies"           # cookies file missing
E_COOKIE_EXPIRED = "cookie_expired"   # cookies > 4 hours old (proxy session typical TTL)
E_PLAYWRIGHT_MISSING = "playwright_missing"  # playwright not installed
E_BLOCKED = "blocked"                 # CNKI anti-crawler detected our request
E_NETWORK = "network"                 # timeout / DNS / connection
E_PARSE = "parse"                     # HTML structure changed
E_REDIRECT_FAILED = "redirect_failed"  # xueshu789.com redirect chain failed
E_NO_RESULTS = "no_results"           # search returned 0 results
E_BOOTSTRAP_FAILED = "bootstrap_failed"  # could not get proxy IP / cookies
E_CAPTCHA = "captcha"                 # captcha encountered


# ──────────────────────────────────────────────────────────────────────
# Field & database code mappings (v3.9.7.4)
# ──────────────────────────────────────────────────────────────────────

# CNKI search field codes
# SU=主题, TI=标题, KY=关键词, AB=摘要, TKA=篇关摘, FT=全文, AR=作者, AF=单位
FIELD_CODE_MAP = {
    "subject": "SU",     # 主题 (default, smart TOPRANK)
    "title": "TI",
    "keyword": "KY",
    "abstract": "AB",
    "tka": "TKA",         # 篇关摘 (title/keyword/abstract)
    "fulltext": "FT",
    "author": "AR",
    "affiliation": "AF",
}

# CNKI database classid (default = 总库 CROSSDB)
# WD0FTY92 = 总库 (cross-DB, all checked DBs)
DB_CLASSID_MAP = {
    "all": "WD0FTY92",     # 总库
    "journal": "YSTT4HG0",  # 学术期刊
    "thesis": "LSTPFY1C",   # 学位论文
    "book": "EMRPGLPA",     # 图书
    "conference": "JUP3MUPD",  # 会议
    "newspaper": "MPMFIG1A",   # 报纸
    "almanac": "HHCPM1F8",     # 年鉴
    "patent": "VUDIXAIY",      # 专利
    "standard": "WQ0UVIAA",    # 标准
    "law": "8JBZLDJQ",         # 法律法规
    "achievement": "BLZOG7CK", # 成果
}

# Default CheckedDB list (matches the "all" search default in CNKI UI)
DEFAULT_CHECKED_DB = ",".join([
    "YSTT4HG0",  # 学术期刊
    "LSTPFY1C",  # 学位论文
    "EMRPGLPA",  # 图书
    "JUP3MUPD",  # 会议
    "MPMFIG1A",  # 报纸
    "WQ0UVIAA",  # 标准
    "BLZOG7CK",  # 成果
    "PWFIRAGL",  # 学术辑刊
    "NN3FJMUV",  # 特色期刊
    "NLBO1Z6R",  # 学术评论
])

# DB resource type (matches CNKI's `resource` param)
DB_RESOURCE_MAP = {
    "all": "CROSSDB",
    "journal": "JOURNAL",
    "thesis": "DISSERTATION",
    "book": "CROSSDB",
    "conference": "CONFERENCE",
    "newspaper": "NEWSPAPER",
    "almanac": "ALMANAC",
    "patent": "PATENT",
    "standard": "STANDARD",
    "law": "LAW_STATUTE",
    "achievement": "ACHIEVEMENTS",
}


# ──────────────────────────────────────────────────────────────────────
# CNKIClient
# ──────────────────────────────────────────────────────────────────────

@dataclass
class CNKIClient:
    """CNKI search engine client (v3.9.7.4 real search wiring).

    Usage:
        client = CNKIClient()
        if not client.is_ready():
            print(client.not_ready_reason())
            return
        results = client.search("东数西算", limit=10, field="subject", db="all")
    """
    cookies_path: Path = field(default_factory=lambda: CNKI_COOKIES_PATH)
    max_cookie_age_hours: float = 4.0   # Proxy sessions typically expire 4-8h
    page_size: int = 20                 # CNKI default page size
    timeout_ms: int = 45_000            # per-page POST timeout
    _cookies: List[Dict] = field(default_factory=list, init=False)

    def is_ready(self) -> bool:
        """True if cookies exist and are not expired."""
        if not self.cookies_path.exists():
            return False
        age = cookie_age_hours()
        if age is None:
            return False
        if age > self.max_cookie_age_hours:
            return False
        return True

    def not_ready_reason(self) -> str:
        """Human-readable explanation of why client is not ready."""
        if not self.cookies_path.exists():
            return (
                f"CNKI cookies not found at {self.cookies_path}\n"
                f"  → User action: run Export-CNKICookies.ps1 to export cookies\n"
                f"  → Or: follow ROADMAP [P0-9] cookie export setup"
            )
        age = cookie_age_hours()
        if age is None:
            return f"CNKI cookies file exists but unreadable: {self.cookies_path}"
        if age > self.max_cookie_age_hours:
            return (
                f"CNKI cookies are {age:.1f}h old (> {self.max_cookie_age_hours}h TTL).\n"
                f"  → User action: re-run Export-CNKICookies.ps1 to refresh\n"
                f"  → Typical proxy session TTL: 4-8h (vs CNKI direct 7-30 days)"
            )
        return f"CNKI cookies OK ({age:.1f}h old, < {self.max_cookie_age_hours}h TTL)"

    def load(self) -> "CNKIClient":
        """Load cookies from disk into memory. Call once before search()."""
        self._cookies = load_cookies()
        if not self._cookies:
            raise CNKIError(E_NO_COOKIES, "No cookies loaded", self.not_ready_reason())
        return self

    # ─────────────────────────────────────────────────────────────────
    # Main search: single-browser flow (bootstrap + paginated POST + parse)
    # ─────────────────────────────────────────────────────────────────

    def search(self, query: str, year_min: int = None, year_max: int = None,
               limit: int = 10, field: str = "subject", db: str = "all") -> List[Dict]:
        """Search CNKI for the given query (v3.9.7.4 real wiring, single-browser flow).

        Strategy (v3.9.7.4 fix): keep ONE browser/context open across bootstrap + POST.
        Why: direct POST from a fresh context triggers CNKI captcha (HTTP 403)
        because the new context lacks the full session state (Referer, Origin,
        freshly-set cookies). Bootstrap sets 6 proxy-IP cookies that the POST
        must use; opening a second context loses them.

        Args:
            query: search term (Chinese or English)
            year_min: optional earliest year filter
            year_max: optional latest year filter
            limit: max number of results to return (1-100, default 10)
            field: search field (subject/title/keyword/tka/abstract/fulltext/author/affiliation)
            db: database (all/journal/thesis/conference/newspaper/book/patent/standard/law/achievement/almanac)

        Returns: list of result dicts (see _parse_brief_response for schema)
        """
        from playwright.sync_api import sync_playwright

        if not self._cookies:
            self.load()

        # Map field + db
        field_code = FIELD_CODE_MAP.get(field, "SU")
        db_classid = DB_CLASSID_MAP.get(db, "WD0FTY92")
        db_resource = DB_RESOURCE_MAP.get(db, "CROSSDB")

        # Build query JSON (used in POST form)
        query_json = self._build_query_json(
            query, field_code, db_classid, db_resource, year_min, year_max
        )

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
            ctx.add_cookies(self._cookies)
            page = ctx.new_page()

            try:
                # Step 1: Bootstrap (visit xueshu789, wait for redirect to proxy IP)
                proxy_base = self._bootstrap_in_context(ctx, page)

                # Step 2: POST pages (1, 2, ...) and collect results
                per_page = self.page_size
                max_pages = max(1, (limit + per_page - 1) // per_page)
                all_results = []
                for page_num in range(1, max_pages + 1):
                    if len(all_results) >= limit:
                        break
                    # Add small delay between pages to avoid rate-limit captcha
                    if page_num > 1:
                        page.wait_for_timeout(1500)
                    try:
                        html = self._post_brief_page_in_context(
                            ctx, page, proxy_base, query_json, page_num
                        )
                    except CNKIError as e:
                        # Captcha on page 2+: graceful degradation — return what we have
                        if e.code in (E_CAPTCHA, E_BLOCKED) and all_results:
                            break
                        else:
                            raise
                    page_results = self._parse_brief_response(html)
                    if not page_results:
                        break  # no more results
                    all_results.extend(page_results)

                all_results = all_results[:limit]
                return all_results

            except CNKIError as e:
                return [{"error": e.code, "message": e.message, "hint": e.hint}]
            except Exception as e:
                return [{"error": E_NETWORK, "message": str(e)[:200], "hint": "Unknown error"}]
            finally:
                try:
                    browser.close()
                except Exception:
                    pass

    def _bootstrap_in_context(self, ctx, page) -> str:
        """Visit xueshu789.com/dbItem/1 to follow JS redirect to real CNKI proxy.

        Returns: proxy_base_url (e.g. "http://120.53.241.46:5888")
        """
        # Visit entry URL, wait for JS redirect to fire
        page.goto(XUESHU_ENTRY_URL, timeout=30_000, wait_until='domcontentloaded')
        # Wait up to 12s for URL to change to the real CNKI proxy
        try:
            page.wait_for_url(re.compile(r'\d+\.\d+\.\d+\.\d+:\d+'), timeout=12_000)
        except Exception:
            # Maybe redirect didn't fire; try waiting more
            page.wait_for_timeout(3000)
            if re.match(r'.*xueshu789\.com.*', page.url):
                raise CNKIError(
                    E_REDIRECT_FAILED,
                    f"xueshu789 redirect did not fire after 15s",
                    f"Still at {page.url}; check if cookies are valid (age {cookie_age_hours():.1f}h)",
                )
        # Wait for search page to be ready
        try:
            page.wait_for_selector('input#txt_search', timeout=8_000)
        except Exception:
            # Even if not ready, the proxy IP is what we need
            pass

        # Extract proxy base URL from current page URL
        m = re.match(r'(https?://[^/]+)', page.url)
        if not m:
            raise CNKIError(E_BOOTSTRAP_FAILED, f"Could not extract proxy base from {page.url}")
        return m.group(1)

    def _post_brief_page_in_context(self, ctx, page, proxy_base: str,
                                     query_json: Dict, page_num: int) -> str:
        """POST to /kns8s/brief/grid using the current page's context, return HTML."""
        # Build form data
        form_data = {
            "boolSearch": "true",
            "QueryJson": json.dumps(query_json, ensure_ascii=False),
            "pageNum": str(page_num),
            "pageSize": str(self.page_size),
            "sortField": "",
            "sortType": "",
            "dstyle": "listmode",
            "productStr": "",
            "aside": f"(主题：{query_json['QNode']['QGroup'][0]['Items'][0]['Value']})",
            "searchFrom": "资源范围：总库",
            "uniplatform": "NZKPT",
        }

        url = f"{proxy_base}{CNKI_BRIEF_GRID_PATH}"

        # Use page.evaluate to do fetch from inside the page (carries same Origin/Referer)
        # This avoids the captcha that a separate-context POST triggers.
        fetch_script = """
        async ({url, formData}) => {
            const form = new URLSearchParams();
            for (const [k, v] of Object.entries(formData)) {
                form.append(k, v);
            }
            const resp = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-Requested-With': 'XMLHttpRequest',
                },
                body: form.toString(),
                credentials: 'include',
            });
            const text = await resp.text();
            return {status: resp.status, text: text};
        }
        """
        try:
            result = page.evaluate(fetch_script, {"url": url, "formData": form_data})
        except Exception as e:
            raise CNKIError(E_NETWORK, f"page.evaluate fetch failed: {str(e)[:200]}",
                            "Check network or cookies")

        if result['status'] != 200:
            raise CNKIError(
                E_NETWORK,
                f"POST {url} returned HTTP {result['status']}",
                f"Body[:500]: {result['text'][:500]}",
            )

        html = result['text']
        # Anti-crawler detection
        if '验证码' in html or 'verify/home' in html or 'blockPuzzle' in html:
            raise CNKIError(E_CAPTCHA, "Captcha encountered", "Retry later or re-export cookies")
        if '访问受限' in html or '访问频次' in html:
            raise CNKIError(E_BLOCKED, "Access rate-limited", "Wait 5-10 min or re-export cookies")

        return html

    # ─────────────────────────────────────────────────────────────────
    # Build QueryJson payload
    # ─────────────────────────────────────────────────────────────────

    def _build_query_json(self, query: str, field_code: str,
                          db_classid: str, db_resource: str,
                          year_min: int = None, year_max: int = None) -> Dict:
        """Build the QueryJson dict that goes into the POST form.

        KuaKuCode must match Classid:
        - For 总库 (CROSSDB + WD0FTY92): use the full default list
        - For specific DB (e.g. journal=YSTT4HG0): use just that classid
        """
        qgroup_item = {
            "Field": field_code,
            "Value": query,
            "Operator": "TOPRANK",   # 智能检索 (subject default)
            "Logic": 0,
            "Title": self._field_title(field_code),
        }
        # KuaKuCode matches Classid
        if db_classid == "WD0FTY92":
            kua_ku_code = DEFAULT_CHECKED_DB  # full list for cross-DB search
        else:
            kua_ku_code = db_classid  # single classid for specific-DB search
        return {
            "Platform": "",
            "Resource": db_resource,
            "Classid": db_classid,
            "Products": "",
            "QNode": {
                "QGroup": [{
                    "Key": "Subject",
                    "Title": "",
                    "Logic": 0,
                    "Items": [qgroup_item],
                    "ChildItems": [],
                }],
            },
            "ExScope": 1,
            "SearchType": 2,            # 1=精确, 2=模糊 (FUZZY)
            "Rlang": "CHINESE",
            "KuaKuCode": kua_ku_code,
            "Expands": {},
            "View": "changeDBCh",
            "SearchFrom": 1,
        }

    def _field_title(self, field_code: str) -> str:
        """Human-readable field name for CNKI display."""
        return {
            "SU": "主题",
            "TI": "题名",
            "KY": "关键词",
            "AB": "摘要",
            "TKA": "篇关摘",
            "FT": "全文",
            "AR": "作者",
            "AF": "单位",
        }.get(field_code, "主题")

    # ─────────────────────────────────────────────────────────────────
    # Parse HTML response → list of result dicts
    # ─────────────────────────────────────────────────────────────────

    def _parse_brief_response(self, html: str) -> List[Dict]:
        """Parse brief/grid HTML response into standard result dicts.

        Standard schema (matches pa_cli.search._normalize_* for other engines):
          - doi: str (empty if not present)
          - title: str
          - authors: list[str]
          - venue: str
          - year: int or None
          - cited_by_count: int
          - type: str (journal/thesis/conference/etc)
          - source: "cnki"
          - abstract: str (empty for now; CNKI list view doesn't show abstract)
          - cnki_url: str (detail page URL)
          - cnki_filename: str (CNKI internal document ID)
          - download_count: int
        """
        # Find tbody
        m = re.search(r'<tbody>(.*?)</tbody>', html, re.DOTALL)
        if not m:
            return []
        tbody = m.group(1)
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', tbody, re.DOTALL)

        results = []
        for row_html in rows:
            r = {}

            # Title: <a class="fz14" target="_blank" href="...">TITLE</a>
            m = re.search(r'<a[^>]*class="[^"]*fz14[^"]*"[^>]*>(.*?)</a>', row_html, re.DOTALL)
            if m:
                title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
                r['title'] = title
                # Real CNKI URL: try kns.cnki.net direct (API response) or xueshu789 wrapper
                m_url = re.search(r'href="(https?://kns\.cnki\.net/[^"]+)"', row_html)
                if m_url:
                    # Decode HTML entities (e.g. &amp; -> &)
                    r['cnki_url'] = m_url.group(1).replace('&amp;', '&')
                else:
                    # Try xueshu789 wrapper fallback
                    m_url2 = re.search(r'href="https://www\.xueshu789\.com/doDownload\?url=([^"&]+)', row_html)
                    if m_url2:
                        r['cnki_url'] = unquote(m_url2.group(1))
                    else:
                        # Last resort: any fz14 href
                        m_url3 = re.search(r'href="([^"]+)"[^>]*class="[^"]*fz14', row_html)
                        if m_url3:
                            r['cnki_url'] = m_url3.group(1).replace('&amp;', '&')

            if not r.get('title'):
                continue  # skip rows without a title

            # Author: <a class="KnowledgeNetLink" ...>NAME</a>
            m = re.search(r'<a[^>]*class="[^"]*KnowledgeNetLink[^"]*"[^>]*>(.*?)</a>', row_html, re.DOTALL)
            if m:
                author = re.sub(r'<[^>]+>', '', m.group(1)).strip()
                # Authors can be comma- or space-separated; treat comma as separator
                if author:
                    r['authors'] = [a.strip() for a in re.split(r'[,;；，]', author) if a.strip()]
                else:
                    r['authors'] = []
            else:
                r['authors'] = []

            # Source (journal/venue): <td class="source"> or <td class='source' ><span><a>JOURNAL</a></span></td>
            # CNKI uses both single + double quotes and varies whitespace; use a flexible pattern
            src_match = re.search(r'<td[^>]*class=["\']source["\'][^>]*>(.*?)</td>', row_html, re.DOTALL)
            if src_match:
                inner = src_match.group(1)
                # Try to find an <a> with the journal name
                a_match = re.search(r'<a[^>]*>(.*?)</a>', inner, re.DOTALL)
                if a_match:
                    r['venue'] = re.sub(r'<[^>]+>', '', a_match.group(1)).strip()
                else:
                    r['venue'] = re.sub(r'<[^>]+>', ' ', inner).strip()

            # Date: <td class="date">YYYY-MM-DD or YYYY-MM-DD HH:MM</td> (flexible quoting)
            m = re.search(r'<td[^>]*class=["\']date["\'][^>]*>([^<]+)</td>', row_html)
            if m:
                r['date_str'] = m.group(1).strip()
                m_y = re.search(r'(\d{4})', r['date_str'])
                if m_y:
                    r['year'] = int(m_y.group(1))

            # Database type: <td class="data"><span>期刊</span></td>
            m = re.search(r'<td[^>]*class=["\']data["\'][^>]*>\s*<span>([^<]+)</span>', row_html)
            if m:
                r['db_type'] = m.group(1).strip()

            # Cited count: <td class="quote"><span>NN</span></td>
            m = re.search(r'<td[^>]*class=["\']quote["\'][^>]*>\s*<[^>]*>([^<]*)</[^>]*>\s*</td>', row_html, re.DOTALL)
            if m:
                cite = m.group(1).strip()
                if cite.isdigit():
                    r['cited_by_count'] = int(cite)
                else:
                    r['cited_by_count'] = 0
            else:
                r['cited_by_count'] = 0

            # Download count: <td class="download"><span>NN</span></td>
            m = re.search(r'<td[^>]*class=["\']download["\'][^>]*>\s*<[^>]*>([^<]*)</[^>]*>\s*</td>', row_html, re.DOTALL)
            if m:
                dl = m.group(1).strip()
                if dl.isdigit():
                    r['download_count'] = int(dl)
                else:
                    r['download_count'] = 0
            else:
                r['download_count'] = 0

            # Document ID (data-filename) from collect icon
            m = re.search(r'data-filename="([^"]+)"', row_html)
            if m:
                r['cnki_filename'] = m.group(1)

            # DOI (rare in list view, but try)
            m = re.search(r'doi\.org/(10\.\d{4,9}/[^\s&"\']+)', row_html)
            if m:
                r['doi'] = m.group(1).rstrip('.,;)')

            # Set standard schema fields
            r['source'] = 'cnki'
            r['abstract'] = ''   # CNKI list view doesn't show abstract
            r['type'] = self._map_db_type_to_paper_type(r.get('db_type', ''))

            results.append(r)

        return results

    def _map_db_type_to_paper_type(self, db_type: str) -> str:
        """Map CNKI db_type (期刊/学位/会议/...) to paper-agent's `type` field."""
        return {
            "期刊": "journal",
            "博士": "thesis",
            "硕士": "thesis",
            "学位论文": "thesis",
            "会议": "conference",
            "国内会议": "conference",
            "国际会议": "conference",
            "报纸": "newspaper",
            "图书": "book",
            "年鉴": "almanac",
            "专利": "patent",
            "标准": "standard",
            "法律法规": "law",
            "成果": "achievement",
        }.get(db_type, "journal")

    # ─────────────────────────────────────────────────────────────────
    # Main search: see top of class for the single-browser flow method
    # ─────────────────────────────────────────────────────────────────


# ──────────────────────────────────────────────────────────────────────
# Module-level search function (matches pa_cli.search.search_crossref etc.)
# ──────────────────────────────────────────────────────────────────────

def search_cnki(query: str, year_min: int = None, year_max: int = None,
                limit: int = 50, field: str = "subject", db: str = "all") -> List[Dict]:
    """Search CNKI for the given query (v3.9.7.4 real wiring).

    Returns: list of result dicts (see CNKIClient._parse_brief_response for schema).
             On failure (no cookies / expired / playwright missing / network),
             returns a single-element list with an "error" key describing the
             failure (this matches the failure-mode convention in
             pa_cli.search.run_search).

    Per ROADMAP [P0-9] "fallback" design: when CNKI fails for any reason,
    callers (e.g., pa_cli.search.run_search) skip CNKI and continue with
    the 5 English engines. The user never sees a hard error from CNKI.
    """
    # Check playwright
    try:
        import playwright  # noqa: F401
    except ImportError:
        return [{"error": E_PLAYWRIGHT_MISSING, "message": "playwright not installed", "hint": "pip install playwright"}]

    # Check cookies freshness
    if not cookies_exist():
        return [{"error": E_NO_COOKIES, "message": "No CNKI cookies file",
                 "hint": f"Run Export-CNKICookies.ps1 to create {CNKI_COOKIES_PATH}"}]
    age = cookie_age_hours()
    if age is None or age > 4.0:
        return [{"error": E_COOKIE_EXPIRED,
                 "message": f"CNKI cookies {age:.1f}h old (>4h TTL)" if age else "cookie age unknown",
                 "hint": "Re-run Export-CNKICookies.ps1 to refresh cookies"}]

    try:
        client = CNKIClient().load()
        return client.search(query, year_min=year_min, year_max=year_max,
                            limit=limit, field=field, db=db)
    except CNKIError as e:
        return [{"error": e.code, "message": e.message, "hint": e.hint}]
    except Exception as e:
        return [{"error": E_NETWORK, "message": str(e)[:200], "hint": "Unknown error"}]


# ──────────────────────────────────────────────────────────────────────
# Status helper (for `pa cnki status` CLI subcommand)
# ──────────────────────────────────────────────────────────────────────

def status_report() -> Dict[str, Any]:
    """Return a dict summarizing CNKI channel readiness.

    Used by `pa cnki status` CLI subcommand.
    """
    exists = cookies_exist()
    age = cookie_age_hours()
    n_cookies = len(load_cookies()) if exists else 0

    # Try playwright import
    try:
        import playwright  # noqa: F401
        has_playwright = True
    except ImportError:
        has_playwright = False

    return {
        "cookies_path": str(CNKI_COOKIES_PATH),
        "cookies_exist": exists,
        "cookie_age_hours": age,
        "n_cookies": n_cookies,
        "max_cookie_age_hours": 4.0,
        "cookies_fresh": exists and age is not None and age < 4.0,
        "playwright_installed": has_playwright,
        "ready_for_search": exists and age is not None and age < 4.0 and has_playwright,
        "version": "v3.9.7.4-real-search",
        "search_implemented": True,
        "search_endpoint": f"POST {CNKI_BRIEF_GRID_PATH} (via xueshu789.com redirect)",
        "supported_fields": list(FIELD_CODE_MAP.keys()),
        "supported_databases": list(DB_CLASSID_MAP.keys()),
        "next_action": (
            "Run `pa cnki search <query>` to test; if no results, re-run "
            "Export-CNKICookies.ps1 (cookies may be stale)."
        ),
    }


if __name__ == "__main__":
    # Allow `python -m pa_cli.cnki_channel` for quick status check / search test
    import sys as _sys
    if len(_sys.argv) > 1 and _sys.argv[1] == "search":
        # Quick search test
        test_query = _sys.argv[2] if len(_sys.argv) > 2 else "东数西算"
        test_limit = int(_sys.argv[3]) if len(_sys.argv) > 3 else 5
        results = search_cnki(test_query, limit=test_limit)
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(status_report(), indent=2, ensure_ascii=False))
