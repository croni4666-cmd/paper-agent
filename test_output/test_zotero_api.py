"""test_zotero_api.py — unit + e2e tests for pa_cli.zotero_api (v3.9.15.0, [P2-17] + [P2-18])

Coverage:
    Unit tests (5):
        T1. normalize_doi() — same matrix as zotero_local
        T2. parse_bibtex_for_doi() — extracts entries with DOIs from .bib
        T3. bibtex_to_zotero_item() — converts Bibtex entry to Zotero API template
        T4. check_dois_in_library() — returns set of DOIs already in library (mocked)
        T5. push_items() — idempotent push, returns 4-bucket result
        T6. search_library() — returns parsed items (mocked)
    E2E test (1):
        T7. get_client() raises ValueError on missing API key / library_id

Total: 7 tests.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

_PAPER_AGENT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PAPER_AGENT_DIR))

from pa_cli import zotero_api  # noqa: E402


# ─────────────────────────────────────────────────────────────────
# Unit tests
# ─────────────────────────────────────────────────────────────────
class TestNormalizeDOI(unittest.TestCase):
    """T1: normalize_doi() — same logic as zotero_local (consistency)."""

    def test_normalize_matrix(self):
        cases = [
            ("10.1038/nature12373", "10.1038/nature12373"),
            ("https://doi.org/10.1038/nature12373", "10.1038/nature12373"),
            ("doi:10.1038/nature12373", "10.1038/nature12373"),
            ("DOI: 10.1038/NATURE12373", "10.1038/nature12373"),
            ("10.1038/nature12373.", "10.1038/nature12373"),
            ("", None),
            (None, None),
            ("not a doi", None),
        ]
        for raw, expected in cases:
            actual = zotero_api.normalize_doi(raw)
            self.assertEqual(actual, expected, f"normalize_doi({raw!r}) returned {actual!r}")


class TestParseBibtex(unittest.TestCase):
    """T2: parse_bibtex_for_doi() — minimal Bibtex DOI extractor."""

    BIBTEX = r"""
@article{key1,
  author = {Smith, J.},
  title = {First Paper},
  doi = {10.1038/nature12373},
  year = {2020}
}

@article{key2,
  author = {Doe, A.},
  title = {Second Paper},
  DOI = "10.1126/science.1259855",
  year = {2021}
}

@article{key3,
  author = {Lee, K.},
  title = {Third Paper},
  year = {2022}    % no DOI, should be skipped
}

@book{key4,
  author = {Wang, L.},
  title = {A Book},
  doi = {10.1145/3592979.3593406}
}
"""

    def test_parse_returns_3_entries(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".bib", delete=False, encoding="utf-8"
        ) as f:
            f.write(self.BIBTEX)
            path = Path(f.name)
        try:
            entries = zotero_api.parse_bibtex_for_doi(path)
            self.assertEqual(len(entries), 3)  # 3 with DOIs (key3 skipped)
            keys = {e["key"] for e in entries}
            self.assertIn("key1", keys)
            self.assertIn("key2", keys)
            self.assertIn("key4", keys)
            # DOI is normalized
            dois = {e["doi"] for e in entries}
            self.assertIn("10.1038/nature12373", dois)
        finally:
            path.unlink(missing_ok=True)

    def test_parse_missing_file(self):
        entries = zotero_api.parse_bibtex_for_doi(Path("/nonexistent/refs.bib"))
        self.assertEqual(entries, [])


class TestBibtexToZoteroItem(unittest.TestCase):
    """T3: bibtex_to_zotero_item() — converts Bibtex entry to Zotero API template."""

    def test_article_to_journal_article(self):
        entry = {
            "key": "smith2020",
            "type": "article",
            "title": "Test Paper",
            "doi": "10.1038/nature12373",
            "author": "Smith, J. and Doe, A.",
            "year": "2020",
            "journal": "Nature",
        }
        item = zotero_api.bibtex_to_zotero_item(entry)
        self.assertEqual(item["itemType"], "journalArticle")
        self.assertEqual(item["title"], "Test Paper")
        self.assertEqual(item["DOI"], "10.1038/nature12373")
        self.assertEqual(item["date"], "2020")
        self.assertEqual(item["publicationTitle"], "Nature")
        self.assertEqual(item["url"], "https://doi.org/10.1038/nature12373")
        # Authors split on " and "
        self.assertEqual(len(item["creators"]), 2)
        self.assertEqual(item["creators"][0]["name"], "Smith, J.")

    def test_inproceedings_to_conference_paper(self):
        entry = {
            "key": "k1",
            "type": "inproceedings",
            "title": "Conf Paper",
            "doi": "10.1109/foo.2020",
            "year": "2020",
        }
        item = zotero_api.bibtex_to_zotero_item(entry)
        self.assertEqual(item["itemType"], "conferencePaper")

    def test_book_to_book(self):
        entry = {
            "key": "b1",
            "type": "book",
            "title": "A Book",
            "doi": "10.1234/book",
            "year": "2020",
            "publisher": "Springer",
        }
        item = zotero_api.bibtex_to_zotero_item(entry)
        self.assertEqual(item["itemType"], "book")
        self.assertEqual(item["publisher"], "Springer")


class TestCheckDoisInLibrary(unittest.TestCase):
    """T4: check_dois_in_library() — uses pyzotero.check_items() under the hood."""

    def test_returns_existing_dois(self):
        # Mock pyzotero.Zotero client
        mock_client = MagicMock()
        # check_items returns a list, with non-None for items that exist
        mock_client.check_items.return_value = [
            {"DOI": "10.1038/nature12373"},  # exists
            None,                            # doesn't exist
            {"DOI": "10.1126/science.1259855"},  # exists
        ]
        existing = zotero_api.check_dois_in_library(
            mock_client,
            ["10.1038/nature12373", "10.9999/not.exist", "10.1126/science.1259855"],
        )
        self.assertEqual(
            existing,
            {"10.1038/nature12373", "10.1126/science.1259855"},
        )
        # Verify the call shape: list of dicts with DOI key
        called = mock_client.check_items.call_args[0][0]
        self.assertEqual(called, [
            {"DOI": "10.1038/nature12373"},
            {"DOI": "10.9999/not.exist"},
            {"DOI": "10.1126/science.1259855"},
        ])

    def test_returns_empty_on_exception(self):
        # Network error or auth error → empty set
        mock_client = MagicMock()
        mock_client.check_items.side_effect = Exception("auth failed")
        existing = zotero_api.check_dois_in_library(mock_client, ["10.1038/x"])
        self.assertEqual(existing, set())


class TestPushItems(unittest.TestCase):
    """T5: push_items() — idempotent, 4-bucket result."""

    SAMPLE_BIBTEX = [
        {
            "key": "new1",
            "type": "article",
            "title": "New Paper 1",
            "doi": "10.1038/new1",
            "author": "Author A",
            "year": "2024",
        },
        {
            "key": "existing1",
            "type": "article",
            "title": "Existing Paper",
            "doi": "10.1038/existing1",
            "author": "Author B",
            "year": "2023",
        },
    ]

    def test_idempotent_push(self):
        # Mock client: existing1 is already in library, new1 is not
        mock_client = MagicMock()
        mock_client.check_items.return_value = [
            None,                            # new1 — not in library
            {"DOI": "10.1038/existing1"},  # existing1 — in library
        ]
        # create_items returns the new items
        mock_client.create_items.return_value = [
            {"successful": {"key": "ZOTERO_NEW1", "DOI": "10.1038/new1"}},
        ]

        result = zotero_api.push_items(
            client=mock_client,
            bibtex_entries=self.SAMPLE_BIBTEX,
            skip_existing=True,
        )
        self.assertEqual(result["n_total"], 2)
        self.assertEqual(result["n_pushed"], 1)
        self.assertEqual(result["n_skipped"], 1)  # existing1
        self.assertEqual(result["n_failed"], 0)
        # Verify skipped result
        skipped = [r for r in result["results"] if r.get("status") == "skipped" or r.get("reason") == "already_in_library"]
        self.assertEqual(len(skipped), 1)
        self.assertEqual(skipped[0]["key"], "existing1")

    def test_no_skip_existing_pushes_all(self):
        mock_client = MagicMock()
        mock_client.check_items.return_value = []  # doesn't matter when skip_existing=False
        mock_client.create_items.return_value = [
            {"successful": {"key": "Z1"}},
            {"successful": {"key": "Z2"}},
        ]
        result = zotero_api.push_items(
            client=mock_client,
            bibtex_entries=self.SAMPLE_BIBTEX,
            skip_existing=False,
        )
        self.assertEqual(result["n_total"], 2)
        self.assertEqual(result["n_pushed"], 2)
        self.assertEqual(result["n_skipped"], 0)

    def test_create_items_failure_marks_failed(self):
        mock_client = MagicMock()
        mock_client.check_items.return_value = [None, None]
        mock_client.create_items.return_value = [
            {"successful": {"key": "Z1"}},
            {"failed": {"code": 400, "message": "Bad request"}},
        ]
        result = zotero_api.push_items(
            client=mock_client,
            bibtex_entries=self.SAMPLE_BIBTEX,
            skip_existing=True,
        )
        self.assertEqual(result["n_pushed"], 1)
        self.assertEqual(result["n_failed"], 1)
        # Failed entry has error
        failed = [r for r in result["results"] if r.get("status") == "failed"]
        self.assertEqual(len(failed), 1)
        self.assertIn("error", failed[0])


class TestSearchLibrary(unittest.TestCase):
    """T6: search_library() — parses Zotero API response."""

    def test_search_returns_parsed_items(self):
        mock_client = MagicMock()
        mock_client.search.return_value = [
            {
                "key": "Z123",
                "title": "Test Paper",
                "creators": [{"name": "Smith, J."}],
                "date": "2020",
                "DOI": "10.1038/nature12373",
                "itemType": "journalArticle",
            },
            {
                "key": "Z124",
                "title": "Another Paper",
                "creators": [],
                "date": "2021",
                "DOI": "",
                "itemType": "book",
            },
        ]
        results = zotero_api.search_library(mock_client, "Test", limit=10)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["title"], "Test Paper")
        self.assertEqual(results[0]["creators"], [{"name": "Smith, J."}])
        # Verify the search call shape
        mock_client.search.assert_called_once_with("Test", qmode="titleCreatorYear", limit=10)

    def test_search_empty_query(self):
        mock_client = MagicMock()
        results = zotero_api.search_library(mock_client, "", limit=10)
        self.assertEqual(results, [])
        mock_client.search.assert_not_called()


# ─────────────────────────────────────────────────────────────────
# E2E: env var validation
# ─────────────────────────────────────────────────────────────────
class TestE2EGetClient(unittest.TestCase):
    """T7: get_client() raises ValueError on missing creds."""

    def setUp(self):
        # Clear env vars
        self._saved_key = os.environ.pop("ZOTERO_API_KEY", None)
        self._saved_id = os.environ.pop("ZOTERO_LIBRARY_ID", None)

    def tearDown(self):
        # Restore
        if self._saved_key is not None:
            os.environ["ZOTERO_API_KEY"] = self._saved_key
        if self._saved_id is not None:
            os.environ["ZOTERO_LIBRARY_ID"] = self._saved_id

    def test_missing_api_key_raises(self):
        os.environ["ZOTERO_LIBRARY_ID"] = "12345"
        # ZOTERO_API_KEY unset
        with self.assertRaises(ValueError) as ctx:
            zotero_api.get_client()
        self.assertIn("API key", str(ctx.exception))

    def test_missing_library_id_raises(self):
        os.environ["ZOTERO_API_KEY"] = "fake_key"
        # ZOTERO_LIBRARY_ID unset
        with self.assertRaises(ValueError) as ctx:
            zotero_api.get_client()
        self.assertIn("library ID", str(ctx.exception))

    def test_both_present_builds_client(self):
        os.environ["ZOTERO_API_KEY"] = "fake_key"
        os.environ["ZOTERO_LIBRARY_ID"] = "12345"
        # Should not raise
        client = zotero_api.get_client()
        # pyzotero's Zotero client has these attrs
        self.assertIsNotNone(client)


if __name__ == "__main__":
    unittest.main(verbosity=2)
