"""Wrapper that runs the e2e test with proper Python subprocess."""
import subprocess
import sys
import os

script = r"G:\minimax - workspace\Paper agent\test_output\_v3_9_26_0_e2e\_e2e_test.py"
env = os.environ.copy()
env["PYTHONIOENCODING"] = "utf-8"
env["PYTHONUTF8"] = "1"
result = subprocess.run(
    [sys.executable, "-u", script],
    capture_output=True, text=True, cwd=r"G:\minimax - workspace\Paper agent",
    env=env, timeout=600,
)
print("STDOUT:")
print(result.stdout)
if result.stderr:
    print("STDERR:")
    print(result.stderr[-2000:])
