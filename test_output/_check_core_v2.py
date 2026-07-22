"""Re-probe CORE v3 API -- is the key really needed? (2026-07-15 follow-up)

NOTE: this script previously hardcoded the CORE API key as a literal string.
That was a SECURITY LEAK and is now fixed -- the key is read from
CORE_API_KEY env var (auto-loaded from .env via pa_cli.search._load_dotenv).

If CORE_API_KEY is not set, probes with key will fail with 401.
Set the env var first, then run.
"""
import os
import urllib.request as ur
import urllib.error
import json

KEY = os.environ.get("CORE_API_KEY", "")


def probe(name, url, hdr=None):
    req = ur.Request(url, headers=hdr or {"User-Agent": "paper-agent/3.9.8.1"})
    try:
        with ur.urlopen(req, timeout=15) as r:
            d = json.loads(r.read().decode("utf-8", errors="ignore"))
            print(f"{name}: HTTP {r.status} | totalHits={d.get('totalHits')} | n={len(d.get('results', []))}")
            for r2 in d.get("results", [])[:2]:
                print(f"  - {str(r2.get('title',''))[:60]} | year={r2.get('yearPublished')} | doi={r2.get('doi')}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")[:200]
        print(f"{name}: HTTP {e.code} | body={body}")
    except Exception as e:
        print(f"{name}: ERROR {e}")


print("=== CORE v3 API probes ===")
probe("NO key, EN", "https://api.core.ac.uk/v3/search/works?q=long-term+care+insurance&limit=2")
probe("NO key, CJK", "https://api.core.ac.uk/v3/search/works?q=" + ur.quote("数字普惠金融") + "&limit=2")
if KEY:
    probe("Auth Bearer", "https://api.core.ac.uk/v3/search/works?q=long-term+care+insurance&limit=2",
          hdr={"User-Agent": "paper-agent/3.9.8.1", "Authorization": f"Bearer {KEY}"})
    probe("Query param key", f"https://api.core.ac.uk/v3/search/works?q=long-term+care+insurance&api_key={KEY}&limit=2")
    probe("X-API-Key header", "https://api.core.ac.uk/v3/search/works?q=long-term+care+insurance&limit=2",
          hdr={"User-Agent": "paper-agent/3.9.8.1", "X-API-Key": KEY})
else:
    print("(CORE_API_KEY env var not set; skipping 3 key-based probes)")
