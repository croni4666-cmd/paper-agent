"""Tests for pa_cli.zotero_api diff / sync functions.

v3.9.19 [P3-28.3] -- incremental Zotero -> local updates.

We mock pyzotero + use tmp_path for the local refs.bib. No live API.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pa_cli import zotero_api
from pa_cli.zotero_api import (
    _parse_refs_bib_dois,
    diff_collection_to_local,
    sync_collection_to_local,
)


# ─────────────────────────────────────────────────────────────────
# Mock helpers
# ─────────────────────────────────────────────────────────────────
def _mock_client(items=None):
    """Build a mock pyzotero.Zotero client with given collection items."""
    client = MagicMock()
    client.collection_items.return_value = items or []
    return client


def _zitem(key, title, doi, item_type="journalArticle", creators=None):
    """Build a pyzotero item dict."""
    return {
        "key": key,
        "data": {
            "key": key,
            "title": title,
            "DOI": doi,
            "date": "2024",
            "itemType": item_type,
            "creators": creators or [{"creatorType": "author", "firstName": "A", "lastName": "B"}],
        },
    }


def _write_local_refs_bib(path, dois_with_keys):
    """Write a minimal refs.bib with the given DOIs."""
    lines = []
    for i, (doi, key) in enumerate(dois_with_keys):
        lines.append(f"@article{{{key},")
        lines.append(f"  title = {{Paper {i}}},")
        lines.append(f"  doi = {{{doi}}}")
        lines.append("}")
    path.write_text("\n\n".join(lines) + "\n", encoding="utf-8")


# ─────────────────────────────────────────────────────────────────
# TestParseRefsBibDois
# ─────────────────────────────────────────────────────────────────
class TestParseRefsBibDois:
    def test_empty(self, tmp_path):
        path = tmp_path / "refs.bib"
        assert _parse_refs_bib_dois(path) == {}

    def test_nonexistent(self, tmp_path):
        path = tmp_path / "nonexistent.bib"
        assert _parse_refs_bib_dois(path) == {}

    def test_parses_dois(self, tmp_path):
        path = tmp_path / "refs.bib"
        _write_local_refs_bib(path, [
            ("10.1234/one", "one"),
            ("10.1234/two", "two"),
        ])
        result = _parse_refs_bib_dois(path)
        assert result == {"10.1234/one": "one", "10.1234/two": "two"}

    def test_normalizes_doi_case(self, tmp_path):
        path = tmp_path / "refs.bib"
        _write_local_refs_bib(path, [("10.1234/Upper.Case", "u")])
        result = _parse_refs_bib_dois(path)
        # DOI normalized to lowercase
        assert "10.1234/upper.case" in result


# ─────────────────────────────────────────────────────────────────
# TestDiffCollectionToLocal
# ─────────────────────────────────────────────────────────────────
class TestDiffCollectionToLocal:
    def test_new_only(self, tmp_path):
        path = tmp_path / "refs.bib"
        _write_local_refs_bib(path, [("10.1234/local.one", "l1")])
        client = _mock_client([
            _zitem("Z1", "Z1", "10.1234/local.one"),  # match
            _zitem("Z2", "Z2", "10.1234/zotero.new"),  # new
        ])
        diff = diff_collection_to_local(client, "COLL", path)
        assert diff["new_dois"] == ["10.1234/zotero.new"]
        assert diff["removed_dois"] == []
        assert diff["unchanged_n"] == 1
        assert diff["zotero_n_items"] == 2
        assert diff["local_n_dois"] == 1

    def test_removed_only(self, tmp_path):
        path = tmp_path / "refs.bib"
        _write_local_refs_bib(path, [
            ("10.1234/local.one", "l1"),
            ("10.1234/local.two", "l2"),
        ])
        client = _mock_client([
            _zitem("Z1", "Z1", "10.1234/local.one"),  # match
        ])
        diff = diff_collection_to_local(client, "COLL", path)
        assert diff["new_dois"] == []
        assert diff["removed_dois"] == ["10.1234/local.two"]
        assert diff["unchanged_n"] == 1

    def test_unchanged_only(self, tmp_path):
        path = tmp_path / "refs.bib"
        _write_local_refs_bib(path, [("10.1234/local.one", "l1")])
        client = _mock_client([_zitem("Z1", "Z1", "10.1234/local.one")])
        diff = diff_collection_to_local(client, "COLL", path)
        assert diff["new_dois"] == []
        assert diff["removed_dois"] == []
        assert diff["unchanged_n"] == 1
        assert len(diff["new_items"]) == 0

    def test_mixed(self, tmp_path):
        path = tmp_path / "refs.bib"
        _write_local_refs_bib(path, [
            ("10.1234/local.one", "l1"),       # match
            ("10.1234/local.two", "l2"),       # removed
            ("10.1234/local.three", "l3"),     # removed
        ])
        client = _mock_client([
            _zitem("Z1", "Z1", "10.1234/local.one"),   # match
            _zitem("Z2", "Z2", "10.1234/zotero.new"),  # new
            _zitem("Z3", "Z3", "10.1234/zotero.other"),  # new
        ])
        diff = diff_collection_to_local(client, "COLL", path)
        assert sorted(diff["new_dois"]) == ["10.1234/zotero.new", "10.1234/zotero.other"]
        assert sorted(diff["removed_dois"]) == ["10.1234/local.three", "10.1234/local.two"]
        assert diff["unchanged_n"] == 1
        assert len(diff["new_items"]) == 2

    def test_local_no_dois_skipped(self, tmp_path):
        # Local entries without DOI are ignored for diff
        path = tmp_path / "refs.bib"
        path.write_text(
            "@misc{nodoi, title = {No DOI paper}}\n",
            encoding="utf-8",
        )
        client = _mock_client([_zitem("Z1", "Z1", "10.1234/zotero.new")])
        diff = diff_collection_to_local(client, "COLL", path)
        # Local has 0 DOIs; Zotero's 1 DOI is "new"
        assert diff["local_n_dois"] == 0
        assert diff["new_dois"] == ["10.1234/zotero.new"]

    def test_zotero_no_dois_skipped(self, tmp_path):
        path = tmp_path / "refs.bib"
        _write_local_refs_bib(path, [("10.1234/local.one", "l1")])
        client = _mock_client([
            _zitem("Z1", "Z1", ""),  # no DOI
            _zitem("Z2", "Z2", "10.1234/local.one"),  # match
        ])
        diff = diff_collection_to_local(client, "COLL", path)
        # Only Z2 has DOI, which matches local
        assert diff["zotero_n_items"] == 2  # total items (including no-DOI)
        assert diff["unchanged_n"] == 1
        assert diff["new_dois"] == []

    def test_empty_collection(self, tmp_path):
        path = tmp_path / "refs.bib"
        _write_local_refs_bib(path, [("10.1234/local.one", "l1")])
        client = _mock_client([])
        diff = diff_collection_to_local(client, "COLL", path)
        assert diff["new_dois"] == []
        assert diff["removed_dois"] == ["10.1234/local.one"]
        assert diff["zotero_n_items"] == 0


# ─────────────────────────────────────────────────────────────────
# TestSyncCollectionToLocal
# ─────────────────────────────────────────────────────────────────
def _setup_pulled_project(tmp_path, slug=None, name="Long-term care",
                         collection_key="COLL_KEY", version=1,
                         local_dois=None):
    """Create a local pa project mimicking what `pull` would have created.

    Default slug is the slugified version of `name` (matching what
    `sync_collection_to_local` derives when no --slug is passed).
    """
    import re as _re
    if slug is None:
        slug = _re.sub(r"[^A-Za-z0-9._-]+", "-", name.strip()).strip("-").lower() or "zotero-project"
    proj_dir = tmp_path / slug
    proj_dir.mkdir()
    refs_path = proj_dir / "refs.bib"
    meta_path = proj_dir / "meta.json"
    _write_local_refs_bib(refs_path, local_dois or [])
    meta = {
        "slug": slug,
        "title": name,
        "description": f"Pulled from Zotero collection '{name}'",
        "zotero_collection_key": collection_key,
        "zotero_collection_name": name,
        "zotero_collection_version": version,
        "source": "zotero-pull",
        "n_items": len(local_dois or []),
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return proj_dir, refs_path, meta_path


class TestSyncCollectionToLocal:
    def test_collection_not_found(self, tmp_path, monkeypatch):
        client = _mock_client([])
        # find_collection_by_name is a module-level function; mock it
        monkeypatch.setattr(zotero_api, "find_collection_by_name", lambda c, n, parent_key=None: None)
        result = sync_collection_to_local(
            client, "NoSuchCollection", project_root=tmp_path
        )
        assert result["status"] == "error"
        assert "not found" in result["error"]

    def test_local_project_not_found(self, tmp_path, monkeypatch):
        # Create a Zotero collection but no local project
        coll = {"key": "COLL", "name": "X", "version": 1}
        client = MagicMock()
        monkeypatch.setattr(zotero_api, "find_collection_by_name", lambda c, n, parent_key=None: coll)
        result = sync_collection_to_local(
            client, "X", project_root=tmp_path, project_slug="nope"
        )
        assert result["status"] == "error"
        assert "local project not found" in result["error"]

    def test_dry_run_default_no_writes(self, tmp_path, monkeypatch):
        proj_dir, refs_path, meta_path = _setup_pulled_project(
            tmp_path, local_dois=[("10.1234/local.one", "l1")],
            version=1,
        )
        coll = {"key": "COLL_KEY", "name": "Long-term care", "version": 5}
        client = MagicMock()
        client.collection_items.return_value = [
            _zitem("Z1", "Z1", "10.1234/local.one"),
            _zitem("Z2", "Z2", "10.1234/zotero.new"),
        ]
        monkeypatch.setattr(zotero_api, "find_collection_by_name", lambda c, n, parent_key=None: coll)
        # Default dry_run=True
        result = sync_collection_to_local(
            client, "Long-term care", project_root=tmp_path
        )
        assert result["status"] == "ok_dry_run"
        assert result["dry_run"] is True
        assert result["applied"] is False
        assert result["n_new"] == 1
        assert result["n_unchanged"] == 1
        assert result["n_removed"] == 0
        # refs.bib NOT modified
        content = refs_path.read_text(encoding="utf-8")
        assert "zotero.new" not in content
        # meta.json NOT modified
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        assert meta["zotero_collection_version"] == 1  # still old
        assert "zotero_last_sync_at" not in meta

    def test_apply_writes_new_items(self, tmp_path, monkeypatch):
        proj_dir, refs_path, meta_path = _setup_pulled_project(
            tmp_path, local_dois=[("10.1234/local.one", "l1")], version=1,
        )
        coll = {"key": "COLL_KEY", "name": "Long-term care", "version": 5}
        client = MagicMock()
        client.collection_items.return_value = [
            _zitem("Z1", "Z1", "10.1234/local.one"),
            _zitem("Z2", "Z2", "10.1234/zotero.new"),
        ]
        monkeypatch.setattr(zotero_api, "find_collection_by_name", lambda c, n, parent_key=None: coll)
        result = sync_collection_to_local(
            client, "Long-term care",
            project_root=tmp_path, dry_run=False,
        )
        assert result["status"] == "ok"
        assert result["applied"] is True
        assert result["n_new"] == 1
        # refs.bib now has both
        content = refs_path.read_text(encoding="utf-8")
        assert "10.1234/local.one" in content
        assert "10.1234/zotero.new" in content
        # meta.json refreshed
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        assert meta["zotero_collection_version"] == 5
        assert "zotero_last_sync_at" in meta
        assert meta["n_items"] == 2

    def test_removed_items_kept_locally_and_tracked(self, tmp_path, monkeypatch):
        proj_dir, refs_path, meta_path = _setup_pulled_project(
            tmp_path,
            local_dois=[
                ("10.1234/local.one", "l1"),
                ("10.1234/local.two", "l2"),  # this is removed from Zotero
            ],
            version=1,
        )
        coll = {"key": "COLL_KEY", "name": "Long-term care", "version": 5}
        client = MagicMock()
        client.collection_items.return_value = [
            _zitem("Z1", "Z1", "10.1234/local.one"),
        ]
        monkeypatch.setattr(zotero_api, "find_collection_by_name", lambda c, n, parent_key=None: coll)
        result = sync_collection_to_local(
            client, "Long-term care",
            project_root=tmp_path, dry_run=False,
        )
        assert result["n_removed"] == 1
        # local kept (not deleted)
        content = refs_path.read_text(encoding="utf-8")
        assert "10.1234/local.two" in content
        # meta.json tracks removed
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        assert "removed_from_zotero" in meta
        assert "10.1234/local.two" in meta["removed_from_zotero"]

    def test_up_to_date(self, tmp_path, monkeypatch):
        proj_dir, refs_path, meta_path = _setup_pulled_project(
            tmp_path, local_dois=[("10.1234/local.one", "l1")], version=1,
        )
        coll = {"key": "COLL_KEY", "name": "Long-term care", "version": 5}
        client = MagicMock()
        client.collection_items.return_value = [
            _zitem("Z1", "Z1", "10.1234/local.one"),
        ]
        monkeypatch.setattr(zotero_api, "find_collection_by_name", lambda c, n, parent_key=None: coll)
        result = sync_collection_to_local(
            client, "Long-term care",
            project_root=tmp_path, dry_run=False,
        )
        assert result["n_new"] == 0
        assert result["n_removed"] == 0
        assert result["n_unchanged"] == 1
        # meta.json still updated (version refresh even when no diff)
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        assert meta["zotero_collection_version"] == 5

    def test_idempotent_apply(self, tmp_path, monkeypatch):
        # Running apply twice should not duplicate items
        proj_dir, refs_path, meta_path = _setup_pulled_project(
            tmp_path, local_dois=[("10.1234/local.one", "l1")], version=1,
        )
        coll = {"key": "COLL_KEY", "name": "Long-term care", "version": 5}
        client = MagicMock()
        client.collection_items.return_value = [
            _zitem("Z1", "Z1", "10.1234/local.one"),
            _zitem("Z2", "Z2", "10.1234/zotero.new"),
        ]
        monkeypatch.setattr(zotero_api, "find_collection_by_name", lambda c, n, parent_key=None: coll)
        # First apply
        sync_collection_to_local(client, "Long-term care",
                                  project_root=tmp_path, dry_run=False)
        # Second apply
        result = sync_collection_to_local(client, "Long-term care",
                                          project_root=tmp_path, dry_run=False)
        # No new items now (already pulled)
        assert result["n_new"] == 0
        # refs.bib should not have duplicate @article entries
        content = refs_path.read_text(encoding="utf-8")
        # Count @article entries (each item has exactly one @article start)
        assert content.count("@article") == 2  # l1 + zotero.new, no dupes


# ─────────────────────────────────────────────────────────────────
# TestCliDiffSync (smoke tests via Click CliRunner)
# ─────────────────────────────────────────────────────────────────
class TestCliDiffSync:
    def test_diff_help(self):
        from click.testing import CliRunner
        from pa_cli import cli
        result = CliRunner().invoke(cli.main, ["zotero-project", "diff", "--help"])
        assert result.exit_code == 0
        assert "--name" in result.output
        assert "--slug" in result.output

    def test_sync_help(self):
        from click.testing import CliRunner
        from pa_cli import cli
        result = CliRunner().invoke(cli.main, ["zotero-project", "sync", "--help"])
        assert result.exit_code == 0
        assert "--apply" in result.output
        assert "--no-apply" in result.output

    def test_diff_missing_name_and_key_errors(self):
        from click.testing import CliRunner
        from pa_cli import cli
        result = CliRunner().invoke(cli.main, ["zotero-project", "diff"])
        assert result.exit_code == 2
        assert "--name or --key" in result.output

    def test_sync_missing_name_and_key_errors(self):
        from click.testing import CliRunner
        from pa_cli import cli
        result = CliRunner().invoke(cli.main, ["zotero-project", "sync"])
        assert result.exit_code == 2
        assert "--name or --key" in result.output
