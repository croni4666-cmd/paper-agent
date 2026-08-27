"""E2E test: pa fetch-batch with all 4 v3.9.26.0 fixes.

Test scenarios:
1. First download: size_bytes should be > 0, n_skipped = 0
2. Second download with --skip-existing: n_skipped = 2, n_success = 0
3. --clean-xml flag should remove .xml intermediate after success
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

PA_ROOT = Path(r"G:\minimax - workspace\Paper agent")
TEST_DIR = Path(r"G:\minimax - workspace\Paper agent\test_output\_v3_9_26_0_e2e\_batch_test")
TEST_DIR.mkdir(parents=True, exist_ok=True)

# Sample refs.bib with 2 known DOIs (from user's actual test):
# 10.1002/hep.32805 (Hepatology Wilson disease) and 10.3390/ijms21239259 (copper homeostasis)
BIB_PATH = TEST_DIR / "refs.bib"
BIB_PATH.write_text("""@article{gromadzka2023wilson,
  author = {Gromadzka, G. and others},
  title = {Wilson's Disease: Genetic and Diagnostic Challenges},
  journal = {Hepatology},
  year = {2023},
  doi = {10.1002/hep.32805}
}

@article{gromadzka2020copper,
  author = {Gromadzka, G. and others},
  title = {Copper Homeostasis and Neurodegenerative Diseases},
  journal = {Int J Mol Sci},
  year = {2020},
  doi = {10.3390/ijms21239259}
}
""", encoding="utf-8")

PDF_DIR = TEST_DIR / "pdfs"
if PDF_DIR.exists():
    shutil.rmtree(PDF_DIR)
PDF_DIR.mkdir(parents=True)

def run_fetch_batch(*extra_args, timeout=300):
    cmd = [
        sys.executable, "-m", "pa_cli.cli", "fetch-batch",
        str(BIB_PATH),
        "--out-dir", str(PDF_DIR),
        "--max-total-sec", "300",
    ] + list(extra_args)
    print(f"\n>>> Running: {' '.join(cmd[2:])}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(PA_ROOT))
    print(f"Exit: {result.returncode}")
    return result

# Test 1: First download
print("=" * 60)
print("TEST 1: First download (no skip, no clean-xml)")
print("=" * 60)
t0 = time.time()
result1 = run_fetch_batch("--summary-json", str(TEST_DIR / "summary1.json"))
t1 = time.time()
print(f"Elapsed: {t1 - t0:.1f}s")

if (TEST_DIR / "summary1.json").exists():
    s1 = json.loads((TEST_DIR / "summary1.json").read_text())
    print(f"\nSummary 1:")
    print(f"  n_total: {s1.get('n_total')}")
    print(f"  n_success: {s1.get('n_success')}")
    print(f"  n_failure: {s1.get('n_failure')}")
    print(f"  n_skipped: {s1.get('n_skipped')}")
    print(f"  total_size_bytes: {s1.get('total_size_bytes')}")
    print(f"\nPer-entry size_bytes:")
    for r in s1.get('results', []):
        print(f"  - {r.get('key')}: size={r.get('size_bytes')}, success={r.get('success')}, error={r.get('error')!r}")

    # Verify fixes
    print(f"\n--- Assertions ---")
    if s1.get('n_success') == 2:
        print("  PASS: n_success = 2")
    else:
        print(f"  FAIL: expected n_success=2, got {s1.get('n_success')}")
    if s1.get('n_skipped') == 0:
        print("  PASS: n_skipped = 0 (no skip on first run)")
    else:
        print(f"  FAIL: expected n_skipped=0, got {s1.get('n_skipped')}")
    if s1.get('total_size_bytes', 0) > 0:
        print(f"  PASS: total_size_bytes = {s1.get('total_size_bytes')} (was 0 before fix)")
    else:
        print(f"  FAIL: total_size_bytes = 0 (Bug 2 not fixed!)")
    for r in s1.get('results', []):
        if r.get('size_bytes', 0) > 0:
            print(f"  PASS: {r.get('key')} size_bytes = {r.get('size_bytes')}")
        else:
            print(f"  FAIL: {r.get('key')} size_bytes = 0")

# Test 2: Skip-existing
print("\n" + "=" * 60)
print("TEST 2: Second download with --skip-existing")
print("=" * 60)
result2 = run_fetch_batch("--summary-json", str(TEST_DIR / "summary2.json"), "--skip-existing")
if (TEST_DIR / "summary2.json").exists():
    s2 = json.loads((TEST_DIR / "summary2.json").read_text())
    print(f"\nSummary 2:")
    print(f"  n_total: {s2.get('n_total')}")
    print(f"  n_success: {s2.get('n_success')}")
    print(f"  n_failure: {s2.get('n_failure')}")
    print(f"  n_skipped: {s2.get('n_skipped')}")
    print(f"  total_size_bytes: {s2.get('total_size_bytes')}")

    print(f"\n--- Assertions (skip mode) ---")
    if s2.get('n_skipped') == 2:
        print("  PASS: n_skipped = 2 (Bug 3 fixed!)")
    else:
        print(f"  FAIL: expected n_skipped=2, got {s2.get('n_skipped')} (Bug 3 still broken)")
    if s2.get('n_success') == 0:
        print("  PASS: n_success = 0 (skip mode should not count as success)")
    else:
        print(f"  FAIL: expected n_success=0, got {s2.get('n_success')}")
    for r in s2.get('results', []):
        if r.get('error') == 'skipped-existing':
            print(f"  PASS: {r.get('key')} marked as 'skipped-existing'")

# Test 3: --clean-xml flag
print("\n" + "=" * 60)
print("TEST 3: --clean-xml (should delete .xml after success)")
print("=" * 60)
if PDF_DIR.exists():
    shutil.rmtree(PDF_DIR)
PDF_DIR.mkdir(parents=True)
result3 = run_fetch_batch("--summary-json", str(TEST_DIR / "summary3.json"), "--clean-xml")
# Check if any .xml files are left
xml_files = list(PDF_DIR.glob("*.xml"))
pdf_files = list(PDF_DIR.glob("*.pdf"))
print(f"\nAfter run with --clean-xml:")
print(f"  PDF files: {len(pdf_files)}")
print(f"  XML files: {len(xml_files)}")
if xml_files:
    print(f"  XML files present: {[f.name for f in xml_files]}")
    print(f"  FAIL: --clean-xml should have removed .xml files")
else:
    print(f"  PASS: No .xml files (clean-xml worked)")
