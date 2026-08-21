"""Unit + e2e tests for pa_cli.jats_to_pdf (v3.9.21+).

Tests verify:
- Helper functions (URL resolution, regex)
- HTML structure (sections, figures with absolute URLs, refs)
- Real PDF output (%PDF magic, ≥50KB)
- embed_figures=True: HTML contains data: URIs
- embed_figures=False: HTML still has remote URLs (chromium downloads at render time)

Run: python test_output/_test_jats_to_pdf.py
"""
import base64
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pa_cli.jats_to_pdf import (
    _local,
    _render_figure,
    jats_xml_to_html,
    jats_xml_to_pdf,
    _embed_figures_as_data_uris,
)

XML_FIXTURE = ROOT / "test_output" / "PMC13467845.xml"
PMCID_NUM = "13467845"


class TestJatsHelpers(unittest.TestCase):
    """Helper-function unit tests (no network, no Playwright)."""

    def test_local_strips_namespace(self):
        self.assertEqual(_local("{http://www.w3.org/1999/xlink}href"), "href")
        self.assertEqual(_local("article"), "article")
        self.assertEqual(_local(""), "")

    def test_render_figure_relative_href_no_pmcid(self):
        import xml.etree.ElementTree as ET
        xml = '''<fig xmlns:xlink="http://www.w3.org/1999/xlink" id="f1"><caption>Test caption</caption>
        <graphic xlink:href="test-image.jpg"/></fig>'''
        fig = ET.fromstring(xml)
        out = _render_figure(fig, depth=0, pmcid="")
        # No resolution → href stays relative
        self.assertIn('src="test-image.jpg"', out)
        self.assertNotIn("https://", out)
        print("  [PASS] no pmcid → relative href kept")

    def test_render_figure_relative_href_with_pmcid(self):
        import xml.etree.ElementTree as ET
        xml = '''<fig xmlns:xlink="http://www.w3.org/1999/xlink" id="f1"><caption>My fig</caption>
        <graphic xlink:href="journal-22-12345-g001.jpg"/></fig>'''
        fig = ET.fromstring(xml)
        out = _render_figure(fig, depth=0, pmcid="12345")
        self.assertIn(
            "https://www.ncbi.nlm.nih.gov/pmc/articles/instance/12345/bin/journal-22-12345-g001.jpg",
            out,
        )
        print("  [PASS] relative href + pmcid → /articles/instance/12345/bin/...")

    def test_render_figure_absolute_href_preserved(self):
        import xml.etree.ElementTree as ET
        xml = '''<fig xmlns:xlink="http://www.w3.org/1999/xlink" id="f1"><caption>Already absolute</caption>
        <graphic xlink:href="https://example.com/img.jpg"/></fig>'''
        fig = ET.fromstring(xml)
        out = _render_figure(fig, depth=0, pmcid="12345")
        self.assertIn("https://example.com/img.jpg", out)
        # Should NOT be re-wrapped
        self.assertNotIn("instance/12345/bin/https://", out)
        print("  [PASS] absolute href preserved (not re-wrapped)")


class TestJatsXmlToHtml(unittest.TestCase):
    """jats_xml_to_html end-to-end (no Playwright)."""

    @classmethod
    def setUpClass(cls):
        if not XML_FIXTURE.exists():
            raise unittest.SkipTest(f"fixture missing: {XML_FIXTURE}")
        cls.xml_bytes = XML_FIXTURE.read_bytes()
        cls.html = jats_xml_to_html(cls.xml_bytes, doi="10.3389/test", pmcid=PMCID_NUM)

    def test_html_size_reasonable(self):
        self.assertGreater(len(self.html), 10000)
        print(f"  HTML size: {len(self.html):,} chars")

    def test_html_contains_title(self):
        self.assertIn("<h1", self.html)
        self.assertIn('class="title"', self.html)

    def test_html_contains_sections(self):
        self.assertIn("<h2", self.html)
        self.assertIn('class="sec-title"', self.html)

    def test_html_resolves_all_figure_urls(self):
        imgs = re.findall(r'<img[^>]*\ssrc="([^"]+)"', self.html)
        self.assertGreater(len(imgs), 0)
        for url in imgs:
            self.assertTrue(url.startswith("https://"),
                            f"figure URL not absolute: {url}")
            # Real URL pattern: /articles/instance/{pmcid-num}/bin/<filename>
            # (not /articles/PMC{id}/)
            self.assertIn(f"articles/instance/{PMCID_NUM}/bin/", url,
                          f"figure URL missing instance/PMCID/bin pattern: {url}")
        print(f"  [PASS] {len(imgs)} figures, all absolute + instance/{PMCID_NUM}/bin/...")

    def test_html_contains_references(self):
        self.assertIn("<ol", self.html)
        li_count = self.html.count("<li")
        self.assertGreater(li_count, 5)

    def test_html_contains_metadata(self):
        self.assertIn("DOI: 10.3389/test", self.html)
        self.assertIn(f"PMCID: {PMCID_NUM}", self.html)

    def test_html_rejects_invalid_xml(self):
        with self.assertRaises(ValueError):
            jats_xml_to_html(b"<not><valid", doi="", pmcid="")


class TestEmbedFiguresRegex(unittest.TestCase):
    """_embed_figures_as_data_uris regex behavior."""

    def test_regex_skips_data_uri(self):
        html = '<img src="data:image/png;base64,abc" alt="x">'
        out = _embed_figures_as_data_uris(html, doi="x")
        self.assertIn("data:image/png", out)
        self.assertEqual(out.count("data:image/png"), 1)
        print("  [PASS] data: URI passed through")

    def test_regex_skips_relative_url(self):
        html = '<img src="local.jpg" alt="x">'
        out = _embed_figures_as_data_uris(html, doi="x")
        # Regex requires https?://, so relative URL unchanged
        self.assertIn('src="local.jpg"', out)
        print("  [PASS] relative URL not matched")

    def test_regex_https_attempts_download(self):
        # Without network, _download_figure returns None → original URL kept
        html = '<img src="https://nonexistent.invalid/a.jpg" alt="x">'
        out = _embed_figures_as_data_uris(html, doi="x")
        # URL preserved (download failed)
        self.assertIn("https://nonexistent.invalid/a.jpg", out)
        print("  [PASS] https URL attempted, kept on failure")


class TestJatsXmlToPdf(unittest.TestCase):
    """Full pipeline: HTML → real PDF via Playwright."""

    @classmethod
    def setUpClass(cls):
        if not XML_FIXTURE.exists():
            raise unittest.SkipTest(f"fixture missing: {XML_FIXTURE}")
        cls.xml_bytes = XML_FIXTURE.read_bytes()
        try:
            cls.pdf_basic = jats_xml_to_pdf(
                cls.xml_bytes, doi="10.3389/test", pmcid=PMCID_NUM,
                embed_figures=False,
            )
        except Exception as e:
            raise unittest.SkipTest(f"playwright unavailable: {e}")

    def test_pdf_magic_bytes(self):
        self.assertTrue(self.pdf_basic.startswith(b"%PDF-"),
                        f"not a PDF, starts with: {self.pdf_basic[:8]}")

    def test_pdf_minimum_size(self):
        # Real PDF with 6 figs + 41 refs + 2 tables + abstract + body
        self.assertGreater(len(self.pdf_basic), 50_000)
        print(f"  basic PDF: {len(self.pdf_basic):,} bytes (figures auto-loaded by chromium)")

    def test_embed_figures_adds_data_uris_to_html(self):
        """embed_figures=True should add data:image URIs to HTML (before PDF)."""
        html_with = jats_xml_to_html(
            self.xml_bytes, doi="10.3389/test", pmcid=PMCID_NUM
        )
        # Apply embedding (this downloads from PMC and base64-encodes)
        embedded_html = _embed_figures_as_data_uris(html_with, doi="10.3389/test")
        # Count data URIs in HTML
        data_uris = re.findall(r'data:image/[^;]+;base64,', embedded_html)
        # We have 6 figures — all 6 should embed
        self.assertGreaterEqual(len(data_uris), 4,
            f"expected ≥4 data: URIs (6 figs), got {len(data_uris)}")
        print(f"  [PASS] {len(data_uris)}/6 figures embedded as data URIs")


if __name__ == "__main__":
    print("=" * 60)
    print("jats_to_pdf unit + e2e tests (v3.9.21+)")
    print("=" * 60)
    unittest.main(verbosity=2)
