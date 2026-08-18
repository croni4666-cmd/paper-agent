"""test_zotero_local.py — unit + e2e tests for pa_cli.zotero_local (v3.9.14.0, [P2-16])

Coverage:
    Unit tests (3):
        T1. normalize_doi() — full URL/strip/case/trailing-punct matrix
        T2. check_corpus() with pre-loaded library — 4-bucket correctness
        T3. extract_dois_from_bibtex() — `doi = {...}` and `doi = "..."`,
              case-insensitive field name, multi-entry file
    E2E test (1):
        T4. Build a minimal Zotero-schema SQLite in tmp, verify get_library_dois()
              returns the DOIs we inserted, then verify check_corpus() against
              a real corpus produces the right in_library/not_in_library split.
              Uses URI mode=ro for the read path.

Total: 4 tests, ~7 sub-assertions per test.
"""

from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

# Add pa_cli/ to path so we can import zotero_local directly
_PAPER_AGENT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PAPER_AGENT_DIR))

from pa_cli import zotero_local  # noqa: E402


# ─────────────────────────────────────────────────────────────────
# Unit tests
# ─────────────────────────────────────────────────────────────────
class TestNormalizeDOI(unittest.TestCase):
    """T1: normalize_doi() — full URL/strip/case/trailing-punct matrix."""

    CASES = [
        # (input, expected_output or None)
        ("10.1038/nature12373", "10.1038/nature12373"),       # raw DOI
        ("https://doi.org/10.1038/nature12373", "10.1038/nature12373"),
        ("http://dx.doi.org/10.1038/nature12373", "10.1038/nature12373"),
        ("DOI: 10.1038/nature12373", "10.1038/nature12373"),
        ("doi:10.1038/nature12373", "10.1038/nature12373"),
        ("10.1038/NATURE12373", "10.1038/nature12373"),       # case-insensitive
        ("10.1038/nature12373.", "10.1038/nature12373"),      # trailing punct
        ("10.1038/nature12373,", "10.1038/nature12373"),
        ("10.1038/nature12373 ;", "10.1038/nature12373"),
        ("  10.1038/nature12373  ", "10.1038/nature12373"),   # whitespace
        ("10.1126/science.1259855", "10.1126/science.1259855"),
        # Invalid inputs → None
        ("", None),
        (None, None),
        ("not a doi", None),
        ("10.short/abc", None),                                # prefix too short
        ("doi.org/10.1038/abc", None),                         # missing 10.
        ("https://example.com/10.1038/abc", None),             # not doi.org
    ]

    def test_normalize_matrix(self):
        for raw, expected in self.CASES:
            actual = zotero_local.normalize_doi(raw)
            self.assertEqual(
                actual, expected,
                f"normalize_doi({raw!r}) returned {actual!r}, expected {expected!r}"
            )


class TestCheckCorpus(unittest.TestCase):
    """T2: check_corpus() with pre-loaded library — 4-bucket correctness."""

    LIBRARY = {
        "10.1038/nature12373",
        "10.1126/science.1259855",
        "10.1145/3592979.3593406",  # a CHI paper
    }

    CORPUS = [
        # in_library
        "10.1038/nature12373",
        "10.1126/science.1259855",
        # not_in_library
        "10.1145/3592979.3593405",  # near-miss (one digit off — not in library)
        "10.1234/new.paper.2024",
        # mixed formats that should normalize to in_library
        "https://doi.org/10.1038/nature12373",  # dup of in_library #1
        "DOI: 10.1126/science.1259855",        # dup of in_library #2
        # invalid
        "not a doi",
        "",
    ]

    def test_four_buckets(self):
        result = zotero_local.check_corpus(self.CORPUS, library_dois=self.LIBRARY)
        # in_library: 2 unique (the dupes dedupe to the same 2)
        self.assertEqual(set(result["in_library"]),
                         {"10.1038/nature12373", "10.1126/science.1259855"})
        # not_in_library: 2 unique (near-miss + new)
        self.assertEqual(set(result["not_in_library"]),
                         {"10.1145/3592979.3593405", "10.1234/new.paper.2024"})
        # invalid_doi: 2 raw inputs (empty string + "not a doi")
        self.assertEqual(len(result["invalid_doi"]), 2)
        # duplicates_in_corpus: 10.1038/nature12373 (raw + URL form), 10.1126/...
        self.assertEqual(set(result["duplicates_in_corpus"]),
                         {"10.1038/nature12373", "10.1126/science.1259855"})

    def test_empty_corpus(self):
        result = zotero_local.check_corpus([], library_dois=self.LIBRARY)
        self.assertEqual(result["in_library"], [])
        self.assertEqual(result["not_in_library"], [])
        self.assertEqual(result["invalid_doi"], [])
        self.assertEqual(result["duplicates_in_corpus"], [])

    def test_empty_library(self):
        result = zotero_local.check_corpus(self.CORPUS, library_dois=set())
        self.assertEqual(result["in_library"], [])
        # All valid DOIs land in not_in_library
        self.assertEqual(len(result["not_in_library"]), 4)


class TestExtractDOIsFromBibtex(unittest.TestCase):
    """T3: extract_dois_from_bibtex() — `doi = {...}` and `doi = "..."`,
    case-insensitive field name, multi-entry file."""

    BIBTEX = r"""
@article{key1,
  author = {Smith, J.},
  title = {A Paper},
  doi = {10.1038/nature12373},
  year = {2020}
}

@article{key2,
  author = {Doe, A.},
  title = {Another Paper},
  DOI = "10.1126/science.1259855",
  year = {2021}
}

@article{key3,
  author = {Lee, K.},
  title = {Third Paper},
  Doi = {https://doi.org/10.1145/3592979.3593406},
  year = {2022}
}

@article{key_no_doi,
  author = {No DOI Author},
  title = {No DOI Here},
  year = {2023}
}
"""

    def test_extract(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".bib", delete=False, encoding="utf-8"
        ) as f:
            f.write(self.BIBTEX)
            path = Path(f.name)
        try:
            dois = zotero_local.extract_dois_from_bibtex(path)
            self.assertEqual(len(dois), 3)
            self.assertIn("10.1038/nature12373", dois)
            self.assertIn("10.1126/science.1259855", dois)
            self.assertIn("https://doi.org/10.1145/3592979.3593406", dois)
        finally:
            path.unlink(missing_ok=True)

    def test_extract_missing_file(self):
        dois = zotero_local.extract_dois_from_bibtex(Path("/nonexistent/refs.bib"))
        self.assertEqual(dois, [])


# ─────────────────────────────────────────────────────────────────
# E2E test: build a real Zotero-schema SQLite, then read it
# ─────────────────────────────────────────────────────────────────
class TestE2EWithMockZoteroDB(unittest.TestCase):
    """T4: Build a minimal Zotero-schema SQLite in tmp, verify get_library_dois()
    + check_corpus() integration. Uses URI mode=ro for the read path."""

    def setUp(self):
        # Create a tmp SQLite file with a Zotero 6+ schema.
        # We need: fields, itemTypes, items, itemData, itemDataValues.
        # v3.9.14.0 fix: code now looks up fieldID and itemTypeID by NAME
        # at runtime, so the test uses named lookups (not hardcoded IDs).
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "zotero.sqlite"
        conn = sqlite3.connect(str(self.db_path))
        try:
            cur = conn.cursor()
            # Minimal Zotero 6+ schema (Zotero 6 renumbered fields + itemTypes)
            cur.execute("""
                CREATE TABLE fields (
                    fieldID INTEGER PRIMARY KEY,
                    fieldName TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE itemTypes (
                    itemTypeID INTEGER PRIMARY KEY,
                    typeName TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE items (
                    itemID INTEGER PRIMARY KEY,
                    itemTypeID INTEGER,
                    key TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE itemData (
                    itemID INTEGER,
                    fieldID INTEGER,
                    valueID INTEGER
                )
            """)
            cur.execute("""
                CREATE TABLE itemDataValues (
                    valueID INTEGER PRIMARY KEY,
                    value TEXT
                )
            """)
            # Seed: minimal field set (DOI = field 59 in Zotero 6+)
            cur.execute("INSERT INTO fields VALUES (1, 'title')")
            cur.execute("INSERT INTO fields VALUES (59, 'DOI')")
            # Seed: item types matching Zotero 6 numbering
            cur.execute("INSERT INTO itemTypes VALUES (1, 'annotation')")
            cur.execute("INSERT INTO itemTypes VALUES (2, 'book')")
            cur.execute("INSERT INTO itemTypes VALUES (3, 'attachment')")
            cur.execute("INSERT INTO itemTypes VALUES (28, 'note')")
            # Seed: 5 items
            # 3 with DOI in library (book = itemTypeID 2)
            # 1 with DOI excluded (note, itemTypeID 28)
            # 1 with DOI excluded (attachment, itemTypeID 3)
            library_dois = [
                "10.1038/nature12373",
                "10.1126/science.1259855",
                "10.1145/3592979.3593406",
            ]
            note_doi = "10.1234/note.9999"
            attachment_doi = "10.1234/attach.9999"
            for doi in library_dois + [note_doi, attachment_doi]:
                cur.execute("INSERT INTO items (itemTypeID, key) VALUES (?, ?)",
                            (2, f"key_{doi[:6]}"))  # default book
                item_id = cur.lastrowid
                # Override itemTypeID for the last two
                if doi == note_doi:
                    cur.execute("UPDATE items SET itemTypeID=28 WHERE itemID=?", (item_id,))
                elif doi == attachment_doi:
                    cur.execute("UPDATE items SET itemTypeID=3 WHERE itemID=?", (item_id,))
                cur.execute("INSERT INTO itemDataValues (value) VALUES (?)", (doi,))
                value_id = cur.lastrowid
                # DOI is field 59, not 1
                cur.execute(
                    "INSERT INTO itemData (itemID, fieldID, valueID) VALUES (?, 59, ?)",
                    (item_id, value_id),
                )
            conn.commit()
        finally:
            conn.close()

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_get_library_dois_excludes_notes_and_attachments(self):
        # Should return 3 DOIs (library), excluding note (1) and attachment (14)
        dois = zotero_local.get_library_dois(db_path=self.db_path)
        self.assertEqual(len(dois), 3)
        self.assertIn("10.1038/nature12373", dois)
        self.assertIn("10.1126/science.1259855", dois)
        self.assertIn("10.1145/3592979.3593406", dois)
        self.assertNotIn("10.1234/note.9999", dois)
        self.assertNotIn("10.1234/attach.9999", dois)

    def test_check_corpus_against_mock_library(self):
        # Corpus: 2 in library, 2 not in library, 1 invalid
        corpus = [
            "10.1038/nature12373",        # in library
            "10.1126/science.1259855",    # in library
            "10.9999/not.in.library",     # not in library
            "10.1234/also.not.in.lib",     # not in library
            "this is not a doi",          # invalid
        ]
        result = zotero_local.check_corpus(corpus, db_path=self.db_path)
        self.assertEqual(set(result["in_library"]),
                         {"10.1038/nature12373", "10.1126/science.1259855"})
        self.assertEqual(set(result["not_in_library"]),
                         {"10.9999/not.in.library", "10.1234/also.not.in.lib"})
        self.assertEqual(result["invalid_doi"], ["this is not a doi"])

    def test_get_library_dois_normalizes_doi_format(self):
        # Insert a DOI in non-canonical format (uppercase + URL prefix).
        # v3.9.14.0: DOI is fieldID=59 in Zotero 6 schema (set up in setUp).
        conn = sqlite3.connect(str(self.db_path))
        try:
            cur = conn.cursor()
            cur.execute("INSERT INTO items (itemTypeID, key) VALUES (2, 'url_doi')")
            item_id = cur.lastrowid
            cur.execute("INSERT INTO itemDataValues (value) VALUES (?)",
                        ("HTTPS://DOI.ORG/10.9999/URL.FORMAT",))
            value_id = cur.lastrowid
            cur.execute(
                "INSERT INTO itemData (itemID, fieldID, valueID) VALUES (?, 59, ?)",
                (item_id, value_id),
            )
            conn.commit()
        finally:
            conn.close()

        dois = zotero_local.get_library_dois(db_path=self.db_path)
        # normalize_doi strips the URL and lowercases
        self.assertIn("10.9999/url.format", dois)

    def test_readonly_cannot_write(self):
        # Verify that even if we somehow tried to write, the URI mode=ro would
        # refuse. (This guards against a future bug that accidentally calls a
        # write statement.)
        import sqlite3 as _sq
        uri = f"file:{self.db_path}?mode=ro"
        conn = _sq.connect(uri, uri=True, timeout=5)
        try:
            cur = conn.cursor()
            with self.assertRaises(_sq.OperationalError):
                cur.execute("INSERT INTO fields VALUES (999, 'should-fail')")
        finally:
            conn.close()

    def test_old_zotero_schema_still_works(self):
        # v3.9.14.0 fix: code looks up fieldID by name, so it works with
        # older Zotero schemas where DOI was fieldID=1. Test by inserting
        # an extra DOI with the OLD fieldID=1 in a fresh DB.
        with tempfile.TemporaryDirectory() as tmp:
            old_db = Path(tmp) / "zotero.sqlite"
            conn = sqlite3.connect(str(old_db))
            try:
                cur = conn.cursor()
                cur.execute("""
                    CREATE TABLE fields (fieldID INTEGER PRIMARY KEY, fieldName TEXT)
                """)
                cur.execute("""
                    CREATE TABLE itemTypes (itemTypeID INTEGER PRIMARY KEY, typeName TEXT)
                """)
                cur.execute("""
                    CREATE TABLE items (itemID INTEGER PRIMARY KEY, itemTypeID INTEGER, key TEXT)
                """)
                cur.execute("""
                    CREATE TABLE itemData (itemID INTEGER, fieldID INTEGER, valueID INTEGER)
                """)
                cur.execute("""
                    CREATE TABLE itemDataValues (valueID INTEGER PRIMARY KEY, value TEXT)
                """)
                # OLD schema: DOI is field 1
                cur.execute("INSERT INTO fields VALUES (1, 'DOI')")
                cur.execute("INSERT INTO itemTypes VALUES (1, 'note')")
                cur.execute("INSERT INTO itemTypes VALUES (2, 'book')")
                # Insert one item with old-schema DOI
                cur.execute("INSERT INTO items (itemTypeID, key) VALUES (2, 'old_key')")
                item_id = cur.lastrowid
                cur.execute("INSERT INTO itemDataValues (value) VALUES ('10.5555/old.schema.doi')")
                value_id = cur.lastrowid
                cur.execute("INSERT INTO itemData (itemID, fieldID, valueID) VALUES (?, 1, ?)",
                            (item_id, value_id))
                conn.commit()
            finally:
                conn.close()

            dois = zotero_local.get_library_dois(db_path=old_db)
            self.assertIn("10.5555/old.schema.doi", dois)


if __name__ == "__main__":
    unittest.main(verbosity=2)
