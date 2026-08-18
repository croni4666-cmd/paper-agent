"""Tests for pa obsidian daily-link (v3.9.20 [P3-29.2]).

Adds a backlink to a research project in today's (or a given date's)
daily note at <vault>/4-Daily/<date>.md. Idempotent via per-project
HTML comment marker.
"""
from __future__ import annotations

import sys
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pa_cli import obsidian as obs_mod


# ─────────────────────────────────────────────────────────────────
# TestDailyLink
# ─────────────────────────────────────────────────────────────────
class TestDailyLink:
    def test_skipped_no_vault(self, monkeypatch):
        # Clear env var
        monkeypatch.delenv("PAPER_AGENT_OBSIDIAN_VAULT", raising=False)
        result = obs_mod.daily_link("long-term care", date="2026-08-18")
        assert result["status"] == "skipped_no_vault"

    def test_vault_path_does_not_exist(self, tmp_path):
        # Point to non-existent path
        fake_vault = tmp_path / "no-such-vault"
        result = obs_mod.daily_link(
            "long-term care", date="2026-08-18", vault_path=fake_vault
        )
        assert result["status"] == "skipped_no_vault"

    def test_skipped_no_daily_note(self, tmp_path):
        # Vault exists but no 4-Daily/2026-08-18.md
        result = obs_mod.daily_link(
            "long-term care", date="2099-01-01", vault_path=tmp_path
        )
        assert result["status"] == "skipped_no_daily_note"
        assert result["link_added"] is False
        # Default: no file created
        assert not (tmp_path / "4-Daily" / "2099-01-01.md").exists()

    def test_create_if_missing(self, tmp_path):
        # --create flag should create a stub daily note
        result = obs_mod.daily_link(
            "long-term care", date="2099-01-01",
            vault_path=tmp_path, create_if_missing=True,
        )
        assert result["status"] == "linked"
        assert result["link_added"] is True
        assert result["section_created"] is True
        daily_path = tmp_path / "4-Daily" / "2099-01-01.md"
        assert daily_path.exists()
        content = daily_path.read_text(encoding="utf-8")
        assert "## Active research projects" in content
        assert "[[0-Research/Projects/long-term-care/index|long-term care]]" in content
        # Idempotency marker for this project
        assert "<!-- paper-agent:daily-link:long-term-care -->" in content

    def test_link_to_existing_daily_note(self, tmp_path):
        # Pre-create a daily note without the section
        daily_dir = tmp_path / "4-Daily"
        daily_dir.mkdir()
        daily_path = daily_dir / "2026-08-18.md"
        daily_path.write_text(
            "# 2026-08-18\n\n## Today\n- [ ] one thing\n",
            encoding="utf-8",
        )
        result = obs_mod.daily_link(
            "long-term care", date="2026-08-18", vault_path=tmp_path
        )
        assert result["status"] == "linked"
        assert result["link_added"] is True
        assert result["section_created"] is True  # new section
        content = daily_path.read_text(encoding="utf-8")
        assert "## Active research projects" in content
        assert "[[0-Research/Projects/long-term-care/index|long-term care]]" in content

    def test_idempotent_link(self, tmp_path):
        # Link once, then again - should be a no-op
        daily_dir = tmp_path / "4-Daily"
        daily_dir.mkdir()
        daily_path = daily_dir / "2026-08-18.md"
        daily_path.write_text("# 2026-08-18\n", encoding="utf-8")
        r1 = obs_mod.daily_link("long-term care", date="2026-08-18", vault_path=tmp_path)
        assert r1["link_added"] is True
        r2 = obs_mod.daily_link("long-term care", date="2026-08-18", vault_path=tmp_path)
        assert r2["link_added"] is False
        assert r2["section_created"] is False
        assert r2["status"] == "linked"
        # File should have only one per-project marker (the comment marker is the dedup key)
        content = daily_path.read_text(encoding="utf-8")
        assert content.count("<!-- paper-agent:daily-link:long-term-care -->") == 1

    def test_multiple_projects_same_day(self, tmp_path):
        # Link 3 different projects on the same day
        daily_dir = tmp_path / "4-Daily"
        daily_dir.mkdir()
        daily_path = daily_dir / "2026-08-18.md"
        daily_path.write_text("# 2026-08-18\n", encoding="utf-8")
        for name in ["long-term care", "digital-finance", "biohack"]:
            r = obs_mod.daily_link(name, date="2026-08-18", vault_path=tmp_path)
            assert r["link_added"] is True
        content = daily_path.read_text(encoding="utf-8")
        # 3 project entries + 1 section header
        assert content.count("[[0-Research/Projects/") == 3
        assert "long-term-care" in content
        assert "digital-finance" in content
        assert "biohack" in content

    def test_link_to_existing_section(self, tmp_path):
        # Pre-create a daily note that already has the section
        daily_dir = tmp_path / "4-Daily"
        daily_dir.mkdir()
        daily_path = daily_dir / "2026-08-18.md"
        daily_path.write_text(
            "# 2026-08-18\n\n## Active research projects\n"
            "- existing-project\n\n## Another section\n",
            encoding="utf-8",
        )
        result = obs_mod.daily_link(
            "long-term care", date="2026-08-18", vault_path=tmp_path
        )
        assert result["link_added"] is True
        # Section already existed, so section_created=False
        assert result["section_created"] is False
        content = daily_path.read_text(encoding="utf-8")
        # Both the existing project and the new one should be there
        assert "existing-project" in content
        assert "long-term care" in content
        # New entry should be BEFORE "## Another section"
        idx_new = content.index("long-term care")
        idx_other = content.index("## Another section")
        assert idx_new < idx_other

    def test_subfolder_override(self, tmp_path, monkeypatch):
        # Custom sub-folder via env var
        monkeypatch.setenv("PAPER_AGENT_OBSIDIAN_SUBFOLDER", "Research")
        (tmp_path / "4-Daily").mkdir()
        (tmp_path / "4-Daily" / "2026-08-18.md").write_text(
            "# 2026-08-18\n", encoding="utf-8"
        )
        result = obs_mod.daily_link(
            "long-term care", date="2026-08-18", vault_path=tmp_path
        )
        assert result["status"] == "linked"
        content = (tmp_path / "4-Daily" / "2026-08-18.md").read_text(encoding="utf-8")
        assert "[[Research/Projects/long-term-care/index" in content


# ─────────────────────────────────────────────────────────────────
# TestCliDailyLink
# ─────────────────────────────────────────────────────────────────
class TestCliDailyLink:
    def test_help(self):
        from click.testing import CliRunner
        from pa_cli import cli
        result = CliRunner().invoke(cli.main, ["obsidian", "daily-link", "--help"])
        assert result.exit_code == 0
        assert "--project" in result.output
        assert "--date" in result.output
        assert "--create" in result.output
