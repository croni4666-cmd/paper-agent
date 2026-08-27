"""Diagnose why python -m pa_cli.cli shows fewer commands."""
import sys
import os
import subprocess

print("=== Test 1: Direct Python import ===")
result = subprocess.run(
    [sys.executable, "-c", """
import sys
sys.path.insert(0, r'G:\\minimax - workspace\\Paper agent')
from pa_cli import cli
print('cli file:', cli.__file__)
print('commands:', sorted(cli.main.list_commands(None)))
"""],
    capture_output=True, text=True, timeout=15,
    cwd=r"G:\minimax - workspace\Paper agent",
)
print("stdout:", result.stdout)
print("stderr:", result.stderr)

print("\n=== Test 2: Run as module (python -m pa_cli.cli --help) ===")
result2 = subprocess.run(
    [sys.executable, "-m", "pa_cli.cli", "--help"],
    capture_output=True, text=True, timeout=15,
    cwd=r"G:\minimax - workspace\Paper agent",
)
print("stdout first 2000:", result2.stdout[:2000])
print("stderr:", result2.stderr[:500])

print("\n=== Test 3: Run as module (python -m pa_cli.cli fetch-batch --help) ===")
result3 = subprocess.run(
    [sys.executable, "-m", "pa_cli.cli", "fetch-batch", "--help"],
    capture_output=True, text=True, timeout=15,
    cwd=r"G:\minimax - workspace\Paper agent",
)
print("stdout first 500:", result3.stdout[:500])
print("stderr:", result3.stderr[:500])
