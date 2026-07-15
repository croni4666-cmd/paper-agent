"""debug_s2_saved.py — inspect S2 results in the saved smoke test JSON."""
import json
from pathlib import Path
from collections import Counter

fp = sorted(Path("test_output").glob("_smoke_search_v3977_*.json"),
            key=lambda p: p.stat().st_mtime, reverse=True)[0]
d = json.loads(fp.read_text(encoding="utf-8"))

# Filter S2 results
s2 = [r for r in d["results"] if r.get("source") == "semanticscholar"]
print(f"S2 results in saved JSON: {len(s2)}\n")

# Field presence in S2 results
for field in ["tldr", "influential_cite_count", "reference_count", "cited_by_count",
              "abstract", "doi", "venue", "authors"]:
    have = sum(1 for r in s2 if r.get(field))
    print(f"  {field}: {have}/{len(s2)} ({100*have/len(s2):.0f}%)")

print("\n--- raw S2 results (first 10) ---")
for r in s2[:10]:
    print(f"\n  title: {r.get('title', '')[:70]}")
    print(f"  year: {r.get('year')}, cited_by: {r.get('cited_by_count')}, "
          f"inf: {r.get('influential_cite_count')}, ref: {r.get('reference_count')}")
    print(f"  tldr: {repr(r.get('tldr', ''))[:120]}")
    print(f"  abstract: {repr(r.get('abstract', ''))[:80]}")
