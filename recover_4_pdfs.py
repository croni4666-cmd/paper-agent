#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Three parallel paths to retrieve the 4 locked PDFs.
Paths:
  A. Anna's Archive (doi redirect to PDF)
  B. CORE API (v3, batch all 4)
  C. Playwright Chromium Python (Python-side, not MCP) on landing pages, click "Download PDF"
"""
import json
import os
import re
import sys
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

# Load .env manually (no dotenv dep)
ENV_PATH = Path(r"G:\minimax - workspace\Paper agent\.env")
env = {}
if ENV_PATH.exists():
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")

CORE_KEY = env.get("CORE_API_KEY")
S2_KEY = env.get("S2_API_KEY")
OA_KEY = env.get("OPENALEX_API_KEY")

CHROME_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

OUTDIR = Path(r"G:\minimax - workspace\Paper agent\results\_example_ai_education_v31_lit_review\pdfs\4_attempt_recovery")
OUTDIR.mkdir(parents=True, exist_ok=True)

FAILED = [
    ("10.1016/j.caeo.2024.100184", "Tzirides_2024"),
    ("10.1016/j.caeai.2023.100127", "Southworth_2023"),
    ("10.36312/7tjb1p58", "Utami_2025"),
    ("10.1080/17516234.2024.2447195", "McMinn_2025"),
]


def fetch_url(url, headers=None, timeout=20):
    h = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    return urllib.request.urlopen(req, timeout=timeout)


def save_pdf(content, name):
    out = OUTDIR / f"{name}.pdf"
    with open(out, "wb") as f:
        f.write(content)
    size_kb = len(content) / 1024
    return out, size_kb


def is_pdf_magic(content):
    return content[:4] == b"%PDF" and len(content) > 5000


# ======================================================================
# PATH A: Anna's Archive (DOI lookup → direct PDF link)
# ======================================================================
def try_annas_archive(doi, name):
    print(f"\n[A] Anna's Archive: {name} ({doi})")
    try:
        # Anna's search endpoint accepts DOI for direct lookup
        url = f"https://annas-archive.org/search?doi={doi}"
        html = fetch_url(url, timeout=20).read().decode("utf-8", errors="ignore")
        # Extract first PDF-like URL on the page
        candidates = re.findall(r'href="(https?://[^"]+\.(?:pdf|PDF)[^"]*)"', html)
        if not candidates:
            # Try fast-download hash links (md5 path)
            md5_matches = re.findall(r'(/md5/[a-f0-9]{32})', html)
            if md5_matches:
                pdf_url = "https://annas-archive.org" + md5_matches[0]
                print(f"  → md5 download path: {pdf_url}")
                pdf_url = pdf_url + ".pdf" if not pdf_url.endswith(".pdf") else pdf_url
                candidates = [pdf_url]
        # Dedupe
        candidates = list(dict.fromkeys(candidates))
        for c in candidates[:5]:
            print(f"  candidate: {c[:120]}")
        for c in candidates[:3]:
            try:
                resp = fetch_url(c, timeout=25)
                data = resp.read()
                resp.close()
                if is_pdf_magic(data):
                    out, kb = save_pdf(data, name + "_via_annas")
                    print(f"  ✓ saved {out} ({kb:.1f} KB)")
                    return True, str(out)
            except Exception as e:
                print(f"  ✗ candidate failed: {type(e).__name__}")
                continue
        print(f"  ✗ no working PDF found in {len(candidates)} candidates")
        return False, None
    except Exception as e:
        print(f"  ✗ AA error: {type(e).__name__}: {str(e)[:100]}")
        return False, None


# ======================================================================
# PATH B: CORE API (search by DOI, fetch downloadUrl)
# ======================================================================
def try_core_api(doi, name):
    print(f"\n[B] CORE API: {name} ({doi})")
    if not CORE_KEY:
        print("  ✗ no CORE_API_KEY in .env")
        return False, None
    try:
        url = f"https://api.core.ac.uk/v3/search/works?q=doi:%22{doi}%22&limit=1"
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {CORE_KEY}"},
        )
        resp = urllib.request.urlopen(req, timeout=20)
        data = json.loads(resp.read().decode("utf-8"))
        resp.close()
        total = data.get("totalHits", 0)
        if total == 0:
            print(f"  ✗ 0 hits")
            return False, None
        hit = data.get("results", [{}])[0]
        core_id = hit.get("id")
        download_url = hit.get("downloadUrl")
        source_urls = hit.get("sourceFulltextUrls") or []
        print(f"  core_id: {core_id}")
        print(f"  downloadUrl: {download_url}")
        print(f"  sourceFulltextUrls: {source_urls[:3]}")
        # Try downloadUrl first
        if download_url:
            try:
                resp = fetch_url(download_url, timeout=30)
                body = resp.read()
                resp.close()
                if is_pdf_magic(body):
                    out, kb = save_pdf(body, name + "_via_core_download")
                    print(f"  ✓ saved via downloadUrl ({kb:.1f} KB)")
                    return True, str(out)
                else:
                    print(f"  downloadUrl returned non-PDF ({len(body)} bytes)")
            except Exception as e:
                print(f"  downloadUrl failed: {type(e).__name__}")
        # Try CORE hosted file endpoint
        if core_id:
            try:
                file_url = f"https://api.core.ac.uk/v3/works/{core_id}/download"
                resp = fetch_url(file_url, headers={"Authorization": f"Bearer {CORE_KEY}"}, timeout=30)
                body = resp.read()
                resp.close()
                if is_pdf_magic(body):
                    out, kb = save_pdf(body, name + "_via_core_file")
                    print(f"  ✓ saved via /works/id/download ({kb:.1f} KB)")
                    return True, str(out)
            except Exception as e:
                print(f"  /works/id/download failed: {type(e).__name__}")
        return False, None
    except Exception as e:
        print(f"  ✗ CORE error: {type(e).__name__}: {str(e)[:100]}")
        return False, None


# ======================================================================
# PATH C: Playwright Chromium Python
# ======================================================================
def try_playwright_chromium(doi, name):
    print(f"\n[C] Playwright Chromium: {name} ({doi})")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  ✗ playwright not installed")
        return False, None
    CHROMIUM_EXE = r"C:\Users\DengN\AppData\Local\ms-playwright\chromium-1223\chrome-win64\chrome.exe"
    if not Path(CHROMIUM_EXE).exists():
        print(f"  ✗ chromium binary missing: {CHROMIUM_EXE}")
        return False, None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                executable_path=CHROMIUM_EXE,
                headless=True,
                args=["--no-sandbox", "--disable-gpu"],
            )
            ctx = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                accept_downloads=True,
            )
            page = ctx.new_page()
            landed = None
            # Try DOI.org redirect first
            try:
                resp = page.goto(f"https://doi.org/{doi}", timeout=30000, wait_until="domcontentloaded")
                landed = page.url
                print(f"  doi.org landed on: {landed}")
            except Exception as e:
                print(f"  doi.org navigation failed: {type(e).__name__}")
            if not landed:
                landed = ""
            # Click / search for a PDF link
            pdf_href = None
            try:
                hrefs = page.eval_on_selector_all("a[href$='.pdf'], a[href*='pdf']", "els => els.map(e => e.href)")
                pdf_href = next((h for h in hrefs if h and h.startswith("http")), None)
            except Exception:
                pass
            if pdf_href:
                print(f"  found PDF link: {pdf_href[:120]}")
            else:
                print(f"  no direct PDF link on page; HTML size: {len(page.content())}")
                browser.close()
                return False, None
            # Try downloading via context
            success = False
            try:
                with page.expect_download(timeout=15000) as dl_info:
                    page.goto(pdf_href, timeout=20000)
                dl = dl_info.value
                target = OUTDIR / f"{name}_via_pw.pdf"
                dl.save_as(str(target))
                size_kb = target.stat().st_size / 1024
                if size_kb > 5:
                    print(f"  ✓ saved via playwright download {target} ({size_kb:.1f} KB)")
                    success = True
            except Exception as e:
                print(f"  expect_download flow failed: {type(e).__name__}: {str(e)[:80]}")
            browser.close()
            return success, str(target) if success else None
    except Exception as e:
        print(f"  ✗ playwright error: {type(e).__name__}: {str(e)[:120]}")
        return False, None


# ======================================================================
# Run all 3 paths on all 4 papers
# ======================================================================
def main():
    results = {}
    for doi, name in FAILED:
        ok_aa, path_aa = try_annas_archive(doi, name)
        ok_core, path_core = try_core_api(doi, name)
        ok_pw, path_pw = try_playwright_chromium(doi, name)
        results[name] = {
            "doi": doi,
            "annas": {"ok": ok_aa, "path": path_aa},
            "core": {"ok": ok_core, "path": path_core},
            "playwright": {"ok": ok_pw, "path": path_pw},
        }

    summary = Path(r"G:\minimax - workspace\Paper agent\results\_example_ai_education_v31_lit_review\4_attempt_recovery_summary.json")
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n=== SUMMARY ===")
    print(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"\nWritten to {summary}")


if __name__ == "__main__":
    main()
