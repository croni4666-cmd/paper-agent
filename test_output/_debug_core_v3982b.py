"""CORE v3 various queries to see which ones work and which timeout."""
import urllib.request as ur
import urllib.error
import json
import time

UA_PLAIN = "paper-agent/3.9.8.2 (test)"
UA_BROWSER = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def probe(ua, q, year_min=None, year_max=None, label=""):
    url = "https://api.core.ac.uk/v3/search/works?q=" + ur.quote(q) + "&limit=3"
    if year_min:
        url += f"&yearPublishedFrom={year_min}"
    if year_max:
        url += f"&yearPublishedTo={year_max}"
    req = ur.Request(url, headers={"User-Agent": ua})
    t0 = time.time()
    try:
        with ur.urlopen(req, timeout=15) as r:
            d = json.loads(r.read().decode("utf-8"))
            dt = time.time() - t0
            print(f"{label} | UA={'plain' if ua==UA_PLAIN else 'browser'} | q={q[:30]!r:32} | "
                  f"HTTP {r.status} | t={dt:.1f}s | n={len(d.get('results',[]))} | "
                  f"total={d.get('totalHits')}")
    except urllib.error.HTTPError as e:
        dt = time.time() - t0
        print(f"{label} | UA={'plain' if ua==UA_BROWSER else 'browser'} | q={q[:30]!r:32} | "
              f"HTTP {e.code} | t={dt:.1f}s")
    except Exception as e:
        dt = time.time() - t0
        print(f"{label} | UA={'plain' if ua==UA_PLAIN else 'browser'} | q={q[:30]!r:32} | "
              f"TIMEOUT/ERR after {dt:.1f}s: {e}")


for q in ["long-term care insurance", "long-term care insurance aging",
          "machine learning", "digital inclusive finance", "数字普惠金融"]:
    probe(UA_PLAIN, q, label="plain")
    probe(UA_BROWSER, q, label="browser")
    print()
