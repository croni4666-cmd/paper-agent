"""smoke_audit.py — Field coverage audit by source engine."""
import json
import sys
from collections import defaultdict
from pathlib import Path

# Find latest smoke test JSON
files = sorted(Path("test_output").glob("_smoke_search_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
if not files:
    print("no smoke_search_*.json found")
    sys.exit(1)
fp = files[0]
print(f"analyzing: {fp.name}\n")
d = json.loads(fp.read_text(encoding="utf-8"))

print(f"query: {d.get('query')}")
print(f"year: {d.get('year_min')}-{d.get('year_max')}")
print(f"by_engine: {d.get('by_engine')}")
print(f"dedup_count: {d.get('dedup_count')}\n")

# Coverage by source
by_src = defaultdict(lambda: {"total": 0, "cite": 0, "abstract": 0, "doi": 0, "venue": 0, "authors": 0, "year": 0})
for r in d["results"]:
    s = r.get("source", "unknown")
    by_src[s]["total"] += 1
    if r.get("cited_by_count"):
        by_src[s]["cite"] += 1
    if r.get("abstract"):
        by_src[s]["abstract"] += 1
    if r.get("doi"):
        by_src[s]["doi"] += 1
    if r.get("venue"):
        by_src[s]["venue"] += 1
    if r.get("authors"):
        by_src[s]["authors"] += 1
    if r.get("year"):
        by_src[s]["year"] += 1

print(f"{'source':<18} {'n':>4} {'cite':>6} {'abs':>6} {'doi':>6} {'venue':>6} {'authors':>8} {'year':>6}")
print("-" * 64)
for s, c in sorted(by_src.items(), key=lambda x: -x[1]["total"]):
    print(f"{s:<18} {c['total']:>4} {c['cite']:>6} {c['abstract']:>6} {c['doi']:>6} {c['venue']:>6} {c['authors']:>8} {c['year']:>6}")

# How many found by multiple engines?
multi = sum(1 for r in d["results"] if len(r.get("found_by", [])) > 1)
print(f"\npapers with multiple sources: {multi}/{len(d['results'])}")

# Among the 15 with cite, distribution by source
print("\n--- cite source breakdown ---")
for r in d["results"]:
    if r.get("cited_by_count"):
        print(f"  [{r.get('source','?'):<12}] {r.get('cited_by_count'):>3} cites | {r.get('title','')[:60]}")
