"""Extract 12 MoE training samples (q051-q062) from labels_clean.json to independent file.

Per Option B (user decision 2026-07-22):
- Move labels to bench/v01/moe_keyword_samples_12.json
- Restore labels_clean.json from v3.9.7.3 backup
- Keep the 12 system_outputs in system_outputs_combined_moe_samples_12/ (already done)
"""
import json
import shutil
from pathlib import Path

ROOT = Path(".")
BENCH = ROOT / "bench" / "v01"
LABELS = BENCH / "labels_clean.json"
LABELS_BACKUP = BENCH / "labels_clean.v3973backup.json"
SAMPLES_OUT = BENCH / "moe_keyword_samples_12.json"

# Load current labels_clean.json
data = json.loads(LABELS.read_text(encoding="utf-8"))
labels = data.get("labels", {})

# Extract q051-q062
samples = {}
for qid in [f"q{i:03d}" for i in range(51, 63)]:
    if qid in labels:
        samples[qid] = labels.pop(qid)
    else:
        print(f"  WARN: {qid} not in labels_clean.json")

print(f"Extracted {len(samples)} samples to {SAMPLES_OUT.name}")
out = {
    "version": "v0.1-moe-samples-12",
    "source": "bench/moe-keyword-samples.md (12 verified papers, 4-dim labels)",
    "engine_distribution": {"crossref": 5, "s2": 3, "openalex": 2, "arxiv": 2, "aminer": 0},
    "topic_clusters": ["maturity", "DEA-Tobit", "edge-AI", "AI-divide"],
    "merge_when": "n_total >= 30 AND aminer samples > 0 (currently 0)",
    "merge_script": "test_output/_merge_moe_samples.py",
    "labels": samples,
}
SAMPLES_OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

# Write back labels_clean.json (without q051-q062)
LABELS.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"labels_clean.json: removed q051-q062, kept {len(labels)} qids")

# Verify against backup
if LABELS_BACKUP.exists():
    backup_labels = json.loads(LABELS_BACKUP.read_text(encoding="utf-8"))["labels"]
    if set(labels.keys()) == set(backup_labels.keys()):
        print(f"OK: labels_clean.json now matches v3.9.7.3 backup ({len(backup_labels)} qids)")
    else:
        diff = set(backup_labels.keys()) ^ set(labels.keys())
        print(f"  MISMATCH: {len(diff)} qids differ: {sorted(diff)[:5]}")
else:
    print(f"  WARN: no backup at {LABELS_BACKUP}")
