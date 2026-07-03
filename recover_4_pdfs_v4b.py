#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pass 4b — last-ditch with strict per-try timeouts (10s)."""
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
OUT_PDF.mkdir(parents=True, exist_ok=True)

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
GBOT = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"


def is_pdf(b):
    return b[:4] == b"%PDF" and len(b) > 5000


def save(b, name):
    p = OUT_PDF / f"{name}.pdf"
    p.write_bytes(b)
    return p, len(b) / 1024


def try_one(url, headers, name, timeout=10):
    try:
        req = urllib.request.Request(url, headers=headers)
        resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
        body = resp.read()
        ct = resp.headers.get("Content-Type", "")
        if "pdf" in ct and is_pdf(body):
            p, kb = save(body, name)
            print(f"  ✓ {kb:.1f} KB via {url[:80]}")
            return True
        else:
            print(f"  {url[:80]}: ct={ct} size={len(body)} magic={body[:4]!r}")
    except Exception as e:
        print(f"  {url[:80]}: {type(e).__name__}: {str(e)[:50]}")
    return False


def main():
    results = {}
    # === McMinn (T&F CF-protected)
    print("=== McMinn 2025 — T&F ===")
    results["McMinn_2025"] = {}
    results["McMinn_2025"]["direct_doi"] = try_one(
        "https://doi.org/10.1080/17516234.2024.2447195", {"User-Agent": UA}, "McMinn_2025_via_doi"
    )
    results["McMinn_2025"]["googlebot_doi"] = try_one(
        "https://doi.org/10.1080/17516234.2024.2447195", {"User-Agent": GBOT, "Accept": "application/pdf"}, "McMinn_2025_via_gbot"
    )
    results["McMinn_2025"]["researchgate_search"] = try_one(
        "https://www.researchgate.net/publication/search?q=McMinn+HE+Zhang+Anand+generative+artificial+intelligence+higher+education",
        {"User-Agent": UA, "Accept": "*/*"},
        "McMinn_2025_via_rg",
    )
    # === Tzirides (Elsevier)
    print("\n=== Tzirides 2024 — Elsevier ===")
    results["Tzirides_2024"] = {}
    results["Tzirides_2024"]["direct_doi"] = try_one(
        "https://doi.org/10.1016/j.caeo.2024.100184", {"User-Agent": UA}, "Tzirides_2024_via_doi"
    )
    results["Tzirides_2024"]["googlebot_doi"] = try_one(
        "https://doi.org/10.1016/j.caeo.2024.100184", {"User-Agent": GBOT, "Accept": "application/pdf"}, "Tzirides_2024_via_gbot"
    )
    results["Tzirides_2024"]["elsevier_sciencedirect"] = try_one(
        "https://www.sciencedirect.com/science/article/pii/S2666557324000247/pdf?md5=&pid=1-s2.0-S2666557324000247-main.pdf",
        {"User-Agent": UA},
        "Tzirides_2024_via_sd",
    )
    # === Southworth (Elsevier)
    print("\n=== Southworth 2023 — Elsevier ===")
    results["Southworth_2023"] = {}
    results["Southworth_2023"]["direct_doi"] = try_one(
        "https://doi.org/10.1016/j.caeai.2023.100127", {"User-Agent": UA}, "Southworth_2023_via_doi"
    )
    results["Southworth_2023"]["googlebot_doi"] = try_one(
        "https://doi.org/10.1016/j.caeai.2023.100127", {"User-Agent": GBOT, "Accept": "application/pdf"}, "Southworth_2023_via_gbot"
    )
    results["Southworth_2023"]["elsevier_sciencedirect"] = try_one(
        "https://www.sciencedirect.com/science/article/pii/S2666920X23000061/pdf?md5=&pid=1-s2.0-S2666920X23000061-main.pdf",
        {"User-Agent": UA},
        "Southworth_2023_via_sd",
    )

    out = Path(r"G:\minimax - workspace\Paper agent\results\_example_ai_education_v31_lit_review\4_attempt_pass4_summary.json")
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\n{json.dumps(results, indent=2)}")
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
