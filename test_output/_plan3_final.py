"""Final Plan 3 smoke test: 4 scenarios covering all features."""
import json
import sys
import time
sys.path.insert(0, r'G:\minimax - workspace\Paper agent')
from pa_cli.cnki_channel import search_cnki, status_report

print("=" * 70)
print("Plan 3 CNKI Real Search — Final Smoke Test")
print("=" * 70)
print()

# Status first
print("--- 1. Channel status ---")
status = status_report()
for k, v in status.items():
    if isinstance(v, (list, dict)):
        print(f"  {k}: <{type(v).__name__} len={len(v) if hasattr(v, '__len__') else '?'}>")
    else:
        print(f"  {k}: {v}")
print()

# Test 1: 中文 query
print("--- 2. 中文 query: '东数西算' (subject, all DB, limit=5) ---")
t0 = time.time()
r = search_cnki('东数西算', limit=5, field='subject', db='all')
t = time.time() - t0
print(f"  Time: {t:.1f}s, Results: {len(r)}")
for i, p in enumerate(r):
    if 'error' in p:
        print(f"  ERROR: {p}")
        break
    print(f"  [{i+1}] {p.get('title','')[:50]}")
    print(f"      {p.get('venue', '?')[:30]} | {p.get('year')} | {p.get('type')}")
print()

# Test 2: 翻页 (limit > 20)
print("--- 3. Pagination: '深度学习' (subject, journal DB, limit=30) ---")
t0 = time.time()
r = search_cnki('深度学习', limit=30, field='subject', db='journal')
t = time.time() - t0
print(f"  Time: {t:.1f}s, Results: {len(r)}")
print(f"  First 3: {[p.get('title','')[:40] for p in r[:3]]}")
print()

# Test 3: title field
print("--- 4. Title field: '保险精算' (title, all DB, limit=5) ---")
t0 = time.time()
r = search_cnki('保险精算', limit=5, field='title', db='all')
t = time.time() - t0
print(f"  Time: {t:.1f}s, Results: {len(r)}")
for i, p in enumerate(r):
    print(f"  [{i+1}] {p.get('title','')[:50]} ({p.get('type')})")
print()

# Test 4: 6-engine integration
print("--- 5. 6-engine integration: 'machine learning' (all engines, limit=10) ---")
sys.path.insert(0, r'G:\minimax - workspace\Paper agent')
from pa_cli.search import run_search
t0 = time.time()
r = run_search('machine learning neural network', engine='all', limit=10)
t = time.time() - t0
print(f"  Time: {t:.1f}s")
print(f"  By engine: {r['by_engine']}")
print(f"  Dedup: {r['dedup_count']}")
print()

print("=" * 70)
print("ALL TESTS COMPLETE")
print("=" * 70)
