"""smoke_audit_en.py — confirm S2 enrichment fields work for English queries."""
import json
from pathlib import Path
from collections import defaultdict

fp = sorted(Path("test_output").glob("_smoke_search_en_*.json"),
            key=lambda p: p.stat().st_mtime, reverse=True)[0]
d = json.loads(fp.read_text(encoding="utf-8"))

print(f"query: {d.get('query')}")
print(f"by_engine: {d.get('by_engine')}")
print(f"dedup: {d.get('dedup_count')}\n")

# Per-source coverage
by_src = defaultdict(lambda: {"n": 0, "cite": 0, "inf": 0, "ref": 0, "abs": 0, "tldr": 0})
for r in d["results"]:
    s = r.get("source", "?")
    by_src[s]["n"] += 1
    if r.get("cited_by_count"): by_src[s]["cite"] += 1
    if r.get("influential_cite_count"): by_src[s]["inf"] += 1
    if r.get("reference_count"): by_src[s]["ref"] += 1
    if r.get("abstract"): by_src[s]["abs"] += 1
    if r.get("tldr"): by_src[s]["tldr"] += 1

print(f"{'source':<18} {'n':>3} {'cite':>5} {'inf':>5} {'ref':>5} {'abs':>4} {'tldr':>5}")
for s, c in sorted(by_src.items(), key=lambda x: -x[1]["n"]):
    print(f"  {s:<16} {c['n']:>3} {c['cite']:>5} {c['inf']:>5} {c['ref']:>5} {c['abs']:>4} {c['tldr']:>5}")

# Overall
total = len(d["results"])
print(f"\noverall:")
for k in ["cited_by_count", "influential_cite_count", "reference_count", "abstract", "tldr"]:
    have = sum(1 for r in d["results"] if r.get(k))
    print(f"  {k}: {have}/{total} ({100*have/total:.0f}%)")

# Top 5 by influential_cite_count
top = sorted([r for r in d["results"] if r.get("influential_cite_count")],
             key=lambda x: -x["influential_cite_count"])[:5]
if top:
    print("\ntop 5 by influential_cite_count:")
    for r in top:
        title = r.get("title", "")[:70]
        print(f"  {r.get('influential_cite_count'):>5} influential | {r.get('cited_by_count'):>5} total | {r.get('source','?'):<10} | {title}")
