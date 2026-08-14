"""
Diagnostic for the two FAILs from the main verifier:
  - Test 3 dedup: by_engine is {engine: int} not {engine: [papers]}
  - Test 6 concept: 0 results, was the concept filter too strict?

Re-runs with correct interpretation of by_engine (counts), and tries
queries known to produce DOI overlap.
"""
import os
import sys
import json
import time
import subprocess
from pathlib import Path

os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"

ROOT = Path(r"G:\minimax - workspace\Paper agent")
TEST_OUT = ROOT / "test_output"
LOG_FILE = TEST_OUT / "_verifier_b_v3_9_11_8_diag.log"

# Ensure root on path
sys.path.insert(0, str(ROOT))


def log(msg: str = "") -> None:
    print(msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def run_pa(args, timeout=180):
    cmd = [sys.executable, "-m", "pa_cli"] + args
    r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                       timeout=timeout, env=os.environ.copy())
    return r.returncode, r.stdout, r.stderr


# Clear log
with open(LOG_FILE, "w", encoding="utf-8") as f:
    f.write("")

log("=" * 70)
log("Diagnostic for v3.9.11.8 backward-compat — interpreting by_engine correctly")
log("=" * 70)

# ------- Dedup test (corrected) -------
log("\n=== Dedup diagnostic: looking for found_by length > 1 across engines ===")
log("Strategy: query a famous paper likely in pubmed + openalex + crossref")
log("Try: 'Attention is all you need' (Vaswani 2017)")

# Use a well-known high-citation paper title
queries_to_try = [
    "Attention is all you need",
    "BERT pre-training of deep bidirectional transformers",
    "Deep residual learning image recognition",
    "mRNA COVID-19 vaccine safety",
    "COVID-19 mRNA vaccine",
]
engine_combos = [
    "openalex,pubmed,crossref",
    "crossref,pubmed,openalex",
]

found_dedup_evidence = False
for engine_arg in engine_combos:
    for q in queries_to_try:
        log(f"\n  query={q!r} engines={engine_arg}")
        rc, out, err = run_pa(["search", q, "--engine", engine_arg,
                                "--limit", "15", "--quiet"])
        if rc != 0:
            log(f"    exit={rc}, stderr={err[-200:]}")
            continue
        try:
            data = json.loads(out)
        except json.JSONDecodeError:
            log(f"    not JSON, first 200: {out[:200]!r}")
            continue
        by_engine = data.get("by_engine", {})
        results = data.get("results", [])
        log(f"    by_engine (counts): {by_engine}")
        log(f"    unified results: {len(results)}")
        # Check found_by across all results
        found_by_dist = {}
        for r in results:
            if not isinstance(r, dict):
                continue
            fb = r.get("found_by", [])
            found_by_dist.setdefault(tuple(fb), 0)
            found_by_dist[tuple(fb)] += 1
        log(f"    found_by distribution: {dict(found_by_dist)}")
        multi = [r for r in results
                 if isinstance(r, dict) and len(r.get("found_by", [])) > 1]
        if multi:
            found_dedup_evidence = True
            log(f"    *** {len(multi)} papers found by multiple engines ***")
            for r in multi[:3]:
                log(f"        title={r.get('title','')[:80]!r}")
                log(f"        doi={r.get('doi','')!r}")
                log(f"        found_by={r.get('found_by')}")
            break
    if found_dedup_evidence:
        break

if not found_dedup_evidence:
    log("\n  No direct DOI overlap found across engines. Trying arXiv id overlap")
    log("  and 'title[:60]' fallback path...")
    rc, out, err = run_pa(["search", "attention is all you need transformer",
                            "--engine", "openalex,arxiv,crossref",
                            "--limit", "20", "--quiet"])
    if rc == 0:
        data = json.loads(out)
        by_engine = data.get("by_engine", {})
        results = data.get("results", [])
        log(f"  by_engine: {by_engine}, unified: {len(results)}")
        multi = [r for r in results
                 if isinstance(r, dict) and len(r.get("found_by", [])) > 1]
        log(f"  multi-engine papers: {len(multi)}")
        if multi:
            found_dedup_evidence = True
            for r in multi[:3]:
                log(f"    title={r.get('title','')[:80]!r}")
                log(f"    doi={r.get('doi','')!r} arxiv={r.get('arxiv_id','')!r}")
                log(f"    found_by={r.get('found_by')}")

log(f"\n  dedup_evidence_found: {found_dedup_evidence}")

# ------- Concept filter diagnostic (corrected) -------
log("\n=== Concept filter diagnostic ===")
log("Try several (query, concept) combinations")

concept_combos = [
    ("transformer", "machine learning"),
    ("transformer", "Artificial Intelligence"),
    ("BERT", "machine learning"),
    ("deep learning", "machine learning"),
    ("neural network", "machine learning"),
    ("convolutional neural network", "computer vision"),
    ("attention", "machine learning"),
]

for query, concept in concept_combos:
    log(f"\n  query={query!r} concept={concept!r}")
    rc, out, err = run_pa(["search", query, "--concept", concept,
                            "--engine", "openalex", "--limit", "3", "--quiet"])
    if rc != 0:
        log(f"    exit={rc}, stderr={err[-300:]}")
        continue
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        log(f"    not JSON, first 200: {out[:200]!r}")
        continue
    by_engine = data.get("by_engine", {})
    results = data.get("results", [])
    log(f"    by_engine: {by_engine}")
    log(f"    concept_mode: {data.get('concept_mode','')}")
    log(f"    unified results: {len(results)}")
    if results:
        first = results[0]
        log(f"    first title: {first.get('title','')[:100]!r}")
        log(f"    first doi:   {first.get('doi','')!r}")
        log(f"    concepts:    {first.get('concepts', [])[:5] if first.get('concepts') else 'n/a'}")
        log(f"    found_by:    {first.get('found_by')}")

# Also try without --quiet so we can see the concept debug print
log("\n  With stderr visible (no --quiet) to see concept resolution:")
rc, out, err = run_pa(["search", "transformer", "--concept", "machine learning",
                        "--engine", "openalex", "--limit", "3"])
log(f"  exit={rc}")
log(f"  stderr (last 500): {err[-500:]}")
log(f"  stdout (last 200): {out[-200:]}")

log("\n=== Diagnostic done ===")
