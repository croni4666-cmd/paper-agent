"""Find what kind of email Unpaywall accepts (real email vs fake vs custom)."""
import os
import sys
import json
from urllib.parse import quote

os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7897"
os.environ["HTTP_PROXY"] = "http://127.0.0.1:7897"
sys.path.insert(0, "G:/minimax - workspace/Paper agent")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from pa_cli.fetch import _http_get_bytes

# Test various email patterns
emails_to_test = [
    # Already-known working
    "developers@unpaywall.org",  # Unpaywall's own email
    # Common real-looking but obvious fakes
    "test@example.com",          # RFC 2606 reserved → should 422
    "user@example.com",          # RFC 2606 reserved → should 422
    "foo@bar.com",               # Random unregistered domain
    # Real public email services
    "dengn@gmail.com",           # Real Gmail format
    "dengn@qq.com",              # Real QQ format
    "dengn@163.com",             # Real 163 format
    "deng.nju@gmail.com",        # Real Gmail with dots
    "dengn+research@outlook.com", # Real Outlook with plus
    "user@mavis.local",          # Custom non-existent domain
    "user@qq.local",             # Custom local
]

print("Testing email patterns against Unpaywall API:")
print("=" * 70)
for email in emails_to_test:
    url = f"https://api.unpaywall.org/v2/10.1038/nature12373?email={quote(email, safe='@')}"
    s, body = _http_get_bytes(url, timeout=20)
    if s == 200 and body[:1] in [b"{", b"["]:
        # try JSON
        try:
            d = json.loads(body)
            t = d.get("title", "")
            oa = (d.get("best_oa_location") or {}).get("url", "")
            print(f"  ✓ {email:35} | HTTP 200 | JSON | title={t[:35]!r} | oa={oa[:50]}")
        except Exception as e:
            print(f"  ⚠ {email:35} | HTTP 200 | JSON fail: {e}")
    elif s == 200:
        print(f"  ✗ {email:35} | HTTP 200 | NOT JSON (anti-bot?) | head={body[:16].hex()}")
    elif s == 422:
        try:
            d = json.loads(body)
            print(f"  ✗ {email:35} | HTTP 422 | {d.get('message','')[:80]}")
        except Exception:
            print(f"  ✗ {email:35} | HTTP 422 | {body[:80]}")
    else:
        print(f"  ✗ {email:35} | HTTP {s} | {body[:60]}")
