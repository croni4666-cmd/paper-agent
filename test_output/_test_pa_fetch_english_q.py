"""English query to verify Unpaywall is actually functional (vs Chinese which it doesn't cover)."""
import os
import sys
from pathlib import Path

os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7897"
os.environ["HTTP_PROXY"] = "http://127.0.0.1:7897"
os.environ.setdefault("UNPAYWALL_EMAIL", "developers@unpaywall.org")

sys.path.insert(0, "G:/minimax - workspace/Paper agent")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from pa_cli.search import run_search
from pa_cli.fetch import fetch_unpaywall_doi

OUT_DIR = Path("G:/minimax - workspace/Paper agent/test_output/_fetch_e2e_english")
OUT_DIR.mkdir(parents=True, exist_ok=True)

QUERY = "attention is all you need transformer"

print("=" * 70)
print(f"English query: '{QUERY}' (all 6 engines, year 2017-2024, limit 30)")
print("=" * 70)
r = run_search(QUERY, year_min=2017, year_max=2024, limit=30, engine="all")
print(f"  engines: {list(r['by_engine'].keys())} | dedup: {r['dedup_count']}")

results = r.get("results", [])
# Show top 15 with DOI — don't filter on is_oa (search engines' flag is unreliable)
candidates = []
print(f"\n  top 15 with DOI (no is_oa filter — let Unpaywall decide):")
for i, p in enumerate(results[:15]):
    doi = p.get("doi", "")
    if not doi:
        continue
    title = p.get("title", "")[:55]
    cited = p.get("cited_by_count", 0)
    is_oa = p.get("is_oa", False)
    oa_url = p.get("oa_url", "")[:60] if p.get("oa_url") else ""
    print(f"  {len(candidates)+1:2}. cited={cited:6} | DOI=YES | "
          f"search_OA={is_oa} | {title}")
    candidates.append((doi, title))

print()
print("=" * 70)
print(f"FETCH: trying top {min(5, len(candidates))} papers (English, OA-flagged)")
print("=" * 70)
results_fetch = []
for i, (doi, title) in enumerate(candidates[:5]):
    safe = "".join(c if c.isalnum() else "_" for c in title[:30])
    out = OUT_DIR / f"{i+1:02d}_{safe}.pdf"
    print(f"\n[{i+1}/{min(5,len(candidates))}] DOI={doi}")
    r2 = fetch_unpaywall_doi(doi, out_path=str(out))
    if r2.get("error"):
        print(f"  ✗ {r2['error']}: {r2.get('message','')[:80]}")
    else:
        size = r2.get("size", r2.get("bytes", 0))
        print(f"  ✓ {size:,}B from {r2.get('source', '?')}")
        print(f"    oa_url: {r2.get('pdf_url','')[:80]}")
        print(f"    saved:  {r2.get('path','?')}")
    results_fetch.append((doi, title, r2))

# Summary
print()
print("=" * 70)
print("ENGLISH QUERY SUMMARY")
print("=" * 70)
ok = sum(1 for _, _, r in results_fetch if not r.get("error"))
fail = sum(1 for _, _, r in results_fetch if r.get("error"))
size = sum(r.get("size", r.get("bytes", 0)) for _, _, r in results_fetch
           if not r.get("error"))
print(f"  ✓ fetched: {ok}/{len(results_fetch)}")
print(f"  total: {size:,}B ({size/1e6:.1f}MB)")
for p in sorted(OUT_DIR.glob("*.pdf")):
    print(f"  {p.name}: {p.stat().st_size:,}B")
