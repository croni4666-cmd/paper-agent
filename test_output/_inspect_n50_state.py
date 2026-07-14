"""Inspect n=50 state — system_outputs, combined, labels."""
import json
from pathlib import Path

sys_dir = Path(r"G:\minimax - workspace\Paper agent\bench\v01\system_outputs")
combined_dir = Path(r"G:\minimax - workspace\Paper agent\bench\v01\system_outputs_combined")
labels_path = Path(r"G:\minimax - workspace\Paper agent\bench\v01\labels_clean.json")

files = sorted(sys_dir.glob("q*.json"))
print(f"system_outputs: {len(files)} files")
for f in files[24:30]:
    obj = json.loads(f.read_text(encoding="utf-8"))
    print(f"  {f.stem}: n_results={len(obj.get('results', []))}, q={obj.get('query', '')[:50]!r}")

# Combined
combined = sorted(combined_dir.glob("q*.json"))
print(f"\ncombined: {len(combined)} files")
print(f"  first: {combined[0].stem}, last: {combined[-1].stem}")

# Labels
labels_data = json.loads(labels_path.read_text(encoding="utf-8"))
qids = sorted(labels_data["labels"].keys())
print(f"\nlabels: {len(qids)} qids")
print(f"  first: {qids[0]}, last: {qids[-1]}")
print(f"  q026+ in labels: {[q for q in qids if int(q[1:]) >= 26]}")
