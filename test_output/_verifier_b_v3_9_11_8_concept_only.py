"""
Concept filter flakiness check. Run 3 attempts to see if
'transformer' + 'machine learning' is reliably 0 or if it's flukey.
"""
import os, sys, json, subprocess
from pathlib import Path

os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"

ROOT = Path(r"G:\minimax - workspace\Paper agent")
LOG = ROOT / "test_output" / "_verifier_b_v3_9_11_8_concept_only.log"
sys.path.insert(0, str(ROOT))

with open(LOG, "w", encoding="utf-8") as f:
    f.write("")

def log(m=""):
    print(m)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(m + "\n")

def run_pa(args, timeout=120):
    r = subprocess.run([sys.executable, "-m", "pa_cli"] + args,
                       cwd=str(ROOT), capture_output=True, text=True,
                       timeout=timeout, env=os.environ.copy())
    return r.returncode, r.stdout, r.stderr

log("=" * 60)
log("Concept filter: 3 attempts of the task-specified query")
log("=" * 60)

# Test 1: exact task-specified query
for i in range(3):
    log(f"\n[attempt {i+1}/3] pa search transformer --concept 'machine learning' --engine openalex --limit 3 --quiet")
    rc, out, err = run_pa(["search", "transformer", "--concept", "machine learning",
                            "--engine", "openalex", "--limit", "3", "--quiet"])
    log(f"  exit={rc}")
    if err:
        log(f"  stderr: {err[-200:]}")
    try:
        data = json.loads(out)
    except Exception as e:
        log(f"  not JSON: {e}, first 200: {out[:200]!r}")
        continue
    log(f"  by_engine: {data.get('by_engine')}")
    log(f"  concept_mode: {data.get('concept_mode', 'NOT SET')!r}")
    log(f"  applied_concepts: {data.get('applied_concepts', 'NOT SET')}")
    log(f"  unified results: {len(data.get('results', []))}")
    if data.get("results"):
        log(f"  first title: {data['results'][0].get('title','')[:100]!r}")

# Test 2: check what concept_id is resolved and if OpenAlex has results
log("\n" + "=" * 60)
log("Compare: 'BERT' + 'machine learning' (we know this works)")
log("=" * 60)
for i in range(3):
    log(f"\n[attempt {i+1}/3] pa search BERT --concept 'machine learning' --engine openalex --limit 3 --quiet")
    rc, out, err = run_pa(["search", "BERT", "--concept", "machine learning",
                            "--engine", "openalex", "--limit", "3", "--quiet"])
    log(f"  exit={rc}")
    try:
        data = json.loads(out)
    except Exception as e:
        log(f"  not JSON: {e}")
        continue
    log(f"  by_engine: {data.get('by_engine')}")
    log(f"  concept_mode: {data.get('concept_mode', 'NOT SET')!r}")
    log(f"  applied_concepts: {data.get('applied_concepts', 'NOT SET')}")
    log(f"  unified results: {len(data.get('results', []))}")
    if data.get("results"):
        log(f"  first title: {data['results'][0].get('title','')[:100]!r}")

# Test 3: test with --concept on something highly indexed
log("\n" + "=" * 60)
log("Highly-indexed query: 'cancer treatment' + 'medicine'")
log("=" * 60)
for i in range(3):
    log(f"\n[attempt {i+1}/3] pa search 'cancer treatment' --concept 'medicine' --engine openalex --limit 3 --quiet")
    rc, out, err = run_pa(["search", "cancer treatment", "--concept", "medicine",
                            "--engine", "openalex", "--limit", "3", "--quiet"])
    log(f"  exit={rc}")
    try:
        data = json.loads(out)
    except Exception as e:
        log(f"  not JSON: {e}")
        continue
    log(f"  by_engine: {data.get('by_engine')}")
    log(f"  concept_mode: {data.get('concept_mode', 'NOT SET')!r}")
    log(f"  applied_concepts: {data.get('applied_concepts', 'NOT SET')}")
    log(f"  unified results: {len(data.get('results', []))}")
    if data.get("results"):
        log(f"  first title: {data['results'][0].get('title','')[:100]!r}")

# Test 4: just check the code path: concept resolution runs without error
log("\n" + "=" * 60)
log("Code-path check: stderr shows concept resolution")
log("=" * 60)
for q, c in [("transformer", "machine learning"),
             ("BERT", "machine learning"),
             ("deep learning", "machine learning")]:
    log(f"\n  query={q!r} concept={c!r}")
    rc, out, err = run_pa(["search", q, "--concept", c, "--engine", "openalex",
                            "--limit", "3"])  # NO --quiet
    for line in (err or "").splitlines():
        if "concept" in line.lower() or "search query" in line:
            log(f"    {line.strip()}")
