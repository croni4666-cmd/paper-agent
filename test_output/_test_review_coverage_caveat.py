"""[P0-12] Smoke test: pa review output includes cite/abstract coverage caveat.

Verifies the [P0-12] acceptance criterion:
- pa review markdown output contains coverage caveat
  citing ROADMAP [P0-12]
  with English/Chinese coverage numbers
  with terminal verdict note

The test is a unit test (no network) that exercises
`build_review_markdown` with a synthetic corpus.
"""
import unittest
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, '.')

from pa_cli.review import synthesize


class TestReviewCoverageCaveat(unittest.TestCase):
    def setUp(self):
        self.corpus = [
            {
                "filename": "test_paper.pdf",
                "title": "A test paper about transformer attention",
                "author": "Test Author",
                "subject": "Test Journal, 2023",
                "doi": "10.1234/test.2023",
                "pages": 12,
                "word_count": 5000,
                "is_full_text": True,
                "abstract": "We propose a new transformer architecture...",
                "error": None,
            },
            {
                "filename": "abstract_only.pdf",
                "title": "Abstract-only paper",
                "author": "Another Author",
                "subject": "Some Conf, 2022",
                "doi": "10.1234/abstract.2022",
                "pages": 0,
                "word_count": 250,
                "is_full_text": False,
                "abstract": "",
                "error": None,
            },
        ]

    def test_review_contains_coverage_caveat(self):
        # Build a fake corpus directory
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            # Write a fake PDF (any text file works for testing the markdown template)
            (tmp_path / "test_paper.pdf").write_text("dummy", encoding="utf-8")
            (tmp_path / "abstract_only.pdf").write_text("dummy", encoding="utf-8")
            md = synthesize(tmp_path, template="v32")
        # Must contain the coverage caveat section
        self.assertIn("Coverage caveat", md)
        self.assertIn("[P0-12]", md)
        # Must contain English/Chinese numbers
        self.assertIn("47% cite", md)
        self.assertIn("21% cite", md)
        # Must contain terminal verdict
        self.assertIn("terminal", md.lower())

    def test_review_contains_open_issues(self):
        """Verify the existing open issues section still works."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "test_paper.pdf").write_text("dummy", encoding="utf-8")
            (tmp_path / "abstract_only.pdf").write_text("dummy", encoding="utf-8")
            md = synthesize(tmp_path, template="v32")
        self.assertIn("Open issues", md)


if __name__ == "__main__":
    unittest.main(verbosity=2)
