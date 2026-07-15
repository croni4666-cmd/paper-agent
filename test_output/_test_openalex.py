import requests
url = "https://api.openalex.org/venues?search=Nature&per_page=1"
s = requests.get(url, timeout=5, headers={"User-Agent": "paper-agent/3.9.7.3 (Mavis)"})
print("status:", s.status_code)
d = s.json()
results = d.get("results", [])
if results:
    print("keys in first result:", list(results[0].keys())[:30])
    for r in results[:3]:
        print(f"  {r.get('id')} | {r.get('display_name')} | works_count={r.get('works_count')} | cited_by_count={r.get('cited_by_count')}")
else:
    print("NO results")
    print("raw response:", d)
