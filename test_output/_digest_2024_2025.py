"""Parse 2024+ pa search JSON outputs into a concise summary for the user."""
import json
import sys
from pathlib import Path

files = [
    "_litsearch_llm_rerank_2024.json",
    "_litsearch_llm_ir_2024.json",
    "_litsearch_rankllm_2024.json",
    "_litsearch_bge_mxbai_2024.json",
]

all_papers = []
for fname in files:
    p = Path("test_output") / fname
    if not p.exists():
        print(f"[missing] {fname}")
        continue
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[err] {fname}: {e}")
        continue
    if isinstance(obj, dict) and "results" in obj:
        results = obj["results"]
    elif isinstance(obj, list):
        results = obj
    else:
        results = []
    if not isinstance(results, list):
        continue
    for r in results:
        if not isinstance(r, dict):
            continue
        title = (r.get("title") or r.get("display_name") or "").strip()
        year = r.get("year") or r.get("publication_year") or "?"
        doi = r.get("doi") or ""
        cites = r.get("cited_by_count", "?")
        venue = ""
        pl = r.get("primary_location")
        if isinstance(pl, dict):
            src = pl.get("source")
            if isinstance(src, dict):
                venue = src.get("display_name") or ""
        # engines may be a string or list
        engines = r.get("engines_found_in") or r.get("sources") or []
        all_papers.append({
            "title": title,
            "year": year,
            "doi": doi,
            "cites": cites,
            "venue": venue,
            "engines": engines if isinstance(engines, list) else [str(engines)],
        })

# Dedup by title
seen = set()
unique = []
for p in all_papers:
    k = p["title"][:80].lower()
    if k in seen or not p["title"]:
        continue
    seen.add(k)
    unique.append(p)

# Sort: 2025+ first, then 2024
def sort_key(p):
    y = p["year"] if isinstance(p["year"], int) else 0
    return -y

unique.sort(key=sort_key)

print(f"\n=== Total unique 2024+ papers from 4 searches: {len(unique)} ===\n")
for i, p in enumerate(unique[:25], 1):
    print(f"[{i:2d}] ({p['year']}) {p['title'][:100]}")
    if p["venue"]:
        print(f"     venue: {p['venue']} | cites: {p['cites']}")
    if p["doi"]:
        print(f"     doi: {p['doi']}")
    print()
