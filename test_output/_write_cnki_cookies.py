"""Write user-provided cookies to cnki.json, then run fetch_cnki_detail E2E."""
import json
import sys
from pathlib import Path

# Force UTF-8 stdout for emoji / non-ASCII
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

COOKIES_OUTPUT = Path.home() / ".paper-agent" / "cookies" / "cnki.json"
COOKIES_OUTPUT.parent.mkdir(parents=True, exist_ok=True)

# User pasted (2026-07-15 22:42)
# Note: domain is null in cookieStore.getAll() — meaning host-only (browser
# auto-sets to current host). For Playwright add_cookies we MUST set a domain
# explicitly. Use www.xueshu789.com (matches v3.9.7.4 pattern).
user_cookies = [
    {
        "name": "PHPSESSID",
        "value": "c89up8bk4g21oo43suuhklsui4",
        "domain": "www.xueshu789.com",
        "path": "/",
        "expires": -1,
        "httpOnly": True,   # PHPSESSID is typically httpOnly
        "secure": False,
        "sameSite": "Lax",
    },
    {
        "name": "user",
        "value": "5Wbv4H9Fy5OUcKW62NADcOgbDzNt_9Zy_xEjZ3MCuU4Y50XWLdPTNfIPOjLELh7fGgbSFeGEgdIYvMxNRG06Ss3",
        "domain": "www.xueshu789.com",
        "path": "/",
        "expires": -1,
        "httpOnly": False,
        "secure": False,
        "sameSite": "Lax",
    },
]

with open(COOKIES_OUTPUT, "w", encoding="utf-8") as f:
    json.dump(user_cookies, f, indent=2, ensure_ascii=False)
print(f"[OK] Wrote {len(user_cookies)} cookies to {COOKIES_OUTPUT}")
print(f"  File size: {COOKIES_OUTPUT.stat().st_size} bytes")
print(f"  Cookie names: {[c['name'] for c in user_cookies]}")

# Verify
sys.path.insert(0, str(Path("G:/minimax - workspace/Paper agent")))
from pa_cli.cnki_channel import cookies_exist, cookie_age_hours
print(f"\n  cookies_exist: {cookies_exist()}")
age = cookie_age_hours()
print(f"  cookie_age_hours: {age:.2f}h" if age is not None else "  cookie_age_hours: None")
print(f"\nNote: 'entrys' and 'expires' missing — may or may not work.")
print(f"      Bootstrap will tell us. If fails, re-export after refresh.")
