"""Test AMiner search by DOI string for Chinese papers."""
import os
import sys
import json

os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7897"
os.environ["HTTP_PROXY"] = "http://127.0.0.1:7897"
sys.path.insert(0, "G:/minimax - workspace/Paper agent")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, "G:/minimax - workspace/Paper agent/pa_cli")
from aminer_channel import search_aminer

dois = [
    "10.3969/j.issn.1003-9031.2022.04.008",
    "10.16525/j.cnki.14-1362/n.2022.08.004",
    "10.15884/j.cnki.issn.1007-0672.2022.04.002",
    "数字普惠金融 家庭消费",  # title as control
]

for q in dois:
    print(f"\n--- {q[:50]} ---")
    try:
        results = search_aminer(q, limit=3)
        print(f"  n={len(results)}")
        for r in results[:2]:
            print(f"  - {r.get('title','')[:60]}")
            print(f"    doi={r.get('doi','?')[:60]} | year={r.get('year','?')}")
    except Exception as e:
        print(f"  ERR: {e}")
