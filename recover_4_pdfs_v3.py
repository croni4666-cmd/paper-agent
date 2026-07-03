#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pass 3 — Utami direct download + McMinn Cloudflare bypass attempts."""
import json
import os
import re
import ssl
import time
import urllib.request
import urllib.error
from pathlib import Path

OUTDIR = Path(r"G:\minimax - workspace\Paper agent\results\_example_ai_education_v31_lit_review\pdfs\4_attempt_recovery")
OUTDIR.mkdir(parents=True, exist_ok=True)

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

CHROME_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf;q=0.8,*/*;q=0.7",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
}


def is_pdf_magic(content):
    return content[:4] == b"%PDF" and len(content) > 5000


def save(content, name):
    out = OUTDIR / f"{name}.pdf"
    out.write_bytes(content)
    return out, len(content) / 1024


# ============================================================
# PASS A3: Utami — direct OJS download endpoint
# OJS pattern: /index.php/<journal>/article/download/<article>/<galley>/<fileId>
# ============================================================
def utami_direct_download():
    print("\n=== [A3] Utami direct OJS download ===")
    # URL was identified from playwright pass:
    url = "https://journal-center.litpam.com/index.php/jolls/article/download/3611/2741/26960"
    # Try as PDF
    try:
        req = urllib.request.Request(url, headers=CHROME_HEADERS)
        resp = urllib.request.urlopen(req, timeout=45, context=ctx)
        body = resp.read()
        ct = resp.headers.get("Content-Type", "")
        cd = resp.headers.get("Content-Disposition", "")
        print(f"  status: {resp.status}, content-type: {ct}")
        print(f"  content-disposition: {cd}")
        print(f"  body size: {len(body)}, magic: {body[:8]!r}")
        if is_pdf_magic(body):
            p, kb = save(body, "Utami_2025_via_ojs")
            print(f"  ✓ saved {p} ({kb:.1f} KB)")
            return {"ok": True, "path": str(p), "details": []}
        elif "html" in ct.lower():
            # Maybe server returned HTML wrapper; inspect for actual PDF URL
            html = body.decode("utf-8", errors="ignore")
            pdf_links = re.findall(r'(https?://[^"\s<>]+\.pdf[^"\s<>]*)', html)
            print(f"  HTML returned, pdf links: {pdf_links[:3]}")
            for plink in pdf_links[:3]:
                try:
                    req2 = urllib.request.Request(plink, headers=CHROME_HEADERS)
                    resp2 = urllib.request.urlopen(req2, timeout=45, context=ctx)
                    b2 = resp2.read()
                    resp2.close()
                    if is_pdf_magic(b2):
                        p, kb = save(b2, "Utami_2025_via_ojs")
                        print(f"  ✓ saved via inner PDF link ({kb:.1f} KB)")
                        return {"ok": True, "path": str(p), "details": []}
                except Exception as e:
                    print(f"  inner link err: {type(e).__name__}")
            # Try pdfjsviewer URL pattern
            viewer = re.search(r'(https://journal-center\.litpam\.com/plugins/generic/pdfJsViewer/[^"\s<>]+)', html)
            if viewer:
                vurl = viewer.group(1)
                print(f"  found viewer URL: {vurl[:120]}")
                # Extract encoded file parameter
                m = re.search(r'file=([^"\s&]+)', vurl)
                if m:
                    encoded = m.group(1)
                    # URL-decode
                    inner_pdf = urllib.parse.unquote(encoded)
                    print(f"  inner PDF URL: {inner_pdf}")
                    try:
                        req3 = urllib.request.Request(inner_pdf, headers=CHROME_HEADERS)
                        resp3 = urllib.request.urlopen(req3, timeout=45, context=ctx)
                        b3 = resp3.read()
                        resp3.close()
                        if is_pdf_magic(b3):
                            p, kb = save(b3, "Utami_2025_via_ojs")
                            print(f"  ✓ saved via pdfjs inner ({kb:.1f} KB)")
                            return {"ok": True, "path": str(p), "details": []}
                    except Exception as e:
                        print(f"  inner pdf err: {type(e).__name__}")
        else:
            # Save as-is for diagnosis
            p, kb = save(body, "Utami_2025_attempt_response")
            print(f"  saved non-PDF response for diagnosis: {kb:.1f} KB")
    except urllib.error.HTTPError as e:
        print(f"  HTTP err: {e.code} {e.reason}")
        # Read error body
        try:
            err_body = e.read()
            print(f"  err body: {err_body[:200]!r}")
        except Exception:
            pass
        return {"ok": False, "path": None, "details": [f"HTTP {e.code}"]}
    except Exception as e:
        print(f"  err: {type(e).__name__}: {str(e)[:100]}")
        return {"ok": False, "path": None, "details": [str(e)]}
    return {"ok": False, "path": None, "details": ["no PDF recovered"]}


# ============================================================
# PASS C3: McMinn — Cloudflare interstitial bypass attempts
# ============================================================
def mcminn_cloudflare_bypass():
    print("\n=== [C3] McMinn Cloudflare bypass ===")
    from playwright.sync_api import sync_playwright
    CHROMIUM_EXE = r"C:\Users\DengN\AppData\Local\ms-playwright\chromium-1223\chrome-win64\chrome.exe"
    out = {"ok": False, "path": None, "details": []}
    landed_urls = []
    pdf_urls_observed = []
    with sync_playwright() as p:
        # Strategy A: stronger chrome-like stealth + wait for challenge
        browser = p.chromium.launch(
            executable_path=CHROMIUM_EXE,
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--window-size=1920,1080",
            ],
        )
        ctx_pw = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            extra_http_headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
            java_script_enabled=True,
            ignore_https_errors=True,
        )
        page = ctx_pw.new_page()
        # Hide webdriver
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)
        def on_response(resp):
            try:
                if "pdf" in resp.url.lower() or resp.headers.get("content-type", "").endswith("application/pdf"):
                    pdf_urls_observed.append((resp.status, resp.url))
            except Exception:
                pass
        page.on("response", on_response)
        # Strategy B: try multiple navigation paths
        targets = [
            "https://www.tandfonline.com/doi/full/10.1080/17516234.2024.2447195",
            "https://doi.org/10.1080/17516234.2024.2447195",
        ]
        for target in targets:
            try:
                print(f"  trying {target}")
                resp = page.goto(target, timeout=45000, wait_until="domcontentloaded")
                landed = page.url
                landed_urls.append(landed)
                print(f"  landed: {landed[:120]}")
                # Wait for CF challenge to resolve (look for title change away from 'Just a moment...')
                for _ in range(15):
                    try:
                        title = page.title()
                        if "Just a moment" not in title and title.strip():
                            print(f"  resolved title: {title[:80]!r}")
                            break
                    except Exception:
                        pass
                    page.wait_for_timeout(2000)
                # Wait for any final load
                try:
                    page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    pass
                title = page.title()
                print(f"  final title: {title[:80]!r}")
                # Re-gather PDF links
                anchors = page.eval_on_selector_all("a", "els => els.map(e => ({href: e.href, text: e.innerText.trim().slice(0, 40)}))")
                pdf_links = [a for a in anchors if a["href"] and ("pdf" in a["href"].lower() or "pdf" in a["text"].lower() or "download" in a["text"].lower())]
                print(f"  PDF-like anchors: {len(pdf_links)}")
                for a in pdf_links[:5]:
                    print(f"    {a['text'][:30]!r:32} -> {a['href'][:120]}")
                if pdf_links:
                    first = pdf_links[0]["href"]
                    print(f"  try first: {first[:120]}")
                    try:
                        with page.expect_download(timeout=15000) as dl_info:
                            page.goto(first, timeout=20000)
                        dl = dl_info.value
                        target_p = OUTDIR / "McMinn_2025_via_pw.pdf"
                        dl.save_as(str(target_p))
                        kb = target_p.stat().st_size / 1024
                        if kb > 5:
                            print(f"  ✓ downloaded {target_p} ({kb:.1f} KB)")
                            out["ok"] = True
                            out["path"] = str(target_p)
                            break
                    except Exception as e:
                        print(f"  click err: {type(e).__name__}")
                        # Try direct nav
                        try:
                            resp = page.goto(first, timeout=30000)
                            body = resp.body() if resp else None
                            if body and is_pdf_magic(body):
                                target_p = OUTDIR / "McMinn_2025_via_pw.pdf"
                                target_p.write_bytes(body)
                                out["ok"] = True
                                out["path"] = str(target_p)
                                print(f"  ✓ direct nav saved ({len(body)/1024:.1f} KB)")
                                break
                        except Exception as e2:
                            print(f"  direct nav err: {type(e2).__name__}")
            except Exception as e:
                print(f"  {target} err: {type(e).__name__}: {str(e)[:80]}")
        if pdf_urls_observed:
            print(f"  PDF network responses: {len(pdf_urls_observed)}")
            for status, url in pdf_urls_observed[:3]:
                print(f"    {status} {url[:120]}")
        browser.close()
    return out


if __name__ == "__main__":
    results = {
        "Utami_2025_direct_OJS": utami_direct_download(),
        "McMinn_2025_CF_bypass": mcminn_cloudflare_bypass(),
    }
    out_path = Path(r"G:\minimax - workspace\Paper agent\results\_example_ai_education_v31_lit_review\4_attempt_pass3_summary.json")
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWritten {out_path}")
    print(f"\nResults: {json.dumps(results, indent=2, ensure_ascii=False)}")
