import sys
sys.path.insert(0, r"G:\minimax - workspace\Paper agent\.agents\skills\paper-agent\scripts")
import subprocess
from pathlib import Path

PYTHON = sys.executable
PA_ROOT = Path(r"G:\minimax - workspace\Paper agent")
cmd = [PYTHON, "-m", "pa_cli.cli", "search", "BERT", "--engine", "semanticscholar", "--limit", "2", "--quiet"]
result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=str(PA_ROOT))
print("RETURNCODE:", result.returncode, file=sys.stderr)
print("STDOUT len:", len(result.stdout), file=sys.stderr)
print("STDERR len:", len(result.stderr), file=sys.stderr)
print("STDOUT first 200:", repr(result.stdout[:200]), file=sys.stderr)
print("STDERR first 200:", repr(result.stderr[:200]), file=sys.stderr)
sys.stdout.write(result.stdout)
