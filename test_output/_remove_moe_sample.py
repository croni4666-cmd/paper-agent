"""Remove a MoE training sample from the library (cleanup utility)."""
import argparse
import json
from pathlib import Path

ROOT = Path(".")
BENCH = ROOT / "bench" / "v01"
SAMPLES_JSON = BENCH / "moe_keyword_samples_12.json"
SYS_OUT_DIR = BENCH / "system_outputs_combined_moe_samples_12"


def main():
    parser = argparse.ArgumentParser(description="Remove a MoE training sample")
    parser.add_argument("--qid", required=True, help="qid to remove (e.g. q063)")
    args = parser.parse_args()

    if not SAMPLES_JSON.exists():
        print(f"ERROR: {SAMPLES_JSON} not found")
        return

    data = json.loads(SAMPLES_JSON.read_text(encoding="utf-8-sig"))
    labels = data.get("labels", {})

    if args.qid not in labels:
        print(f"{args.qid} not in library (current: {sorted(labels.keys())})")
        return

    del labels[args.qid]
    data["labels"] = labels
    tmp = SAMPLES_JSON.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(SAMPLES_JSON)
    print(f"  [labels] {args.qid} removed")

    sys_out = SYS_OUT_DIR / f"{args.qid}.json"
    if sys_out.exists():
        sys_out.unlink()
        print(f"  [system_outputs] {sys_out.name} deleted")
    else:
        print(f"  [system_outputs] {args.qid}.json not in {SYS_OUT_DIR.name}/ (skipped)")

    from _status_moe_samples import print_status
    print()
    print_status()


if __name__ == "__main__":
    main()
