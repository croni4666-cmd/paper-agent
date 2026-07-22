"""Real E2E: search 数字普惠金融 → fetch top papers with OA PDF."""
import os
import sys
import json
from pathlib import Path

# Set env BEFORE importing pa_cli (proxy + email)
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7897"
os.environ["HTTP_PROXY"] = "http://127.0.0.1:7897"
os.environ.setdefault("UNPAYWALL_EMAIL", "developers@unpaywall.org")

sys.path.insert(0, "G:/minimax - workspace/Paper agent")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from pa_cli.search import run_search
from pa_cli.fetch import fetch, fetch_unpaywall_doi

CORPUS_DIR = Path("G:/minimax - workspace/Paper agent/test_output/_fetch_e2e_user")
CORPUS_DIR.mkdir(parents=True, exist_ok=True)

QUERY = "数字普惠金融 家庭消费"

print("=" * 70)
print(f"STEP 1: pa search '{QUERY}' (all 6 engines, year 2022-2024, limit 30)")
print("=" * 70)
r = run_search(QUERY, year_min=2022, year_max=2024, limit=30, engine="all")
results = r.get("results", [])
print(f"  engines used: {list(r['by_engine'].keys())}")
print(f"  total results (deduped): {r['dedup_count']}")
print(f"  top 10 by cited_by_count:")

# Show top 10 with DOI
candidates = []
for i, p in enumerate(results[:15]):
    doi = p.get("doi", "")
    title = p.get("title", "")[:55]
    cited = p.get("cited_by_count", 0)
    is_oa = p.get("is_oa", False)
    has_doi = bool(doi)
    print(f"  {i+1:2}. {title:55} | cited={cited:5} | DOI={doi[:35] if doi else 'NO'} | "
          f"OA={is_oa}")
    if has_doi:
        candidates.append((doi, p.get("title", "")[:60], p.get("oa_url", "")))

print()
print("=" * 70)
print(f"STEP 2: pa fetch each candidate ({len(candidates)} papers with DOI)")
print("=" * 70)
results_fetch = []
for i, (doi, title, hint_oa) in enumerate(candidates):
    safe_name = "".join(c if c.isalnum() else "_" for c in title[:30])
    out = CORPUS_DIR / f"{i+1:02d}_{safe_name}.pdf"
    print(f"\n[{i+1}/{len(candidates)}] DOI={doi}")
    print(f"  title: {title}")
    r2 = fetch_unpaywall_doi(doi, out_path=str(out))
    if r2.get("error"):
        print(f"  ✗ {r2['error']}: {r2.get('message','')[:80]}")
        if r2.get("hint"):
            print(f"    hint: {r2['hint'][:80]}")
    else:
        size = r2.get("size", r2.get("bytes", 0))
        print(f"  ✓ {size:,}B from {r2.get('source', '?')}")
        print(f"    oa_url: {r2.get('pdf_url','')[:80]}")
        print(f"    saved: {r2.get('path','?')}")
    results_fetch.append((doi, title, r2))

# Summary
print()
print("=" * 70)
print("FINAL SUMMARY")
print("=" * 70)
ok = sum(1 for _, _, r in results_fetch if not r.get("error"))
fail = sum(1 for _, _, r in results_fetch if r.get("error"))
total_size = sum(r.get("size", r.get("bytes", 0)) for _, _, r in results_fetch
                 if not r.get("error"))
print(f"  queried: {QUERY}")
print(f"  candidates: {len(candidates)} papers with DOI")
print(f"  ✓ fetched: {ok}")
print(f"  ✗ failed:  {fail}")
print(f"  total downloaded: {total_size:,}B ({total_size/1e6:.1f}MB)")
print()
print("Files on disk:")
for p in sorted(CORPUS_DIR.glob("*.pdf")):
    print(f"  {p.name}: {p.stat().st_size:,}B")
