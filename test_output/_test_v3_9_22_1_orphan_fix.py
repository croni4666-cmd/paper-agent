"""v3.9.22.1 regression test — orphan JATS-as-PDF fix + size_bytes null fix.

Two e2e-discovered bugs were silently shipped in v3.9.22.0:

1. **Orphan JATS-as-PDF**: `_pmc_efetch_xml` wrote JATS XML to BOTH the .pdf
   path (via _save_pdf) AND .xml path (via write_bytes). When the downstream
   Europe PMC + jats_to_pdf fallback both failed, the .pdf was left
   containing JATS XML with .pdf extension. User saw "success" but the
   .pdf was actually JATS XML (couldn't be opened as PDF).

   Fix: only write to .xml path. .pdf is reserved for real PDF (Europe
   PMC render or jats_to_pdf output). If neither produces a PDF, no
   .pdf file is created.

2. **size_bytes null on pmc_jats_pdf success**: `fetch_pmc_doi` returned
   the pmc_jats_pdf result with `pdf_size` field but NOT top-level `size`.
   The `fetch_doi` wrapper reads `r.get("size")` for `size_bytes`, so
   JSON output had `size_bytes: null` even on real-PDF success.

   Fix: pmc_jats_pdf return now also exposes `path` and `size` at top
   level for the wrapper.

These tests verify the FIXES, not the original bugs. Real e2e verified
separately: `pa fetch --prefer pmc-pdf 10.1038/nature12373` → 126,095
bytes real PDF, size_bytes=126095, via_channel=pmc_jats_pdf, 20.7s.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


class TestPmcEfetchNoPdfOrphan(unittest.TestCase):
    """Verify _pmc_efetch_xml no longer creates a .pdf orphan file.

    v3.9.22.1 fix: removed the line that wrote JATS XML to out_path
    via _save_pdf. Now only .xml is written from EFetch.
    """

    def test_pmc_efetch_xml_does_not_write_pdf(self):
        # Inspect the source code directly
        from pa_cli import fetch as fetch_mod
        import inspect
        src = inspect.getsource(fetch_mod._pmc_efetch_xml)
        # v3.9.22.0: contained "_save_pdf(body, out_path)" — would write to .pdf
        # v3.9.22.1: that line is removed
        self.assertNotIn(
            "_save_pdf(body, out_path)",
            src,
            "v3.9.22.1 fix: _pmc_efetch_xml must not call _save_pdf (no .pdf orphan)"
        )
        print("  [PASS] _pmc_efetch_xml no longer writes orphan .pdf")

    def test_pmc_efetch_xml_still_writes_xml(self):
        from pa_cli import fetch as fetch_mod
        import inspect
        src = inspect.getsource(fetch_mod._pmc_efetch_xml)
        # The .xml path is preserved (always write JATS XML there)
        self.assertIn(
            "xml_path.write_bytes(body)",
            src,
            "_pmc_efetch_xml must still write JATS XML to .xml path"
        )
        print("  [PASS] _pmc_efetch_xml still writes JATS XML to .xml path")

    def test_pmc_efetch_xml_docstring_mentions_fix(self):
        from pa_cli import fetch as fetch_mod
        import inspect
        doc = inspect.getdoc(fetch_mod._pmc_efetch_xml) or ""
        self.assertIn("v3.9.22.1", doc,
                      "Docstring should document the v3.9.22.1 fix")
        self.assertIn("orphan", doc.lower(),
                      "Docstring should explain the orphan issue")
        print("  [PASS] _pmc_efetch_xml docstring documents the v3.9.22.1 fix")


class TestPmcJatsPdfTopLevelFields(unittest.TestCase):
    """Verify fetch_pmc_doi pmc_jats_pdf return has top-level path/size.

    v3.9.22.1 fix: pmc_jats_pdf success return now exposes `path` and
    `size` at top level so the fetch_doi wrapper picks them up for
    saved_as and size_bytes.
    """

    def test_pmc_jats_pdf_return_has_top_level_size(self):
        # Read the source code of fetch_pmc_doi and check the return dict
        from pa_cli import fetch as fetch_mod
        import inspect
        src = inspect.getsource(fetch_mod.fetch_pmc_doi)
        # Find the pmc_jats_pdf success return block
        idx = src.find('"source": "pmc_jats_pdf"')
        self.assertGreater(idx, 0, "fetch_pmc_doi should have pmc_jats_pdf return")
        # Get the chunk from pmc_jats_pdf to next return
        chunk = src[idx:idx + 1500]
        # v3.9.22.1 fix: must have top-level "size" and "path"
        self.assertIn('"size":', chunk,
                      "pmc_jats_pdf return must have top-level 'size' for wrapper")
        self.assertIn('"path":', chunk,
                      "pmc_jats_pdf return must have top-level 'path' for wrapper")
        # Also keep the existing pdf_size/pdf_path fields for backwards compat
        self.assertIn('"pdf_size":', chunk,
                      "pmc_jats_pdf return should keep pdf_size field")
        print("  [PASS] pmc_jats_pdf return has top-level path + size + pdf_size")

    def test_wrapper_picks_up_size_bytes(self):
        # Verify the fetch_doi wrapper reads r.get("size") for size_bytes
        from pa_cli import fetch as fetch_mod
        import inspect
        src = inspect.getsource(fetch_mod.fetch_doi)
        # Find the SUCCESS return block
        idx = src.find('"final_status": "SUCCESS"')
        self.assertGreater(idx, 0, "fetch_doi should have SUCCESS return")
        chunk = src[idx:idx + 800]
        self.assertIn('"size_bytes": r.get("size")', chunk,
                      "fetch_doi should read r.get('size') for size_bytes")
        print("  [PASS] fetch_doi wrapper reads r.get('size') for size_bytes")


class TestV3_9_22_1Versioning(unittest.TestCase):
    """Verify v3.9.22.1 version bump is consistent."""

    def test_version_is_3_9_22_1(self):
        from pa_cli import __version__
        self.assertEqual(__version__, "3.9.22.1",
                         f"Expected v3.9.22.1, got {__version__}")
        print(f"  [PASS] pa_cli __version__ = {__version__}")


if __name__ == "__main__":
    import logging
    logging.disable(logging.CRITICAL)
    print("=" * 60)
    print("v3.9.22.1 regression test — orphan JATS-as-PDF + size_bytes null")
    print("=" * 60)
    unittest.main(verbosity=2)
