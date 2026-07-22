"""Re-run pa search on 50 queries with v3.9.10.11 (gzip/brotli fix + S2 throttling).

Generates new system_outputs_combined/<qid>.json (replacing v3.9.7.3 versions
that had silent gzip-decode failures and lacked S2 relevance signal).

Saves to a backup dir first so v3.9.7.3 data isn't lost.

Strategy: ALL 6 engines (crossref, openalex, arxiv, semanticscholar, aminer, cnki).
S2 is throttled to 1 RPS with 429 backoff/retry (added in v3.9.10.11 [P1-20]).
Expected batch time: 50 queries * 1 S2 call = ~50s of S2 wall time, plus other
engines.
"""
import json
import sys
import time
import shutil
from pathlib import Path

sys.path.insert(0, '.')

from pa_cli.search import run_search
from pa_cli.scaffold import load_bibtex  # noqa: F401

bench_dir = Path('bench/v01')
queries_path = bench_dir / 'queries.json'
combined_dir = bench_dir / 'system_outputs_combined'
backup_dir = bench_dir / 'system_outputs_combined_v3_9_7_3_backup'

# Backup current v3.9.7.3 system_outputs_combined (if not already backed up)
if not backup_dir.exists():
    shutil.copytree(combined_dir, backup_dir)
    print(f'Backed up v3.9.7.3 system_outputs_combined to {backup_dir}')
else:
    print(f'Backup already exists at {backup_dir}')

# Load queries
queries_raw = json.loads(queries_path.read_text(encoding='utf-8'))
queries = queries_raw['queries']
print(f'\n{len(queries)} queries to re-run (6 engines WITH throttled S2)')

# Run pa search for each query, save to system_outputs_combined/<qid>.json
n_done = 0
n_failed = 0
t0 = time.time()
for i, q in enumerate(queries, start=1):
    qid = q['id']
    query = q['query']
    try:
        result = run_search(
            query=query,
            limit=50,
            engine='crossref,openalex,arxiv,semanticscholar,aminer,cnki',
            sort_by='cite',
            enrich_top=0,
        )
    except Exception as e:
        print(f'  [{i:2d}/{len(queries)}] {qid}: ERROR {e}')
        n_failed += 1
        continue
    by_engine_counts = result.get('by_engine', {})
    candidates = result.get('results', [])
    out = {
        'query_id': qid,
        'query': query,
        'topic_bucket': q.get('topic_bucket', ''),
        'source': q.get('source', ''),
        'generated_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'config': {
            'limit': 50,
            'engine': 'crossref,openalex,arxiv,semanticscholar,aminer,cnki',
            'sort_by': 'cite',
            'enrich_top': 0,
            'fix_version': 'v3.9.10.11',
            's2_throttle': '1 RPS + 1s/2s/4s backoff (max 3 retries)',
        },
        'n_returned': len(candidates),
        'top_n': 50,
        'by_engine': by_engine_counts,
        'results': candidates,
    }
    out_path = combined_dir / f'{qid}.json'
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding='utf-8')
    n_done += 1
    if i % 5 == 0 or i == len(queries):
        elapsed = time.time() - t0
        avg = elapsed / i
        remaining = (len(queries) - i) * avg
        print(f'  [{i:2d}/{len(queries)}] {n_done} done, {n_failed} failed, '
              f'{elapsed:.0f}s elapsed, ~{remaining:.0f}s left', flush=True)

print(f'\nDone: {n_done} succeeded, {n_failed} failed in {time.time()-t0:.0f}s')
print(f'Backup: {backup_dir}')
print(f'New combined dir: {combined_dir}')

