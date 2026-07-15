"""Test year filter on real queries."""
import json
import sys
import time
sys.path.insert(0, r'G:\minimax - workspace\Paper agent')
from pa_cli.cnki_channel import search_cnki

tests = [
    # (label, query, year_min, year_max, expected years in result)
    ('No year filter (baseline)', '深度学习', None, None, 'all'),
    ('year_min=2020 only (≥2020)', '深度学习', 2020, None, '≥2020'),
    ('year_max=2024 only (≤2024)', '深度学习', None, 2024, '≤2024'),
    ('year_min=2020, year_max=2024 (2020-2024)', '深度学习', 2020, 2024, '2020-2024'),
    ('year_min=2024, year_max=2024 (only 2024)', '深度学习', 2024, 2024, '2024'),
    ('year_min=2025, year_max=2026 (2025-2026)', '东数西算', 2025, 2026, '2025-2026'),
]

for label, query, year_min, year_max, expected in tests:
    t0 = time.time()
    r = search_cnki(query, limit=10, year_min=year_min, year_max=year_max)
    t = time.time() - t0
    if not r or 'error' in r[0]:
        print(f'\n=== {label} ===')
        print(f'  Time: {t:.1f}s, ERROR: {r[0] if r else "no result"}')
        continue
    years = sorted(set(p.get('year') for p in r if p.get('year')))
    print(f'\n=== {label} (expected: {expected}) ===')
    print(f'  Time: {t:.1f}s, Results: {len(r)}, years in result: {years}')
    # Show first 3 titles
    for p in r[:3]:
        print(f'    [{p.get("year")}] {p.get("title", "")[:50]} ({p.get("venue", "?")[:20]})')
