"""End-to-end test for jats_to_pdf: fetch PMC XML, convert with PMCID, verify PDF.

Verifies:
1. _render_figure now resolves relative xlink:href to full PMC URL
2. embed_figures=True downloads and base64-encodes figures (PDF grows)
3. PDF magic bytes are valid
"""
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pa_cli.jats_to_pdf import jats_xml_to_html, jats_xml_to_pdf, _embed_figures_as_data_uris

PMCID = "PMC13467845"
XML_PATH = ROOT / "test_output" / f"{PMCID}.xml"
PDF_NO_FIG = ROOT / "test_output" / f"{PMCID}_nofig.pdf"
PDF_WITH_FIG = ROOT / "test_output" / f"{PMCID}_withfig.pdf"

# 1. Fetch XML if missing
if not XML_PATH.exists():
    print(f"[fetch] {XML_PATH.name}...")
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pmc&id={PMCID[3:]}&rettype=xml"
    req = urllib.request.Request(url, headers={"User-Agent": "paper-agent-test/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    XML_PATH.write_bytes(data)
    print(f"  downloaded: {len(data)} bytes")
else:
    print(f"[reuse] {XML_PATH.name} ({XML_PATH.stat().st_size} bytes)")

xml_bytes = XML_PATH.read_bytes()

# 2. Render HTML with PMCID, check img src resolution
print("[html] render with pmcid=" + PMCID[3:])
html = jats_xml_to_html(xml_bytes, doi="10.3389/fendo.2026.1798827", pmcid=PMCID[3:])

# Find all <img src=...> tags
imgs = re.findall(r'<img[^>]*\ssrc="([^"]+)"', html)
print(f"  total <img> tags: {len(imgs)}")
relative = [u for u in imgs if not u.startswith("http")]
absolute = [u for u in imgs if u.startswith("http")]
print(f"  relative (BUG): {len(relative)}")
print(f"  absolute (FIXED): {len(absolute)}")
if relative:
    print(f"  FIRST RELATIVE: {relative[0]}")
if absolute:
    print(f"  FIRST ABSOLUTE: {absolute[0]}")
    # Verify the URL pattern
    if f"PMC{PMCID[3:]}/bin/" in absolute[0]:
        print("  [PASS] URL pattern is correct: /articles/PMC{}/bin/<filename>".format(PMCID[3:]))
    else:
        print(f"  [FAIL] URL pattern unexpected: {absolute[0]}")

# Save HTML for inspection
html_path = ROOT / "test_output" / f"{PMCID}.html"
html_path.write_text(html, encoding="utf-8")
print(f"  saved HTML: {html_path}")

# 3. Convert WITHOUT embed_figures (control)
print("[pdf-1] convert WITHOUT embed_figures (control)...")
import time
t0 = time.time()
pdf_nofig = jats_xml_to_pdf(xml_bytes, doi="10.3389/fendo.2026.1798827", pmcid=PMCID[3:], embed_figures=False)
t1 = time.time()
PDF_NO_FIG.write_bytes(pdf_nofig)
print(f"  size: {len(pdf_nofig):,} bytes, time: {t1-t0:.1f}s")
assert pdf_nofig.startswith(b"%PDF-"), "not a valid PDF"
print("  magic: %PDF OK")

# 4. Convert WITH embed_figures (downloads 6 figures from PMC)
print("[pdf-2] convert WITH embed_figures (downloads figures)...")
t0 = time.time()
try:
    pdf_withfig = jats_xml_to_pdf(xml_bytes, doi="10.3389/fendo.2026.1798827", pmcid=PMCID[3:], embed_figures=True)
    t1 = time.time()
    PDF_WITH_FIG.write_bytes(pdf_withfig)
    print(f"  size: {len(pdf_withfig):,} bytes, time: {t1-t0:.1f}s")
    assert pdf_withfig.startswith(b"%PDF-"), "not a valid PDF"

    # Check size diff: with figures should be LARGER (data URIs add bytes)
    diff = len(pdf_withfig) - len(pdf_nofig)
    pct = (diff / len(pdf_nofig)) * 100
    print(f"  size diff: {diff:+,} bytes ({pct:+.1f}%)")
    if diff > 0:
        print(f"  [PASS] embed_figures added bytes -> figures are embedded")
    else:
        print(f"  [WARN] embed_figures did NOT grow PDF -- check if downloads worked")
except Exception as e:
    print(f"  [ERROR] {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    pdf_withfig = b""

# 5. Test with INVALID XML
print("[error] test invalid XML handling...")
try:
    jats_xml_to_pdf(b"<not><valid", doi="x", pmcid="1")
    print("  [FAIL] should have raised")
except ValueError as e:
    print(f"  [PASS] ValueError raised: {e}")
except Exception as e:
    print(f"  [WARN] unexpected error type: {type(e).__name__}: {e}")

print("\n=== SUMMARY ===")
print(f"  XML: {XML_PATH} ({XML_PATH.stat().st_size:,} bytes)")
print(f"  HTML: {html_path} ({html_path.stat().st_size:,} bytes)")
print(f"  PDF (no figures): {PDF_NO_FIG} ({len(pdf_nofig):,} bytes)")
if pdf_withfig:
    print(f"  PDF (with figures): {PDF_WITH_FIG} ({len(pdf_withfig):,} bytes)")
    print(f"  Embedding delta: {len(pdf_withfig) - len(pdf_nofig):+,} bytes")
