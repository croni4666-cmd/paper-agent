# -*- coding: utf-8 -*-
"""Fetch a single paper to see if pa fetch returns abstract"""
import os
import subprocess

os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:10808"

CWD = r"G:\minimax - workspace\Paper agent"

# Try fetching the 2026 Lactobacillus paper (most relevant)
DOI = "10.3389/fimmu.2026.1905146"
print(f"Fetching {DOI}...")

# Just try a DOI lookup (no full PDF download, just metadata)
cmd = ["python", "-m", "pa_cli", "fetch", DOI, "--prefer", "auto"]
r = subprocess.run(cmd, cwd=CWD, capture_output=True, text=True, encoding="utf-8", timeout=120)
print(f"Return: {r.returncode}")
print("STDOUT:")
print(r.stdout[:2000])
print("STDERR:")
print(r.stderr[:1000])
