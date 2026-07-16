"""Test OpenAlex by DOI for Chinese papers."""
import os
import sys
import json

os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7897"
os.environ["HTTP_PROXY"] = "http://127.0.0.1:7897"
sys.path.insert(0, "G:/minimax - workspace/Paper agent")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import urllib.request as ur
import urllib.error
from urllib.parse import quote

# 1. Direct OpenAlex test
dois = [
    "10.3969/j.issn.1003-9031.2022.04.008",
    "10.16525/j.cnki.14-1362/n.2022.08.004",
    # English one for baseline
    "10.1038/nature12373",
    # Another Chinese
    "10.15884/j.cnki.issn.1007-0672.2022.04.002",
]

for doi in dois:
    url = f"https://api.openalex.org/works/doi:{quote(doi, safe='/')}"
    print(f"\n--- {doi} ---")
    print(f"URL: {url}")
    req = ur.Request(url, headers={
        "User-Agent": "paper-agent/3.9.8.3 (mailto:dengn@gmail.com)",
        "Accept": "application/json",
    })
    try:
        with ur.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8", errors="ignore"))
        if data.get("id") and not data.get("error"):
            t = data.get("title") or data.get("display_name") or "?"
            print(f"  [OK] {t[:80]}")
            print(f"  year: {data.get('publication_year')} | cited: {data.get('cited_by_count')}")
            print(f"  openalex_id: {data.get('id', '?')[:60]}")
        else:
            print(f"  [X] error: {data.get('error', '?')}")
            print(f"  message: {data.get('message', '?')}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")[:200]
        print(f"  HTTP {e.code} | {body}")
    except Exception as e:
        print(f"  ERR: {e}")
