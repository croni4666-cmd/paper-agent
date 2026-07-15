"""debug_s2_chinese.py — directly call S2 with the Chinese query to see what fields it returns."""
import os
import json
import urllib.request
from urllib.parse import quote

key = os.environ.get("S2_API_KEY", "")
headers = {"User-Agent": "pa-debug/1.0"}
if key:
    headers["x-api-key"] = key

# Same query that was used in smoke test
q = "金融科技 风险承担"
url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={quote(q)}&limit=10&fields=title,year,citationCount,influentialCitationCount,referenceCount,tldr"
req = urllib.request.Request(url, headers=headers)
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))
        print(f"S2 returned {len(data.get('data', []))} papers for query: {q}\n")
        for p in data.get("data", []):
            print("---")
            print(f"  title: {p.get('title', '')[:80]}")
            print(f"  year: {p.get('year')}")
            print(f"  citationCount: {p.get('citationCount')}")
            print(f"  influentialCitationCount: {p.get('influentialCitationCount')}")
            print(f"  referenceCount: {p.get('referenceCount')}")
            tldr = p.get("tldr")
            if isinstance(tldr, dict):
                print(f"  tldr: {tldr.get('text', '')[:100]}")
            else:
                print(f"  tldr: {tldr}")
except Exception as e:
    print(f"err: {e}")
