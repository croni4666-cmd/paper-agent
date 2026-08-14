"""v3.9.12.0 ClinicalTrials.gov end-to-end test (5 cases)."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

PROJ = r"G:\minimax - workspace\Paper agent"
os.chdir(PROJ)


def run_pa(query, engine=None, year_min=None, year_max=None, limit=5, timeout_sec=60):
    cmd = ["python", "-m", "pa_cli", "search", query, "--limit", str(limit), "--format", "json"]
    if engine:
        cmd.extend(["--engine", engine])
    if year_min is not None:
        cmd.extend(["--year-min", str(year_min)])
    if year_max is not None:
        cmd.extend(["--year-max", str(year_max)])
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["HTTPS_PROXY"] = "http://127.0.0.1:10808"
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout_sec,
            encoding="utf-8", errors="replace", env=env
        )
    except subprocess.TimeoutExpired:
        return None, f"TIMEOUT after {timeout_sec}s"
    cleaned = "\n".join(L for L in result.stdout.splitlines() if not L.startswith("[pa]"))
    s = cleaned.find("{")
    if s < 0:
        return None, f"No JSON. rc={result.returncode} tail={result.stdout[-200:]!r}"
    try:
        return json.loads(cleaned[s:]), None
    except json.JSONDecodeError as e:
        return None, f"JSON parse: {e}"


def show(name, data, source_filter=None):
    if isinstance(data, dict):
        papers = data.get("results", [])
        by_engine = data.get("by_engine", {})
    else:
        papers = data
        by_engine = {}
    if source_filter:
        papers = [p for p in papers if p.get("source") == source_filter]
    by_engine_str = ", ".join(f"{k}={v}" for k, v in by_engine.items())
    print(f"  {name}: {len(papers)} papers (by_engine: {by_engine_str})")
    for i, r in enumerate(papers[:3]):
        print(f"  [{i+1}] source={r.get('source', '?'):15s}  year={str(r.get('year', '?')):5s}  "
              f"nct={r.get('nct_id', '-')}")
        print(f"      title: {(r.get('title') or '')[:80]}")
        if r.get('conditions'):
            print(f"      conditions: {r['conditions'][:3]}")
        if r.get('interventions'):
            print(f"      interventions: {r['interventions'][:2]}")
        if r.get('status'):
            print(f"      status: {r['status']}  phase: {r.get('phase', '-')}")


print("=" * 78)
print("v3.9.12.0 ClinicalTrials.gov end-to-end test")
print("=" * 78)

# Test 1: clinicaltrials alone with cervical muscle query
print("\n--- Test 1: clinicaltrials alone (cervical muscle) ---")
data, err = run_pa("cervical muscle", engine="clinicaltrials", limit=5)
if err:
    print(f"  ERROR: {err}")
    t1_ok = False
else:
    show("clinicaltrials", data, source_filter="clinicaltrials")
    papers = [p for p in data.get("results", []) if p.get("source") == "clinicaltrials"]
    t1_ok = len(papers) >= 3 and all(p.get("nct_id") for p in papers[:3])
    print(f"  Test 1: {'PASS' if t1_ok else 'FAIL'}")

# Test 2: clinicaltrials alone with OPLL query
print("\n--- Test 2: clinicaltrials alone (OPLL) ---")
data, err = run_pa("ossification posterior longitudinal ligament", engine="clinicaltrials", limit=5)
if err:
    print(f"  ERROR: {err}")
    t2_ok = False
else:
    show("clinicaltrials", data, source_filter="clinicaltrials")
    papers = [p for p in data.get("results", []) if p.get("source") == "clinicaltrials"]
    t2_ok = len(papers) >= 1
    print(f"  Test 2: {'PASS' if t2_ok else 'FAIL'}")

# Test 3: year_min filter
print("\n--- Test 3: year filter (mRNA COVID vaccine, year>=2023) ---")
data, err = run_pa("mRNA COVID vaccine", engine="clinicaltrials", year_min=2023, limit=5)
if err:
    print(f"  ERROR: {err}")
    t3_ok = False
else:
    show("clinicaltrials", data, source_filter="clinicaltrials")
    papers = [p for p in data.get("results", []) if p.get("source") == "clinicaltrials"]
    years = [p.get("year") for p in papers if p.get("year")]
    t3_ok = len(papers) >= 1 and all(y and y >= 2023 for y in years)
    print(f"  Test 3: {'PASS' if t3_ok else 'FAIL'}")

# Test 4: --engine all includes clinicaltrials
print("\n--- Test 4: --engine all includes clinicaltrials ---")
data, err = run_pa("cervical pain", engine="all", limit=10, timeout_sec=180)
if err:
    print(f"  ERROR: {err}")
    t4_ok = False
else:
    by_engine = data.get("by_engine", {})
    ct_count = by_engine.get("clinicaltrials", 0)
    print(f"  engines: {list(by_engine.keys())}")
    print(f"  clinicaltrials in by_engine: {ct_count}")
    t4_ok = "clinicaltrials" in by_engine and ct_count >= 1
    print(f"  Test 4: {'PASS' if t4_ok else 'FAIL'}")

# Test 5: empty result
print("\n--- Test 5: empty result (gibberish query) ---")
data, err = run_pa("asdfqwerzxcvbnmlkjh", engine="clinicaltrials", limit=5)
if err:
    print(f"  ERROR: {err}")
    t5_ok = False
else:
    papers = [p for p in data.get("results", []) if p.get("source") == "clinicaltrials"]
    print(f"  papers: {len(papers)}")
    t5_ok = len(papers) == 0
    print(f"  Test 5: {'PASS' if t5_ok else 'FAIL'}")

# Test 6: has nct_id + start_date
print("\n--- Test 6: nct_id + start_date fields populated ---")
data, err = run_pa("cancer immunotherapy", engine="clinicaltrials", limit=3)
if err:
    print(f"  ERROR: {err}")
    t6_ok = False
else:
    papers = [p for p in data.get("results", []) if p.get("source") == "clinicaltrials"]
    if papers:
        p = papers[0]
        print(f"  nct_id: {p.get('nct_id', '?')}")
        print(f"  start_date: {p.get('start_date', '?')}")
        print(f"  status: {p.get('status', '?')}")
        print(f"  phase: {p.get('phase', '?')}")
        t6_ok = bool(p.get("nct_id")) and bool(p.get("start_date"))
    else:
        t6_ok = False
    print(f"  Test 6: {'PASS' if t6_ok else 'FAIL'}")

# Summary
print()
print("=" * 78)
print("SUMMARY")
print("=" * 78)
results = {"Test 1": t1_ok, "Test 2": t2_ok, "Test 3": t3_ok,
           "Test 4": t4_ok, "Test 5": t5_ok, "Test 6": t6_ok}
for name, ok in results.items():
    print(f"  {name:8s} {'PASS' if ok else 'FAIL'}")
total = sum(results.values())
print(f"  TOTAL: {total}/{len(results)}")
sys.exit(0 if total == len(results) else 1)
