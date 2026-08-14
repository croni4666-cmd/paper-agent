# -*- coding: utf-8 -*-
"""Fetch 4 more key papers in parallel"""
import os
import subprocess
import json
import time

os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:10808"

CWD = r"G:\minimax - workspace\Paper agent"

DOIS = [
    "10.3389/fmicb.2025.1661211",       # Gut microbiota hypothyroidism 2025
    "10.1007/s10238-024-01304-4",       # Intestinal microbiota gut-thyroid 2024
    "10.3390/ijms252010918",             # Unveiling Role of Gut Microbiota in AITD 2024
    "10.3389/fcimb.2024.1465928",        # Recent advances gut microbiota thyroid 2024
]

results = {}
for doi in DOIS:
    print(f"\nFetching {doi}...")
    cmd = ["python", "-m", "pa_cli", "fetch", doi, "--prefer", "auto"]
    r = subprocess.run(cmd, cwd=CWD, capture_output=True, text=True, encoding="utf-8", timeout=180)
    if r.returncode == 0:
        try:
            data = json.loads(r.stdout)
            results[doi] = data
            print(f"  ✅ {data.get('final_status')} via {data.get('via_channel')}, size: {data.get('size_bytes', 0)} bytes")
        except:
            results[doi] = {"raw": r.stdout[:500]}
    else:
        results[doi] = {"error": r.stderr[:200]}
        print(f"  ❌ {r.stderr[:200]}")

with open(r"G:\minimax - workspace\Paper agent\test_output\probiotics_fetch_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"\nDone. Saved to probiotics_fetch_results.json")
