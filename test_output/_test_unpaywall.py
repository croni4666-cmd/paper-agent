"""pa fetch v3.9.8.1 + Unpaywall smoke test"""
import sys, os
sys.path.insert(0, r'G:\minimax - workspace\Paper agent')
os.environ["UNPAYWALL_EMAIL"] = "paper-agent-test@mavis.local"
from pa_cli.fetch import fetch, fetch_unpaywall_doi, fetch_scihub_doi

# 1. 已知 OA paper (BERT 2018)
print("=== Test 1: BERT (10.48550/arxiv.1810.04805, definitely OA) ===")
r = fetch_unpaywall_doi("10.48550/arxiv.1810.04805")
if "error" in r:
    print(f"  ERR: {r['error']} - {r.get('message', '')[:100]}")
else:
    print(f"  OK! source={r.get('source')}  size={r.get('size')}  oa_status={r.get('oa_status')}")
    if r.get("path"):
        import os as _os
        print(f"  saved: {r['path']}  size={_os.path.getsize(r['path'])} bytes")

# 2. ROADMAP 2024-2024 中常见的 1 个
print("\n=== Test 2: Through unified fetch() ===")
r = fetch(doi="10.48550/arxiv.1810.04805", out_path="G:/minimax - workspace/Paper agent/test_output/_bert.pdf")
if "error" in r:
    print(f"  ERR: {r['error']} - {r.get('message', '')[:150]}")
    print(f"  hint: {r.get('hint', '')}")
else:
    print(f"  OK! source={r.get('source')}  size={r.get('size')}")
    print(f"  path: {r.get('path')}")
