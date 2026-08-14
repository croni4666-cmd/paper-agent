"""Diagnose: does --format bibtex work for pubmed engine?"""
import subprocess
import os
import sys
import re

PROJ = r"G:\minimax - workspace\Paper agent"
os.chdir(PROJ)
env = os.environ.copy()
env["PYTHONIOENCODING"] = "utf-8"
env["PYTHONUTF8"] = "1"
env["PYTHONPATH"] = PROJ + os.pathsep + env.get("PYTHONPATH", "")

# Test A: --format bibtex with --engine pubmed
print("=" * 70)
print("A) --engine pubmed --format bibtex")
print("=" * 70)
cmd = [sys.executable, "-m", "pa_cli", "search", "hypertension treatment",
       "--engine", "pubmed", "--limit", "3", "--format", "bibtex"]
r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                   errors="replace", env=env, timeout=60)
print(f"rc={r.returncode}  stdout_len={len(r.stdout)}  stderr_len={len(r.stderr)}")
print("STDOUT (raw, first 800 chars):")
print(r.stdout[:800])
print("STDERR (raw, first 400 chars):")
print(r.stderr[:400])

# Test B: --format bibtex with --engine crossref (control)
print()
print("=" * 70)
print("B) --engine crossref --format bibtex (control)")
print("=" * 70)
cmd2 = [sys.executable, "-m", "pa_cli", "search", "hypertension treatment",
        "--engine", "crossref", "--limit", "3", "--format", "bibtex"]
r2 = subprocess.run(cmd2, capture_output=True, text=True, encoding="utf-8",
                    errors="replace", env=env, timeout=60)
print(f"rc={r2.returncode}  stdout_len={len(r2.stdout)}  stderr_len={len(r2.stderr)}")
print("STDOUT (raw, first 800 chars):")
print(r2.stdout[:800])
print("STDERR (raw, first 400 chars):")
print(r2.stderr[:400])

# Test C: --format bibtex with --engine all
print()
print("=" * 70)
print("C) --engine all --format bibtex")
print("=" * 70)
cmd3 = [sys.executable, "-m", "pa_cli", "search", "hypertension treatment",
        "--engine", "all", "--limit", "5", "--format", "bibtex"]
r3 = subprocess.run(cmd3, capture_output=True, text=True, encoding="utf-8",
                    errors="replace", env=env, timeout=120)
print(f"rc={r3.returncode}  stdout_len={len(r3.stdout)}  stderr_len={len(r3.stderr)}")
print("STDOUT (raw, first 1500 chars):")
print(r3.stdout[:1500])
print("STDERR (raw, first 400 chars):")
print(r3.stderr[:400])

# Test D: pubmed JSON to see what fields are present
print()
print("=" * 70)
print("D) --engine pubmed --format json — what fields are present?")
print("=" * 70)
cmd4 = [sys.executable, "-m", "pa_cli", "search", "hypertension treatment",
        "--engine", "pubmed", "--limit", "3", "--format", "json"]
r4 = subprocess.run(cmd4, capture_output=True, text=True, encoding="utf-8",
                    errors="replace", env=env, timeout=60)
print(f"rc={r4.returncode}  stdout_len={len(r4.stdout)}")
# find first {
s = r4.stdout.find("{")
if s >= 0:
    import json
    try:
        d = json.loads(r4.stdout[s:])
        if d.get("results"):
            p0 = d["results"][0]
            print("First paper fields:")
            for k, v in p0.items():
                vs = str(v)[:80]
                print(f"  {k:20s} = {vs!r}")
    except Exception as e:
        print(f"  parse err: {e}")
