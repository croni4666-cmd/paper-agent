"""Complete the v3.9.10.11 rebuild for the remaining 22 queries (q029-q050).

[Honest finding] The S2 free tier returns 429 on EVERY call when there's
no S2_API_KEY set in env. The throttle+retry works (verified by 8/8 unit
tests), but 4 retries * 15s backoff = 60s per S2 call that ultimately
fails. Without an S2 API key, [P1-20] doesn't materially change results
vs no S2 — S2 just returns 0 papers in both cases.

Strategy for the remaining 22 queries (q029-q050): use ALL 6 engines with
S2 throttling (it won't add data but it documents the attempt). If S2
free tier is too slow, fallback to 5 engines (skip S2) for these queries.
"""
import json
import sys
import time
import shutil
import os
from pathlib import Path

sys.path.insert(0, '.')

from pa_cli.search import run_search

bench_dir = Path('bench/v01')
queries_path = bench_dir / 'queries.json'
combined_dir = bench_dir / 'system_outputs_combined'
backup_dir = bench_dir / 'system_outputs_v3_9_10_10_no_s2'

# Load queries
queries_raw = json.loads(queries_path.read_text(encoding='utf-8'))
queries = queries_raw['queries']

# Find queries that haven't been updated to v3.9.10.11
remaining = []
for q in queries:
    qid = q['id']
    qfile = combined_dir / f'{qid}.json'
    if qfile.exists():
        try:
            data = json.loads(qfile.read_text(encoding='utf-8'))
            config = data.get('config', {})
            if isinstance(config, dict) and config.get('fix_version') == 'v3.9.10.11':
                continue
        except Exception:
            pass
    remaining.append(q)

print(f'Already done: {len(queries) - len(remaining)}/{len(queries)}')
print(f'Remaining: {len(remaining)}')

# For remaining queries, decide: include S2 or not based on S2_API_KEY
has_s2_key = bool(os.environ.get('S2_API_KEY'))
engine_str = 'crossref,openalex,arxiv,semanticscholar,aminer,cnki' if has_s2_key else 'crossref,openalex,arxiv,aminer,cnki'
print(f'S2_API_KEY set: {has_s2_key}; engine list: {engine_str}')

n_done = 0
n_failed = 0
t0 = time.time()
for i, q in enumerate(remaining, start=1):
    qid = q['id']
    query = q['query']
    try:
        result = run_search(
            query=query,
            limit=50,
            engine=engine_str,
            sort_by='cite',
            enrich_top=0,
        )
    except Exception as e:
        print(f'  {qid}: ERROR {e}')
        n_failed += 1
        continue
    candidates = result.get('results', [])
    out = {
        'query_id': qid,
        'query': query,
        'topic_bucket': q.get('topic_bucket', ''),
        'source': q.get('source', ''),
        'generated_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'config': {
            'limit': 50,
            'engine': engine_str,
            'sort_by': 'cite',
            'enrich_top': 0,
            'fix_version': 'v3.9.10.11',
            's2_throttle': '1 RPS + 1s/2s/4s backoff (max 3 retries)' if has_s2_key else 'SKIPPED (no S2_API_KEY)',
        },
        'n_returned': len(candidates),
        'top_n': 50,
        'by_engine': result.get('by_engine', {}),
        'results': candidates,
    }
    out_path = combined_dir / f'{qid}.json'
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding='utf-8')
    n_done += 1
    if i % 5 == 0 or i == len(remaining):
        elapsed = time.time() - t0
        avg = elapsed / i
        remaining_est = (len(remaining) - i) * avg
        print(f'  [{i}/{len(remaining)}] {n_done} done, {n_failed} failed, '
              f'{elapsed:.0f}s elapsed, ~{remaining_est:.0f}s left', flush=True)

print(f'\nDone: {n_done}/{len(remaining)} succeeded, {n_failed} failed in {time.time()-t0:.0f}s')
