"""End-to-end test of pa fetch fallback chain (v3.9.8.1+).
Goal: verify sci-hub + annas-archive paths actually work, not just Unpaywall.
"""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, "G:/minimax - workspace/Paper agent")

from pa_cli.fetch import (
    status_report,
    fetch_unpaywall_doi,
    fetch_scihub_doi,
    fetch_annas_search,
    fetch_annas_md5,
    fetch,
    SCIHUB_MIRRORS,
    ANNAS_DOMAINS,
)

OUT_DIR = Path("G:/minimax - workspace/Paper agent/test_output/_fetch_e2e")
OUT_DIR.mkdir(parents=True, exist_ok=True)

print("=" * 70)
print("STEP 1: Health check (status_report)")
print("=" * 70)
h = status_report()
print(f"scihub: {h['scihub']}")
print(f"annas:  {h['annas']}")

print()
print("=" * 70)
print("STEP 2: Unpaywall (known working baseline)")
print("=" * 70)
r = fetch_unpaywall_doi("10.1038/nature12373", out_path=str(OUT_DIR / "unpaywall_nature12373.pdf"))
print(f"  ok={r.get('ok')} | source={r.get('source')} | bytes={r.get('bytes', 0)} | "
      f"url={r.get('oa_url', '?')[:80] if r.get('oa_url') else '?'} | err={r.get('error')}")

print()
print("=" * 70)
print("STEP 3: sci-hub (each mirror) — DOI 10.1038/nature12373")
print("=" * 70)
for m in SCIHUB_MIRRORS:
    t0 = time.time()
    try:
        # fetch_scihub_doi loops all mirrors; let's just hit one URL directly to see
        from pa_cli.fetch import _http_get_bytes, COMMON_HEADERS
        url = f"{m}/10.1038/nature12373"
        s, body = _http_get_bytes(url, timeout=15)
        dt = time.time() - t0
        # Sample: show first 200 bytes to detect hijack
        sample = body[:200].decode("utf-8", errors="ignore").replace("\n", " ")[:160]
        is_hijack = ("Mirror" in sample or "mirror" in sample or "选择" in sample
                     or "Telegram" in sample or "navigation" in sample.lower())
        marker = " ⚠️ HIJACK" if is_hijack else (" ✓ PDF" if body[:4] == b"%PDF" else "")
        print(f"  {m:30} HTTP {s:3} t={dt:5.1f}s | {len(body):8d}B | {sample[:80]}{marker}")
    except Exception as e:
        dt = time.time() - t0
        print(f"  {m:30} ERR  t={dt:5.1f}s | {str(e)[:80]}")

print()
print("=" * 70)
print("STEP 4: fetch_scihub_doi() — full function with all mirrors")
print("=" * 70)
r = fetch_scihub_doi("10.1038/nature12373", out_path=str(OUT_DIR / "scihub_nature12373.pdf"))
print(f"  ok={r.get('ok')} | source={r.get('source')} | bytes={r.get('bytes', 0)} | "
      f"err={r.get('error')}")
if r.get("tried_mirrors"):
    print(f"  tried mirrors: {r['tried_mirrors']}")

print()
print("=" * 70)
print("STEP 5: annas-archive search (real query)")
print("=" * 70)
r = fetch_annas_search("attention is all you need", limit=5)
print(f"  ok={r.get('ok')} | n={r.get('n', 0)} | err={r.get('error')}")
for it in r.get("results", [])[:3]:
    print(f"  - {it.get('title','')[:60]} | md5={it.get('md5','')[:16]} | size={it.get('size','')}")

print()
print("=" * 70)
print("STEP 6: annas-archive MD5 path (real MD5 from step 5)")
print("=" * 70)
if r.get("results") and r["results"][0].get("md5"):
    md5 = r["results"][0]["md5"]
    print(f"  trying md5={md5}")
    r2 = fetch_annas_md5(md5, out_path=str(OUT_DIR / f"annas_{md5[:8]}.pdf"))
    print(f"  ok={r2.get('ok')} | bytes={r2.get('bytes', 0)} | err={r2.get('error')}")
    if r2.get("redirect_url"):
        print(f"  redirect_url: {r2['redirect_url'][:120]}")
else:
    print("  (skip — no md5 from step 5)")

print()
print("=" * 70)
print("STEP 7: fetch() end-to-end, prefer='auto' (Unpaywall → sci-hub → annas)")
print("=" * 70)
r = fetch(doi="10.1038/nature12373", out_path=str(OUT_DIR / "auto_nature12373.pdf"),
          prefer="auto")
print(f"  ok={r.get('ok')} | source={r.get('source')} | bytes={r.get('bytes', 0)} | "
      f"err={r.get('error')}")
if r.get("chain"):
    for step in r["chain"]:
        ok = "✓" if step.get("ok") else "✗"
        print(f"  {ok} {step.get('source'):12} | {step.get('err','ok')}")

print()
print("=" * 70)
print("STEP 8: fetch() with title fallback (Unpaywall will miss → try sci-hub search)")
print("=" * 70)
# Use a paper title; Unpaywall needs DOI so it will fail
r = fetch(title="Attention Is All You Need",
          out_path=str(OUT_DIR / "auto_attention.pdf"), prefer="auto")
print(f"  ok={r.get('ok')} | source={r.get('source')} | bytes={r.get('bytes', 0)} | "
      f"err={r.get('error')}")
if r.get("chain"):
    for step in r["chain"]:
        ok = "✓" if step.get("ok") else "✗"
        print(f"  {ok} {step.get('source'):12} | {step.get('err','ok')}")
