"""Run all 4 cache tests and summarise."""
import os
import subprocess
import sys
from pathlib import Path

TESTS = [
    "test_cache_smoke.py",
    "test_cache_integration.py",
    "test_keys_cache.py",
    "test_pa_cache_cli.py",
]

ROOT = Path(__file__).resolve().parent.parent

# Minimal env: only essentials. Avoid leaking user vars that may
# trigger auto-install of playwright/browser.
MIN_ENV = {
    "PATH": os.environ.get("PATH", ""),
    "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
    "TEMP": os.environ.get("TEMP", ""),
    "TMP": os.environ.get("TMP", ""),
    "USERPROFILE": os.environ.get("USERPROFILE", ""),
    "HOME": os.environ.get("HOME", ""),
    "PYTHONIOENCODING": "utf-8",
    "PYTHONUTF8": "1",
}

for t in TESTS:
    script = ROOT / "test_output" / t
    r = subprocess.run([sys.executable, str(script)], capture_output=True,
                       text=True, encoding="utf-8", env=MIN_ENV, cwd=str(ROOT),
                       stdin=subprocess.DEVNULL, timeout=15)
    markers = [l for l in r.stdout.splitlines()
               if "PASS" in l or "TESTS PASSED" in l or "=== ALL" in l]
    fail_markers = [l for l in r.stdout.splitlines() if "FAIL" in l or "Error" in l.lower()][:2]
    last_marker = markers[-1] if markers else "NONE"
    status = "PASS" if r.returncode == 0 and any("ALL" in m or "PASS" in m for m in markers) else "FAIL"
    print(f"  {t}: exit={r.returncode} status={status} last_marker={last_marker!r} fail_markers={fail_markers}")
