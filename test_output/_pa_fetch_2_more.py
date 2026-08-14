# -*- coding: utf-8 -*-
"""Fetch 2 more papers with sci-hub"""
import os
import subprocess
import json

os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:10808"

CWD = r"G:\minimax - workspace\Paper agent"

DOIS = [
    "10.1007/s10238-024-01304-4",
    "10.3390/ijms252010918",
]

for doi in DOIS:
    print(f"\nFetching {doi} via sci-hub...")
    cmd = ["python", "-m", "pa_cli", "fetch", doi, "--prefer", "scihub"]
    r = subprocess.run(cmd, cwd=CWD, capture_output=True, text=True, encoding="utf-8", timeout=180)
    if r.returncode == 0:
        try:
            data = json.loads(r.stdout)
            print(f"  ✅ {data.get('final_status')} via {data.get('via_channel')}, size: {data.get('size_bytes', 0)} bytes")
        except:
            print(f"  OK (no JSON): {r.stdout[:200]}")
    else:
        print(f"  ❌ FAILED")
        print(f"  stderr: {r.stderr[:200]}")
