"""E2E test runner."""
import subprocess
import sys
import os

code = r'''
import click, sys, json
print("click version:", click.__version__)
sys.path.insert(0, r"G:\minimax - workspace\Paper agent")
from pa_cli import cli
print("cli imported")
print("commands:", sorted(cli.main.list_commands(None)))
print("---")
from click.testing import CliRunner
runner = CliRunner()
r1 = runner.invoke(cli.main, ["fetch-batch", "--help"])
print("fetch-batch Exit:", r1.exit_code, "len:", len(r1.output))
print("Output first 500:")
print(r1.output[:500])
print("---")
r2 = runner.invoke(cli.main, ["cnki-guide", "--help"])
print("cnki-guide Exit:", r2.exit_code, "len:", len(r2.output))
print("Output first 500:")
print(r2.output[:500])
'''
script_path = r"G:\minimax - workspace\Paper agent\test_output\_v3_9_26_0_e2e\_inline_test.py"
with open(script_path, "w", encoding="utf-8") as f:
    f.write(code)

env = os.environ.copy()
env["PYTHONIOENCODING"] = "utf-8"
env["PYTHONUTF8"] = "1"
result = subprocess.run(
    [sys.executable, script_path],
    capture_output=True, text=True,
    env=env, timeout=30, cwd=r"G:\minimax - workspace\Paper agent",
)
print("STDOUT:")
print(result.stdout)
if result.stderr:
    print("STDERR:")
    print(result.stderr[:2000])
