"""Filter more searches: BGB 551, Japan law, jeonse insurance, US deposit."""
import json, sys
sys.stdout.reconfigure(encoding="utf-8")

QUERIES = {
    "BGB §551": ("searches/germany_bgb.json", ["bgb", "mietkaution", "mietsicherheit", "deposit"]),
    "Japan law": ("searches/japan_law.json", ["japan", "借地", "借家", "tenant", "deposit", "shikikin", "保証金"]),
    "jeonse insurance": ("searches/jeonse_ins.json", ["jeonse", "korea", "deposit", "guarantee", "insurance", "전세"]),
    "US deposit": ("searches/us.json", ["security deposit", "tenant", "us ", "united states", "america", "state"]),
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
        if any(k.lower() in text for k in must_have):
            matched.append(r)
    matched.sort(key=lambda r: -(r.get("cited_by_count") or 0))
    print(f"\n=== {name.upper()} ===")
    print(f"  Total: {len(results)} -> matched: {len(matched)}")
    for r in matched[:8]:
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
