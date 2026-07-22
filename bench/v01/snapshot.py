"""
paper-agent-bench-v0.1 — snapshot.py
Run current 5-engine paper-agent for each query, save top-N candidates to
system_outputs/<query_id>.json. This is the **fixed candidate pool** that all
v4 evaluations compare against.

Usage:
    python -m bench.v0.1.snapshot \
        --queries bench/v0.1/queries.json \
        --out bench/v0.1/system_outputs \
        [--top-n 30] [--config "baseline-v0.1"]

Behavior:
    For each non-placeholder query in queries.json:
        - Calls pa search (current 5-engine + dedup, no PaSa-lite, no MoE,
          no reranker) for that query
        - Takes top-N results (default 30)
        - Saves as system_outputs/<query_id>.json with full metadata

Output format: see system_outputs/_schema.json (auto-created on first run).
"""

import argparse
import json
import os
import sys
import subprocess
import shutil
from pathlib import Path
from datetime import datetime

BENCH_ROOT = Path(__file__).resolve().parent
PA_CLI_PATH = BENCH_ROOT.parent.parent / "pa_cli"


def run_pa_search(query: str, top_n: int = 30, config: str = "baseline-v0.1") -> list[dict]:
    """Invoke pa_cli search for one query, return top-N results as list of dicts.

    Returns: [{"rank": 1, "doi": "10.1234/abc", "title": "...", "abstract": "...",
               "year": 2023, "venue": "...", "citation_count": 124,
               "engines_found_in": [...], "score": 0.87}, ...]
    """
    # try to find python on PATH
    py = sys.executable or "python"

    # we need to call pa_cli search via subprocess so we don't pollute current env
    # and don't accidentally import conflicting modules
    cmd = [
        py, "-m", "pa_cli", "search",
        query,
        "--top-n", str(top_n),
        "--config", config,
        "--json",  # need pa_cli to support this flag (TODO: confirm/add)
    ]

    pa_cli_dir = str(PA_CLI_PATH.parent)
    env = os.environ.copy()
    env["PYTHONPATH"] = pa_cli_dir + os.pathsep + env.get("PYTHONPATH", "")

    try:
        result = subprocess.run(
            cmd,
            env=env,
            cwd=str(PA_CLI_PATH.parent),
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            print(f"  ERROR: pa_cli search failed for '{query}'", file=sys.stderr)
            print(f"    stderr: {result.stderr[:500]}", file=sys.stderr)
            return []
        data = json.loads(result.stdout)
        return data.get("results", [])
    except json.JSONDecodeError as e:
        print(f"  ERROR: pa_cli output not JSON: {e}", file=sys.stderr)
        print(f"    stdout first 500 chars: {result.stdout[:500]}", file=sys.stderr)
        return []
    except subprocess.TimeoutExpired:
        print(f"  ERROR: pa_cli search timed out for '{query}'", file=sys.stderr)
        return []
    except Exception as e:
        print(f"  ERROR: {e}", file=sys.stderr)
        return []


def normalize_results(raw: list[dict], top_n: int) -> list[dict]:
    """Ensure each result has rank + DOI + the fields eval.py needs."""
    out = []
    for i, r in enumerate(raw[:top_n], start=1):
        out.append({
            "rank": i,
            "doi": r.get("doi") or "",
            "title": r.get("title", ""),
            "abstract": r.get("abstract", ""),
            "year": r.get("year"),
            "venue": r.get("venue") or r.get("journal") or "",
            "citation_count": r.get("citation_count", 0) or 0,
            "engines_found_in": r.get("engines_found_in", []),
            "score": r.get("score", 0.0),
        })
    return out


def main():
    ap = argparse.ArgumentParser(description="Snapshot top-N baseline candidates for benchmark queries")
    ap.add_argument("--queries", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--top-n", type=int, default=30)
    ap.add_argument("--config", default="baseline-v0.1")
    ap.add_argument("--dry-run", action="store_true",
                    help="print commands but don't actually run pa search")
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)

    data = json.loads(args.queries.read_text(encoding="utf-8"))
    queries = data.get("queries", [])

    # filter out placeholders
    real_queries = [q for q in queries if not q["query"].startswith("[USER-PROVIDED")]

    print(f"[snapshot] {len(real_queries)} real queries (filtered from {len(queries)})")
    print(f"[snapshot] top_n={args.top_n}, config={args.config}")
    print(f"[snapshot] out={args.out}")

    skipped = []
    done = 0
    for q in real_queries:
        qid = q["id"]
        out_path = args.out / f"{qid}.json"
        if out_path.exists():
            print(f"  [SKIP] {qid} (already exists)")
            continue
        if args.dry_run:
            print(f"  [DRY] would run pa search for {qid}: {q['query'][:60]}")
            continue
        print(f"  [RUN] {qid}: {q['query'][:60]}...")
        raw = run_pa_search(q["query"], args.top_n, args.config)
        if not raw:
            skipped.append(qid)
            print(f"    → skipped (no results)")
            continue
        normalized = normalize_results(raw, args.top_n)
        snapshot = {
            "query_id": qid,
            "query": q["query"],
            "topic_bucket": q.get("topic_bucket", ""),
            "source": q.get("source", ""),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "config": args.config,
            "top_n": args.top_n,
            "n_returned": len(normalized),
            "results": normalized,
        }
        out_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        done += 1
        print(f"    → {len(normalized)} papers → {out_path.name}")

    print("")
    print(f"[snapshot] done: {done} queries, skipped: {len(skipped)}")
    if skipped:
        print(f"[snapshot] skipped IDs: {skipped}")


if __name__ == "__main__":
    main()