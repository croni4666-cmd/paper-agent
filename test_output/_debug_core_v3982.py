import urllib.request as ur
import json

url = ("https://api.core.ac.uk/v3/search/works?q=" + ur.quote("long-term care insurance")
       + "&yearPublishedFrom=2022&yearPublishedTo=2024&limit=5")
req = ur.Request(url, headers={"User-Agent": "paper-agent/3.9.8.2 (test)"})
with ur.urlopen(req, timeout=20) as r:
    d = json.loads(r.read().decode("utf-8"))
print("totalHits:", d.get("totalHits"))
print("n returned:", len(d.get("results", [])))
for it in d.get("results", [])[:3]:
    print(f"  - {it.get('title','')[:60]} | year={it.get('yearPublished')}")
