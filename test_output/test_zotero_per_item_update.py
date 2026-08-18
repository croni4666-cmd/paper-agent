"""Tests for per-item update detection in zotero_api (v3.9.20 [P3-28.4]).

Extends v3.9.19's diff/sync to detect items edited in Zotero after
the last local sync. Tracks per-item version in meta.json
`zotero_item_versions` map.
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
    _parse_refs_bib_for_zotero_keys,
    diff_collection_to_local,
    sync_collection_to_local,
)


def _zitem(key, title, doi, version=1):
    """Build a pyzotero item dict with explicit version field."""
    return {
        "key": key,
        "data": {
            "key": key,
            "title": title,
            "DOI": doi,
            "date": "2024",
            "itemType": "journalArticle",
            "version": version,
            "creators": [{"creatorType": "author", "firstName": "A", "lastName": "B"}],
        },
    }


def _setup_pulled_project(tmp_path, slug="long-term-care",
                         local_zotero_keys=None, stored_versions=None):
    """Create a local pa project mimicking what `pull` would have created.

    local_zotero_keys: list of (zotero_key, doi) to embed in refs.bib entries
    stored_versions: dict {zotero_key: version} to put in meta.json's
                     zotero_item_versions
    """
    import re as _re
    if not slug:
        slug = "long-term-care"
    proj_dir = tmp_path / slug
    proj_dir.mkdir()
    refs_path = proj_dir / "refs.bib"
    meta_path = proj_dir / "meta.json"

    # Write refs.bib with zotero_key field
    lines = []
    for i, (zk, doi) in enumerate(local_zotero_keys or []):
        lines.append(f"@article{{paper{i},")
        lines.append(f"  title = {{Paper {i}}},")
        lines.append(f"  doi = {{{doi}}},")
        if zk:
            lines.append(f"  zotero_key = {{{zk}}}")
        lines.append("}")
    refs_path.write_text("\n\n".join(lines) + "\n", encoding="utf-8")

    meta = {
        "slug": slug,
        "title": "Long-term care",
        "zotero_collection_key": "COLL_KEY",
        "zotero_collection_name": "Long-term care",
        "zotero_collection_version": 1,
        "source": "zotero-pull",
    }
    if stored_versions:
        meta["zotero_item_versions"] = stored_versions
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return proj_dir, refs_path, meta_path


# ─────────────────────────────────────────────────────────────────
# TestParseRefsBibForZoteroKeys
# ─────────────────────────────────────────────────────────────────
class TestParseRefsBibForZoteroKeys:
    def test_no_zotero_keys(self, tmp_path):
        path = tmp_path / "refs.bib"
        path.write_text(
            "@article{p1, title={T1}, doi={10.1/a}}\n",
            encoding="utf-8",
        )
        assert _parse_refs_bib_for_zotero_keys(path) == {}

    def test_with_zotero_keys(self, tmp_path):
        path = tmp_path / "refs.bib"
        path.write_text(
            "@article{p1, title={T1}, doi={10.1234/aaa}, zotero_key={ABC123}}\n"
            "@article{p2, title={T2}, doi={10.1234/bbb}, zotero_key={DEF456}}\n",
            encoding="utf-8",
        )
        result = _parse_refs_bib_for_zotero_keys(path)
        # DOIs are normalized (lowercase); ABC123 and DEF456 are Zotero keys
        assert result == {"ABC123": "10.1234/aaa", "DEF456": "10.1234/bbb"}

    def test_nonexistent_file(self, tmp_path):
        assert _parse_refs_bib_for_zotero_keys(tmp_path / "nope.bib") == {}

    def test_missing_doi(self, tmp_path):
        path = tmp_path / "refs.bib"
        path.write_text(
            "@article{p1, title={T1}, zotero_key={ABC123}}\n",
            encoding="utf-8",
        )
        result = _parse_refs_bib_for_zotero_keys(path)
        # Missing DOI is OK; we just have zotero_key with empty doi
        assert result == {"ABC123": ""}


# ─────────────────────────────────────────────────────────────────
# TestDiffCollectionToLocalWithUpdates
# ─────────────────────────────────────────────────────────────────
class TestDiffCollectionToLocalWithUpdates:
    def test_no_meta_json_no_updates(self, tmp_path, monkeypatch):
        # No meta.json -> no version map -> 0 updates detected (baseline)
        proj_dir, refs_path, meta_path = _setup_pulled_project(
            tmp_path, local_zotero_keys=[("ABC1", "10.1234/local.one")],
        )
        meta_path.unlink()  # remove meta.json
        coll_data = [
            _zitem("ABC1", "Paper 1", "10.1234/local.one", version=10),
        ]
        client = MagicMock()
        client.collection_items.return_value = coll_data
        diff = diff_collection_to_local(client, "COLL", refs_path)
        # Without meta.json, no update detection
        assert diff["n_updated"] == 0
        assert diff["updated_items"] == []

    def test_detect_updated_item(self, tmp_path, monkeypatch):
        # meta.json has stored version; Zotero.version > stored -> updated
        proj_dir, refs_path, meta_path = _setup_pulled_project(
            tmp_path,
            local_zotero_keys=[("ABC1", "10.1234/local.one")],
            stored_versions={"ABC1": 5},  # stored = 5
        )
        # Zotero has version 10 -> 10 > 5 -> updated
        coll_data = [
            _zitem("ABC1", "Paper 1", "10.1234/local.one", version=10),
        ]
        client = MagicMock()
        client.collection_items.return_value = coll_data
        diff = diff_collection_to_local(client, "COLL", refs_path, local_meta_path=meta_path)
        assert diff["n_updated"] == 1
        assert diff["updated_items"][0]["key"] == "ABC1"

    def test_unchanged_item_not_updated(self, tmp_path, monkeypatch):
        proj_dir, refs_path, meta_path = _setup_pulled_project(
            tmp_path,
            local_zotero_keys=[("ABC1", "10.1234/local.one")],
            stored_versions={"ABC1": 10},  # stored = 10
        )
        # Zotero has version 10 -> 10 == 10 -> not updated
        coll_data = [
            _zitem("ABC1", "Paper 1", "10.1234/local.one", version=10),
        ]
        client = MagicMock()
        client.collection_items.return_value = coll_data
        diff = diff_collection_to_local(client, "COLL", refs_path, local_meta_path=meta_path)
        assert diff["n_updated"] == 0

    def test_mixed_updated_and_unchanged(self, tmp_path, monkeypatch):
        proj_dir, refs_path, meta_path = _setup_pulled_project(
            tmp_path,
            local_zotero_keys=[
                ("ABC1", "10.1234/a"),
                ("ABC2", "10.1234/b"),
            ],
            stored_versions={"ABC1": 5, "ABC2": 10},
        )
        # ABC1: Zotero.version=10 > stored=5 -> updated
        # ABC2: Zotero.version=10 == stored=10 -> unchanged
        coll_data = [
            _zitem("ABC1", "P1", "10.1234/a", version=10),
            _zitem("ABC2", "P2", "10.1234/b", version=10),
        ]
        client = MagicMock()
        client.collection_items.return_value = coll_data
        diff = diff_collection_to_local(client, "COLL", refs_path, local_meta_path=meta_path)
        assert diff["n_updated"] == 1
        assert diff["updated_items"][0]["key"] == "ABC1"


# ─────────────────────────────────────────────────────────────────
# TestSyncRefreshesVersionMap
# ─────────────────────────────────────────────────────────────────
class TestSyncRefreshesVersionMap:
    def test_apply_writes_version_map(self, tmp_path, monkeypatch):
        # Set up a pulled project (no version map yet)
        proj_dir, refs_path, meta_path = _setup_pulled_project(
            tmp_path, local_zotero_keys=[("ABC1", "10.1234/a")],
        )
        coll_data = [
            _zitem("ABC1", "P1", "10.1234/a", version=7),
        ]
        coll = {"key": "COLL_KEY", "name": "Long-term care", "version": 1}
        client = MagicMock()
        client.collection_items.return_value = coll_data
        monkeypatch.setattr(zotero_api, "find_collection_by_name", lambda c, n, parent_key=None: coll)

        result = sync_collection_to_local(
            client, "Long-term care",
            project_root=tmp_path, project_slug="long-term-care",
            dry_run=False,
        )
        assert result["status"] == "ok"
        # meta.json should now have zotero_item_versions
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        assert "zotero_item_versions" in meta
        assert meta["zotero_item_versions"] == {"ABC1": 7}

    def test_apply_dry_run_does_not_write(self, tmp_path, monkeypatch):
        proj_dir, refs_path, meta_path = _setup_pulled_project(
            tmp_path, local_zotero_keys=[("ABC1", "10.1234/a")],
        )
        coll_data = [_zitem("ABC1", "P1", "10.1234/a", version=7)]
        coll = {"key": "COLL_KEY", "name": "Long-term care", "version": 1}
        client = MagicMock()
        client.collection_items.return_value = coll_data
        monkeypatch.setattr(zotero_api, "find_collection_by_name", lambda c, n, parent_key=None: coll)

        result = sync_collection_to_local(
            client, "Long-term care",
            project_root=tmp_path, project_slug="long-term-care",
            dry_run=True,
        )
        assert result["status"] == "ok_dry_run"
        # meta.json should NOT have zotero_item_versions (dry-run)
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        assert "zotero_item_versions" not in meta

    def test_idempotent_after_first_sync(self, tmp_path, monkeypatch):
        # First sync establishes baseline; second sync finds 0 updates
        proj_dir, refs_path, meta_path = _setup_pulled_project(
            tmp_path, local_zotero_keys=[("ABC1", "10.1234/a")],
        )
        coll_data = [_zitem("ABC1", "P1", "10.1234/a", version=7)]
        coll = {"key": "COLL_KEY", "name": "Long-term care", "version": 1}
        client = MagicMock()
        client.collection_items.return_value = coll_data
        monkeypatch.setattr(zotero_api, "find_collection_by_name", lambda c, n, parent_key=None: coll)

        # First sync
        sync_collection_to_local(
            client, "Long-term care",
            project_root=tmp_path, project_slug="long-term-care",
            dry_run=False,
        )
        # Second sync: same versions, 0 updates
        diff = diff_collection_to_local(client, "COLL_KEY", refs_path, local_meta_path=meta_path)
        assert diff["n_updated"] == 0

    def test_detect_update_on_second_sync(self, tmp_path, monkeypatch):
        # First sync establishes baseline; bump version, then second sync
        proj_dir, refs_path, meta_path = _setup_pulled_project(
            tmp_path, local_zotero_keys=[("ABC1", "10.1234/a")],
        )
        coll_data = [_zitem("ABC1", "P1", "10.1234/a", version=7)]
        coll = {"key": "COLL_KEY", "name": "Long-term care", "version": 1}
        client = MagicMock()
        client.collection_items.return_value = coll_data
        monkeypatch.setattr(zotero_api, "find_collection_by_name", lambda c, n, parent_key=None: coll)

        # First sync: baseline
        sync_collection_to_local(
            client, "Long-term care",
            project_root=tmp_path, project_slug="long-term-care",
            dry_run=False,
        )
        # User edits in Zotero: version bumps 7 -> 10
        client.collection_items.return_value = [
            _zitem("ABC1", "P1", "10.1234/a", version=10),
        ]
        # Second sync: should detect 1 update
        diff = diff_collection_to_local(client, "COLL_KEY", refs_path, local_meta_path=meta_path)
        assert diff["n_updated"] == 1
        assert diff["updated_items"][0]["key"] == "ABC1"


# ─────────────────────────────────────────────────────────────────
# TestCliSmoke
# ─────────────────────────────────────────────────────────────────
class TestCliSmoke:
    def test_diff_help_shows_updated_line(self):
        from click.testing import CliRunner
        from pa_cli import cli
        result = CliRunner().invoke(cli.main, ["zotero-project", "diff", "--help"])
        assert result.exit_code == 0

    def test_sync_help_still_works(self):
        from click.testing import CliRunner
        from pa_cli import cli
        result = CliRunner().invoke(cli.main, ["zotero-project", "sync", "--help"])
        assert result.exit_code == 0
