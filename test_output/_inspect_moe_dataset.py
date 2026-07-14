"""Diagnose MoE n=50 dataset — what queries get skipped?"""
import json
import sys
from pathlib import Path

sys.path.insert(0, r"G:\minimax - workspace\Paper agent")

# Backup
real_path = Path(r"G:\minimax - workspace\Paper agent\bench\v01\labels_clean.json")
real = json.load(open(real_path, encoding="utf-8"))
n50 = json.load(open(r"G:\minimax - workspace\Paper agent\bench\v01\labels_n50_mixed.json", encoding="utf-8"))

# Swap
swapped = {"version": "v3.9.7.3-n50-temp", "n_queries": 50, "labels": n50["labels"]}
real_path.write_text(json.dumps(swapped, ensure_ascii=False, indent=2), encoding="utf-8")

try:
    from pa_cli.moe_router import assemble_dataset, ENGINES
    dataset = assemble_dataset(Path(r"G:\minimax - workspace\Paper agent\bench\v01"), source_condition="system_outputs_combined")
    print(f"n_queries in dataset: {len(dataset['queries'])}")
    qids = sorted(dataset["queries"], key=lambda x: int(x[1:]))
    print(f"queries: {qids[:10]} ... {qids[-5:]}")
    for q, lbl in list(zip(dataset["queries"], dataset["labels"]))[:5]:
        print(f"  {q}: dominant={ENGINES[lbl]}")
    # Check q026-q050
    q026_q050_in = [q for q in qids if int(q[1:]) >= 26]
    print(f"\nq026-q050 included: {len(q026_q050_in)}")
    print(f"  {q026_q050_in}")

    # Why excluded?
    bench_dir = Path(r"G:\minimax - workspace\Paper agent\bench/v01")
    labels_data = n50["labels"]
    for qid in ["q026", "q027", "q028", "q042", "q043"]:
        snap_path = bench_dir / "system_outputs_combined" / f"{qid}.json"
        obj = json.loads(snap_path.read_text(encoding="utf-8"))
        cands = obj.get("results", [])
        q_labels = labels_data.get(qid, {})
        cands_with_label = []
        for c in cands[:10]:
            doi = (c.get("doi") or "").strip()
            label = q_labels.get(doi, {}).get("label", 0) or 0
            cands_with_label.append((doi, label))
        l2_in_top10 = sum(1 for x in cands_with_label if x[1] >= 2)
        print(f"\n{qid}: n_cands_top10={len(cands_with_label)}, L2_in_top10={l2_in_top10}, top10: {cands_with_label[:3]}")
finally:
    real_path.write_text(json.dumps(real, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nrestored")
