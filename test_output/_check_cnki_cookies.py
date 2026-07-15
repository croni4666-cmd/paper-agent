"""Check existing CNKI cookies state."""
import sys
import json
from pathlib import Path

sys.path.insert(0, "G:/minimax - workspace/Paper agent")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from pa_cli.cnki_channel import cookies_exist, cookie_age_hours, CNKI_COOKIES_PATH

print(f"cookies file: {CNKI_COOKIES_PATH}")
print(f"exists:       {cookies_exist()}")
age = cookie_age_hours()
print(f"age (hours):  {age}")
if age is not None and age > 4.0:
    print(f"  ⚠️ EXPIRED — needs re-export (>4h TTL)")
elif age is not None:
    print(f"  ✓ fresh ({age:.2f}h)")

if CNKI_COOKIES_PATH.exists():
    cookies = json.loads(CNKI_COOKIES_PATH.read_text(encoding="utf-8"))
    print(f"n_cookies:    {len(cookies)}")
    print(f"first 5:")
    for c in cookies[:5]:
        nm = c.get("name", "")
        v = c.get("value", "")[:25]
        d = c.get("domain", "")
        print(f"  {nm:30} = {v:25} | domain={d}")
    domains = set(c.get("domain", "") for c in cookies)
    print(f"unique domains: {sorted(domains)}")
