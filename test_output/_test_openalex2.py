import requests

# OpenAlex 'sources' endpoint (venues are subset of sources)
url = "https://api.openalex.org/sources?search=Nature&per_page=1"
s = requests.get(url, timeout=5, headers={"User-Agent": "paper-agent/3.9.7.3"})
print("status:", s.status_code)
d = s.json()
results = d.get("results", [])
if results:
    print("keys in first result:", list(results[0].keys())[:25])
    for r in results[:2]:
        print(f"  id={r.get('id')} | display_name={r.get('display_name')} | works_count={r.get('works_count')} | cited_by_count={r.get('cited_by_count')}")
else:
    print("NO results, response keys:", list(d.keys()))
    print("msg:", d.get("message"))
