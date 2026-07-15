"""smoke_audit_v3977.py — Re-audit after S2 tldr + influential_cite + reference_count + crossref references-count added."""
import json
import sys
from collections import defaultdict
from pathlib import Path

files = sorted(Path("test_output").glob("_smoke_search_v3977_*.json"),
               key=lambda p: p.stat().st_mtime, reverse=True)
if not files:
    print("no smoke_search_v3977_*.json found")
    sys.exit(1)
fp = files[0]
print(f"analyzing: {fp.name}\n")
d = json.loads(fp.read_text(encoding="utf-8"))

print(f"query: {d.get('query')}")
print(f"year: {d.get('year_min')}-{d.get('year_max')}")
print(f"by_engine: {d.get('by_engine')}")
print(f"dedup_count: {d.get('dedup_count')}\n")

# Coverage by source + new fields
by_src = defaultdict(lambda: {"total": 0, "cite": 0, "inf_cite": 0, "ref_count": 0,
                                "abstract": 0, "tldr": 0, "doi": 0, "venue": 0})
for r in d["results"]:
    s = r.get("source", "unknown")
    by_src[s]["total"] += 1
    if r.get("cited_by_count"):
        by_src[s]["cite"] += 1
    if r.get("influential_cite_count"):
        by_src[s]["inf_cite"] += 1
    if r.get("reference_count"):
        by_src[s]["ref_count"] += 1
    if r.get("abstract"):
        by_src[s]["abstract"] += 1
    if r.get("tldr"):
        by_src[s]["tldr"] += 1
    if r.get("doi"):
        by_src[s]["doi"] += 1
    if r.get("venue"):
        by_src[s]["venue"] += 1

print(f"{'source':<18} {'n':>4} {'cite':>6} {'infcite':>8} {'refcnt':>7} {'abs':>5} {'tldr':>5} {'doi':>5} {'venue':>6}")
print("-" * 80)
for s, c in sorted(by_src.items(), key=lambda x: -x[1]["total"]):
    print(f"{s:<18} {c['total']:>4} {c['cite']:>6} {c['inf_cite']:>8} {c['ref_count']:>7} "
          f"{c['abstract']:>5} {c['tldr']:>5} {c['doi']:>5} {c['venue']:>6}")

# Overall
print("\n--- overall (all sources) ---")
total = len(d["results"])
all_keys = ["cited_by_count", "influential_cite_count", "reference_count", "abstract", "tldr", "doi", "venue", "authors", "year"]
for k in all_keys:
    have = sum(1 for r in d["results"] if r.get(k))
    print(f"  {k}: {have}/{total} ({100*have/total:.0f}%)")

# How many abstracts came from tldr (would be empty if not for the merge fix)
print("\n--- tldr → abstract fallback check ---")
n_tldr_only = sum(1 for r in d["results"] if r.get("abstract") and r.get("tldr") and r.get("abstract") == r.get("tldr"))
print(f"  results with abstract == tldr: {n_tldr_only} (these are tldr-merged)")

# multi-source papers
multi = sum(1 for r in d["results"] if len(r.get("found_by", [])) > 1)
print(f"\npapers with multiple sources: {multi}/{len(d['results'])}")

# Top 5 by influential_cite_count (for lit review use)
print("\n--- top 5 by influential_cite_count ---")
top = sorted([r for r in d["results"] if r.get("influential_cite_count")],
             key=lambda x: -x["influential_cite_count"])[:5]
for r in top:
    title = r.get("title", "")
    if len(title) > 70:
        title = title[:70] + "..."
    print(f"  {r.get('influential_cite_count'):>4} influential | {r.get('cited_by_count'):>4} total | {title}")
