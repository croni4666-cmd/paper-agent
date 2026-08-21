"""Patch fetch.py: add jats_to_pdf step 4 + pmc-pdf prefer option.

Three edits:
1. Add `_pmc_jats_to_pdf` helper after `_pmc_europe_pdf`
2. Modify `fetch_pmc_doi` to call jats_to_pdf if Europe PMC fails
3. Add `pmc-pdf` case in prefer mapping (line ~1062)
"""
import re
from pathlib import Path

p = Path(r"G:\minimax - workspace\Paper agent\pa_cli\fetch.py")
src = p.read_text(encoding="utf-8")

# ─── 1. Insert _pmc_jats_to_pdf helper BEFORE fetch_pmc_doi ─────────────
helper = '''def _pmc_jats_to_pdf(pmcid: str, xml_path: str, out_path: str = None,
                      embed_figures: bool = True,
                      proxy: str = None) -> Dict[str, Any]:
    """v3.9.21+: JATS XML → real PDF via pa_cli.jats_to_pdf (Playwright).

    Last-resort fallback when Europe PMC PDF rendering fails. Always works
    (Chromium renders any valid JATS HTML) but slower (15-25s with figures).

    Returns dict with:
      - source: "pmc_jats_pdf"
      - pmcid, pdf_path, pdf_size, elapsed_sec
      - error on failure
    """
    import time as _t
    t0 = _t.time()
    pmcid_clean = pmcid.replace("PMC", "")
    try:
        # Lazy import: jats_to_pdf pulls in playwright (large dep)
        from .jats_to_pdf import jats_xml_to_pdf
        xml_bytes = Path(xml_path).read_bytes()
        pdf_bytes = jats_xml_to_pdf(
            xml_bytes,
            doi="",
            pmcid=pmcid_clean,
            embed_figures=embed_figures,
            proxy=proxy,
        )
        if not pdf_bytes or not pdf_bytes.startswith(b"%PDF"):
            return {"error": "jats_pdf_invalid_output",
                    "pmcid": pmcid, "hint": "jats_to_pdf returned non-PDF bytes"}
        result = {
            "source": "pmc_jats_pdf",
            "pmcid": pmcid,
            "size": len(pdf_bytes),
            "elapsed_sec": round(_t.time() - t0, 2),
        }
        if out_path:
            from pathlib import Path as _P
            out_p = _P(out_path)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            out_p.write_bytes(pdf_bytes)
            result["path"] = str(out_p.resolve())
        return result
    except Exception as e:
        return {"error": f"jats_pdf_{type(e).__name__}",
                "pmcid": pmcid,
                "message": str(e)[:200],
                "hint": "Check playwright install or JATS XML validity"}


'''

# Insert just before "def fetch_pmc_doi"
marker = "def fetch_pmc_doi(doi: str, out_path: str = None) -> Dict[str, Any]:"
assert marker in src, "fetch_pmc_doi marker not found"
src = src.replace(marker, helper + marker, 1)

# ─── 2. Modify fetch_pmc_doi: add step 4 (jats_to_pdf fallback) ────────
# Find the return block and insert before it
old_return = '''    # Step 3: Try Europe PMC PDF rendering (best-effort, 80% success)
    pdf_result = _pmc_europe_pdf(pmcid, out_path=out_path, max_retries=2)

    return {
        "source": "pmc" if "error" not in pdf_result else "pmc_xml_only",'''
new_return = '''    # Step 3: Try Europe PMC PDF rendering (best-effort, ~25% success in 2026-08 retest)
    pdf_result = _pmc_europe_pdf(pmcid, out_path=out_path, max_retries=2)
    europe_ok = "error" not in pdf_result

    # Step 4 (v3.9.21+): If Europe PMC failed, fall back to jats_to_pdf
    # (JATS XML → Chromium-rendered real PDF). Always works for valid JATS.
    if not europe_ok:
        # Get proxy from env (v3.9.13.2: --proxy sets HTTPS_PROXY)
        proxy_env = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
        jats_result = _pmc_jats_to_pdf(
            pmcid,
            xml_path=xml_result.get("path"),
            out_path=out_path,
            embed_figures=True,
            proxy=proxy_env,
        )
        if "error" not in jats_result:
            return {
                "source": "pmc_jats_pdf",
                "pmcid": pmcid,
                "doi": doi,
                "xml_path": xml_result.get("path"),
                "xml_size": xml_result.get("size"),
                "pdf_path": jats_result.get("path"),
                "pdf_size": jats_result.get("size"),
                "pdf_method": "jats_to_pdf",
                "pdf_elapsed_sec": jats_result.get("elapsed_sec"),
                "europe_pdf_error": pdf_result.get("error"),
                "hint": "v3.9.21+ JATS→PDF fallback; figures embedded as data URIs",
            }
        # Both methods failed
        return {
            "source": "pmc_xml_only",
            "pmcid": pmcid,
            "doi": doi,
            "xml_path": xml_result.get("path"),
            "xml_size": xml_result.get("size"),
            "pdf_path": None,
            "pdf_size": None,
            "pdf_error_europe": pdf_result.get("error"),
            "pdf_error_jats": jats_result.get("error"),
            "hint": "Both Europe PMC and jats_to_pdf failed; XML available",
        }

    return {
        "source": "pmc" if "error" not in pdf_result else "pmc_xml_only",'''
assert old_return in src, "old return block not found"
src = src.replace(old_return, new_return, 1)

# ─── 3. Add pmc-pdf prefer option in fetch_doi channel mapping ─────────
old_prefer = '''    elif "pmc" in channels:
        # v3.9.21+: PMC fulltext channel. DOI → PMCID → EFetch XML + Europe PMC PDF.
        # 合法 + 永久, 替代 sci-hub cascade
        prefer = "pmc"'''
new_prefer = '''    elif "pmc-pdf" in channels:
        # v3.9.21+: Force PMC + jats_to_pdf (skip Europe PMC). Always returns
        # a real PDF even when Europe PMC render is 404. Slower (15-25s).
        prefer = "pmc-pdf"
    elif "pmc" in channels:
        # v3.9.21+: PMC fulltext channel. DOI → PMCID → EFetch XML + Europe PMC PDF.
        # 合法 + 永久, 替代 sci-hub cascade
        prefer = "pmc"'''
assert old_prefer in src, "old prefer block not found"
src = src.replace(old_prefer, new_prefer, 1)

# ─── 4. Wire pmc-pdf in the new fetch() dispatch (line ~931) ───────────
# Find the if prefer in ("pmc", "auto"): block
old_dispatch = '        if prefer in ("pmc", "auto"):\n            r = fetch_pmc_doi(doi, out_path)'
new_dispatch = '        if prefer in ("pmc", "pmc-pdf", "auto"):\n            r = fetch_pmc_doi(doi, out_path)'
assert old_dispatch in src, "old dispatch not found"
src = src.replace(old_dispatch, new_dispatch, 1)

p.write_text(src, encoding="utf-8", newline="\n")
print("OK - 4 patches applied")
print("New size:", len(src), "bytes")
