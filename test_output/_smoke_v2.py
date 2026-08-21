"""Smoke test the fixed URL pattern."""
import sys
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pa_cli.jats_to_pdf import jats_xml_to_html, jats_xml_to_pdf

xml = (ROOT / "test_output" / "PMC13467845.xml").read_bytes()
html = jats_xml_to_html(xml, doi="10.3389/fendo.2026.1798827", pmcid="13467845")

imgs = re.findall(r'<img[^>]*\ssrc="([^"]+)"', html)
print("img src URLs:")
for u in imgs:
    print(" ", u)

# Now test embed_figures
print("\nTesting embed_figures...")
import time
t0 = time.time()
pdf = jats_xml_to_pdf(xml, doi="10.3389/fendo.2026.1798827", pmcid="13467845", embed_figures=True)
t1 = time.time()
out = ROOT / "test_output" / "PMC13467845_v2.pdf"
out.write_bytes(pdf)
print(f"  size: {len(pdf):,} bytes, time: {t1-t0:.1f}s")
print(f"  saved: {out}")
print(f"  magic: {pdf[:8]}")
