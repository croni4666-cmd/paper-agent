"""debug_s2.py — direct test of S2 search fields to see what's actually returned."""
import os
import json
import urllib.request
from urllib.parse import quote

key = os.environ.get("S2_API_KEY", "")
headers = {"User-Agent": "pa-debug/1.0"}
if key:
    headers["x-api-key"] = key

url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={quote('machine learning')}&limit=3&fields=title,year,citationCount,influentialCitationCount,referenceCount,tldr"
req = urllib.request.Request(url, headers=headers)
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))
        for p in data.get("data", []):
            print("---")
            for k, v in p.items():
                s = repr(v)[:80]
                print(f"  {k}: {s}")
except Exception as e:
    print(f"err: {e}")
