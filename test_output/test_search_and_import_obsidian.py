"""Tests for pa_cli.search_and_import.setup_obsidian_project (v3.9.17.2 [P3-29.1])."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pa_cli import search_and_import as sai


# ─────────────────────────────────────────────────────────────────
# TestSetupObsidianProject
# ─────────────────────────────────────────────────────────────────
class TestSetupObsidianProject:
    def test_skips_when_vault_env_var_unset(self, monkeypatch):
        """Without $PAPER_AGENT_OBSIDIAN_VAULT, return status='skipped' gracefully."""
        monkeypatch.delenv("PAPER_AGENT_OBSIDIAN_VAULT", raising=False)
        result = sai.setup_obsidian_project(
            project_name="test",
            zotero_project_key="Z1",
            zotero_note_key="N1",
            n_downloaded=5,
            n_failed=1,
        )
        assert result["status"] == "skipped"
        assert "not set" in result["reason"].lower()

    def test_creates_project_and_adds_thought(self, tmp_path, monkeypatch):
        """With vault set: create project + add thought referencing Zotero."""
        vault = tmp_path / "vault"
        vault.mkdir()
        monkeypatch.setenv("PAPER_AGENT_OBSIDIAN_VAULT", str(vault))
        monkeypatch.delenv("PAPER_AGENT_OBSIDIAN_SUBFOLDER", raising=False)

        fake_obs = MagicMock()
        fake_obs.create_project.return_value = {
            "status": "created",
            "slug": "test-topic",
            "path": str(vault / "0-Research" / "Projects" / "test-topic" / "index.md"),
        }
        fake_obs.add_thought.return_value = {
            "status": "ok", "thought_count": 1,
        }
        with patch.object(sai, "_import_obsidian", return_value=fake_obs), \
             patch("builtins.print"):
            result = sai.setup_obsidian_project(
                project_name="test-topic",
                zotero_project_key="Z123",
                zotero_note_key="N456",
                n_downloaded=10,
                n_failed=2,
            )
        assert result["status"] == "ok"
        assert result["project_status"] == "created"
        assert result["project_slug"] == "test-topic"
        assert result["thought_count"] == 1
        # Verify create_project + add_thought called
        fake_obs.create_project.assert_called_once()
        fake_obs.add_thought.assert_called_once()
        # Verify add_thought content references Zotero project + note
        call_kwargs = fake_obs.add_thought.call_args[1]
        content = call_kwargs["content"]
        assert "Z123" in content
        assert "N456" in content
        assert "10 paper" in content
        assert "2 failed" in content

    def test_idempotent_existing_project(self, tmp_path, monkeypatch):
        """Existing Obsidian project: status='exists', still adds thought."""
        vault = tmp_path / "vault"
        vault.mkdir()
        monkeypatch.setenv("PAPER_AGENT_OBSIDIAN_VAULT", str(vault))

        fake_obs = MagicMock()
        fake_obs.create_project.return_value = {
            "status": "exists",
            "slug": "test",
            "path": str(vault / "0-Research" / "Projects" / "test" / "index.md"),
        }
        fake_obs.add_thought.return_value = {"status": "ok", "thought_count": 3}
        with patch.object(sai, "_import_obsidian", return_value=fake_obs), \
             patch("builtins.print"):
            result = sai.setup_obsidian_project(
                project_name="test",
                zotero_project_key="Z",
                zotero_note_key="N",
                n_downloaded=5,
                n_failed=0,
            )
        assert result["status"] == "ok"
        assert result["project_status"] == "exists"

    def test_thought_add_failure_continues(self, tmp_path, monkeypatch):
        """If add_thought fails, still return status='ok' (project is created)."""
        vault = tmp_path / "vault"
        vault.mkdir()
        monkeypatch.setenv("PAPER_AGENT_OBSIDIAN_VAULT", str(vault))

        fake_obs = MagicMock()
        fake_obs.create_project.return_value = {
            "status": "created", "slug": "t", "path": "/x",
        }
        fake_obs.add_thought.return_value = {
            "status": "error", "error": "permission denied",
        }
        with patch.object(sai, "_import_obsidian", return_value=fake_obs), \
             patch("builtins.print"):
            result = sai.setup_obsidian_project(
                project_name="t", zotero_project_key="", zotero_note_key="",
                n_downloaded=0, n_failed=0,
            )
        # Project is OK but thought failed
        assert result["status"] == "ok"
        assert result["thought_count"] == 0
        assert result["thought_status"] == "error"

    def test_create_project_failure_returns_error(self, tmp_path, monkeypatch):
        vault = tmp_path / "vault"
        vault.mkdir()
        monkeypatch.setenv("PAPER_AGENT_OBSIDIAN_VAULT", str(vault))

        fake_obs = MagicMock()
        fake_obs.create_project.return_value = {
            "status": "error", "error": "mkdir failed",
        }
        with patch.object(sai, "_import_obsidian", return_value=fake_obs), \
             patch("builtins.print"):
            result = sai.setup_obsidian_project(
                project_name="t", zotero_project_key="", zotero_note_key="",
                n_downloaded=0, n_failed=0,
            )
        assert result["status"] == "error"
        assert "mkdir" in result["error"]

    def test_thought_content_includes_zotero_refs(self, tmp_path, monkeypatch):
        """When both project + note keys are present, thought content
        includes both as bullet points."""
        vault = tmp_path / "vault"
        vault.mkdir()
        monkeypatch.setenv("PAPER_AGENT_OBSIDIAN_VAULT", str(vault))

        fake_obs = MagicMock()
        fake_obs.create_project.return_value = {
            "status": "created", "slug": "t", "path": "/x",
        }
        fake_obs.add_thought.return_value = {"status": "ok", "thought_count": 1}
        with patch.object(sai, "_import_obsidian", return_value=fake_obs), \
             patch("builtins.print"):
            sai.setup_obsidian_project(
                project_name="t",
                zotero_project_key="PROJKEY",
                zotero_note_key="NOTEKEY",
                n_downloaded=3,
                n_failed=1,
            )
        content = fake_obs.add_thought.call_args[1]["content"]
        assert "PROJKEY" in content
        assert "NOTEKEY" in content
        # Both lines should be bullets
        assert "- Zotero project (collection) key" in content
        assert "- Zotero master note key" in content

    def test_thought_content_handles_missing_zotero_refs(self, tmp_path, monkeypatch):
        """When no Zotero refs (e.g. --no-project), thought still created
        with just download counts."""
        vault = tmp_path / "vault"
        vault.mkdir()
        monkeypatch.setenv("PAPER_AGENT_OBSIDIAN_VAULT", str(vault))

        fake_obs = MagicMock()
        fake_obs.create_project.return_value = {
            "status": "created", "slug": "t", "path": "/x",
        }
        fake_obs.add_thought.return_value = {"status": "ok", "thought_count": 1}
        with patch.object(sai, "_import_obsidian", return_value=fake_obs), \
             patch("builtins.print"):
            sai.setup_obsidian_project(
                project_name="t",
                zotero_project_key="",
                zotero_note_key="",
                n_downloaded=7,
                n_failed=0,
            )
        content = fake_obs.add_thought.call_args[1]["content"]
        # No Zotero bullet lines, but download counts present
        assert "7 paper" in content
        assert "Zotero project" not in content


# ─────────────────────────────────────────────────────────────────
# TestRunSearchAndImportObsidianIntegration
# ─────────────────────────────────────────────────────────────────
class TestRunSearchAndImportObsidianIntegration:
    def test_obsidian_step_only_runs_when_flag_true(self, tmp_path, monkeypatch):
        """Without --with-obsidian, no obsidian step in result."""
        monkeypatch.delenv("PAPER_AGENT_OBSIDIAN_VAULT", raising=False)
        mock_search_results = {
            "results": [], "by_engine": {}, "dedup_count": 0,
        }
        with patch.object(sai, "_import_run_search", return_value=lambda *a, **kw: mock_search_results), \
             patch.object(sai, "_import_write_bibtex", return_value=lambda *a, **kw: None), \
             patch("builtins.print"):
            result = sai.run_search_and_import(
                query="x", project_name="x",
                out_dir=tmp_path / "pdfs", quiet=True,
                with_obsidian=False,  # default
            )
        assert "obsidian" not in result["steps"]

    def test_obsidian_step_runs_when_flag_true(self, tmp_path, monkeypatch):
        """With --with-obsidian, obsidian step included when search returns results."""
        monkeypatch.setenv("PAPER_AGENT_OBSIDIAN_VAULT", str(tmp_path / "vault"))
        (tmp_path / "vault").mkdir()
        # Need >=1 search result for orchestrator to continue past search step
        mock_paper = {"key": "k1", "doi": "10.1/k1", "title": "K1", "authors": [{"name": "A"}], "year": 2024, "source": "openalex"}
        mock_search_results = {
            "results": [mock_paper], "by_engine": {"openalex": 1}, "dedup_count": 1,
        }
        # Mock fetch
        fetch_results = [MagicMock(key="k1", doi="10.1/k1", title="K1",
                                success=True, saved_as="k1.pdf", size_bytes=1024,
                                error=None, elapsed_sec=5.0)]
        mock_summary = MagicMock()
        mock_summary.results = fetch_results
        mock_summary.n_total = 1
        mock_summary.n_success = 1
        mock_summary.n_failure = 0
        mock_summary.n_skipped = 0
        mock_summary.total_size_bytes = 1024
        mock_summary.total_elapsed_sec = 5.0
        # Mock zotero_api
        mock_zapi = MagicMock()
        mock_zapi.get_client.return_value = MagicMock()
        mock_zapi.create_collection.return_value = {
            "status": "created", "key": "ZKEY", "name": "x",
        }
        mock_zapi.add_items_to_collection.return_value = {"n_added": 0, "n_failed": 0, "results": []}
        mock_zapi.create_collection_note.return_value = {"status": "created", "key": "NKEY", "title": "x"}
        # Mock obsidian
        mock_obs = MagicMock()
        mock_obs.create_project.return_value = {
            "status": "created", "slug": "x", "path": "/x",
        }
        mock_obs.add_thought.return_value = {"status": "ok", "thought_count": 1}

        with patch.object(sai, "_import_run_search", return_value=lambda *a, **kw: mock_search_results), \
             patch.object(sai, "_import_write_bibtex", return_value=lambda *a, **kw: None), \
             patch.object(sai, "_import_run_fetch_batch", return_value=(lambda *a, **kw: mock_summary, MagicMock, MagicMock, lambda *a, **kw: None)), \
             patch.object(sai, "_import_zotero_api", return_value=mock_zapi), \
             patch.object(sai, "_import_obsidian", return_value=mock_obs), \
             patch("builtins.print"):
            result = sai.run_search_and_import(
                query="x", project_name="x",
                out_dir=tmp_path / "pdfs", quiet=True,
                with_obsidian=True,
            )
        assert "obsidian" in result["steps"]
        # Zotero project was created, so obsidian step should reference its keys
        obs = result["steps"]["obsidian"]
        assert obs["status"] == "ok"
        # Verify cross-ref content
        content = mock_obs.add_thought.call_args[1]["content"]
        assert "ZKEY" in content
        assert "NKEY" in content

    def test_obsidian_step_skipped_when_env_var_unset(self, tmp_path, monkeypatch):
        """With --with-obsidian but no $PAPER_AGENT_OBSIDIAN_VAULT, status='skipped'."""
        monkeypatch.delenv("PAPER_AGENT_OBSIDIAN_VAULT", raising=False)
        # Need >=1 search result for orchestrator to continue
        mock_paper = {"key": "k1", "doi": "10.1/k1", "title": "K1", "authors": [{"name": "A"}], "year": 2024, "source": "openalex"}
        mock_search_results = {
            "results": [mock_paper], "by_engine": {"openalex": 1}, "dedup_count": 1,
        }
        fetch_results = [MagicMock(key="k1", doi="10.1/k1", title="K1",
                                success=True, saved_as="k1.pdf", size_bytes=1024,
                                error=None, elapsed_sec=5.0)]
        mock_summary = MagicMock()
        mock_summary.results = fetch_results
        mock_summary.n_total = 1
        mock_summary.n_success = 1
        mock_summary.n_failure = 0
        mock_summary.n_skipped = 0
        mock_summary.total_size_bytes = 1024
        mock_summary.total_elapsed_sec = 5.0
        mock_zapi = MagicMock()
        mock_zapi.get_client.return_value = MagicMock()
        mock_zapi.create_collection.return_value = {
            "status": "created", "key": "ZKEY", "name": "x",
        }
        mock_zapi.add_items_to_collection.return_value = {"n_added": 0, "n_failed": 0, "results": []}
        mock_zapi.create_collection_note.return_value = {"status": "created", "key": "NKEY", "title": "x"}

        with patch.object(sai, "_import_run_search", return_value=lambda *a, **kw: mock_search_results), \
             patch.object(sai, "_import_write_bibtex", return_value=lambda *a, **kw: None), \
             patch.object(sai, "_import_run_fetch_batch", return_value=(lambda *a, **kw: mock_summary, MagicMock, MagicMock, lambda *a, **kw: None)), \
             patch.object(sai, "_import_zotero_api", return_value=mock_zapi), \
             patch("builtins.print"):
            result = sai.run_search_and_import(
                query="x", project_name="x",
                out_dir=tmp_path / "pdfs", quiet=True,
                with_obsidian=True,
            )
        obs = result["steps"]["obsidian"]
        assert obs["status"] == "skipped"
        assert "not set" in obs["reason"].lower()
        # Should NOT count as an error (graceful)
        assert not result["errors"]

    def test_obsidian_step_with_zotero_keys(self, tmp_path, monkeypatch):
        """Full happy path: project + obsidian with cross-refs."""
        vault = tmp_path / "vault"
        vault.mkdir()
        monkeypatch.setenv("PAPER_AGENT_OBSIDIAN_VAULT", str(vault))
        # Mock search
        mock_papers = [{"key": "k1", "doi": "10.1/k1", "title": "K1", "authors": [{"name": "A"}], "year": 2024, "source": "openalex"}]
        mock_search_results = {
            "results": mock_papers, "by_engine": {"openalex": 1}, "dedup_count": 1,
        }
        # Mock fetch: 1 downloaded, 0 failed
        fetch_results = [MagicMock(key="k1", doi="10.1/k1", title="K1", success=True, saved_as="k1.pdf", size_bytes=1024, error=None, elapsed_sec=5.0)]
        mock_summary = MagicMock()
        mock_summary.results = fetch_results
        mock_summary.n_total = 1
        mock_summary.n_success = 1
        mock_summary.n_failure = 0
        mock_summary.n_skipped = 0
        mock_summary.total_size_bytes = 1024
        mock_summary.total_elapsed_sec = 5.0
        # Mock zotero_api
        mock_zapi = MagicMock()
        mock_zapi.get_client.return_value = MagicMock()
        mock_zapi.create_collection.return_value = {
            "status": "created", "key": "ZOTEROPROJ", "name": "x",
        }
        mock_zapi.add_items_to_collection.return_value = {"n_added": 0, "n_failed": 0, "results": []}
        mock_zapi.create_collection_note.return_value = {"status": "created", "key": "ZOTERONOTE", "title": "x"}
        # Mock obsidian
        mock_obs = MagicMock()
        mock_obs.create_project.return_value = {
            "status": "created", "slug": "x", "path": "/x",
        }
        mock_obs.add_thought.return_value = {"status": "ok", "thought_count": 1}

        with patch.object(sai, "_import_run_search", return_value=lambda *a, **kw: mock_search_results), \
             patch.object(sai, "_import_write_bibtex", return_value=lambda *a, **kw: None), \
             patch.object(sai, "_import_run_fetch_batch", return_value=(lambda *a, **kw: mock_summary, MagicMock, MagicMock, lambda *a, **kw: None)), \
             patch.object(sai, "_import_zotero_api", return_value=mock_zapi), \
             patch.object(sai, "_import_obsidian", return_value=mock_obs), \
             patch("builtins.print"):
            result = sai.run_search_and_import(
                query="x", project_name="x",
                out_dir=tmp_path / "pdfs", quiet=True,
                with_obsidian=True,
            )
        # Both Zotero project + Obsidian project should be created
        assert result["steps"]["project"]["status"] == "ok"
        assert result["steps"]["obsidian"]["status"] == "ok"
        # Obsidian thought should reference Zotero keys
        content = mock_obs.add_thought.call_args[1]["content"]
        assert "ZOTEROPROJ" in content
        assert "ZOTERONOTE" in content
