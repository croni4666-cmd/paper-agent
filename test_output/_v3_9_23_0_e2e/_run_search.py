"""Debug: run search.py and capture output."""
import subprocess
import sys
from pathlib import Path

# Find search.py
script = Path(r"G:\minimax - workspace\Paper agent\.agents\skills\paper-agent\scripts\search.py")
print(f"Script exists: {script.is_file()}")
print(f"Script size: {script.stat().st_size}")

# Run search.py with --help first
result = subprocess.run(
    [sys.executable, str(script), "--help"],
    capture_output=True, text=True, timeout=15,
)
print(f"--help exit: {result.returncode}")
print(f"--help stdout len: {len(result.stdout)}")
print(f"--help stderr len: {len(result.stderr)}")
if result.stdout:
    print("stdout first 200:", result.stdout[:200])
if result.stderr:
    print("stderr first 200:", result.stderr[:200])

# Now run with real args
print("\n--- Real run ---")
result = subprocess.run(
    [sys.executable, str(script), "BERT", "--engine", "semanticscholar", "--limit", "2"],
    capture_output=True, text=True, timeout=60,
)
print(f"exit: {result.returncode}")
print(f"stdout len: {len(result.stdout)}")
print(f"stderr len: {len(result.stderr)}")
if result.stdout:
    print("stdout first 500:", result.stdout[:500])
if result.stderr:
    print("stderr first 500:", result.stderr[:500])
