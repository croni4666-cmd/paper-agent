"""compare_cn_fair.py — fair v3.9.7.7 vs v3.9.7.8 Chinese query comparison (both limit=20)."""
import json
from pathlib import Path
from collections import defaultdict

v78 = sorted(Path("test_output").glob("_smoke_v3978_cn20_*.json"),
             key=lambda p: p.stat().st_mtime, reverse=True)[0]
v77 = sorted(Path("test_output").glob("_smoke_search_v3977_*.json"),  # original cn v3.9.7.7 limit=20
             key=lambda p: p.stat().st_mtime, reverse=True)[0]

def metrics(d):
    total = len(d["results"])
    return {
        "total": total,
        "cite": sum(1 for r in d["results"] if r.get("cited_by_count")),
        "inf": sum(1 for r in d["results"] if r.get("influential_cite_count")),
        "abs": sum(1 for r in d["results"] if r.get("abstract")),
        "tldr": sum(1 for r in d["results"] if r.get("tldr")),
        "s2_enriched": sum(1 for r in d["results"] if r.get("_enrichment", {}).get("s2_doi")),
        "cr_enriched": sum(1 for r in d["results"] if r.get("_enrichment", {}).get("crossref_title")),
    }

d78 = json.loads(v78.read_text(encoding="utf-8"))
d77 = json.loads(v77.read_text(encoding="utf-8"))

m78 = metrics(d78)
m77 = metrics(d77)

print("Chinese query (limit=20, year 2020-2024, query='金融科技 风险承担'):")
print()
print(f"{'metric':<12} {'v3.9.7.7':>10} {'v3.9.7.8':>10} {'Δ':>10}")
print("-" * 50)
for k in ("total", "cite", "inf", "abs", "tldr"):
    pct78 = 100 * m78[k] / m78["total"] if m78["total"] else 0
    pct77 = 100 * m77[k] / m77["total"] if m77["total"] else 0
    delta = pct78 - pct77
    print(f"  {k:<10} {m77[k]:>4}/{m77['total']:<2} ({pct77:>4.0f}%)   "
          f"{m78[k]:>4}/{m78['total']:<2} ({pct78:>4.0f}%)   {delta:>+5.0f}pp")
print()
print(f"  S2 deep lookups succeeded: {m78['s2_enriched']}/{m78['total']}")
print(f"  Crossref-by-title lookups succeeded: {m78['cr_enriched']}/{m78['total']}")

# Look at top-10 specifically (where the enrichment is applied)
print("\nTop-10 papers, post-enrichment coverage:")
for r in d78["results"][:10]:
    en = r.get("_enrichment", {})
    print(f"  [{r.get('source','?'):<12}] cite={r.get('cited_by_count','-'):<4} "
          f"inf={r.get('influential_cite_count','-'):<4} "
          f"abs={'Y' if r.get('abstract') else 'N'} "
          f"tldr={'Y' if r.get('tldr') else 'N'}  "
          f"enrich={list(en.keys())}")
