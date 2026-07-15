"""pa_cli/cnki_channel.py — CNKI 6th search engine skeleton (v3.9.7.3).

Per ROADMAP [P0-9] (added 2026-07-14, user-confirmed design 2026-07-14):
  - 中文 paper 收录 (CNKI = China National Knowledge Infrastructure)
  - Cookies 来自 user-maintained export script (4-8 hour proxy session)
  - **NOT** through clash proxy (CNKI 国内站, user 用"其他代理"如 校园 VPN / EZproxy / 机构图书馆)

**v3.9.7.3 skeleton**:
  - Cookies 加载 interface (从 `~/.paper-agent/cookies/cnki.json`)
  - Search endpoint interface (`https://www.cnki.net/KNS/brief/default_result.aspx`)
  - HTML 解析 stub (返回 placeholder result; real parser 在 cookies 接入后实现)
  - 错误处理: cookies 缺失 / 过期 / 反爬检测都返回明确 error code

**Not implemented in v3.9.7.3 (deferred to next session after user provides proxy + cookies)**:
  - POST form payload (txt=$query, sort=desc, etc.)
  - HTML table parsing (title, authors, abstract, year, journal)
  - Captcha detection + retry
  - 多页翻页 (page=1, 2, 3 ...)
  - 自动 cookie refresh on expiry

**5-check Global Rule audit** (per ROADMAP [P0-9]):
1. ✅ $0 cost (CNKI 订阅 + 代理 都在 user 侧)
2. ✅ No hosted service (cookies 本地, playwright 本地, 不经过 clash proxy)
3. ✅ Maintenance ~250 LOC + 复用 fetch.py playwright 框架
4. ✅ No publish obligation
5. ✅ Free-tier degradation: cookies 过期 → fallback to 5 英文 engine (no regression)
"""
import json
import os
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Dict, Optional, Any


# ──────────────────────────────────────────────────────────────────────
# Cookie management
# ──────────────────────────────────────────────────────────────────────

CNKI_COOKIES_PATH = Path.home() / ".paper-agent" / "cookies" / "cnki.json"


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
    import time
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
E_NOT_IMPLEMENTED = "not_implemented" # v3.9.7.3 skeleton: real search not yet wired


# ──────────────────────────────────────────────────────────────────────
# CNKIClient
# ──────────────────────────────────────────────────────────────────────

@dataclass
class CNKIClient:
    """CNKI search engine client (v3.9.7.3 skeleton).

    Usage:
        client = CNKIClient()
        if not client.is_ready():
            print(client.not_ready_reason())
            return
        results = client.search("东数西算", limit=10)
    """
    cookies_path: Path = field(default_factory=lambda: CNKI_COOKIES_PATH)
    cnki_url: str = "https://www.cnki.net/KNS/brief/default_result.aspx"
    max_cookie_age_hours: float = 4.0   # Proxy sessions typically expire 4-8h
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

    def search(self, query: str, year_min: int = None, year_max: int = None,
               limit: int = 10) -> List[Dict]:
        """Search CNKI for the given query.

        v3.9.7.3 skeleton behavior:
          - Validates cookies
          - Returns placeholder result list (1 dummy result with metadata)
          - The real playwright + HTML parse is NOT wired in this commit

        Returns: list of result dicts matching the standard schema (see
                 `pa_cli.search._normalize_*` for examples).

        Each result dict has at least:
          - doi: str ("" if no DOI; CNKI uses internal IDs)
          - title: str
          - authors: list[str]
          - venue: str
          - year: int
          - cited_by_count: int
          - type: str
          - source: "cnki"
          - abstract: str (truncated to 500 chars)
          - cnki_url: str (paper detail page on cnki.net)
        """
        # Validate cookies
        if not self._cookies:
            self.load()

        # v3.9.7.3 SKELETON: real search not yet implemented
        # The next commit (after user provides proxy + cookies + runs Export script) will:
        # 1. Launch playwright headless chromium (no proxy, direct CNKI hostname)
        # 2. add_cookies(playwright) from self._cookies
        # 3. page.goto(self.cnki_url + "?txt=" + quote(query) + "&sort=desc")
        # 4. Wait for results table (or captcha)
        # 5. Parse HTML rows: title, authors, abstract, year, journal, cnki_url
        # 6. Paginate (page=2, 3, ...) up to `limit` results
        # 7. Return normalized list

        # For now, return a placeholder result so callers can test the plumbing
        # without crashing
        return [
            {
                "doi": "",
                "title": f"[CNKI SKELETON] placeholder for query: {query}",
                "authors": [],
                "venue": "CNKI (search not yet implemented in v3.9.7.3)",
                "year": year_min or 2024,
                "cited_by_count": 0,
                "type": "journal",
                "source": "cnki",
                "abstract": (
                    "This is a placeholder result from the v3.9.7.3 CNKI skeleton. "
                    "The real playwright + HTML parser will be wired in once the user "
                    "provides CNKI proxy access + cookies via Export-CNKICookies.ps1. "
                    f"Query was: {query!r}, year range: {year_min}-{year_max}, limit: {limit}."
                ),
                "cnki_url": "https://www.cnki.net/KNS/brief/default_result.aspx",
            }
        ]


# ──────────────────────────────────────────────────────────────────────
# Module-level search function (matches pa_cli.search.search_crossref etc.)
# ──────────────────────────────────────────────────────────────────────

def search_cnki(query: str, year_min: int = None, year_max: int = None,
                limit: int = 50) -> List[Dict]:
    """Search CNKI for the given query (v3.9.7.3 skeleton).

    Returns: list of result dicts (see CNKIClient.search for schema).
             On failure (no cookies / expired / playwright missing), returns
             a single-element list with an "error" key describing the failure
             (this matches the failure-mode convention in pa_cli.search.run_search).

    Per ROADMAP [P0-9] "fallback" design: when CNKI fails for any reason,
    callers (e.g., pa_cli.search.run_search) skip CNKI and continue with
    the 5 English engines. The user never sees a hard error from CNKI.
    """
    try:
        client = CNKIClient().load()
    except CNKIError as e:
        return [{"error": e.code, "message": e.message, "hint": e.hint}]

    try:
        return client.search(query, year_min=year_min, year_max=year_max, limit=limit)
    except CNKIError as e:
        return [{"error": e.code, "message": e.message, "hint": e.hint}]
    except Exception as e:
        return [{"error": E_NETWORK, "message": str(e)[:200]}]


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
        "version": "v3.9.7.3-skeleton",
        "search_implemented": False,  # Will be True after next commit wires playwright + parse
        "next_action": (
            "User provides: (1) 代理入口 URL (校园 VPN / EZproxy / 机构图书馆), "
            "(2) login credentials, (3) test 1 cookie export session TTL. "
            "Then Mavis wires real playwright + HTML parser in next commit."
        ),
    }


if __name__ == "__main__":
    # Allow `python -m pa_cli.cnki_channel` for quick status check
    import json as _json
    print(_json.dumps(status_report(), indent=2, ensure_ascii=False))
