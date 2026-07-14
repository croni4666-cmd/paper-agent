import json
d = json.load(open(r'G:\minimax - workspace\Paper agent\bench\v01\system_outputs_biencoder\q001.json', encoding='utf-8'))
r = d['results']
print(f'n_results: {len(r)}')
print(f'first result keys: {list(r[0].keys())}')
print(f'first result biencoder_score: {r[0].get("biencoder_score", "MISSING")}')
print(f'first result rank: {r[0].get("rank")}')
print(f'first 3 ranks: {[c.get("rank") for c in r[:3]]}')
print(f'first 3 biencoder_scores: {[c.get("biencoder_score") for c in r[:3]]}')
print(f'first 3 dois: {[c.get("doi") for c in r[:3]]}')
