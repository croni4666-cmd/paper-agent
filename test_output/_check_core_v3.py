"""Test if paper-agent style urllib can hit CORE without a key."""
import urllib.request as ur
import urllib.error
import json
import os

# Simulate paper-agent's http_get_json (uses UA_BROWSER, no Authorization header)
UA_BROWSER = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def http_get_json(url, headers=None, timeout=15):
    h = {"User-Agent": UA_BROWSER, "Accept": "application/json"}
    if headers:
        h.update(headers)
    req = ur.Request(url, headers=h)
    try:
        with ur.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8", errors="ignore"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8", errors="ignore"))
        except Exception:
            return e.code, {}
    except Exception as e:
        return 0, {}


print("=== paper-agent urllib style (no key) ===")
for q in ["long-term care insurance", "数字普惠金融", "金融科技 风险承担"]:
    url = f"https://api.core.ac.uk/v3/search/works?q={ur.quote(q)}&limit=5"
    s, d = http_get_json(url)
    print(f"Q={q!r}: HTTP {s} | totalHits={d.get('totalHits')} | n={len(d.get('results',[]))}")
    for r2 in d.get("results", [])[:3]:
        print(f"  - {str(r2.get('title',''))[:60]} | year={r2.get('yearPublished')} | doi={r2.get('doi')}")

print("\n=== With CORE_API_KEY env var (Bearer style) ===")
# SECURITY: do NOT hardcode the key here. Read from env (.env auto-loaded
# by pa_cli.search._load_dotenv). If not set, skip the key-based probes.
KEY = os.environ.get("CORE_API_KEY", "")
if not KEY:
    print("(CORE_API_KEY env var not set; skipping Bearer + ?api_key= probes)")
else:
    for q in ["long-term care insurance"]:
        # Try Bearer
        s, d = http_get_json(f"https://api.core.ac.uk/v3/search/works?q={ur.quote(q)}&limit=3",
                             headers={"Authorization": f"Bearer {KEY}"})
        print(f"Q={q!r} (Bearer): HTTP {s} | totalHits={d.get('totalHits')}")
        # Try query param
        s, d = http_get_json(f"https://api.core.ac.uk/v3/search/works?q={ur.quote(q)}&api_key={KEY}&limit=3")
        print(f"Q={q!r} (?api_key=): HTTP {s} | totalHits={d.get('totalHits')}")
