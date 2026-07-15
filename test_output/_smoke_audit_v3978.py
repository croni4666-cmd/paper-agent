"""smoke_audit_v3978.py — Compare v3.9.7.7 vs v3.9.7.8 (top-N deep enrichment) on CN+EN queries."""
import json
from pathlib import Path
from collections import defaultdict


def audit_v3978(json_path, label):
    d = json.loads(json_path.read_text(encoding="utf-8"))
    print(f"\n=== {label} ===")
    print(f"  query: {d.get('query')}")
    print(f"  by_engine: {d.get('by_engine')}")
    print(f"  dedup: {d.get('dedup_count')}, enrich_top: {d.get('enrich_top', 0)}")
    total = len(d["results"])
    if total == 0:
        print("  no results")
        return
    by_src = defaultdict(lambda: {"n": 0, "cite": 0, "inf": 0, "ref": 0, "abs": 0, "tldr": 0})
    enrich_stats = {"s2_doi": 0, "crossref_title": 0}
    for r in d["results"]:
        s = r.get("source", "?")
        by_src[s]["n"] += 1
        if r.get("cited_by_count"): by_src[s]["cite"] += 1
        if r.get("influential_cite_count"): by_src[s]["inf"] += 1
        if r.get("reference_count"): by_src[s]["ref"] += 1
        if r.get("abstract"): by_src[s]["abs"] += 1
        if r.get("tldr"): by_src[s]["tldr"] += 1
        en = r.get("_enrichment", {})
        if en.get("s2_doi"): enrich_stats["s2_doi"] += 1
        if en.get("crossref_title"): enrich_stats["crossref_title"] += 1
    print(f"  enrichment: {enrich_stats}")
    print(f"  {'source':<18} {'n':>3} {'cite':>5} {'inf':>5} {'ref':>5} {'abs':>4} {'tldr':>5}")
    for s, c in sorted(by_src.items(), key=lambda x: -x[1]["n"]):
        print(f"    {s:<16} {c['n']:>3} {c['cite']:>5} {c['inf']:>5} {c['ref']:>5} {c['abs']:>4} {c['tldr']:>5}")
    print(f"  overall: cite={sum(1 for r in d['results'] if r.get('cited_by_count'))}/{total}, "
          f"inf={sum(1 for r in d['results'] if r.get('influential_cite_count'))}/{total}, "
          f"abs={sum(1 for r in d['results'] if r.get('abstract'))}/{total}, "
          f"tldr={sum(1 for r in d['results'] if r.get('tldr'))}/{total}")


# v3.9.7.8 results
v78_cn = sorted(Path("test_output").glob("_smoke_v3978_cn_*.json"),
               key=lambda p: p.stat().st_mtime, reverse=True)[0]
v78_en = sorted(Path("test_output").glob("_smoke_v3978_en_*.json"),
               key=lambda p: p.stat().st_mtime, reverse=True)[0]
audit_v3978(v78_cn, "v3.9.7.8 Chinese query (金融科技 风险承担, --enrich-top 10)")
audit_v3978(v78_en, "v3.9.7.8 English query (transformer attention, --enrich-top 10)")

# v3.9.7.7 baseline (no enrich)
v77_cn = sorted(Path("test_output").glob("_smoke_search_v3977b_*.json"),
               key=lambda p: p.stat().st_mtime, reverse=True)[0]
v77_en = sorted(Path("test_output").glob("_smoke_search_en_*.json"),
               key=lambda p: p.stat().st_mtime, reverse=True)[0]
print("\n--- v3.9.7.7 baseline (no --enrich-top) for comparison ---")
audit_v3978(v77_cn, "v3.9.7.7 Chinese query baseline")
audit_v3978(v77_en, "v3.9.7.7 English query baseline")
