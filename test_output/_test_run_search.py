"""Integration test: pa search with cnki engine."""
import json
import sys
sys.path.insert(0, r'G:\minimax - workspace\Paper agent')

from pa_cli.search import run_search, _try_import_cnki

# Test 1: Can we import CNKI?
print('=== _try_import_cnki() ===')
print(json.dumps(_try_import_cnki(), indent=2, ensure_ascii=False))

# Test 2: Run a Chinese query via run_search
print('\n=== run_search with cnki engine ===')
result = run_search('东数西算', engine='cnki', limit=10)
print(f'Query: {result["query"]}')
print(f'By engine: {result["by_engine"]}')
print(f'Dedup count: {result["dedup_count"]}')
print(f'\nFirst 5 results:')
for i, p in enumerate(result['results'][:5]):
    print(f'  [{i}] {p.get("title", "")[:60]}')
    print(f'       source={p.get("source")}, venue={p.get("venue")}, year={p.get("year")}')
    print(f'       authors={p.get("authors", [])[:2]}')
    print(f'       url={p.get("cnki_url", p.get("url", ""))[:80]}')
