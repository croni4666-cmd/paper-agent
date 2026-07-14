import json
no_ext = json.load(open(r'G:\minimax - workspace\Paper agent\bench\v01\system_outputs_biencoder\q001', encoding='utf-8'))
with_ext = json.load(open(r'G:\minimax - workspace\Paper agent\bench\v01\system_outputs_biencoder\q001.json', encoding='utf-8'))
print(f'no_ext: n_results={len(no_ext["results"])}')
print(f'with_ext: n_results={len(with_ext["results"])}')
print(f'no_ext first 3 biencoder_scores: {[c.get("biencoder_score") for c in no_ext["results"][:3]]}')
print(f'with_ext first 3 biencoder_scores: {[c.get("biencoder_score") for c in with_ext["results"][:3]]}')
print(f'no_ext first 3 dois: {[c.get("doi") for c in no_ext["results"][:3]]}')
print(f'with_ext first 3 dois: {[c.get("doi") for c in with_ext["results"][:3]]}')
