"""Batch generate system_outputs/q026.json ... q050.json for n=50 bench.

For each q026-q050 query:
  1. Call `pa search <query> --limit 10 --format json` (per-engine 10, ~30 deduped)
  2. Convert new schema to old snapshot.py schema (add query_id, generated_at, config;
     rename found_by -> engines_found_in; add rank)
  3. Save to bench/v01/system_outputs/qNNN.json

Then v4_rerank n=50 will pick them up automatically.

Note: PA_KEYS demo-api-key is EXPIRED but pa search still works (only 3 of 5 engines).
This is the same state as n=25 baseline was generated in.
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

QUERIES_PATH = ROOT / "bench" / "v01" / "queries.json"
OUT_DIR = ROOT / "bench" / "v01" / "system_outputs"


def main():
    obj = json.loads(QUERIES_PATH.read_text(encoding="utf-8"))
    queries = [q for q in obj["queries"] if q.get("source") == "user" and q.get("id") not in {f"q{i:03d}" for i in range(1, 26)}]
    print(f"Found {len(queries)} user queries q026-q050 to process")
    assert len(queries) == 25, f"Expected 25 user queries, got {len(queries)}"

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    py = sys.executable
    generated_at = datetime.now().isoformat(timespec="seconds")

    success = 0
    fail = 0
    for q in queries:
        qid = q["id"]
        query_text = q["query"]
        out_path = OUT_DIR / f"{qid}.json"
        if out_path.exists():
            print(f"  {qid}: SKIP (already exists)")
            continue

        # Use Python subprocess with UTF-8 env to avoid GBK encoding errors
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")

        cmd = [
            py, "-m", "pa_cli", "search", query_text,
            "--limit", "10",
            "--format", "json",
            "-o", str(out_path.with_suffix(".tmp.json")),
        ]
        try:
            result = subprocess.run(
                cmd, env=env,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=60,
            )
            if result.returncode != 0:
                print(f"  {qid}: FAIL (returncode={result.returncode})")
                fail += 1
                continue
        except subprocess.TimeoutExpired:
            print(f"  {qid}: FAIL (timeout)")
            fail += 1
            continue

        tmp_path = out_path.with_suffix(".tmp.json")
        if not tmp_path.exists():
            print(f"  {qid}: FAIL (no output file)")
            fail += 1
            continue

        # Convert new schema → old snapshot schema
        try:
            raw = json.loads(tmp_path.read_text(encoding="utf-8"))
            new_results = raw.get("results", [])
            old_results = []
            for i, r in enumerate(new_results, start=1):
                old_results.append({
                    "rank": i,
                    "doi": r.get("doi", ""),
                    "title": r.get("title", ""),
                    "abstract": r.get("abstract", ""),
                    "year": r.get("year"),
                    "venue": r.get("venue", ""),
                    "citation_count": r.get("cited_by_count", 0),
                    "engines_found_in": r.get("found_by", []),
                    "score": r.get("score", 0.0),
                    "source": r.get("source", ""),
                    "type": r.get("type", ""),
                })
            snap = {
                "query_id": qid,
                "query": query_text,
                "generated_at": generated_at,
                "config": "v3.9.0-baseline-n50",
                "by_engine": raw.get("by_engine", {}),
                "dedup_count": raw.get("dedup_count", len(old_results)),
                "results": old_results,
            }
            out_path.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp_path.unlink()
            print(f"  {qid}: OK ({len(old_results)} candidates)")
            success += 1
        except Exception as e:
            print(f"  {qid}: FAIL (convert: {e})")
            fail += 1
            if tmp_path.exists():
                tmp_path.unlink()

    print(f"\nDone. Success: {success}, Fail: {fail}")
    print(f"Output dir: {OUT_DIR}")


if __name__ == "__main__":
    main()
