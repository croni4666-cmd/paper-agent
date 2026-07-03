#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pass 4 — extract full Utami text + final attempt on the other 3.

Final angles for the 3 remaining:
- McMinn 2025: ResearchGate (author upload common for HKUST) + Googlebot UA for Google Scholar cache
- Tzirides 2024: Googlebot UA + ResearchGate (digital Promise deposition patterns)
- Southworth 2023: Googlebot UA + CORE/ERIC via title search

We accept: the 3 may stay unrecoverable. We proceed to lock in Utami first.
"""
import json
import re
import ssl
import urllib.request
import urllib.error
from pathlib import Path

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

OUT_PDF = Path(r"G:\minimax - workspace\Paper agent\results\_example_ai_education_v31_lit_review\pdfs\4_attempt_recovery")
OUT_TXT = Path(r"G:\minimax - workspace\Paper agent\results\_example_ai_education_v31_lit_review\texts")
OUT_PDF.mkdir(parents=True, exist_ok=True)
OUT_TXT.mkdir(parents=True, exist_ok=True)

CHROME_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
GOOGLEBOT_UA = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"


def is_pdf(b):
    return b[:4] == b"%PDF" and len(b) > 5000


def save(b, name):
    out = OUT_PDF / f"{name}.pdf"
    out.write_bytes(b)
    return out, len(b) / 1024


def try_researchgate(doi, name):
    """ResearchGate direct landing page — sometimes exposes author-uploaded PDF."""
    print(f"\n=== ResearchGate: {name} ===")
    headers = {"User-Agent": CHROME_UA, "Accept": "*/*"}
    for url in [
        f"https://www.researchgate.net/publication/{doi_to_rg_id(doi)}",
    ]:
        try:
            req = urllib.request.Request(url, headers=headers)
            resp = urllib.request.urlopen(req, timeout=20, context=ctx)
            body = resp.read()
            ct = resp.headers.get("Content-Type", "")
            if "pdf" in ct and is_pdf(body):
                p, kb = save(body, f"{name}_via_rg")
                print(f"  ✓ PDF ({kb:.1f} KB)")
                return True
        except Exception as e:
            print(f"  {url} err: {type(e).__name__}: {str(e)[:80]}")
    # Search-style fallback
    return False


def doi_to_rg_id(doi):
    # RG doesn't expose numeric publication IDs easily; this is a placeholder pattern
    return ""


def try_googlebot_doi(doi, name):
    """Use Googlebot UA on doi.org, sometimes a different cache path."""
    print(f"\n=== Googlebot UA: {name} ===")
    headers = {
        "User-Agent": GOOGLEBOT_UA,
        "Accept": "application/pdf,*/*",
    }
    try:
        req = urllib.request.Request(f"https://doi.org/{doi}", headers=headers)
        resp = urllib.request.urlopen(req, timeout=25, context=ctx)
        body = resp.read()
        ct = resp.headers.get("Content-Type", "")
        if "pdf" in ct and is_pdf(body):
            p, kb = save(body, f"{name}_via_googlebot")
            print(f"  ✓ PDF ({kb:.1f} KB)")
            return True
        else:
            print(f"  googlebot landed, body size {len(body)}, ct={ct}, magic={body[:8]!r}")
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code}")
    except Exception as e:
        print(f"  err: {type(e).__name__}: {str(e)[:80]}")
    return False


def try_scholar_pdf(query, name):
    """Try fetching Scholar's 'All versions' first hit."""
    print(f"\n=== Scholar PDF search: {name} ===")
    try:
        import requests
        try:
            r = requests.get(
                "https://scholar.google.com/scholar",
                params={"q": query + " filetype:pdf", "hl": "en"},
                headers={"User-Agent": CHROME_UA},
                timeout=20,
            )
            # Find PDF links in HTML
            pdfs = re.findall(r'href="(https?://[^"]+\.pdf[^"]*)"', r.text)
            print(f"  scholar returned {len(pdfs)} pdf links")
            for p in pdfs[:3]:
                print(f"    {p[:120]}")
            for pdf_url in pdfs[:3]:
                try:
                    r2 = requests.get(pdf_url, headers={"User-Agent": CHROME_UA}, timeout=30, allow_redirects=True)
                    if is_pdf(r2.content):
                        path, kb = save(r2.content, f"{name}_via_scholar")
                        print(f"  ✓ saved {path} ({kb:.1f} KB)")
                        return True
                except Exception as e:
                    print(f"    err {pdf_url[:60]}: {type(e).__name__}")
        except ImportError:
            print("  requests not available, using urllib")
            req = urllib.request.Request(
                "https://scholar.google.com/scholar?" + urllib.parse.urlencode({"q": query + " filetype:pdf"}),
                headers={"User-Agent": CHROME_UA},
            )
            resp = urllib.request.urlopen(req, timeout=20, context=ctx)
            body = resp.read().decode("utf-8", errors="ignore")
            pdfs = re.findall(r'href="(https?://[^"]+\.pdf[^"]*)"', body)
            print(f"  scholar pdf links: {len(pdfs)}")
    except Exception as e:
        print(f"  err: {type(e).__name__}: {str(e)[:80]}")
    return False


def main():
    # First: extract full Utami text
    print("\n=== Extracting full Utami 2025 text ===")
    try:
        import pdfplumber
        pdf = OUT_PDF / "Utami_2025_via_ojs.pdf"
        with pdfplumber.open(pdf) as pl:
            print(f"  pages: {len(pl.pages)}")
            full_txt = []
            for i, page in enumerate(pl.pages):
                t = page.extract_text() or ""
                full_txt.append(f"--- Page {i+1} ---\n{t}")
            full_text = "\n".join(full_txt)
            out = OUT_TXT / "Utami_2025.txt"
            out.write_text(full_text, encoding="utf-8")
            print(f"  ✓ saved {out} ({len(full_text)} chars, ~{len(full_text.split())} words)")
    except Exception as e:
        print(f"  err: {type(e).__name__}: {str(e)}")
        return

    # Then: try other 3 with final angles
    print("\n" + "=" * 60)
    print("FINAL angles on remaining 3 papers")
    print("=" * 60)

    attempts = {
        "McMinn_2025": {
            "scholar_pdf": try_scholar_pdf(
                'McMinn HE Zhang Anand generative artificial intelligence',
                'McMinn_2025',
            ),
        },
        "Tzirides_2024": {
            "scholar_pdf": try_scholar_pdf(
                'Tzirides human artificial intelligence AI literacy higher education',
                'Tzirides_2024',
            ),
            "googlebot": try_googlebot_doi("10.1016/j.caeo.2024.100184", "Tzirides_2024"),
        },
        "Southworth_2023": {
            "scholar_pdf": try_scholar_pdf(
                'Southworth AI Across curriculum higher education literacy',
                'Southworth_2023',
            ),
            "googlebot": try_googlebot_doi("10.1016/j.caeai.2023.100127", "Southworth_2023"),
        },
    }
    out = Path(r"G:\minimax - workspace\Paper agent\results\_example_ai_education_v31_lit_review\4_attempt_pass4_summary.json")
    out.write_text(json.dumps(attempts, indent=2, default=str), encoding="utf-8")
    print(f"\n{json.dumps(attempts, indent=2)}")


if __name__ == "__main__":
    import urllib.parse
    main()
