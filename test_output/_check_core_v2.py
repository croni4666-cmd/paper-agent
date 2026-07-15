"""Re-probe CORE v3 API — is the key really needed? (2026-07-15 follow-up)"""
import urllib.request as ur
import urllib.error
import json

KEY = "<REDACTED-CORE-KEY>"


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
probe("Auth Bearer", "https://api.core.ac.uk/v3/search/works?q=long-term+care+insurance&limit=2",
      hdr={"User-Agent": "paper-agent/3.9.8.1", "Authorization": f"Bearer {KEY}"})
probe("Query param key", f"https://api.core.ac.uk/v3/search/works?q=long-term+care+insurance&api_key={KEY}&limit=2")
probe("X-API-Key header", "https://api.core.ac.uk/v3/search/works?q=long-term+care+insurance&limit=2",
      hdr={"User-Agent": "paper-agent/3.9.8.1", "X-API-Key": KEY})
