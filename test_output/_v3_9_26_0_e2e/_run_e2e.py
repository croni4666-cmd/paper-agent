"""Run e2e test."""
import subprocess
import sys
import os
script = r"G:\minimax - workspace\Paper agent\test_output\_v3_9_26_0_e2e\_e2e_full.py"
env = os.environ.copy()
env["PYTHONIOENCODING"] = "utf-8"
env["PYTHONUTF8"] = "1"
result = subprocess.run(
    [sys.executable, "-u", script],
    capture_output=True, text=True,
    env=env, timeout=600, cwd=r"G:\minimax - workspace\Paper agent",
)
print("STDOUT:")
print(result.stdout)
if result.stderr:
    print("STDERR (last 2000):")
    print(result.stderr[-2000:])
