"""v3.9.11.9 year filter edge cases — make sure no regression."""
import json
import os
import subprocess
import sys

PROJ = r"G:\minimax - workspace\Paper agent"
os.chdir(PROJ)
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"


def run_pa(query, year_min=None, year_max=None, limit=10, timeout_sec=60):
    cmd = ["python", "-m", "pa_cli", "search", query, "--engine", "pubmed",
           "--limit", str(limit), "--format", "json"]
    if year_min is not None:
        cmd.extend(["--year-min", str(year_min)])
    if year_max is not None:
        cmd.extend(["--year-max", str(year_max)])
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout_sec, encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return None, "TIMEOUT"
    cleaned = "\n".join(L for L in r.stdout.splitlines() if not L.startswith("[pa]"))
    s = cleaned.find("{")
    if s < 0:
        return None, f"No JSON. tail={r.stdout[-200:]!r}"
    try:
        return json.loads(cleaned[s:]), None
    except json.JSONDecodeError as e:
        return None, f"JSON err: {e}"


def check(name, query, year_min=None, year_max=None, limit=10, expected_min=None, expected_max=None, allow_zero=False):
    data, err = run_pa(query, year_min, year_max, limit)
    if err:
        print(f"  [{name}] ERROR: {err}")
        return False
    papers = [p for p in data["results"] if p.get("source") == "pubmed"]
    years = [p.get("year") for p in papers if p.get("year")]
    print(f"  [{name}] {len(papers)} papers, years={years[:5]}{'...' if len(years) > 5 else ''}")
    # Check year constraints
    ok = True
    if not allow_zero and len(papers) == 0:
        print(f"    -> FAIL: 0 papers (expected >=1)")
        ok = False
    if year_min is not None and years:
        below = [y for y in years if y < year_min]
        if below:
            print(f"    -> FAIL: {len(below)} papers below year_min={year_min}: {below}")
            ok = False
    if year_max is not None and years:
        above = [y for y in years if y > year_max]
        if above:
            print(f"    -> FAIL: {len(above)} papers above year_max={year_max}: {above}")
            ok = False
    if expected_min is not None and len(papers) < expected_min:
        print(f"    -> FAIL: only {len(papers)} papers (expected >= {expected_min})")
        ok = False
    if expected_max is not None and len(papers) > expected_max:
        print(f"    -> FAIL: {len(papers)} papers (expected <= {expected_max})")
        ok = False
    if ok:
        print(f"    -> PASS")
    return ok


print("=" * 70)
print("v3.9.11.9 year filter edge cases (regression check)")
print("=" * 70)

results = []

# Test A: --year-min only, lower bound
print("\n--- A: --year-min 2024 only (no upper) ---")
results.append(("A year_min only", check("A", "ACE inhibitors", year_min=2024, expected_min=1)))

# Test B: --year-max only, upper bound
print("\n--- B: --year-max 2015 only (no lower) ---")
results.append(("B year_max only", check("B", "ACE inhibitors", year_max=2015, expected_min=1)))

# Test C: --year-min == --year-max (the original bug case)
print("\n--- C: --year-min 2020 --year-max 2020 (was the bug) ---")
results.append(("C year range both", check("C", "diabetes", year_min=2020, year_max=2020, expected_min=1)))

# Test D: no year filter, should work
print("\n--- D: no year filter at all ---")
results.append(("D no filter", check("D", "aspirin", expected_min=1)))

# Test E: very recent range
print("\n--- E: --year-min 2026 (very recent) ---")
results.append(("E recent year", check("E", "machine learning medical", year_min=2026, allow_zero=True)))

# Test F: very old range (e.g. 1990-1995)
print("\n--- F: --year-min 1990 --year-max 1995 (historical) ---")
results.append(("F historical", check("F", "insulin diabetes", year_min=1990, year_max=1995, allow_zero=True)))

# Test G: limit smaller than results
print("\n--- G: --year-min 2020 --year-max 2020 --limit 2 ---")
results.append(("G small limit", check("G", "diabetes", year_min=2020, year_max=2020, limit=2, expected_min=1, expected_max=2)))

# Test H: count post-filter impact — should not crash with limit=1 after filter
print("\n--- H: --year-min 2020 --year-max 2020 --limit 1 (post-filter may give 0) ---")
results.append(("H tight limit", check("H", "diabetes", year_min=2020, year_max=2020, limit=1, allow_zero=True)))

print()
print("=" * 70)
print("SUMMARY")
print("=" * 70)
for name, ok in results:
    print(f"  {name:30s} {'PASS' if ok else 'FAIL'}")
total_pass = sum(1 for _, ok in results if ok)
print(f"  TOTAL: {total_pass}/{len(results)}")
sys.exit(0 if total_pass == len(results) else 1)
