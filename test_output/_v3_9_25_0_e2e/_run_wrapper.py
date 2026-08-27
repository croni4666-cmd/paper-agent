import subprocess
import sys
import os
script = r"G:\minimax - workspace\Paper agent\test_output\_v3_9_25_0_e2e\test_search_nospc.py"
env = os.environ.copy()
env["PYTHONIOENCODING"] = "utf-8"
env["PYTHONUTF8"] = "1"
env["PYTHONPATH"] = r"G:\minimax - workspace\Paper agent"
result = subprocess.run([sys.executable, "-u", script], capture_output=True, text=True, cwd=r"G:\minimax - workspace\Paper agent", env=env, timeout=180)
print("STDOUT:")
print(result.stdout)
print("STDERR (last 500):")
print(result.stderr[-500:])
