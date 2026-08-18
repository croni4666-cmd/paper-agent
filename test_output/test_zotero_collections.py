"""Tests for pa_cli.zotero_api collection functions.

v3.9.16 [P3-28] — collection-as-research-project.

We mock pyzotero so tests don't need a real Zotero account. The mock
follows the shape of pyzotero responses closely enough to exercise
the wrapper logic (list_collections, find_collection_by_name,
create_collection, get_collection_items, add_items_to_collection,
create_collection_note, list_collection_notes).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pa_cli import zotero_api


# ─────────────────────────────────────────────────────────────────
# Mock helpers
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


def _item(key, title, doi="", date="2024", item_type="journalArticle", collections=None):
    """Build a pyzotero item dict."""
    return {
        "key": key,
        "data": {
            "key": key,
            "title": title,
            "DOI": doi,
            "date": date,
            "itemType": item_type,
            "creators": [{"name": "Author One"}, {"name": "Author Two"}],
            "collections": collections or [],
        }
    }


# ─────────────────────────────────────────────────────────────────
# TestListCollections
# ─────────────────────────────────────────────────────────────────
class TestListCollections:
    def test_returns_sorted_list(self):
        client = MagicMock()
        client.collections_top.return_value = [
            _coll("Zebra", "ZZZ"),
            _coll("Apple", "AAA"),
            _coll("Mango", "MMM"),
        ]
        result = zotero_api.list_collections(client, top_only=True)
        assert [c["name"] for c in result] == ["Apple", "Mango", "Zebra"]

    def test_extracts_key_fields(self):
        client = MagicMock()
        client.collections_top.return_value = [
            _coll("Foo", "ABC123", num_items=5, num_collections=2, version=42),
        ]
        c = zotero_api.list_collections(client, top_only=True)[0]
        assert c["key"] == "ABC123"
        assert c["name"] == "Foo"
        assert c["numItems"] == 5
        assert c["numCollections"] == 2
        assert c["version"] == 42

    def test_top_only_uses_collections_top(self):
        client = MagicMock()
        client.collections_top.return_value = []
        zotero_api.list_collections(client, top_only=True)
        client.collections_top.assert_called_once()
        client.collections.assert_not_called()

    def test_not_top_only_uses_collections(self):
        client = MagicMock()
        client.collections.return_value = []
        zotero_api.list_collections(client, top_only=False)
        client.collections.assert_called_once()

    def test_empty_on_exception(self):
        client = MagicMock()
        client.collections_top.side_effect = RuntimeError("network error")
        assert zotero_api.list_collections(client) == []


# ─────────────────────────────────────────────────────────────────
# TestFindCollectionByName
# ─────────────────────────────────────────────────────────────────
class TestFindCollectionByName:
    def test_exact_match(self):
        client = MagicMock()
        client.collections.return_value = [
            _coll("long-term care", "LTC001"),
            _coll("digital finance", "DF001"),
        ]
        result = zotero_api.find_collection_by_name(client, "long-term care")
        assert result is not None
        assert result["key"] == "LTC001"
        assert result["name"] == "long-term care"

    def test_case_insensitive(self):
        client = MagicMock()
        client.collections.return_value = [_coll("Long-Term Care", "LTC001")]
        result = zotero_api.find_collection_by_name(client, "long-term care")
        assert result is not None
        assert result["key"] == "LTC001"

    def test_not_found_returns_none(self):
        client = MagicMock()
        client.collections.return_value = [_coll("other", "X")]
        assert zotero_api.find_collection_by_name(client, "missing") is None

    def test_empty_name_returns_none(self):
        client = MagicMock()
        assert zotero_api.find_collection_by_name(client, "") is None
        assert zotero_api.find_collection_by_name(client, "   ") is None

    def test_parent_key_filter(self):
        client = MagicMock()
        client.collections.return_value = [
            _coll("subtopic", "SUB", parent="PARENT001"),
            _coll("subtopic", "SUB2", parent="PARENT002"),
        ]
        result = zotero_api.find_collection_by_name(client, "subtopic", parent_key="PARENT001")
        assert result["key"] == "SUB"


# ─────────────────────────────────────────────────────────────────
# TestCreateCollection
# ─────────────────────────────────────────────────────────────────
class TestCreateCollection:
    def test_create_new(self):
        client = MagicMock()
        client.collections.return_value = []  # find_collection_by_name sees no match
        client.create_collections.return_value = [{"successful": {"key": "NEW001"}}]

        result = zotero_api.create_collection(client, "new project")
        assert result["status"] == "created"
        assert result["key"] == "NEW001"
        assert result["name"] == "new project"
        # Verify API called with correct payload
        call_args = client.create_collections.call_args
        payload = call_args[0][0]
        assert payload == [{"name": "new project"}]

    def test_create_idempotent_when_exists(self):
        client = MagicMock()
        client.collections.return_value = [_coll("existing", "EXIST001", num_items=3)]
        result = zotero_api.create_collection(client, "existing")
        assert result["status"] == "exists"
        assert result["key"] == "EXIST001"
        assert result["numItems"] == 3
        client.create_collections.assert_not_called()

    def test_create_with_parent_key(self):
        client = MagicMock()
        client.collections.return_value = []
        client.create_collections.return_value = [{"successful": {"key": "CHILD001"}}]
        result = zotero_api.create_collection(client, "child", parent_key="PARENT001")
        assert result["status"] == "created"
        payload = client.create_collections.call_args[0][0]
        assert payload[0]["parentCollection"] == "PARENT001"

    def test_create_empty_name_returns_error(self):
        client = MagicMock()
        result = zotero_api.create_collection(client, "")
        assert result["status"] == "error"
        client.create_collections.assert_not_called()

    def test_create_api_error_handled(self):
        client = MagicMock()
        client.collections.return_value = []
        client.create_collections.return_value = [{"failed": "permission denied"}]
        result = zotero_api.create_collection(client, "x")
        assert result["status"] == "error"
        assert "permission" in result["error"].lower()

    def test_create_api_exception_handled(self):
        client = MagicMock()
        client.collections.return_value = []
        client.create_collections.side_effect = RuntimeError("503 Service Unavailable")
        result = zotero_api.create_collection(client, "x")
        assert result["status"] == "error"
        assert "503" in result["error"] or "RuntimeError" in result["error"]

    def test_create_strips_whitespace(self):
        client = MagicMock()
        client.collections.return_value = []
        client.create_collections.return_value = [{"successful": {"key": "W001"}}]
        result = zotero_api.create_collection(client, "  spaced name  ")
        assert result["status"] == "created"
        assert result["name"] == "spaced name"


# ─────────────────────────────────────────────────────────────────
# TestGetCollectionItems
# ─────────────────────────────────────────────────────────────────
class TestGetCollectionItems:
    def test_returns_only_bibliographic_items(self):
        client = MagicMock()
        client.collection_items.return_value = [
            _item("ITM1", "Paper A", doi="10.1/aaa"),
            _item("NOTE1", "Some note", item_type="note"),
            _item("ATT1", "paper.pdf", item_type="attachment"),
        ]
        items = zotero_api.get_collection_items(client, "COLL1")
        # Filtered out note + attachment
        assert len(items) == 1
        assert items[0]["key"] == "ITM1"
        assert items[0]["title"] == "Paper A"

    def test_sorts_by_date_desc(self):
        client = MagicMock()
        client.collection_items.return_value = [
            _item("OLD", "Old Paper", date="2020"),
            _item("NEW", "New Paper", date="2024"),
            _item("MID", "Mid Paper", date="2022"),
        ]
        items = zotero_api.get_collection_items(client, "X")
        # Sorted by date desc — 2024 first
        assert [i["key"] for i in items] == ["NEW", "MID", "OLD"]

    def test_empty_key_returns_empty(self):
        client = MagicMock()
        assert zotero_api.get_collection_items(client, "") == []

    def test_exception_returns_empty(self):
        client = MagicMock()
        client.collection_items.side_effect = RuntimeError("403 Forbidden")
        assert zotero_api.get_collection_items(client, "X") == []


# ─────────────────────────────────────────────────────────────────
# TestAddItemsToCollection
# ─────────────────────────────────────────────────────────────────
class TestAddItemsToCollection:
    def test_adds_items_to_collection(self):
        client = MagicMock()
        # Mock the .item() return so update_item doesn't fail
        client.item.return_value = _item("ITM1", "Paper A", collections=["OTHER"])
        result = zotero_api.add_items_to_collection(client, ["ITM1", "ITM2"], "TARGET")
        assert result["n_added"] == 2
        assert result["n_failed"] == 0
        # Verify the target collection was added
        update_calls = client.update_item.call_args_list
        assert len(update_calls) == 2

    def test_no_duplicates_in_existing_collections(self):
        client = MagicMock()
        client.item.return_value = _item("ITM1", "Paper A", collections=["TARGET"])
        result = zotero_api.add_items_to_collection(client, ["ITM1"], "TARGET")
        # update_item should still be called (re-setting is idempotent)
        assert result["n_added"] == 1
        assert client.update_item.call_count == 1

    def test_empty_inputs_return_zero(self):
        client = MagicMock()
        result = zotero_api.add_items_to_collection(client, [], "X")
        assert result == {"n_added": 0, "n_failed": 0, "results": []}
        result2 = zotero_api.add_items_to_collection(client, ["ITM1"], "")
        assert result2 == {"n_added": 0, "n_failed": 0, "results": []}

    def test_exception_counted_as_failed(self):
        client = MagicMock()
        client.item.side_effect = RuntimeError("network error")
        result = zotero_api.add_items_to_collection(client, ["ITM1"], "X")
        assert result["n_added"] == 0
        assert result["n_failed"] == 1
        assert result["results"][0]["status"] == "failed"


# ─────────────────────────────────────────────────────────────────
# TestCreateCollectionNote
# ─────────────────────────────────────────────────────────────────
class TestCreateCollectionNote:
    def test_create_plain_text_note(self):
        client = MagicMock()
        client.create_items.return_value = [{"successful": {"key": "NOTE001"}}]
        result = zotero_api.create_collection_note(
            client, "COLL1", "my note", "body of the note"
        )
        assert result["status"] == "created"
        assert result["key"] == "NOTE001"
        assert result["title"] == "my note"
        # Verify payload
        call_args = client.create_items.call_args
        payload = call_args[0][0]
        assert payload[0]["itemType"] == "note"
        assert payload[0]["title"] == "my note"
        assert "COLL1" in payload[0]["collections"]
        assert "<pre>" in payload[0]["note"]

    def test_create_html_note_passes_through(self):
        client = MagicMock()
        client.create_items.return_value = [{"successful": {"key": "NOTE002"}}]
        html = "<h1>Heading</h1><p>Paragraph</p>"
        result = zotero_api.create_collection_note(client, "X", "title", html)
        assert result["status"] == "created"
        payload = client.create_items.call_args[0][0]
        # HTML passes through unchanged (not wrapped in <pre>)
        assert payload[0]["note"] == html

    def test_create_note_with_tag(self):
        client = MagicMock()
        client.create_items.return_value = [{"successful": {"key": "N"}}]
        zotero_api.create_collection_note(client, "X", "t", "c")
        payload = client.create_items.call_args[0][0]
        assert {"tag": "paper-agent-project-note"} in payload[0]["tags"]

    def test_create_note_empty_inputs_return_error(self):
        client = MagicMock()
        assert zotero_api.create_collection_note(client, "", "t", "c")["status"] == "error"
        assert zotero_api.create_collection_note(client, "X", "", "c")["status"] == "error"

    def test_create_note_api_failure(self):
        client = MagicMock()
        client.create_items.return_value = [{"failed": "validation error"}]
        result = zotero_api.create_collection_note(client, "X", "t", "c")
        assert result["status"] == "error"
        assert "validation" in result["error"].lower()

    def test_create_note_exception(self):
        client = MagicMock()
        client.create_items.side_effect = RuntimeError("timeout")
        result = zotero_api.create_collection_note(client, "X", "t", "c")
        assert result["status"] == "error"


# ─────────────────────────────────────────────────────────────────
# TestListCollectionNotes
# ─────────────────────────────────────────────────────────────────
class TestListCollectionNotes:
    def test_returns_only_notes(self):
        client = MagicMock()
        client.collection_items.return_value = [
            _item("ITM1", "Paper A", item_type="journalArticle"),
            _item("NOTE1", "my note", item_type="note"),
            _item("ATT1", "paper.pdf", item_type="attachment"),
        ]
        notes = zotero_api.list_collection_notes(client, "COLL1")
        assert len(notes) == 1
        assert notes[0]["key"] == "NOTE1"

    def test_sorts_by_date_modified_desc(self):
        client = MagicMock()
        client.collection_items.return_value = [
            {"data": {"key": "N1", "title": "older", "note": "x",
                     "dateModified": "2024-01-01T00:00:00Z", "version": 1, "itemType": "note"}},
            {"data": {"key": "N2", "title": "newer", "note": "y",
                     "dateModified": "2024-12-01T00:00:00Z", "version": 2, "itemType": "note"}},
        ]
        notes = zotero_api.list_collection_notes(client, "X")
        assert notes[0]["key"] == "N2"
        assert notes[1]["key"] == "N1"

    def test_empty_key_returns_empty(self):
        client = MagicMock()
        assert zotero_api.list_collection_notes(client, "") == []

    def test_exception_returns_empty(self):
        client = MagicMock()
        client.collection_items.side_effect = RuntimeError("network")
        assert zotero_api.list_collection_notes(client, "X") == []


# ─────────────────────────────────────────────────────────────────
# TestGetClientStillWorks
# ─────────────────────────────────────────────────────────────────
class TestGetClientStillWorks:
    """Make sure adding collection functions didn't break the existing API."""

    def test_get_client_missing_api_key(self, monkeypatch):
        from pa_cli import zotero_api
        monkeypatch.delenv("ZOTERO_API_KEY", raising=False)
        monkeypatch.delenv("ZOTERO_LIBRARY_ID", raising=False)
        with pytest.raises(ValueError, match="API key missing"):
            zotero_api.get_client()

    def test_get_client_missing_library_id(self, monkeypatch):
        from pa_cli import zotero_api
        monkeypatch.setenv("ZOTERO_API_KEY", "test-key")
        monkeypatch.delenv("ZOTERO_LIBRARY_ID", raising=False)
        with pytest.raises(ValueError, match="library ID missing"):
            zotero_api.get_client()
