"""Direct module test for v3.9.26.0 fetch_batch fixes (no subprocess needed)."""
import json
import shutil
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

PA_ROOT = Path(r"G:\minimax - workspace\Paper agent")
sys.path.insert(0, str(PA_ROOT))

# Test 1: Verify size key is 'size_bytes' (not 'size')
print("=" * 60)
print("Test 1: Verify size key fix (was 'size', now 'size_bytes')")
print("=" * 60)
from pa_cli.fetch_batch import _fetch_one_entry, FetchResult, FetchSummary
import inspect
src = inspect.getsource(_fetch_one_entry)
# Count occurrences of the size key
old_count = src.count("r.get('size', 0)")
new_count = src.count("r.get('size_bytes', 0)")
print(f"  Old pattern 'r.get(\"size\", 0)': {old_count} occurrences (should be 0)")
print(f"  New pattern 'r.get(\"size_bytes\", 0)': {new_count} occurrences (should be 2)")
if old_count == 0 and new_count == 2:
    print("  PASS: Bug 2 fixed (size key now 'size_bytes')")
else:
    print("  FAIL: Bug 2 not properly fixed")

# Test 2: Verify skip counter logic
print()
print("=" * 60)
print("Test 2: Verify skip counter fix (n_skipped instead of n_success)")
print("=" * 60)
# Read the run_fetch_batch function
from pa_cli import fetch_batch as fb_module
src = inspect.getsource(fb_module.run_fetch_batch)
if "result.error == 'skipped-existing'" in src:
    print("  PASS: Bug 3 fixed (skipped-existing checked before n_success)")
else:
    print("  FAIL: Bug 3 not fixed")

# Test 3: Verify run_fetch_batch signature has clean_xml
print()
print("=" * 60)
print("Test 3: Verify --clean-xml option is plumbed through")
print("=" * 60)
sig = inspect.signature(fb_module.run_fetch_batch)
if "clean_xml" in sig.parameters:
    print(f"  PASS: run_fetch_batch has 'clean_xml' parameter (default={sig.parameters['clean_xml'].default})")
else:
    print("  FAIL: run_fetch_batch missing 'clean_xml' parameter")

# Test 4: Verify XML cleanup logic exists
print()
print("=" * 60)
print("Test 4: Verify XML cleanup logic")
print("=" * 60)
if "xml_path.unlink()" in src:
    print("  PASS: XML cleanup logic present (xml_path.unlink())")
else:
    print("  FAIL: XML cleanup logic missing")

# Test 5: Verify the click command is renamed to cnki-guide
print()
print("=" * 60)
print("Test 5: Verify click commands (cnki-guide + fetch-batch)")
print("=" * 60)
import click
from click.testing import CliRunner
from pa_cli.cli import main as cli_main
runner = CliRunner()

# Check that cnki-guide exists
r1 = runner.invoke(cli_main, ['cnki-guide', '--help'])
print(f"  cnki-guide --help: exit={r1.exit_code}, len={len(r1.output)}")
if r1.exit_code == 0 and 'cnki-guide' in r1.output:
    print("    PASS: cnki-guide command works")
else:
    print("    FAIL: cnki-guide not found")

# Check that fetch-batch exists
r2 = runner.invoke(cli_main, ['fetch-batch', '--help'])
print(f"  fetch-batch --help: exit={r2.exit_code}, len={len(r2.output)}")
if r2.exit_code == 0 and 'fetch-batch' in r2.output:
    print("    PASS: fetch-batch command works")
else:
    print("    FAIL: fetch-batch not found")

# Check that --clean-xml is in fetch-batch options
if '--clean-xml' in r2.output:
    print("    PASS: --clean-xml flag visible")
else:
    print("    FAIL: --clean-xml flag missing")

# Test 6: Verify old fetch_batch (underscore) command does NOT exist
r3 = runner.invoke(cli_main, ['fetch_batch', '--help'])
if r3.exit_code != 0 and 'No such command' in r3.output:
    print(f"  fetch_batch (underscore) --help: exit={r3.exit_code} (correctly fails)")
    print("    PASS: old fetch_batch command is gone")
else:
    print("    FAIL: old fetch_batch command should not exist")
