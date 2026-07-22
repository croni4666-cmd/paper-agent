"""pa fetch v3.9.8.1 smoke test"""
import sys
sys.path.insert(0, r'G:\minimax - workspace\Paper agent')
from pa_cli.fetch import status_report, fetch_scihub_doi, fetch_annas_search

print("=== fetch.py import OK ===")
print()
print("=== Health check ===")
h = status_report()
for src, mirrors in h.items():
    print(f"{src}:")
    for m, status in mirrors.items():
        print(f"  {m}: {status}")
print()
print("=== Sci-Hub DOI smoke test (BERT paper) ===")
r = fetch_scihub_doi("10.48550/arxiv.1810.04805")
if "error" in r:
    print(f"Error: {r['error']}")
    print(f"  message: {r.get('message', '')[:150]}")
    print(f"  hint: {r.get('hint', '')}")
else:
    print(f"OK! size={r.get('size')} bytes, mirror={r.get('mirror')}")
    if r.get("path"):
        print(f"  saved: {r['path']}")
print()
print("=== annas-archive search smoke test ===")
results = fetch_annas_search("BERT language model", limit=3)
print(f"annas search returned {len(results)} results")
for i, r in enumerate(results[:3]):
    print(f"  [{i+1}] md5_path={r.get('md5_path')}")
