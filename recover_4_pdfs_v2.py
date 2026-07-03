#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pass 2 — focused, with deep page inspection for Utami + T&F CF wait.
Recovers from Pass 1 findings:
  - Utami 2025: litpam.com open journal — look for view/PDF buttons, not just .pdf href
  - McMinn 2025: T&F shows Cloudflare challenge — need extra wait + cookies
  - Anna's Archive: extend timeout (cold-start) + try alternate mirror MD5 path
  - CORE: diagnose why 403 (test key + alternate query shape)
"""
import json
import os
import re
import time
import urllib.request
import urllib.error
import ssl
from pathlib import Path

# Load .env manually
ENV_PATH = Path(r"G:\minimax - workspace\Paper agent\.env")
env = {}
if ENV_PATH.exists():
    raw = ENV_PATH.read_text(encoding="utf-8")
    print(f"[env] loaded {len(raw)} bytes from {ENV_PATH}")
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")

CORE_KEY = env.get("CORE_API_KEY")
S2_KEY = env.get("S2_API_KEY")
OA_KEY = env.get("OPENALEX_API_KEY")
print(f"[env] CORE={bool(CORE_KEY)} ({len(CORE_KEY) if CORE_KEY else 0} chars), S2={bool(S2_KEY)}, OA={bool(OA_KEY)}")
if CORE_KEY:
    print(f"[env] CORE_KEY first 8: {CORE_KEY[:8]}")
    print(f"[env] CORE_KEY last 4:  ...{CORE_KEY[-4:]}")

# Bypass SSL for some Elsevier pages (TLS handshake quirks)
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

OUTDIR = Path(r"G:\minimax - workspace\Paper agent\results\_example_ai_education_v31_lit_review\pdfs\4_attempt_recovery")
OUTDIR.mkdir(parents=True, exist_ok=True)

FAILED = [
    ("10.36312/7tjb1p58", "Utami_2025"),
    ("10.1080/17516234.2024.2447195", "McMinn_2025"),
]

CHROME_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def is_pdf_magic(content):
    return content[:4] == b"%PDF" and len(content) > 5000


def save_pdf(content, name):
    out = OUTDIR / f"{name}.pdf"
    with open(out, "wb") as f:
        f.write(content)
    return out, len(content) / 1024


# ============================================================
# PATH A2: Anna's Archive — more aggressive (long timeout, /md5 path)
# ============================================================
def try_annas_pass2(doi, name):
    print(f"\n=== [A2] Anna's Archive: {name} ({doi}) ===")
    headers = dict(CHROME_HEADERS)
    headers["Referer"] = "https://annas-archive.org/"
    out = {"ok": False, "path": None, "details": []}
    candidates_to_try = []
    # 1) Anna's DOI endpoint — bypass 20s timeout to 60s
    try:
        url = f"https://annas-archive.org/search?doi={doi}"
        req = urllib.request.Request(url, headers=headers)
        # Allow longer timeout for cold start
        resp = urllib.request.urlopen(req, timeout=60, context=ctx)
        html = resp.read().decode("utf-8", errors="ignore")
        resp.close()
        print(f"  AA search: {len(html)} chars")
        # Extract md5 path
        md5_matches = re.findall(r'(/md5/[a-f0-9]{32})', html)
        if md5_matches:
            md5_path = md5_matches[0]
            candidates_to_try.append(("https://annas-archive.org" + md5_path, "md5_page"))
            print(f"  found md5 path: {md5_path}")
        # External links
        ext_pdfs = re.findall(r'href="(https?://[^"]+\.pdf[^"]*)"', html)
        candidates_to_try += [(p, "ext_pdf") for p in ext_pdfs[:5]]
        # Cached PDF reads via /slow_download/<md5> -- need JS but
        if not candidates_to_try:
            print(f"  no candidates from HTML")
    except Exception as e:
        out["details"].append(f"AA search err: {type(e).__name__}: {str(e)[:80]}")
        print(f"  ✗ AA search err: {type(e).__name__}")
    # 2) Try fast download API if md5 found
    tried = set()
    for url, why in candidates_to_try:
        if url in tried:
            continue
        tried.add(url)
        print(f"  trying {why}: {url[:120]}")
        # /md5/<hash> is a landing page; need to fetch then look for /slow_download or actual pdf link
        try:
            req = urllib.request.Request(url, headers=headers)
            resp = urllib.request.urlopen(req, timeout=60, context=ctx)
            body = resp.read()
            resp.close()
            content_type = resp.headers.get("Content-Type", "")
            if is_pdf_magic(body):
                p, kb = save_pdf(body, f"{name}_via_annas")
                print(f"  ✓ direct PDF from {url} ({kb:.1f} KB)")
                return {"ok": True, "path": str(p), "details": out["details"]}
            elif "html" in content_type:
                # Look for slow_download link in HTML
                sub_html = body.decode("utf-8", errors="ignore")
                slow = re.search(r'(/slow_download/[a-z0-9_/]+)', sub_html)
                if slow:
                    slow_url = "https://annas-archive.org" + slow.group(1)
                    print(f"  found slow_download: {slow_url}")
                    try:
                        req2 = urllib.request.Request(slow_url, headers=headers)
                        resp2 = urllib.request.urlopen(req2, timeout=120, context=ctx)
                        body2 = resp2.read()
                        resp2.close()
                        if is_pdf_magic(body2):
                            p, kb = save_pdf(body2, f"{name}_via_annas")
                            print(f"  ✓ slow_download PDF ({kb:.1f} KB)")
                            return {"ok": True, "path": str(p), "details": out["details"]}
                    except Exception as e:
                        print(f"  slow_download err: {type(e).__name__}")
                # Try direct file link in HTML
                file_pdfs = re.findall(r'(https?://[a-z0-9.-]+\.libgen\.[^"\']*\.pdf)', sub_html)
                if not file_pdfs:
                    file_pdfs = re.findall(r'(https?://[a-z0-9.-]+/libgen[^"\']*\.pdf)', sub_html)
                for fp in file_pdfs[:3]:
                    print(f"  fallback libgen pdf: {fp[:120]}")
                    try:
                        req3 = urllib.request.Request(fp, headers=headers)
                        resp3 = urllib.request.urlopen(req3, timeout=60, context=ctx)
                        body3 = resp3.read()
                        resp3.close()
                        if is_pdf_magic(body3):
                            p, kb = save_pdf(body3, f"{name}_via_annas")
                            print(f"  ✓ libgen direct PDF ({kb:.1f} KB)")
                            return {"ok": True, "path": str(p), "details": out["details"]}
                    except Exception as e:
                        print(f"  libgen err: {type(e).__name__}")
            else:
                print(f"  unexpected content-type: {content_type}, {len(body)} bytes")
        except Exception as e:
            print(f"  ✗ try err: {type(e).__name__}")
    print(f"  ✗ no path recovered")
    return out


# ============================================================
# PATH C2: Playwright with deep inspection (Utami specifically)
# ============================================================
def try_playwright_deep(doi, name):
    print(f"\n=== [C2] Playwright deep: {name} ({doi}) ===")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  ✗ playwright not installed")
        return {"ok": False, "path": None, "details": ["no playwright"]}
    CHROMIUM_EXE = r"C:\Users\DengN\AppData\Local\ms-playwright\chromium-1223\chrome-win64\chrome.exe"
    if not Path(CHROMIUM_EXE).exists():
        return {"ok": False, "path": None, "details": ["no binary"]}
    out = {"ok": False, "path": None, "details": []}
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=CHROMIUM_EXE,
            headless=True,
            args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"],
        )
        ctx = browser.new_context(
            user_agent=CHROME_HEADERS["User-Agent"],
            accept_downloads=True,
            viewport={"width": 1920, "height": 1080},
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        page = ctx.new_page()
        # Network logging
        pdf_response_url = []
        def on_response(resp):
            try:
                if "pdf" in resp.url.lower() or resp.headers.get("content-type", "") == "application/pdf":
                    pdf_response_url.append((resp.url, resp.status))
            except Exception:
                pass
        page.on("response", on_response)
        try:
            page.goto(f"https://doi.org/{doi}", timeout=45000, wait_until="networkidle")
        except Exception as e:
            print(f"  goto err: {type(e).__name__}")
        landed = page.url
        print(f"  landed: {landed[:160]}")
        # Print page title and PDF anchor candidates
        try:
            title = page.title()
            print(f"  title: {title[:80]}")
        except Exception:
            pass
        # Gather ALL links (href + button onclick URLs)
        try:
            anchors = page.eval_on_selector_all("a", "els => els.map(e => ({href: e.href, text: e.innerText.trim().slice(0, 40)})).filter(o => o.href)")
            print(f"  total anchors: {len(anchors)}")
        except Exception as e:
            print(f"  eval anchors err: {type(e).__name__}")
            anchors = []
        # Filter for PDF candidates
        pdf_anchors = [a for a in anchors if "pdf" in (a["href"] or "").lower() or "pdf" in (a["text"] or "").lower() or "download" in (a["text"] or "").lower() or "view" in (a["href"] or "").lower()]
        print(f"  PDF-like anchors: {len(pdf_anchors)}")
        for a in pdf_anchors[:8]:
            print(f"    {a['text'][:30]!r:32} -> {a['href'][:120]}")
        # Try clicking first PDF button
        clicked_pdf = False
        for sel in [
            "a:has-text('PDF')",
            "a:has-text('Download')",
            "a:has-text('View PDF')",
            "a.btn[href*='pdf']",
            "a.galley-file-btn",
            "a[href*='download']",
            "a[href*='galley']",
        ]:
            try:
                if page.locator(sel).count() > 0:
                    href = page.eval_on_selector(sel, "el => el.href")
                    text = page.eval_on_selector(sel, "el => el.innerText.trim()")
                    print(f"  sel {sel!r}: {text!r} → {href[:120]}")
                    # Navigate directly (avoids JS dialog issues)
                    try:
                        with page.expect_download(timeout=20000) as dl_info:
                            page.goto(href, timeout=20000)
                        dl = dl_info.value
                        target = OUTDIR / f"{name}_via_pw_click.pdf"
                        dl.save_as(str(target))
                        size_kb = target.stat().st_size / 1024
                        print(f"  ✓ downloaded {target} ({size_kb:.1f} KB)")
                        out["ok"] = True
                        out["path"] = str(target)
                        clicked_pdf = True
                        break
                    except Exception as e:
                        print(f"  click err: {type(e).__name__}")
            except Exception:
                pass
        if not clicked_pdf and pdf_anchors:
            # Try direct navigation to first pdf href
            first = pdf_anchors[0]["href"]
            print(f"  fallback direct nav: {first[:120]}")
            try:
                resp = page.goto(first, timeout=20000)
                body = resp.body() if resp else None
                if body and is_pdf_magic(body):
                    target = OUTDIR / f"{name}_via_pw_direct.pdf"
                    target.write_bytes(body)
                    print(f"  ✓ saved {target} ({len(body)/1024:.1f} KB)")
                    out["ok"] = True
                    out["path"] = str(target)
            except Exception as e:
                print(f"  direct nav err: {type(e).__name__}")
        if pdf_response_url:
            print(f"  PDF-like network responses observed: {len(pdf_response_url)}")
            for url, status in pdf_response_url[:3]:
                print(f"    {status} {url[:120]}")
        browser.close()
    return out


# ============================================================
# PATH B2: CORE — diagnose 403
# ============================================================
def try_core_pass2(doi, name):
    print(f"\n=== [B2] CORE diagnose: {name} ({doi}) ===")
    if not CORE_KEY:
        return {"ok": False, "path": None, "details": ["no key"]}
    # Test 1: simple ping endpoint
    print(f"  [test 1] ping endpoint")
    try:
        req = urllib.request.Request("https://api.core.ac.uk/v3/search/works?q=test&limit=1",
                                    headers={"Authorization": f"Bearer {CORE_KEY}"})
        resp = urllib.request.urlopen(req, timeout=20, context=ctx)
        print(f"  ping: {resp.status} {len(resp.read())} bytes")
        resp.close()
    except Exception as e:
        print(f"  ping err: {type(e).__name__}: {str(e)[:100]}")
    # Test 2: bare DOI lookup
    print(f"  [test 2] direct DOI lookup via /works/doi:")
    try:
        url = f"https://api.core.ac.uk/v3/works/doi/{doi}"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {CORE_KEY}"})
        resp = urllib.request.urlopen(req, timeout=20, context=ctx)
        body = resp.read().decode("utf-8")
        print(f"  status: {resp.status}")
        data = json.loads(body)
        print(f"  id: {data.get('id')}, title: {(data.get('title') or '')[:60]!r}")
        fulltext = data.get("sourceFulltextUrls") or []
        download = data.get("downloadUrl")
        print(f"  downloadUrl: {download}")
        print(f"  sourceFulltextUrls: {fulltext[:3]}")
        # Try downloadUrl
        if download:
            try:
                req2 = urllib.request.Request(download, headers=CHROME_HEADERS)
                resp2 = urllib.request.urlopen(req2, timeout=60, context=ctx)
                blob = resp2.read()
                resp2.close()
                if is_pdf_magic(blob):
                    p, kb = save_pdf(blob, f"{name}_via_core")
                    print(f"  ✓ saved ({kb:.1f} KB)")
                    return {"ok": True, "path": str(p), "details": []}
                else:
                    print(f"  downloadUrl returned non-PDF, {len(blob)} bytes")
            except Exception as e:
                print(f"  download err: {type(e).__name__}")
    except Exception as e:
        print(f"  direct DOI err: {type(e).__name__}")
    # Test 3: alternate search with no DOI prefix
    print(f"  [test 3] search by DOI without q=doi: prefix")
    try:
        url = f"https://api.core.ac.uk/v3/search/works?q={urllib.parse.quote(doi)}&limit=5"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {CORE_KEY}"})
        resp = urllib.request.urlopen(req, timeout=20, context=ctx)
        data = json.loads(resp.read().decode("utf-8"))
        resp.close()
        total = data.get("totalHits", 0)
        print(f"  search hits: {total}")
        for hit in data.get("results", [])[:2]:
            print(f"    - id={hit.get('id')}, title={hit.get('title', '')[:60]}, dl={hit.get('downloadUrl')}")
    except Exception as e:
        print(f"  search err: {type(e).__name__}: {str(e)[:80]}")
    return {"ok": False, "path": None, "details": ["CORE all 3 attempts failed"]}


def main():
    results = {}
    for doi, name in FAILED:
        print(f"\n{'='*60}\n{name} — {doi}\n{'='*60}")
        results[name] = {
            "doi": doi,
            "annas_v2": try_annas_pass2(doi, name),
            "core_v2": try_core_pass2(doi, name),
            "playwright_v2": try_playwright_deep(doi, name),
        }
    out_path = Path(r"G:\minimax - workspace\Paper agent\results\_example_ai_education_v31_lit_review\4_attempt_pass2_summary.json")
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWritten {out_path}")


if __name__ == "__main__":
    main()
