import json
no_ext = json.load(open(r'G:\minimax - workspace\Paper agent\bench\v01\system_outputs_biencoder\q001', encoding='utf-8'))
with_ext = json.load(open(r'G:\minimax - workspace\Paper agent\bench\v01\system_outputs_biencoder\q001.json', encoding='utf-8'))
# Check all 30 cands match
no_dois = [c.get("doi") for c in no_ext["results"]]
we_dois = [c.get("doi") for c in with_ext["results"]]
print(f"dois match: {no_dois == we_dois}")
# Check all 30 biencoder_scores
no_bi = [c.get("biencoder_score") for c in no_ext["results"]]
we_bi = [c.get("biencoder_score") for c in with_ext["results"]]
print(f"biencoder_scores match: {no_bi == we_bi}")
# Top-level keys
print(f"no_ext keys: {sorted(no_ext.keys())}")
print(f"with_ext keys: {sorted(with_ext.keys())}")
# v4_score
print(f"no_ext first 3 v4_score: {[c.get('v4_score') for c in no_ext['results'][:3]]}")
print(f"with_ext first 3 v4_score: {[c.get('v4_score') for c in with_ext['results'][:3]]}")
# ranks
print(f"no_ext first 3 rank: {[c.get('rank') for c in no_ext['results'][:3]]}")
print(f"with_ext first 3 rank: {[c.get('rank') for c in with_ext['results'][:3]]}")
