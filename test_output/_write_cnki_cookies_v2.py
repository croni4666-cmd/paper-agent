"""Write user's 4-cookie session + run E2E fetch test."""
import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

COOKIES_OUTPUT = Path.home() / ".paper-agent" / "cookies" / "cnki.json"
COOKIES_OUTPUT.parent.mkdir(parents=True, exist_ok=True)

# User provided 2026-07-16 08:38 (4 cookies!)
cookies = [
    {
        "name": "PHPSESSID",
        "value": "mtbapuk4vsfjqj7g3stg8rca86",
        "domain": "www.xueshu789.com",
        "path": "/",
        "expires": -1,
        "httpOnly": True,
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
    {
        "name": "entrys",
        "value": "1",
        "domain": "www.xueshu789.com",
        "path": "/",
        "expires": -1,
        "httpOnly": False,
        "secure": False,
        "sameSite": "Lax",
    },
    {
        "name": "expires",
        "value": "gvh_qgeTOSNpc_iJ-VKnJoOj3s9UABR",
        "domain": "www.xueshu789.com",
        "path": "/",
        "expires": -1,
        "httpOnly": False,
        "secure": False,
        "sameSite": "Lax",
    },
]

with open(COOKIES_OUTPUT, "w", encoding="utf-8") as f:
    json.dump(cookies, f, indent=2, ensure_ascii=False)
print(f"[OK] Wrote {len(cookies)} cookies to {COOKIES_OUTPUT}")
print(f"  File size: {COOKIES_OUTPUT.stat().st_size} bytes")
print(f"  Cookie names: {[c['name'] for c in cookies]}")

# Verify
sys.path.insert(0, "G:/minimax - workspace/Paper agent")
from pa_cli.cnki_channel import cookies_exist, cookie_age_hours, status_report
print(f"\n  cookies_exist: {cookies_exist()}")
age = cookie_age_hours()
print(f"  cookie_age_hours: {age:.2f}h" if age is not None else "  cookie_age_hours: None")
st = status_report()
print(f"  ready_for_search: {st['ready_for_search']}")
print(f"  cookies_fresh: {st['cookies_fresh']}")
