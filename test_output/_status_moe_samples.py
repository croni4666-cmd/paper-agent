"""[v3.9.7.4-indep] Show status of MoE training sample library.

Per user request 2026-07-22: incremental sample library.
- Shows n_total, engine distribution, topic distribution
- Shows distance to merge threshold (n>=30, aminer>=1)
- Suggests what to add next

Usage:
    python test_output/_status_moe_samples.py
"""
import json
import sys
from pathlib import Path
from collections import Counter

ROOT = Path(".")
BENCH = ROOT / "bench" / "v01"
SAMPLES_JSON = BENCH / "moe_keyword_samples_12.json"
SYS_OUT_DIR = BENCH / "system_outputs_combined_moe_samples_12"

MERGE_THRESHOLDS = {
    "n_total": 30,
    "aminer": 1,
}


def print_status():
    """Print current status of the sample library."""
    if not SAMPLES_JSON.exists():
        print(f"ERROR: {SAMPLES_JSON} not found")
        return

    data = json.loads(SAMPLES_JSON.read_text(encoding="utf-8-sig"))
    labels = data.get("labels", {})

    print("=" * 70)
    print(f"MoE Training Sample Library — v{data.get('version', 'unknown')}")
    print("=" * 70)
    print(f"Source: {data.get('source', 'unknown')}")
    print(f"Total samples: {len(labels)}")
    print()

    # Engine distribution
    engines = Counter()
    for qid, qdata in labels.items():
        for doi, dinfo in qdata.items():
            reason = dinfo.get("reason", "")
            if "engine=" in reason:
                eng = reason.split("engine=")[1].split()[0]
                engines[eng] += 1
    print("Engine distribution:")
    if engines:
        for eng, n in sorted(engines.items(), key=lambda x: -x[1]):
            bar = "█" * n
            print(f"  {eng:12s} {n:3d} {bar}")
    else:
        print("  (none)")
    print()

    # Topic distribution
    topics = Counter()
    for qid, qdata in labels.items():
        for doi, dinfo in qdata.items():
            reason = dinfo.get("reason", "")
            if "[" in reason and "]" in reason:
                tag = reason.split("[")[1].split("]")[0]
                topic = tag.split("/")[0]
                topics[topic] += 1
    print("Topic distribution:")
    if topics:
        for t, n in sorted(topics.items()):
            print(f"  {t:5s} {n:3d}")
    else:
        print("  (none)")
    print()

    # System_outputs file count
    n_sysout = len(list(SYS_OUT_DIR.glob("q*.json"))) if SYS_OUT_DIR.exists() else 0
    print(f"System outputs files: {n_sysout} (in {SYS_OUT_DIR.name}/)")
    print()

    # Distance to merge threshold
    print("Merge conditions (test_output/_merge_moe_samples.py):")
    n_total = len(labels)
    n_aminer = engines.get("aminer", 0)
    n_need = max(0, MERGE_THRESHOLDS["n_total"] - n_total)
    amin_need = max(0, MERGE_THRESHOLDS["aminer"] - n_aminer)
    print(f"  n_total >= {MERGE_THRESHOLDS['n_total']}: {n_total}/{MERGE_THRESHOLDS['n_total']} "
          f"({'OK' if n_total >= MERGE_THRESHOLDS['n_total'] else f'need +{n_need}'})")
    print(f"  aminer >= {MERGE_THRESHOLDS['aminer']}: {n_aminer}/{MERGE_THRESHOLDS['aminer']} "
          f"({'OK' if n_aminer >= MERGE_THRESHOLDS['aminer'] else f'need +{amin_need}'})")

    if n_need == 0 and amin_need == 0:
        print()
        print("  All conditions met! Run: python test_output/_merge_moe_samples.py")
    else:
        print()
        print("  Suggested additions:")
        if amin_need > 0:
            print(f"    - +{amin_need} China-local query (route to aminer)")
            print(f"      Example: --query '海宁经编 算力券 政策 杠杆' --engine aminer \\")
            print(f"                --topic t5 --method m13 --data d11 --industry i3")
        if n_need > 0:
            print(f"    - +{n_need} more keyword samples (any topic)")

    print()
    print("Add a sample: python test_output/_add_moe_sample.py --help")
    print("=" * 70)


if __name__ == "__main__":
    print_status()
