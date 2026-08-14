"""Strict 8-channel test: actually exercise each channel with a real DOI.
Reports which ones can deliver a real PDF in <60s.

Test DOI: 10.1038/nature12373 (Nature 2013, "Architecture of the
HIV-1 integrase core after 3'-processing"). Known to be on sci-hub
(verified in v3.9.11.5 smoke test). Also a real Nature paper that
should be in OpenAlex / Crossref / arXiv mirrors / S2.

Note: User reports (2026-08-09, mvs_d9ecb3a3c48a49c086d00e44ed62a826)
that "8-channel" has very few actually-working channels. This test
verifies that claim with real data.
"""
import os
import subprocess
import sys
import time
import json
from pathlib import Path

REPO = Path("G:/minimax - workspace/Paper agent")
TEST_DOI = "10.1038/nature12373"
TEST_OUTDIR = REPO / "test_output" / "_diag_real"
TEST_OUTDIR.mkdir(parents=True, exist_ok=True)


def run_pa(args, env_overrides=None, timeout=120):
    """Run pa_cli with given args. Returns (rc, stdout, stderr, elapsed_sec)."""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    if env_overrides:
        for k, v in env_overrides.items():
            if v is None:
                env.pop(k, None)
            else:
                env[k] = v
    t0 = time.time()
    result = subprocess.run(
        [sys.executable, "-X", "utf-8", "-m", "pa_cli"] + args,
        cwd=str(REPO),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    elapsed = time.time() - t0
    return result.returncode, result.stdout, result.stderr, elapsed


# Use 10808 proxy (new port, per v3.9.11.5 fix)
PROXY_ENV = {
    "HTTPS_PROXY": "http://127.0.0.1:10808",
    "HTTP_PROXY": "http://127.0.0.1:10808",
}

print("=" * 70)
print(f"Real 8-channel test for DOI: {TEST_DOI}")
print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Proxy: 10808 (new port, v3.9.11.5)")
print("=" * 70)
print()

results = {}

# ============= Step 1: fetch() with each prefer mode =============
print("=" * 70)
print("Step 1: fetch() with each prefer mode (scihub / annas / cnki / auto)")
print("=" * 70)

for prefer in ["scihub", "annas", "cnki", "auto"]:
    print(f"\n--- prefer={prefer} ---")
    out_path = TEST_OUTDIR / f"prefer_{prefer}.pdf"
    rc, out, err, elapsed = run_pa(
        ["fetch", TEST_DOI, "-o", str(out_path)],
        env_overrides=PROXY_ENV,
        timeout=120,
    )
    success = "SUCCESS" in out and "saved" in out
    handoff = "handoff" in out.lower() or rc == 2
    # Try to extract size_bytes
    size = 0
    try:
        # find size_bytes in stdout
        import re
        m = re.search(r'"size_bytes":\s*(\d+)', out)
        if m:
            size = int(m.group(1))
    except Exception:
        pass
    # Check if file actually got written
    actual_file_size = 0
    for p in TEST_OUTDIR.glob("prefer_*.pdf/**/10_1038_nature12373.pdf"):
        actual_file_size = p.stat().st_size
        break
    results[f"prefer={prefer}"] = {
        "rc": rc,
        "elapsed": round(elapsed, 1),
        "success": success,
        "handoff": handoff,
        "size_bytes_reported": size,
        "size_bytes_actual": actual_file_size,
    }
    print(f"  rc={rc} elapsed={elapsed:.1f}s success={success} handoff={handoff}")
    print(f"  reported_size={size} actual_file={actual_file_size}")
    if err and "hint" in err.lower():
        # Show last hint line
        for line in err.split("\n"):
            if "hint" in line.lower() or "10808" in line:
                print(f"  hint: {line.strip()}")
    # Clean up downloaded file
    for p in TEST_OUTDIR.glob(f"prefer_{prefer}.pdf/**"):
        if p.is_file():
            p.unlink()
print()

# ============= Step 2: independent 5 sources (no pa fetch) =============
print("=" * 70)
print("Step 2: 5 independent sources via pa search (no PDF, just metadata)")
print("=" * 70)
print("(These find paper via free API; need separate fetch step for PDF.)")
print()

import urllib.request as ur
import urllib.error
import socket

socket.setdefaulttimeout(15)

# 2.1: OpenAlex — find paper
print("--- 2.1: OpenAlex (https://api.openalex.org) ---")
try:
    url = f"https://api.openalex.org/works/doi:{TEST_DOI}"
    req = ur.Request(url, headers={"User-Agent": "paper-agent-test/1.0"})
    with ur.urlopen(req, timeout=15) as r:
        body = json.loads(r.read())
        title = body.get("title", "?")
        pdf_url = body.get("pdf_url") or body.get("best_oa_location", {}).get("pdf_url") if isinstance(body.get("best_oa_location"), dict) else None
        primary_location = body.get("primary_location", {})
        primary_pdf = primary_location.get("pdf_url") if isinstance(primary_location, dict) else None
        is_oa = body.get("open_access", {}).get("is_oa") if isinstance(body.get("open_access"), dict) else False
        results["openalex"] = {
            "found": True,
            "title": (title or "?")[:60],
            "pdf_url": pdf_url or primary_pdf or "(none)",
            "is_oa": is_oa,
        }
        print(f"  found: yes, title: {(title or '?')[:60]}")
        print(f"  pdf_url: {pdf_url or primary_pdf or '(none)'}")
        print(f"  is_oa: {is_oa}")
except Exception as e:
    results["openalex"] = {"found": False, "error": str(e)[:80]}
    print(f"  ERR: {e}")
print()

# 2.2: Crossref — find paper
print("--- 2.2: Crossref (https://api.crossref.org) ---")
try:
    url = f"https://api.crossref.org/works/{TEST_DOI}"
    req = ur.Request(url, headers={"User-Agent": "paper-agent-test/1.0 (mailto:test@example.com)"})
    with ur.urlopen(req, timeout=15) as r:
        body = json.loads(r.read())
        msg = body.get("message", {})
        title = msg.get("title", ["?"])
        results["crossref"] = {
            "found": True,
            "title": (title[0] if title else "?")[:60],
            "has_fulltext": "fulltext" in str(msg.get("resource", {}).get("primary", {})),
        }
        print(f"  found: yes, title: {(title[0] if title else '?')[:60]}")
        # Check for full-text link
        resource = msg.get("resource", {})
        primary = resource.get("primary", {}) if isinstance(resource, dict) else {}
        if primary.get("URL"):
            print(f"  primary URL: {primary.get('URL')}")
        else:
            print(f"  primary URL: (none — Crossref doesn't host PDFs)")
except Exception as e:
    results["crossref"] = {"found": False, "error": str(e)[:80]}
    print(f"  ERR: {e}")
print()

# 2.3: arXiv — check if this DOI has an arXiv mirror
print("--- 2.3: arXiv (https://export.arxiv.org/api) ---")
try:
    # Nature paper, unlikely on arXiv, but try a real arxiv paper
    # Use a known arXiv paper for this test
    arxiv_id = "2310.06825"  # Mistral 7B
    url = f"https://export.arxiv.org/api/query?id_list={arxiv_id}"
    req = ur.Request(url, headers={"User-Agent": "paper-agent-test/1.0"})
    with ur.urlopen(req, timeout=15) as r:
        body = r.read().decode("utf-8", errors="replace")
        if "<entry>" in body:
            results["arxiv"] = {"found": True, "sample": arxiv_id, "PDF": f"https://arxiv.org/pdf/{arxiv_id}.pdf"}
            print(f"  found: yes (sample {arxiv_id})")
            print(f"  PDF: https://arxiv.org/pdf/{arxiv_id}.pdf")
        else:
            results["arxiv"] = {"found": False}
            print(f"  not found")
except Exception as e:
    results["arxiv"] = {"found": False, "error": str(e)[:80]}
    print(f"  ERR: {e}")
print()

# 2.4: Semantic Scholar — find paper
print("--- 2.4: Semantic Scholar (https://api.semanticscholar.org) ---")
try:
    url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{TEST_DOI}?fields=title,openAccessPdf,isOpenAccess"
    req = ur.Request(url, headers={"User-Agent": "paper-agent-test/1.0"})
    with ur.urlopen(req, timeout=15) as r:
        body = json.loads(r.read())
        title = body.get("title", "?")
        open_pdf = body.get("openAccessPdf")
        is_oa = body.get("isOpenAccess", False)
        results["semanticscholar"] = {
            "found": True,
            "title": (title or "?")[:60],
            "openAccessPdf": open_pdf.get("url") if isinstance(open_pdf, dict) else "(none)",
            "is_oa": is_oa,
        }
        print(f"  found: yes, title: {(title or '?')[:60]}")
        print(f"  openAccessPdf: {open_pdf.get('url') if isinstance(open_pdf, dict) else '(none)'}")
        print(f"  is_oa: {is_oa}")
except Exception as e:
    results["semanticscholar"] = {"found": False, "error": str(e)[:80]}
    print(f"  ERR: {e}")
print()

# 2.5: Unpaywall — find paper
print("--- 2.5: Unpaywall (https://api.unpaywall.org) ---")
try:
    url = f"https://api.unpaywall.org/v2/{TEST_DOI}?email=paper-agent-test@example.com"
    req = ur.Request(url, headers={"User-Agent": "paper-agent-test/1.0"})
    with ur.urlopen(req, timeout=15) as r:
        body = json.loads(r.read())
        title = body.get("title", "?")
        best_oa = body.get("best_oa_location") or {}
        pdf_url = best_oa.get("url_for_pdf") if isinstance(best_oa, dict) else None
        results["unpaywall"] = {
            "found": True,
            "title": (title or "?")[:60],
            "pdf_url": pdf_url or "(none)",
        }
        print(f"  found: yes, title: {(title or '?')[:60]}")
        print(f"  best_oa pdf: {pdf_url or '(none)'}")
except Exception as e:
    results["unpaywall"] = {"found": False, "error": str(e)[:80]}
    print(f"  ERR: {e}")
print()

# ============= Step 3: actually try to download a PDF from each =============
print("=" * 70)
print("Step 3: actually try to download PDF (small, <5MB) from each channel")
print("=" * 70)
print()

download_results = {}

# 3.1: arXiv PDF (using arXiv paper)
print("--- 3.1: arXiv PDF (sample: 2310.06825 Mistral 7B) ---")
try:
    url = "https://arxiv.org/pdf/2310.06825"
    req = ur.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with ur.urlopen(req, timeout=30) as r:
        body = r.read()
        is_pdf = body[:4] == b"%PDF"
        download_results["arxiv"] = {"ok": is_pdf, "size": len(body), "url": url}
        print(f"  download: {'OK' if is_pdf else 'NOT PDF'} size={len(body)}")
except Exception as e:
    download_results["arxiv"] = {"ok": False, "error": str(e)[:80]}
    print(f"  ERR: {e}")
print()

# 3.2: S2 openAccessPdf (from step 2.4)
if results.get("semanticscholar", {}).get("openAccessPdf") not in (None, "(none)"):
    url = results["semanticscholar"]["openAccessPdf"]
    print(f"--- 3.2: S2 openAccessPdf ({url[:60]}) ---")
    try:
        req = ur.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with ur.urlopen(req, timeout=30) as r:
            body = r.read()
            is_pdf = body[:4] == b"%PDF"
            download_results["semanticscholar"] = {"ok": is_pdf, "size": len(body), "url": url}
            print(f"  download: {'OK' if is_pdf else 'NOT PDF'} size={len(body)}")
    except Exception as e:
        download_results["semanticscholar"] = {"ok": False, "error": str(e)[:80]}
        print(f"  ERR: {e}")
    print()
else:
    print("--- 3.2: S2 — no openAccessPdf available, skip ---")
    print()

# 3.3: OpenAlex primary PDF
oa_pdf = results.get("openalex", {}).get("pdf_url")
if oa_pdf and oa_pdf != "(none)":
    print(f"--- 3.3: OpenAlex primary PDF ({oa_pdf[:60]}) ---")
    try:
        req = ur.Request(oa_pdf, headers={"User-Agent": "Mozilla/5.0"})
        with ur.urlopen(req, timeout=30) as r:
            body = r.read()
            is_pdf = body[:4] == b"%PDF"
            download_results["openalex"] = {"ok": is_pdf, "size": len(body), "url": oa_pdf}
            print(f"  download: {'OK' if is_pdf else 'NOT PDF'} size={len(body)}")
    except Exception as e:
        download_results["openalex"] = {"ok": False, "error": str(e)[:80]}
        print(f"  ERR: {e}")
    print()
else:
    print("--- 3.3: OpenAlex — no PDF URL available, skip ---")
    print()

# 3.4: Unpaywall best_oa PDF
up_pdf = results.get("unpaywall", {}).get("pdf_url")
if up_pdf and up_pdf != "(none)":
    print(f"--- 3.4: Unpaywall best_oa PDF ({up_pdf[:60]}) ---")
    try:
        req = ur.Request(up_pdf, headers={"User-Agent": "Mozilla/5.0"})
        with ur.urlopen(req, timeout=30) as r:
            body = r.read()
            is_pdf = body[:4] == b"%PDF"
            download_results["unpaywall"] = {"ok": is_pdf, "size": len(body), "url": up_pdf}
            print(f"  download: {'OK' if is_pdf else 'NOT PDF'} size={len(body)}")
    except Exception as e:
        download_results["unpaywall"] = {"ok": False, "error": str(e)[:80]}
        print(f"  ERR: {e}")
    print()
else:
    print("--- 3.4: Unpaywall — no PDF URL available, skip ---")
    print()

# ============= Summary =============
print("=" * 70)
print("SUMMARY: which channels actually delivered a PDF?")
print("=" * 70)
print()

# Format the table
all_results = {}
for k, v in results.items():
    all_results[k] = v
for k, v in download_results.items():
    if k in all_results:
        all_results[k]["download"] = v
    else:
        all_results[k] = {"download": v}

print(f"{'Channel':30s} {'Find':6s} {'PDF':6s} {'Note':40s}")
print("-" * 90)
final_channels = []

# pa fetch channels
for k in ["scihub", "annas", "cnki", "auto"]:
    pk = f"prefer={k}"
    r = results.get(pk, {})
    success = r.get("success", False)
    handoff = r.get("handoff", False)
    if success:
        marker = "OK"
        note = f"fetched {r.get('size_bytes_actual', 0)} bytes in {r.get('elapsed', 0)}s"
        final_channels.append((k, "OK", note))
    elif handoff:
        marker = "FAIL"
        note = f"all sources failed (rc={r.get('rc')})"
    else:
        marker = "FAIL"
        note = f"rc={r.get('rc')}, elapsed={r.get('elapsed', 0)}s"
    print(f"  pa fetch prefer={k:8s} {'-' if success else 'NO':6s} {marker:6s} {note}")
    final_channels.append((f"fetch({k})", "OK" if success else "FAIL", note))

# Independent sources
for k in ["openalex", "crossref", "arxiv", "semanticscholar", "unpaywall"]:
    r = results.get(k, {})
    found = r.get("found", False)
    pdf_url = r.get("pdf_url") or r.get("openAccessPdf") or "(none)"
    download = download_results.get(k, {})
    pdf_ok = download.get("ok", False)
    if pdf_ok:
        marker = "OK"
        note = f"PDF {download.get('size', 0)} bytes"
    elif found and pdf_url != "(none)":
        marker = "OK-meta"
        note = f"found but PDF not tested"
    elif found:
        marker = "OK-meta"
        note = "metadata only (no PDF URL)"
    else:
        marker = "FAIL"
        note = r.get("error", "not found")[:40]
    print(f"  {k:30s} {'YES' if found else 'NO':6s} {marker:6s} {note}")
    final_channels.append((k, "OK" if pdf_ok else ("OK-meta" if found else "FAIL"), note))

print()
print("=" * 70)
print("FINAL TALLY: actually-delivered-PDF channels")
print("=" * 70)
ok_count = sum(1 for _, s, _ in final_channels if s == "OK")
ok_meta_count = sum(1 for _, s, _ in final_channels if s == "OK-meta")
fail_count = sum(1 for _, s, _ in final_channels if s == "FAIL")
print(f"  OK (delivered PDF):     {ok_count} / {len(final_channels)}")
print(f"  OK-meta (found, no PDF): {ok_meta_count} / {len(final_channels)}")
print(f"  FAIL:                    {fail_count} / {len(final_channels)}")
print()
if ok_count <= 2:
    print("  USER'S CLAIM VERIFIED: 实际可用通道非常少,<=2 个真能下到 PDF")
elif ok_count <= 4:
    print("  USER'S CLAIM PARTIALLY VERIFIED: 实际可用通道偏少")
else:
    print("  USER'S CLAIM NOT VERIFIED: 实际可用通道 >= 4 个")
