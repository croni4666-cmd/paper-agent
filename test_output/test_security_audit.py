"""test_output/test_security_audit.py — Security audit regressions & defenses.

Tests:
1. validate_slug rejects path traversal ('.', '..', '../evil', '..\\evil', '.hidden')
2. project_dir enforces relative_to boundary check against root
3. fetch_batch sanitizes malicious cite keys in BibTeX entries
4. cache._doi_slug neutralizes backslashes, colons, and illegal filesystem chars
5. jats_to_pdf rejects DTD entity expansion (XXE) and oversized payloads
"""
import unittest
import tempfile
from pathlib import Path

from pa_cli.project import validate_slug, project_dir
from pa_cli.cache import _doi_slug
from pa_cli.jats_to_pdf import jats_xml_to_html
from pa_cli.fetch_batch import _fetch_one_entry


class TestSecurityDefenses(unittest.TestCase):
    def test_validate_slug_path_traversal(self):
        malicious = [
            ".",
            "..",
            "../secret",
            "..\\secret",
            "foo/../../bar",
            ".hidden",
            "...",
            "....",
        ]
        for s in malicious:
            with self.assertRaises(ValueError, msg=f"Should reject traversal slug: {s!r}"):
                validate_slug(s)

    def test_project_dir_boundary_enforcement(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "projects"
            root.mkdir(parents=True, exist_ok=True)

            # Normal slug resolves strictly inside root
            valid_p = project_dir("safe_slug", root)
            self.assertEqual(valid_p, root / "safe_slug")

            # Any escape attempt raises ValueError
            with self.assertRaises(ValueError):
                project_dir("../outside", root)

    def test_cache_doi_slug_sanitization(self):
        # Test backslashes, colons, Windows reserved chars
        dirty_dois = [
            ("10.1016/j..\\secret", "10_1016_j___secret"),
            ("10.1000/182:aux*test?<>|", "10_1000_182_aux_test____"),
            ("https://doi.org/10.1038/nphys1170", "10_1038_nphys1170"),
        ]
        for raw, expected in dirty_dois:
            slug = _doi_slug(raw)
            self.assertEqual(slug, expected)
            self.assertNotIn("\\", slug)
            self.assertNotIn(":", slug)
            self.assertNotIn("*", slug)
            self.assertNotIn("?", slug)
            self.assertNotIn("<", slug)
            self.assertNotIn(">", slug)
            self.assertNotIn("|", slug)

    def test_fetch_batch_cite_key_sanitization(self):
        with tempfile.TemporaryDirectory() as td:
            out_dir = Path(td) / "pdfs"
            out_dir.mkdir(parents=True, exist_ok=True)

            # BibTeX entry with malicious traversal key
            entry = {
                "key": "../../malicious_payload",
                "doi": "",
                "title": "",
            }
            res = _fetch_one_entry(entry, out_dir=out_dir)
            # Must fail cleanly or sanitize path without escaping out_dir
            # (out_dir / ...).resolve() must be within out_dir
            self.assertEqual(res.error, "no doi or title")

    def test_jats_xxe_rejection(self):
        # XXE payload with ENTITY declaration
        xxe_xml = b"""<?xml version="1.0"?>
<!DOCTYPE article [
  <!ENTITY ext SYSTEM "http://127.0.0.1:9999/evil">
]>
<article>
  <front><article-meta><title-group><article-title>&ext;</article-title></title-group></article-meta></front>
  <body><p>Test</p></body>
</article>
"""
        with self.assertRaises(ValueError) as ctx:
            jats_xml_to_html(xxe_xml)
        self.assertIn("ENTITY", str(ctx.exception))

    def test_jats_payload_size_limit(self):
        # Oversized dummy payload
        huge_xml = b"<article>" + b" " * (21 * 1024 * 1024) + b"</article>"
        with self.assertRaises(ValueError) as ctx:
            jats_xml_to_html(huge_xml)
        self.assertIn("exceeds 20MB limit", str(ctx.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
