"""Merge MoE keyword samples into main training data (gated on n>=30 + aminer samples).

Per Option B (user decision 2026-07-22):
- 12 samples are kept in independent files (moe_keyword_samples_12.json +
  system_outputs_combined_moe_samples_12/)
- This script is the GATED merger: runs only when conditions are met

Merge conditions (from moe-keyword-samples.md):
1. n_total >= 30 (currently 12 — need 18+ more)
2. aminer samples > 0 (currently 0 — need at least 1 China-local sample)

Usage:
    # Add more samples to bench/v01/moe_keyword_samples_12.json (edit directly)
    # Then run this script
    python test_output/_merge_moe_samples.py

Safety:
- Refuses to merge if conditions not met
- Backs up labels_clean.json and system_outputs_combined/ before merge
- Atomic writes (write to .tmp, then rename)
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(".")
BENCH = ROOT / "bench" / "v01"
LABELS = BENCH / "labels_clean.json"
SAMPLES = BENCH / "moe_keyword_samples_12.json"
SYS_OUT = BENCH / "system_outputs_combined"
SYS_SAMPLES = BENCH / "system_outputs_combined_moe_samples_12"

# Merge conditions (from moe-keyword-samples.md §6)
MIN_TOTAL = 30  # n_total must be at least 30
MIN_AMINER = 1  # at least 1 aminer sample


def main():
    # Load samples
    if not SAMPLES.exists():
        print(f"ERROR: {SAMPLES} not found")
        sys.exit(1)
    samples_data = json.loads(SAMPLES.read_text(encoding="utf-8-sig"))
    samples = samples_data.get("labels", {})
    n_samples = len(samples)
    print(f"Samples file: {SAMPLES.name} ({n_samples} qids)")

    # Count engines in samples
    engine_dist = {}
    for qid, qdata in samples.items():
        for doi, dinfo in qdata.items():
            reason = dinfo.get("reason", "")
            if "engine=" in reason:
                eng = reason.split("engine=")[1].split()[0]
                engine_dist[eng] = engine_dist.get(eng, 0) + 1
    print(f"Sample engine distribution: {engine_dist}")
    n_aminer = engine_dist.get("aminer", 0)
    print(f"  aminer samples: {n_aminer} (need >= {MIN_AMINER})")

    # Check merge conditions
    if n_samples < MIN_TOTAL:
        print(f"\nREFUSE: n_samples={n_samples} < {MIN_TOTAL}")
        print(f"  Need to add {MIN_TOTAL - n_samples} more samples to {SAMPLES.name}")
        print(f"  Suggested: more China-local samples (route to aminer)")
        sys.exit(2)
    if n_aminer < MIN_AMINER:
        print(f"\nREFUSE: aminer samples={n_aminer} < {MIN_AMINER}")
        print(f"  Need to add at least {MIN_AMINER} China-local query (route to aminer)")
        sys.exit(2)

    # All conditions met, proceed with merge
    print(f"\nAll merge conditions met. Proceeding...")

    # Backup current state
    backup_dir = BENCH / f"labels_clean.pre_merge_{__import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
    shutil.copy(LABELS, backup_dir)
    print(f"  Backup: {backup_dir.name}")

    sys_backup = BENCH / f"system_outputs_combined.pre_merge_{__import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
    if sys_backup.exists():
        shutil.rmtree(sys_backup)
    shutil.copytree(SYS_OUT, sys_backup)
    print(f"  Backup: {sys_backup.name}")

    # Merge labels
    data = json.loads(LABELS.read_text(encoding="utf-8-sig"))
    n_existing = len(data["labels"])
    for qid, qdata in samples.items():
        if qid in data["labels"]:
            print(f"  WARN: {qid} already in labels_clean.json, overwriting")
        data["labels"][qid] = qdata
    # Atomic write
    tmp = LABELS.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(LABELS)
    print(f"  labels_clean.json: {n_existing} -> {len(data['labels'])} qids")

    # Merge system_outputs
    n_sys_existing = len(list(SYS_OUT.glob("q*.json")))
    for qfile in SYS_SAMPLES.glob("q*.json"):
        dst = SYS_OUT / qfile.name
        if dst.exists():
            print(f"  WARN: {dst.name} already in system_outputs_combined/, overwriting")
        shutil.copy(qfile, dst)
    n_sys_new = len(list(SYS_OUT.glob("q*.json")))
    print(f"  system_outputs_combined: {n_sys_existing} -> {n_sys_new} files")

    print(f"\nMerge complete. Run `pa_cli.moe_router` to re-evaluate.")


if __name__ == "__main__":
    main()
