"""E2E test for v3.9.26.0 fixes (size_bytes, n_skipped, --clean-xml)."""
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

PA_ROOT = Path(r"G:\minimax - workspace\Paper agent")
TEST_DIR = PA_ROOT / "test_output" / "_v3_9_26_0_e2e" / "_batch_test"
if TEST_DIR.exists():
    shutil.rmtree(TEST_DIR)
TEST_DIR.mkdir(parents=True)

# Use a small test DOI that should fetch fast from PMC
BIB_PATH = TEST_DIR / "refs.bib"
# 10.1002/hep.32805 is the Wilson disease AASLD guideline (user's actual test)
# 10.3390/ijms21239259 is copper homeostasis (user's actual test)
BIB_PATH.write_text("""@article{gromadzka2023wilson,
  author = {Gromadzka, G.},
  title = {Wilson Disease: Update on Pathophysiology and Treatment},
  journal = {Hepatology},
  year = {2023},
  doi = {10.1002/hep.32805}
}

@article{gromadzka2020copper,
  author = {Gromadzka, G.},
  title = {Copper Homeostasis and Neurodegenerative Diseases},
  journal = {Int J Mol Sci},
  year = {2020},
  doi = {10.3390/ijms21239259}
}
""", encoding="utf-8")

PDF_DIR = TEST_DIR / "pdfs"
PDF_DIR.mkdir(parents=True)

def run_fetch_batch(*extra_args, timeout=180):
    cmd = [
        sys.executable, "-m", "pa_cli.cli", "fetch-batch",
        str(BIB_PATH),
        "--out-dir", str(PDF_DIR),
        "--max-total-sec", "300",
    ] + list(extra_args)
    print(f"\n>>> Running: pa_cli.cli fetch-batch ... {' '.join(extra_args)}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(PA_ROOT))
    print(f"Exit: {result.returncode}")
    if result.stderr:
        print(f"stderr (last 500): {result.stderr[-500:]}")
    if result.stdout:
        print(f"stdout (last 300): {result.stdout[-300:]}")
    return result

# Test 1: First download
print("=" * 60)
print("TEST 1: First download (verify size_bytes > 0)")
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
    print(f"\nPer-entry:")
    for r in s1.get('results', []):
        print(f"  - key={r.get('key')!r:30s} size={r.get('size_bytes'):>10} B "
              f"success={r.get('success')} error={r.get('error')!r}")

    print(f"\n--- Bug 2 assertions (size_bytes) ---")
    if s1.get('total_size_bytes', 0) > 0:
        print(f"  PASS: total_size_bytes = {s1.get('total_size_bytes')}")
    else:
        print(f"  FAIL: total_size_bytes = 0 (Bug 2 not fixed!)")
    for r in s1.get('results', []):
        if r.get('size_bytes', 0) > 0:
            print(f"  PASS: {r.get('key')} size_bytes = {r.get('size_bytes')}")
        else:
            print(f"  FAIL: {r.get('key')} size_bytes = 0 (Bug 2)")
    print(f"\n--- Bug 3 assertions (skip counter, first run) ---")
    if s1.get('n_skipped') == 0:
        print(f"  PASS: n_skipped = 0 (correct, no skip on first run)")
    else:
        print(f"  FAIL: n_skipped = {s1.get('n_skipped')} (should be 0)")

# Test 2: Skip-existing
print("\n" + "=" * 60)
print("TEST 2: Second download with --skip-existing (verify n_skipped)")
print("=" * 60)
result2 = run_fetch_batch("--summary-json", str(TEST_DIR / "summary2.json"), "--skip-existing")

if (TEST_DIR / "summary2.json").exists():
    s2 = json.loads((TEST_DIR / "summary2.json").read_text())
    print(f"\nSummary 2:")
    print(f"  n_total: {s2.get('n_total')}")
    print(f"  n_success: {s2.get('n_success')}")
    print(f"  n_failure: {s2.get('n_failure')}")
    print(f"  n_skipped: {s2.get('n_skipped')}")

    print(f"\n--- Bug 3 assertions (skip counter, second run) ---")
    if s2.get('n_skipped') == 2:
        print(f"  PASS: n_skipped = 2 (Bug 3 FIXED!)")
    else:
        print(f"  FAIL: n_skipped = {s2.get('n_skipped')} (expected 2, Bug 3 still broken)")
    if s2.get('n_success') == 0:
        print(f"  PASS: n_success = 0 (skip should not count as success)")
    else:
        print(f"  FAIL: n_success = {s2.get('n_success')} (should be 0)")
    for r in s2.get('results', []):
        if r.get('error') == 'skipped-existing':
            print(f"  PASS: {r.get('key')} marked 'skipped-existing'")

# Test 3: --clean-xml
print("\n" + "=" * 60)
print("TEST 3: --clean-xml (should remove .xml after success)")
print("=" * 60)
if PDF_DIR.exists():
    shutil.rmtree(PDF_DIR)
PDF_DIR.mkdir(parents=True)
result3 = run_fetch_batch("--summary-json", str(TEST_DIR / "summary3.json"), "--clean-xml")

# Check files
xml_files = list(PDF_DIR.glob("*.xml"))
pdf_files = list(PDF_DIR.glob("*.pdf"))
print(f"\nAfter --clean-xml run:")
print(f"  PDF files: {len(pdf_files)} -> {[f.name for f in pdf_files]}")
print(f"  XML files: {len(xml_files)} -> {[f.name for f in xml_files]}")
if not xml_files:
    print(f"  PASS: --clean-xml removed all .xml files")
else:
    print(f"  FAIL: --clean-xml left {len(xml_files)} .xml files")
