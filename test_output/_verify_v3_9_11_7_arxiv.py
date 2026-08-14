"""Verify v3.9.11.7: 2nd arXiv input form, --prefer auto, post-commit.

Note: pa_cli.fetch.fetch() returns the INNER result shape (source/size/arxiv_id
for arxiv channel). The CLI wrapper in pa_cli.cli adds via_channel/size_bytes/
final_status fields. So we check the inner shape here.
"""
import sys
from pathlib import Path
# When run as `python test_output/_verify_v3_9_11_7_arxiv.py`, sys.path[0]
# is the test_output/ dir, not the project root. Add project root so
# `from pa_cli.fetch import fetch` resolves.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pa_cli.fetch import fetch, _extract_arxiv_id  # noqa: E402

cases = [
    ("arxiv:1706.03762", "Attention Is All You Need (arxiv: prefix form)"),
    ("10.48550/arXiv.2310.06825", "arXiv DOI form (re-test)"),
    ("2310.06825", "arXiv bare ID form"),
    ("https://arxiv.org/abs/1706.03762v7", "arXiv URL tail form"),
]

print("=" * 70)
print("v3.9.11.7 post-commit verify: fetch_doi arxiv routing")
print("=" * 70)
print()
print("--- arxiv ID extraction (no network) ---")
for inp, _label in cases:
    aid = _extract_arxiv_id(inp)
    print(f"  _extract_arxiv_id({inp!r:50}) = {aid!r}")

print()
print("--- network fetch (prefer=auto) ---")

results = []
for inp, label in cases:
    print(f"\n--- {label} ---")
    print(f"input: {inp!r}")
    try:
        r = fetch(inp, prefer="auto")
        # Inner result: keys = source, arxiv_id, pdf_url, size
        source = r.get("source", "?")
        arxiv_id = r.get("arxiv_id", "?")
        pdf_url = r.get("pdf_url", "?")
        size = r.get("size", 0)
        print(f"  source:    {source!r}")
        print(f"  arxiv_id:  {arxiv_id!r}")
        print(f"  pdf_url:   {pdf_url!r}")
        print(f"  size:      {size:,}")
        results.append((inp, source, size, arxiv_id))
    except Exception as e:
        print(f"  EXCEPTION: {type(e).__name__}: {e}")
        results.append((inp, "EXCEPTION", 0, ""))

print()
print("=" * 70)
print("Summary")
print("=" * 70)
ok = sum(1 for r in results if r[1] == "arxiv" and r[2] > 0)
print(f"  arxiv-routed + non-zero size: {ok}/{len(results)}")
for inp, source, size, arxiv_id in results:
    flag = "OK" if (source == "arxiv" and size > 0) else "FAIL"
    print(f"  [{flag}] {inp!r:50}  source={source!r:12}  size={size:>10,}  arxiv_id={arxiv_id!r}")

sys.exit(0 if ok == len(results) else 1)
