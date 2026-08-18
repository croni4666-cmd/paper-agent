"""Tests for pa_cli.zotero_api pull / export-bib functions.

v3.9.18 [P3-28.2] -- bidirectional Zotero <-> local pa project.

We mock pyzotero so tests don't need a real Zotero account. The mocks
follow pyzotero response shapes closely enough to exercise the wrapper
logic (zotero_item_to_bibtex, collection_items_to_bibtex,
pull_collection_to_project).
"""
from __future__ import annotations

import json
import sys
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pa_cli import zotero_api


# ─────────────────────────────────────────────────────────────────
# Mock helpers (mirror test_zotero_collections.py)
# ─────────────────────────────────────────────────────────────────
def _coll(name, key, parent=False, num_items=0, num_collections=0, version=1):
    """Build a pyzotero collection dict (data-wrapped)."""
    return {
        "data": {
            "key": key,
            "name": name,
            "parentCollection": parent if parent else False,
            "numItems": num_items,
            "numCollections": num_collections,
            "version": version,
        }
    }


def _item(key, title, doi="", date="2024", item_type="journalArticle",
          creators=None, extra=None):
    """Build a pyzotero item dict."""
    data = {
        "key": key,
        "title": title,
        "DOI": doi,
        "date": date,
        "itemType": item_type,
        "creators": creators or [],
    }
    if extra:
        data.update(extra)
    return {"key": key, "data": data}


def _mock_client(collections=None, collection_items=None):
    """Build a mock pyzotero.Zotero client."""
    client = MagicMock()
    client.collections.return_value = collections or []
    client.collections_top.return_value = collections or []
    client.collection_items.return_value = collection_items or []
    return client


# ─────────────────────────────────────────────────────────────────
# TestZoteroTypeToBibtex
# ─────────────────────────────────────────────────────────────────
class TestZoteroTypeToBibtex:
    def test_journal_article(self):
        assert zotero_api._zotero_type_to_bibtex_type("journalArticle") == "article"

    def test_book(self):
        assert zotero_api._zotero_type_to_bibtex_type("book") == "book"

    def test_conference_paper(self):
        assert zotero_api._zotero_type_to_bibtex_type("conferencePaper") == "inproceedings"

    def test_book_section(self):
        assert zotero_api._zotero_type_to_bibtex_type("bookSection") == "incollection"

    def test_phd_thesis_default(self):
        # Default: no thesisType -> phdthesis
        assert zotero_api._zotero_type_to_bibtex_type("thesis") == "phdthesis"

    def test_master_thesis(self):
        # thesisType contains "master" -> mastersthesis
        assert zotero_api._zotero_type_to_bibtex_type(
            "thesis", {"thesisType": "Master of Science"}
        ) == "mastersthesis"

    def test_report(self):
        assert zotero_api._zotero_type_to_bibtex_type("report") == "techreport"

    def test_preprint(self):
        assert zotero_api._zotero_type_to_bibtex_type("preprint") == "misc"

    def test_unknown_falls_back_to_misc(self):
        assert zotero_api._zotero_type_to_bibtex_type("veryUnusualType") == "misc"

    def test_patent(self):
        assert zotero_api._zotero_type_to_bibtex_type("patent") == "patent"


# ─────────────────────────────────────────────────────────────────
# TestZoteroCreatorsToBibtexAuthor
# ─────────────────────────────────────────────────────────────────
class TestZoteroCreatorsToBibtexAuthor:
    def test_single_first_last(self):
        creators = [{"creatorType": "author", "firstName": "Alice", "lastName": "Smith"}]
        assert zotero_api._zotero_creators_to_bibtex_author(creators) == "Smith, Alice"

    def test_multi_first_last(self):
        creators = [
            {"creatorType": "author", "firstName": "Alice", "lastName": "Smith"},
            {"creatorType": "author", "firstName": "Bob", "lastName": "Jones"},
        ]
        assert zotero_api._zotero_creators_to_bibtex_author(creators) == "Smith, Alice and Jones, Bob"

    def test_organization_single_name(self):
        creators = [{"creatorType": "author", "name": "World Health Organization"}]
        assert zotero_api._zotero_creators_to_bibtex_author(creators) == "World Health Organization"

    def test_mixed_first_last_and_org(self):
        creators = [
            {"creatorType": "author", "firstName": "Alice", "lastName": "Smith"},
            {"creatorType": "author", "name": "WHO"},
        ]
        assert zotero_api._zotero_creators_to_bibtex_author(creators) == "Smith, Alice and WHO"

    def test_empty(self):
        assert zotero_api._zotero_creators_to_bibtex_author([]) == ""

    def test_skip_non_author_role(self):
        creators = [
            {"creatorType": "editor", "firstName": "Ed", "lastName": "Itor"},
            {"creatorType": "author", "firstName": "Alice", "lastName": "Smith"},
        ]
        # Editor is skipped; only author remains
        assert zotero_api._zotero_creators_to_bibtex_author(creators) == "Smith, Alice"

    def test_translator_excluded(self):
        # translator role goes in 'translator' Bibtex field, not 'author'
        creators = [
            {"creatorType": "translator", "firstName": "Tr", "lastName": "Ansl"},
        ]
        assert zotero_api._zotero_creators_to_bibtex_author(creators) == ""


# ─────────────────────────────────────────────────────────────────
# TestSanitizeBibtexKey
# ─────────────────────────────────────────────────────────────────
class TestSanitizeBibtexKey:
    def test_simple_word(self):
        assert zotero_api._sanitize_bibtex_key("hello") == "hello"

    def test_punctuation_replaced(self):
        assert zotero_api._sanitize_bibtex_key("Hello, World!") == "hello_world"

    def test_truncate_to_40(self):
        long = "a" * 50
        assert len(zotero_api._sanitize_bibtex_key(long)) == 40

    def test_empty_returns_fallback(self):
        assert zotero_api._sanitize_bibtex_key("") == "ref"
        assert zotero_api._sanitize_bibtex_key("   ") == "ref"
        assert zotero_api._sanitize_bibtex_key("!!!") == "ref"

    def test_explicit_fallback(self):
        assert zotero_api._sanitize_bibtex_key("", fallback="mykey") == "mykey"


# ─────────────────────────────────────────────────────────────────
# TestZoteroItemToBibtex
# ─────────────────────────────────────────────────────────────────
class TestZoteroItemToBibtex:
    def test_journal_article_full(self):
        item = _item(
            "ABC1", "Long-term care insurance",
            doi="10.1234/ltc.2024",
            date="2024-05-10",
            item_type="journalArticle",
            creators=[{"creatorType": "author", "firstName": "Alice", "lastName": "Smith"}],
            extra={"publicationTitle": "J Health Econ", "volume": "45", "issue": "3",
                   "pages": "123-145", "abstractNote": "An abstract."},
        )
        bib = zotero_api.zotero_item_to_bibtex(item)
        assert bib is not None
        assert bib.startswith("@article{")
        assert "title" in bib and "Long-term care insurance" in bib
        assert "author" in bib and "Smith, Alice" in bib
        assert "year" in bib and "2024" in bib
        assert "doi" in bib and "10.1234/ltc.2024" in bib
        assert "url" in bib and "https://doi.org/10.1234/ltc.2024" in bib
        assert "journal" in bib and "J Health Econ" in bib
        assert "volume" in bib and "45" in bib
        assert "number" in bib and "3" in bib
        assert "pages" in bib and "123-145" in bib
        assert "abstract" in bib and "An abstract." in bib
        assert "zotero_key" in bib and "ABC1" in bib

    def test_book_org_author(self):
        item = _item(
            "B1", "Handbook of Health Economics",
            date="2023-06-15",
            item_type="book",
            creators=[{"creatorType": "author", "name": "World Health Organization"}],
            extra={"publisher": "WHO Press", "place": "Geneva"},
        )
        bib = zotero_api.zotero_item_to_bibtex(item)
        assert bib is not None
        assert bib.startswith("@book{")
        assert "WHO" in bib or "World" in bib  # org name appears
        assert "publisher" in bib and "WHO Press" in bib
        # Note: place is not a recognized field for @book (use address for publisher location)
        # We don't emit 'place' for books; just 'publisher'
        assert "year" in bib and "2023" in bib

    def test_thesis_master(self):
        item = _item(
            "T1", "Master thesis on care",
            date="2022",
            item_type="thesis",
            creators=[{"creatorType": "author", "firstName": "Carol", "lastName": "Lee"}],
            extra={"thesisType": "Master of Science", "institution": "MIT", "place": "Cambridge, MA"},
        )
        bib = zotero_api.zotero_item_to_bibtex(item)
        assert bib is not None
        assert bib.startswith("@mastersthesis{")
        assert "type" in bib and "Master of Science" in bib
        assert "school" in bib and "MIT" in bib
        assert "address" in bib and "Cambridge, MA" in bib

    def test_conference_paper(self):
        item = _item(
            "C1", "Conference proceedings",
            doi="10.1109/conf.2024.001",
            date="2024",
            item_type="conferencePaper",
            creators=[{"creatorType": "author", "firstName": "Bob", "lastName": "Jones"}],
        )
        bib = zotero_api.zotero_item_to_bibtex(item)
        assert bib is not None
        assert bib.startswith("@inproceedings{")

    def test_book_section_uses_booktitle(self):
        item = _item(
            "BS1", "A chapter",
            date="2024",
            item_type="bookSection",
            creators=[{"creatorType": "author", "firstName": "Dan", "lastName": "Smith"}],
            extra={"bookTitle": "Handbook of X", "publisher": "PubCo"},
        )
        bib = zotero_api.zotero_item_to_bibtex(item)
        assert bib is not None
        assert bib.startswith("@incollection{")
        assert "booktitle" in bib and "Handbook of X" in bib

    def test_preprint(self):
        item = _item(
            "P1", "Preprint on AI",
            doi="10.48550/arXiv.2401.00001",
            date="2024",
            item_type="preprint",
            creators=[{"creatorType": "author", "firstName": "Eve", "lastName": "Adams"}],
        )
        bib = zotero_api.zotero_item_to_bibtex(item)
        assert bib is not None
        assert bib.startswith("@misc{")
        assert "arxiv" in bib.lower() or "2401" in bib

    def test_no_title_returns_none(self):
        item = {"key": "X1", "data": {"key": "X1", "title": "", "itemType": "journalArticle"}}
        assert zotero_api.zotero_item_to_bibtex(item) is None

    def test_no_doi_uses_author_year_cite_key(self):
        item = _item(
            "N1", "No DOI paper",
            date="2024",
            item_type="journalArticle",
            creators=[{"creatorType": "author", "firstName": "Frank", "lastName": "Garcia"}],
        )
        bib = zotero_api.zotero_item_to_bibtex(item)
        assert bib is not None
        # Cite-key should contain author surname + year
        first_line = bib.split("\n", 1)[0]
        assert "garcia2024" in first_line.lower()

    def test_long_abstract_truncated(self):
        long_abstract = "x" * 5000
        item = _item(
            "L1", "Long abstract paper",
            doi="10.1234/long.2024",
            date="2024",
            item_type="journalArticle",
            creators=[{"creatorType": "author", "firstName": "G", "lastName": "H"}],
            extra={"abstractNote": long_abstract},
        )
        bib = zotero_api.zotero_item_to_bibtex(item)
        assert bib is not None
        # Abstract truncated to 4000 + "..."
        assert "..." in bib
        # Should NOT contain the full 5000-char string
        assert long_abstract not in bib

    def test_brace_escape(self):
        # Braces in field values should be escaped to \{ \}
        item = _item(
            "BR1", "Title with {curly} braces",
            doi="10.1234/curly.2024",
            date="2024",
            item_type="journalArticle",
            creators=[{"creatorType": "author", "firstName": "H", "lastName": "I"}],
        )
        bib = zotero_api.zotero_item_to_bibtex(item)
        assert bib is not None
        # Curly braces should be escaped
        assert "\\{curly\\}" in bib


# ─────────────────────────────────────────────────────────────────
# TestCollectionItemsToBibtex
# ─────────────────────────────────────────────────────────────────
class TestCollectionItemsToBibtex:
    def test_happy(self):
        items = [
            _item("P1", "Paper one", doi="10.1234/one.2024", date="2024",
                  item_type="journalArticle",
                  creators=[{"creatorType": "author", "firstName": "A", "lastName": "B"}]),
            _item("P2", "Paper two", doi="10.1234/two.2023", date="2023",
                  item_type="journalArticle",
                  creators=[{"creatorType": "author", "firstName": "C", "lastName": "D"}]),
        ]
        client = _mock_client(collection_items=items)
        result = zotero_api.collection_items_to_bibtex(client, "COLL")
        assert result["n_total"] == 2
        assert result["n_converted"] == 2
        assert result["n_skipped"] == 0
        assert result["n_failed"] == 0
        assert "@article" in result["bibtex_str"]
        assert result["out_path"] is None

    def test_empty_collection(self):
        client = _mock_client(collection_items=[])
        result = zotero_api.collection_items_to_bibtex(client, "EMPTY")
        assert result["n_total"] == 0
        assert result["n_converted"] == 0
        assert result["bibtex_str"] == ""

    def test_writes_to_file(self, tmp_path):
        items = [
            _item("P1", "Paper one", doi="10.1234/one.2024", date="2024",
                  item_type="journalArticle",
                  creators=[{"creatorType": "author", "firstName": "A", "lastName": "B"}]),
        ]
        client = _mock_client(collection_items=items)
        out = tmp_path / "refs.bib"
        result = zotero_api.collection_items_to_bibtex(client, "COLL", out_path=out)
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "@article" in content
        assert "Paper one" in content
        assert result["out_path"] == str(out)

    def test_cite_key_collision_dedup(self):
        # Two items with same DOI would get same cite-key; verify _2 suffix
        items = [
            _item("P1", "Paper one", doi="10.1234/same.2024", date="2024",
                  item_type="journalArticle",
                  creators=[{"creatorType": "author", "firstName": "A", "lastName": "B"}]),
            _item("P2", "Paper two", doi="10.1234/same.2024", date="2024",
                  item_type="journalArticle",
                  creators=[{"creatorType": "author", "firstName": "C", "lastName": "D"}]),
        ]
        client = _mock_client(collection_items=items)
        result = zotero_api.collection_items_to_bibtex(client, "COLL")
        assert result["n_converted"] == 2
        # First key is the base; second is the deduped version
        assert result["results"][0]["cite_key"] == "same_2024"
        assert result["results"][1]["cite_key"] == "same_2024_2"
        # Verify the bibtex_str has both entries
        assert result["bibtex_str"].count("@article") == 2
        assert "same_2024," in result["bibtex_str"]
        assert "same_2024_2," in result["bibtex_str"]


# ─────────────────────────────────────────────────────────────────
# TestPullCollectionToProject
# ─────────────────────────────────────────────────────────────────
class TestPullCollectionToProject:
    def _setup(self, items=None):
        colls = [_coll("Long-term care", "COLL_KEY", num_items=2, version=5)]
        items = items or [
            _item("P1", "Long-term care insurance paper", doi="10.1234/ltc.2024", date="2024",
                  item_type="journalArticle",
                  creators=[{"creatorType": "author", "firstName": "A", "lastName": "Smith"}]),
            _item("P2", "Caregiving in OECD", doi="10.1234/care.2023", date="2023",
                  item_type="journalArticle",
                  creators=[{"creatorType": "author", "firstName": "B", "lastName": "Jones"}]),
        ]
        return _mock_client(colls, items)

    def test_happy_path(self, tmp_path):
        client = self._setup()
        result = zotero_api.pull_collection_to_project(
            client, "Long-term care", project_root=tmp_path
        )
        assert result["status"] == "created"
        assert result["project_slug"] == "long-term-care"
        assert result["zotero_key"] == "COLL_KEY"
        assert result["zotero_collection_name"] == "Long-term care"
        assert result["n_total"] == 2
        assert result["n_converted"] == 2
        # Files exist
        assert Path(result["refs_path"]).exists()
        assert Path(result["meta_path"]).exists()
        assert Path(result["judges_path"]).exists()
        # meta.json has Zotero-specific fields
        meta = json.loads(Path(result["meta_path"]).read_text(encoding="utf-8"))
        assert meta["zotero_collection_key"] == "COLL_KEY"
        assert meta["zotero_collection_name"] == "Long-term care"
        assert meta["zotero_collection_version"] == 5
        assert meta["source"] == "zotero-pull"
        # refs.bib has 2 entries
        refs_content = Path(result["refs_path"]).read_text(encoding="utf-8")
        assert refs_content.count("@article") == 2

    def test_idempotent_refuses_existing(self, tmp_path):
        client = self._setup()
        # First run
        zotero_api.pull_collection_to_project(client, "Long-term care", project_root=tmp_path)
        # Second run should refuse
        result2 = zotero_api.pull_collection_to_project(
            client, "Long-term care", project_root=tmp_path
        )
        assert result2["status"] == "error"
        assert "already exists" in result2["error"]

    def test_overwrite_replaces_existing(self, tmp_path):
        client = self._setup()
        zotero_api.pull_collection_to_project(client, "Long-term care", project_root=tmp_path)
        result2 = zotero_api.pull_collection_to_project(
            client, "Long-term care", project_root=tmp_path, overwrite=True
        )
        assert result2["status"] == "overwritten"
        assert result2["n_converted"] == 2

    def test_custom_slug(self, tmp_path):
        client = self._setup()
        result = zotero_api.pull_collection_to_project(
            client, "Long-term care", project_slug="ltc-custom",
            project_root=tmp_path,
        )
        assert result["status"] == "created"
        assert result["project_slug"] == "ltc-custom"

    def test_collection_not_found(self, tmp_path):
        client = _mock_client(collections=[])
        result = zotero_api.pull_collection_to_project(
            client, "NonExistent", project_root=tmp_path
        )
        assert result["status"] == "error"
        assert "not found" in result["error"]

    def test_empty_collection_name(self, tmp_path):
        client = self._setup()
        result = zotero_api.pull_collection_to_project(
            client, "", project_root=tmp_path
        )
        assert result["status"] == "error"
        assert "empty" in result["error"]

    def test_creates_valid_judges_sqlite(self, tmp_path):
        client = self._setup()
        result = zotero_api.pull_collection_to_project(
            client, "Long-term care", project_root=tmp_path
        )
        judges_path = Path(result["judges_path"])
        assert judges_path.exists()
        # Verify it's a real sqlite with the judgements table
        conn = sqlite3.connect(str(judges_path))
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        assert "judgements" in tables
        conn.close()


# ─────────────────────────────────────────────────────────────────
# TestCliPullAndExport (smoke tests via Click CliRunner)
# ─────────────────────────────────────────────────────────────────
class TestCliPullAndExport:
    def test_pull_help(self):
        from click.testing import CliRunner
        from pa_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli.main, ["zotero-project", "pull", "--help"])
        assert result.exit_code == 0
        assert "--name" in result.output
        assert "--key" in result.output
        assert "--slug" in result.output
        assert "--overwrite" in result.output

    def test_export_bib_help(self):
        from click.testing import CliRunner
        from pa_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli.main, ["zotero-project", "export-bib", "--help"])
        assert result.exit_code == 0
        assert "--name" in result.output
        assert "--key" in result.output
        assert "--out" in result.output

    def test_pull_missing_name_and_key_errors(self):
        from click.testing import CliRunner
        from pa_cli import cli
        runner = CliRunner()
        result = runner.invoke(cli.main, ["zotero-project", "pull"])
        assert result.exit_code == 2
        assert "--name or --key" in result.output

    def test_pull_name_and_key_mutually_exclusive(self):
        from click.testing import CliRunner
        from pa_cli import cli
        runner = CliRunner()
        result = runner.invoke(
            cli.main, ["zotero-project", "pull", "--name", "x", "--key", "Y"]
        )
        assert result.exit_code == 2
        assert "mutually exclusive" in result.output
