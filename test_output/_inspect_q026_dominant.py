import sys
import json
sys.path.insert(0, r"G:\minimax - workspace\Paper agent")
from pa_cli.moe_router import ENGINES, _dominant_engine_for_query

snap = json.load(open(r"G:\minimax - workspace\Paper agent\bench\v01\system_outputs_combined\q026.json", encoding="utf-8"))
cands = snap["results"][:10]
n50 = json.load(open(r"G:\minimax - workspace\Paper agent\bench\v01\labels_n50_mixed.json", encoding="utf-8"))
labels = {doi: v.get("label", 0) for doi, v in n50["labels"]["q026"].items()}
print("q026 cands top 10:")
for c in cands:
    doi = (c.get("doi") or "").strip()
    print(f"  doi={doi!r}, engines={c.get('engines_found_in',[])}, label={labels.get(doi, 0)}")
dom = _dominant_engine_for_query(cands, labels, top_k=10)
print(f"dominant: {dom}")

# Test all q026-q050
print("\nAll q026-q050 dominant engine:")
for qid_int in range(26, 51):
    qid = f"q{qid_int:03d}"
    sp = f"G:/minimax - workspace/Paper agent/bench/v01/system_outputs_combined/{qid}.json"
    try:
        snap = json.load(open(sp, encoding="utf-8"))
    except FileNotFoundError:
        print(f"{qid}: NO FILE")
        continue
    cands = snap["results"][:10]
    q_labels = {doi: v.get("label", 0) for doi, v in n50["labels"].get(qid, {}).items()}
    dom = _dominant_engine_for_query(cands, q_labels, top_k=10)
    print(f"{qid}: dominant={dom}, n_cands={len(cands)}")
