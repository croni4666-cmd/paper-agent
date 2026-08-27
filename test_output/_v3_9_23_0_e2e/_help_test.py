"""Test all 8 wrappers' --help after refactor."""
import subprocess
import sys
from pathlib import Path

SKILL_SCRIPTS = Path(r"G:\minimax - workspace\Paper agent\.agents\skills\paper-agent\scripts")
WRAPPERS = ["search.py", "fetch.py", "fetch_batch.py", "review.py",
            "citations.py", "keys.py", "cache.py", "version.py"]

for w in WRAPPERS:
    script = SKILL_SCRIPTS / w
    r = subprocess.run(
        [sys.executable, str(script), "--help"],
        capture_output=True, text=True, timeout=15,
    )
    status = "OK" if r.returncode == 0 else f"FAIL({r.returncode})"
    print(f"  {w}: {status} (stdout={len(r.stdout)}B, stderr={len(r.stderr)}B)")

# Also test version.py (no args, returns JSON)
print("\n=== version.py real run ===")
r = subprocess.run(
    [sys.executable, str(SKILL_SCRIPTS / "version.py")],
    capture_output=True, text=True, timeout=15,
)
print(f"exit: {r.returncode}, stdout: {len(r.stdout)}B")
if r.stdout:
    print(r.stdout[:300])
