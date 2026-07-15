"""E2E test: fetch_cnki_detail with freshly exported cookies (only 2 cookies)."""
import os
import sys
from pathlib import Path

# Force proxy OFF — xueshu789 needs user's real IP (NOT clash)
for v in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
    os.environ.pop(v, None)

sys.path.insert(0, "G:/minimax - workspace/Paper agent")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from pa_cli.fetch import fetch_cnki_detail
from pa_cli.cnki_channel import status_report

OUT_DIR = Path("G:/minimax - workspace/Paper agent/test_output/_fetch_e2e_cnki")
OUT_DIR.mkdir(parents=True, exist_ok=True)

print("=" * 70)
print("STATUS (should be ready_for_search=True)")
print("=" * 70)
st = status_report()
print(f"  cookies_fresh:      {st['cookies_fresh']}")
print(f"  n_cookies:          {st['n_cookies']}")
print(f"  ready_for_search:   {st['ready_for_search']}")

# Test with the most-cited paper from earlier search
TEST_DOIS = [
    "10.3969/j.issn.1003-9031.2022.04.008",  # 数字普惠金融对经济高质量发展的影响研究
    "10.16525/j.cnki.14-1362/n.2022.08.004",  # 数字普惠金融、科技创新与制造业产业结构升级
]

for i, doi in enumerate(TEST_DOIS):
    print()
    print("=" * 70)
    print(f"TEST {i+1}/{len(TEST_DOIS)}: DOI {doi}")
    print("=" * 70)
    safe = doi.replace("/", "_").replace(".", "_")
    out = OUT_DIR / f"{i+1}_{safe}.pdf"
    print(f"Output: {out}")
    print(f"Calling fetch_cnki_detail (this may take 15-30s due to bootstrap + search + detail)...")
    r = fetch_cnki_detail(doi, out_path=str(out))
    if "error" in r:
        print(f"  X {r['error']}: {r.get('message','')[:200]}")
        if r.get("hint"):
            print(f"    hint: {r['hint'][:150]}")
    else:
        size = r.get("size", 0)
        print(f"  [OK] source={r.get('source')} | size={size:,}B")
        print(f"    saved: {r.get('path')}")
        print(f"    pdf_url: {r.get('pdf_url','')[:80]}")

print()
print("=" * 70)
print("SUMMARY")
print("=" * 70)
files = list(OUT_DIR.glob("*.pdf"))
print(f"PDFs on disk: {len(files)}")
for p in sorted(files):
    print(f"  {p.name}: {p.stat().st_size:,}B")
