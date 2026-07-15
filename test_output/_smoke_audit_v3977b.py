"""smoke_audit_v3977b.py — verify placeholder filter blocks bogus tldr → abstract merges."""
import json
from pathlib import Path
from collections import defaultdict

fp = sorted(Path("test_output").glob("_smoke_search_v3977b_*.json"),
            key=lambda p: p.stat().st_mtime, reverse=True)[0]
d = json.loads(fp.read_text(encoding="utf-8"))

# All S2 results
s2 = [r for r in d["results"] if r.get("source") == "semanticscholar"]
print(f"S2 results: {len(s2)}")
print(f"  with tldr (non-empty): {sum(1 for r in s2 if r.get('tldr'))}")
print(f"  with abstract (non-empty): {sum(1 for r in s2 if r.get('abstract'))}")
print(f"  with both tldr and abstract: {sum(1 for r in s2 if r.get('tldr') and r.get('abstract'))}")

# How many of the 3 tldrs were placeholders?
placeholders = 0
for r in s2:
    tldr = r.get("tldr", "")
    if tldr and ("dust off" in tldr):
        placeholders += 1
print(f"  tldrs with 'dust off' placeholder: {placeholders}")

# Overall coverage
total = len(d["results"])
print(f"\noverall abstract coverage: {sum(1 for r in d['results'] if r.get('abstract'))}/{total} ({100*sum(1 for r in d['results'] if r.get('abstract'))/total:.0f}%)")
print(f"overall tldr coverage: {sum(1 for r in d['results'] if r.get('tldr'))}/{total}")
print(f"overall cited_by_count: {sum(1 for r in d['results'] if r.get('cited_by_count'))}/{total}")
print(f"overall influential_cite_count: {sum(1 for r in d['results'] if r.get('influential_cite_count'))}/{total}")
print(f"overall reference_count: {sum(1 for r in d['results'] if r.get('reference_count'))}/{total}")

# Source breakdown
by_src = defaultdict(lambda: {"n": 0, "cite": 0, "inf": 0, "ref": 0, "abs": 0, "tldr": 0})
for r in d["results"]:
    s = r.get("source", "?")
    by_src[s]["n"] += 1
    if r.get("cited_by_count"): by_src[s]["cite"] += 1
    if r.get("influential_cite_count"): by_src[s]["inf"] += 1
    if r.get("reference_count"): by_src[s]["ref"] += 1
    if r.get("abstract"): by_src[s]["abs"] += 1
    if r.get("tldr"): by_src[s]["tldr"] += 1

print(f"\n{'source':<18} {'n':>3} {'cite':>5} {'inf':>5} {'ref':>5} {'abs':>4} {'tldr':>5}")
for s, c in sorted(by_src.items(), key=lambda x: -x[1]["n"]):
    print(f"  {s:<16} {c['n']:>3} {c['cite']:>5} {c['inf']:>5} {c['ref']:>5} {c['abs']:>4} {c['tldr']:>5}")
