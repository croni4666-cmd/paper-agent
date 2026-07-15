"""Test run_search with all 6 engines."""
import json
import sys
sys.path.insert(0, r'G:\minimax - workspace\Paper agent')
from pa_cli.search import run_search

# English query - should use all 6 engines
result = run_search('machine learning neural network', engine='all', limit=10)
print('By engine:', result['by_engine'])
print('Dedup count:', result['dedup_count'])
print()
for i, p in enumerate(result['results'][:10]):
    print(f'  [{i}] {p.get("title", "")[:60]}')
    print(f'       source={p.get("source")}, year={p.get("year")}, found_by={p.get("found_by", [])}')
