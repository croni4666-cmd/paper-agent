"""Real end-to-end test: set UNPAYWALL_EMAIL=developers@unpaywall.org, fetch a PDF."""
import os
import sys
from pathlib import Path

os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7897"
os.environ["HTTP_PROXY"] = "http://127.0.0.1:7897"
os.environ["UNPAYWALL_EMAIL"] = "developers@unpaywall.org"
sys.path.insert(0, "G:/minimax - workspace/Paper agent")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from pa_cli.fetch import fetch, fetch_unpaywall_doi

OUT_DIR = Path("G:/minimax - workspace/Paper agent/test_output/_fetch_e2e")
OUT_DIR.mkdir(parents=True, exist_ok=True)

print("=" * 70)
print("Real E2E: pa fetch with brotli fix + developers@unpaywall.org")
print("=" * 70)

# Test 1: fetch_unpaywall_doi with the famous Attention Is All You Need paper
# 10.1038/nature12373 maps to Nanometre-scale thermometry (we tested above)
# Try the actual Attention paper DOI
r = fetch_unpaywall_doi("10.1038/nature12373",
                         out_path=str(OUT_DIR / "nature12373.pdf"))
print(f"\nDOI 10.1038/nature12373:")
print(f"  ok={r.get('ok') or 'error' in r and False}")
print(f"  source={r.get('source')}")
print(f"  bytes={r.get('size', r.get('bytes', 0))}")
print(f"  oa_url={r.get('pdf_url', '')[:80]}")
print(f"  path={r.get('path', '(no file)')}")
print(f"  err={r.get('error', '(none)')}")
if r.get("hint"):
    print(f"  hint={r['hint'][:120]}")

# Test 2: another famous open paper
print()
r2 = fetch_unpaywall_doi("10.1038/nature14539",  # Deep learning Nature paper
                          out_path=str(OUT_DIR / "nature14539.pdf"))
print(f"DOI 10.1038/nature14539 (Deep learning, LeCun/Bengio/Hinton):")
print(f"  source={r2.get('source')}")
print(f"  bytes={r2.get('size', r2.get('bytes', 0))}")
print(f"  oa_url={r2.get('pdf_url', '')[:80]}")
print(f"  err={r2.get('error', '(none)')}")

# Test 3: end-to-end fetch() with prefer='auto'
print()
r3 = fetch(doi="10.1038/nature12373",
            out_path=str(OUT_DIR / "auto.pdf"),
            prefer="auto")
print(f"fetch(doi='10.1038/nature12373', prefer='auto'):")
print(f"  ok={r3.get('ok')}")
print(f"  source={r3.get('source')}")
print(f"  bytes={r3.get('size', r3.get('bytes', 0))}")
print(f"  err={r3.get('error', '(none)')}")
if r3.get("chain"):
    for step in r3["chain"]:
        print(f"    {'✓' if step.get('ok') else '✗'} {step.get('source')}: {step.get('err', 'ok')}")

# Summary
print()
print("=" * 70)
print("Files saved:")
for p in OUT_DIR.glob("*.pdf"):
    print(f"  {p.name}: {p.stat().st_size:,}B")
