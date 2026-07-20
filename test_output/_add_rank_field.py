"""Add `rank` field to each candidate in system_outputs/*.json (v3.9.10.10 data).

The v3.9.7.3 pipeline (via `_v4_rerank.py`) expected each candidate to have a
`rank` field already set. The v3.9.10.10 rebuild via `run_search` does NOT
emit `rank`. So we add it post-hoc so v4_rerank can use it.

`rank` = 1-based position in the original `results` list.
"""
import json
from pathlib import Path

bench_dir = Path("bench/v01")
in_dir = bench_dir / "system_outputs"

n_files = 0
n_cands = 0
for f in sorted(in_dir.glob("q*.json")):
    snap = json.loads(f.read_text(encoding="utf-8"))
    results = snap.get("results", [])
    for i, r in enumerate(results, start=1):
        if "rank" not in r:
            r["rank"] = i
            n_cands += 1
    snap["results"] = results
    f.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
    n_files += 1

print(f"Added rank to {n_cands} candidates across {n_files} files")
