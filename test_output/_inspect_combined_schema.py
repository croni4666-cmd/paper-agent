"""Inspect schema of system_outputs_combined/q001.json to understand combined_score."""
import json
from pathlib import Path
d = json.load(open('bench/v01/system_outputs_combined/q001.json', encoding='utf-8'))
# top-level is dict with 'results' key
print(f'top-level keys: {list(d.keys())[:20]}')
print(f'n_returned: {d.get("n_returned", "?")}, top_n: {d.get("top_n", "?")}')
if 'results' in d:
    cands = d['results']
    print(f'\nn_candidates: {len(cands)}')
    print(f'first candidate keys: {list(cands[0].keys())[:20] if cands else "empty"}')
    if cands:
        print('---')
        for k in ['bm25_score','biencoder_score','combined_score','v4_score','score']:
            if k in cands[0]:
                print(f'{k}: {cands[0][k]}')
        print('---')
        print('Top-3 by combined_score (or whichever key exists):')
        score_key = 'combined_score' if 'combined_score' in cands[0] else next((k for k in ['bm25_score','biencoder_score','score','v4_score'] if k in cands[0]), None)
        if score_key:
            for c in sorted(cands, key=lambda x: -x.get(score_key, 0))[:3]:
                bi = c.get('biencoder_score', 0)
                bm = c.get('bm25_score', 0)
                co = c.get('combined_score', 0)
                doi = (c.get('doi', '') or c.get('id','') or c.get('title',''))[:40]
                print(f'  bm25={bm:.3f} bi={bi:.3f} comb={co:.3f} key={score_key}={c.get(score_key,0):.3f} doi={doi}')
