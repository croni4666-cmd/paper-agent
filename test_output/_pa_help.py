# -*- coding: utf-8 -*-
"""Get pa search --help"""
import os
import subprocess

os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:10808"

cmd = ["python", "-m", "pa_cli", "search", "--help"]
r = subprocess.run(cmd, cwd=r"G:\minimax - workspace\Paper agent",
                   capture_output=True, text=True, encoding="utf-8", timeout=60)
print("STDOUT:", r.stdout)
print("STDERR:", r.stderr)
