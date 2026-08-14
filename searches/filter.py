"""Filter paper-agent results by relevance to deposit/housing/jeonse comparison."""
import json, sys
sys.stdout.reconfigure(encoding="utf-8")

QUERIES = {
    "jeonse": ("searches/jeonse.json", ["jeonse", "chonsei", "korea", "deposit"]),
    "japan": ("searches/japan.json", ["japan", "shikikin", "shiki-kin", "deposit"]),
    "germany": ("searches/germany.json", ["germany", "german", "mietkaution", "bgb", "mietsicherheit", "deposit"]),
    "oecd": ("searches/oecd.json", ["oecd", "tenure", "deposit", "comparison", "international"]),
    "china": ("searches/china.json", ["china", "chinese", "deposit", "押", "rental housing"]),
}

for name, (path, must_have) in QUERIES.items():
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"{name}: load failed: {e}")
        continue
    results = data.get("results", [])
    matched = []
    for r in results:
        title = (r.get("title") or "").lower()
        abstract = (r.get("abstract") or "").lower() if r.get("abstract") else ""
        text = title + " " + abstract
        if any(k in text for k in must_have) and any(k in text for k in ["deposit", "jeonse", "shikikin", "mietkaution", "tenure", "rental", "tenant", "押", "housing"]):
            matched.append(r)
    matched.sort(key=lambda r: -(r.get("cited_by_count") or 0))
    print(f"\n=== {name.upper()} ===")
    print(f"  Total: {len(results)} -> matched: {len(matched)}")
    for r in matched[:10]:
        year = r.get("year", "?")
        cited = r.get("cited_by_count", 0)
        doi = r.get("doi", "")
        title = (r.get("title") or "")[:100]
        venue = r.get("venue", "")
        src = r.get("source", "")
        oa = r.get("is_oa", False)
        print(f"  [{year}] cites={cited} src={src} oa={oa} | {venue}")
        print(f"    {title}")
        print(f"    DOI: {doi}")
