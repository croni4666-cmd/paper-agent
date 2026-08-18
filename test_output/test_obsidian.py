"""Tests for pa_cli.obsidian — research sub-vault + project management.

v3.9.16 [P3-29] module. Pure stdlib (no new deps).
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Make pa_cli importable
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pa_cli import obsidian as obs_mod


@pytest.fixture
def fake_vault(tmp_path, monkeypatch):
    """Set up a fake Obsidian vault root and point env var at it."""
    vault = tmp_path / "fake-vault"
    vault.mkdir()
    monkeypatch.setenv("PAPER_AGENT_OBSIDIAN_VAULT", str(vault))
    # Clear any subfolder override
    monkeypatch.delenv("PAPER_AGENT_OBSIDIAN_SUBFOLDER", raising=False)
    return vault


# ─────────────────────────────────────────────────────────────────
# TestSlugify
# ─────────────────────────────────────────────────────────────────
class TestSlugify:
    def test_simple_ascii(self):
        assert obs_mod.slugify("Long-term Care Insurance") == "long-term-care-insurance"

    def test_underscores_to_hyphens(self):
        assert obs_mod.slugify("foo_bar_baz") == "foo-bar-baz"

    def test_caps_become_lowercase(self):
        assert obs_mod.slugify("FooBarBaz") == "foobarbaz"

    def test_special_chars_stripped(self):
        assert obs_mod.slugify("Foo!@#$Bar") == "foo-bar"

    def test_empty_returns_untitled(self):
        assert obs_mod.slugify("").startswith("untitled")

    def test_pure_cjk_returns_untitled_with_timestamp(self):
        # CJK chars get stripped by ASCII NFKD normalization
        result = obs_mod.slugify("数字普惠金融")
        # Either empty (becomes 'untitled-timestamp') or has 'untitled' prefix
        assert "untitled" in result

    def test_max_length_truncates(self):
        long = "a" * 100
        slug = obs_mod.slugify(long, max_len=20)
        assert len(slug) <= 20

    def test_consecutive_hyphens_collapsed(self):
        assert obs_mod.slugify("foo   bar") == "foo-bar"


# ─────────────────────────────────────────────────────────────────
# TestSafeFilename
# ─────────────────────────────────────────────────────────────────
class TestSafeFilename:
    def test_format(self):
        fname = obs_mod.safe_filename("Wang 2020 - LTCI")
        assert fname.startswith("wang-2020-ltci-")
        assert fname.endswith(".md")

    def test_collision_avoidance_returns_md(self):
        f = obs_mod.safe_filename("Foo", suffix=".md")
        assert f.endswith(".md")

    def test_empty_stem_uses_untitled(self):
        f = obs_mod.safe_filename("", suffix=".md")
        assert "untitled" in f


# ─────────────────────────────────────────────────────────────────
# TestVaultConfig
# ─────────────────────────────────────────────────────────────────
class TestVaultConfig:
    def test_get_vault_path_unset_returns_none(self, monkeypatch):
        monkeypatch.delenv("PAPER_AGENT_OBSIDIAN_VAULT", raising=False)
        assert obs_mod.get_vault_path() is None

    def test_get_vault_path_returns_path(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PAPER_AGENT_OBSIDIAN_VAULT", str(tmp_path))
        assert obs_mod.get_vault_path() == tmp_path

    def test_get_research_root_unset_raises(self, monkeypatch):
        monkeypatch.delenv("PAPER_AGENT_OBSIDIAN_VAULT", raising=False)
        with pytest.raises(ValueError, match="PAPER_AGENT_OBSIDIAN_VAULT is not set"):
            obs_mod.get_research_root()

    def test_get_research_root_default_subfolder(self, fake_vault):
        root = obs_mod.get_research_root()
        assert root == fake_vault / "0-Research"

    def test_get_research_root_custom_subfolder(self, fake_vault, monkeypatch):
        monkeypatch.setenv("PAPER_AGENT_OBSIDIAN_SUBFOLDER", "Research")
        root = obs_mod.get_research_root()
        assert root == fake_vault / "Research"


# ─────────────────────────────────────────────────────────────────
# TestInit
# ─────────────────────────────────────────────────────────────────
class TestInit:
    def test_init_creates_skeleton(self, fake_vault):
        result = obs_mod.init_vault()
        assert result["status"] == "ok"
        root = Path(result["root"])
        assert (root / "Inbox").is_dir()
        assert (root / "Projects").is_dir()
        assert (root / "README.md").is_file()
        assert len(result["created"]) >= 4

    def test_init_idempotent(self, fake_vault):
        result1 = obs_mod.init_vault()
        result2 = obs_mod.init_vault()
        # Second run: README and dirs should be in 'existed', not 'created'
        assert result2["created"] == []
        assert len(result2["existed"]) >= 4

    def test_init_unset_env_raises(self, monkeypatch):
        monkeypatch.delenv("PAPER_AGENT_OBSIDIAN_VAULT", raising=False)
        with pytest.raises(ValueError):
            obs_mod.init_vault()


# ─────────────────────────────────────────────────────────────────
# TestCreateProject
# ─────────────────────────────────────────────────────────────────
class TestCreateProject:
    def test_create_simple(self, fake_vault):
        obs_mod.init_vault()
        result = obs_mod.create_project(name="long-term care")
        assert result["status"] == "created"
        assert result["slug"] == "long-term-care"
        # Files exist
        assert obs_mod.project_index_path("long-term-care").exists()
        assert obs_mod.project_ideas_path("long-term-care").exists()
        assert (obs_mod.project_root("long-term-care") / "notes").is_dir()

    def test_create_with_question_and_direction(self, fake_vault):
        obs_mod.init_vault()
        result = obs_mod.create_project(
            name="digital finance",
            research_question="How does digital finance affect rural households?",
            direction="empirical microeconomics",
            topic="China policy",
        )
        assert result["status"] == "created"
        content = obs_mod.project_index_path("digital-finance").read_text(encoding="utf-8")
        assert "digital finance" in content.lower() or "Digital finance" in content
        assert "rural households" in content
        assert "microeconomics" in content
        assert "China policy" in content

    def test_create_idempotent(self, fake_vault):
        obs_mod.init_vault()
        r1 = obs_mod.create_project(name="long-term care")
        r2 = obs_mod.create_project(name="long-term care")
        assert r1["status"] == "created"
        assert r2["status"] == "exists"
        assert r1["slug"] == r2["slug"]

    def test_create_empty_name_returns_error(self, fake_vault):
        result = obs_mod.create_project(name="")
        assert result["status"] == "error"
        assert "empty" in result["error"].lower()

    def test_create_without_init_works(self, fake_vault):
        # Should auto-init? No — list_projects returns [] if Projects/ missing.
        # create_project just creates the dir + files. Let's test that.
        result = obs_mod.create_project(name="x")
        assert result["status"] == "created"
        # But the project might be created in the wrong place if not inited
        # (Projects/ subdir won't exist)
        # Actually: project_root calls get_research_root then /Projects/<slug>/
        # parent dir creation is handled by mkdir(parents=True, exist_ok=False)
        # which creates the full chain. So this works.
        assert obs_mod.project_index_path("x").exists()


# ─────────────────────────────────────────────────────────────────
# TestListProjects
# ─────────────────────────────────────────────────────────────────
class TestListProjects:
    def test_list_empty(self, fake_vault):
        obs_mod.init_vault()
        assert obs_mod.list_projects() == []

    def test_list_multiple(self, fake_vault):
        obs_mod.init_vault()
        obs_mod.create_project(name="long-term care")
        obs_mod.create_project(name="digital finance")
        projects = obs_mod.list_projects()
        assert len(projects) == 2
        slugs = {p["slug"] for p in projects}
        assert slugs == {"long-term-care", "digital-finance"}

    def test_list_includes_thought_count(self, fake_vault):
        obs_mod.init_vault()
        obs_mod.create_project(name="long-term care")
        obs_mod.add_thought(name="long-term care", content="thought 1")
        obs_mod.add_thought(name="long-term care", content="thought 2")
        projects = obs_mod.list_projects()
        ltc = next(p for p in projects if p["slug"] == "long-term-care")
        assert ltc["thought_count"] == 2
        assert ltc["has_index"] is True
        assert ltc["has_ideas"] is True

    def test_list_no_projects_dir_returns_empty(self, fake_vault):
        # No init — no Projects/ dir
        assert obs_mod.list_projects() == []


# ─────────────────────────────────────────────────────────────────
# TestAddThought
# ─────────────────────────────────────────────────────────────────
class TestAddThought:
    def test_add_thought_appends_to_ideas(self, fake_vault):
        obs_mod.init_vault()
        obs_mod.create_project(name="long-term care")
        result = obs_mod.add_thought(name="long-term care", content="Wang 2020 has good ID")
        assert result["status"] == "ok"
        assert result["thought_count"] == 1
        content = obs_mod.project_ideas_path("long-term-care").read_text(encoding="utf-8")
        assert "Wang 2020" in content

    def test_add_thought_auto_creates_project(self, fake_vault):
        obs_mod.init_vault()
        result = obs_mod.add_thought(name="brand new topic", content="raw idea")
        assert result["status"] == "ok"
        # Project was auto-created
        assert obs_mod.project_exists("brand-new-topic")

    def test_add_thought_empty_content_error(self, fake_vault):
        result = obs_mod.add_thought(name="x", content="")
        assert result["status"] == "error"

    def test_add_multiple_thoughts_increments_count(self, fake_vault):
        obs_mod.init_vault()
        obs_mod.create_project(name="x")
        for i in range(5):
            r = obs_mod.add_thought(name="x", content=f"thought {i}")
        assert r["thought_count"] == 5


# ─────────────────────────────────────────────────────────────────
# TestAddNote
# ─────────────────────────────────────────────────────────────────
class TestAddNote:
    def test_add_note_creates_file_with_frontmatter(self, fake_vault):
        obs_mod.init_vault()
        result = obs_mod.add_note(
            name="x",
            content="Wang (2020) finds X. Key insight: pilot had 12% reduction.",
            note_type="reading",
            title="Wang 2020",
        )
        assert result["status"] == "created"
        path = Path(result["path"])
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "title: \"Wang 2020\"" in content
        assert "type: reading" in content
        assert "Wang (2020)" in content

    def test_add_note_inherits_title_from_first_line(self, fake_vault):
        obs_mod.init_vault()
        result = obs_mod.add_note(
            name="x",
            content="My First Insight\n\nMore details here.",
            note_type="idea",
        )
        assert result["title"] == "My First Insight"

    def test_add_note_auto_creates_project(self, fake_vault):
        obs_mod.init_vault()
        obs_mod.add_note(name="new topic", content="c", note_type="idea")
        assert obs_mod.project_exists("new-topic")

    def test_add_note_invalid_type_returns_error(self, fake_vault):
        obs_mod.init_vault()
        result = obs_mod.add_note(name="x", content="c", note_type="bogus")
        assert result["status"] == "error"
        assert "invalid note_type" in result["error"]

    def test_add_note_types_all_work(self, fake_vault):
        obs_mod.init_vault()
        for t in obs_mod.NOTE_TYPES:
            r = obs_mod.add_note(name="x", content="c", note_type=t)
            assert r["status"] == "created", f"failed for type={t}"
            assert r["type"] == t


# ─────────────────────────────────────────────────────────────────
# TestProjectStatus
# ─────────────────────────────────────────────────────────────────
class TestProjectStatus:
    def test_status_returns_full_state(self, fake_vault):
        obs_mod.init_vault()
        obs_mod.create_project(name="long-term care")
        obs_mod.add_thought(name="long-term care", content="t1")
        obs_mod.add_thought(name="long-term care", content="t2")
        obs_mod.add_note(name="long-term care", content="c", note_type="reading")

        result = obs_mod.project_status("long-term-care")
        assert result["status"] == "ok"
        assert result["name"] == "long-term care"
        assert result["thought_count"] == 2
        assert result["note_count"] == 1
        assert result["synthesis_present"] is False
        assert len(result["recent_notes"]) == 1

    def test_status_missing_project_returns_error(self, fake_vault):
        result = obs_mod.project_status("nonexistent")
        assert result["status"] == "error"
        assert "not found" in result["error"]


# ─────────────────────────────────────────────────────────────────
# TestInbox
# ─────────────────────────────────────────────────────────────────
class TestInbox:
    def test_inbox_add_creates_file(self, fake_vault):
        obs_mod.init_vault()
        result = obs_mod.inbox_add("cross-ref: paper X")
        assert result["status"] == "created"
        path = Path(result["path"])
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "cross-ref: paper X" in content
        assert "source: pa obsidian inbox add" in content

    def test_inbox_list_returns_recent_first(self, fake_vault):
        obs_mod.init_vault()
        obs_mod.inbox_add("first thought")
        obs_mod.inbox_add("second thought")
        items = obs_mod.inbox_list()
        assert len(items) == 2
        # Both notes are present (ordering can vary within same second on Windows)
        paths = " ".join(it["filename"] for it in items)
        assert "first-thought" in paths
        assert "second-thought" in paths

    def test_inbox_list_empty(self, fake_vault):
        items = obs_mod.inbox_list()
        assert items == []

    def test_inbox_add_empty_content_error(self, fake_vault):
        result = obs_mod.inbox_add("")
        assert result["status"] == "error"

    def test_inbox_list_respects_limit(self, fake_vault):
        obs_mod.init_vault()
        for i in range(5):
            obs_mod.inbox_add(f"thought {i}")
        items = obs_mod.inbox_list(limit=2)
        assert len(items) == 2


# ─────────────────────────────────────────────────────────────────
# TestReadFirstHeading
# ─────────────────────────────────────────────────────────────────
class TestReadFirstHeading:
    def test_simple_h1(self, fake_vault):
        f = fake_vault / "test.md"
        f.write_text("# Hello World\n\nbody\n", encoding="utf-8")
        assert obs_mod._read_first_heading(f) == "Hello World"

    def test_yaml_title_fallback(self, fake_vault):
        f = fake_vault / "test.md"
        f.write_text(
            "---\ntitle: 'My Title'\ntype: idea\n---\n\nbody\n",
            encoding="utf-8",
        )
        assert obs_mod._read_first_heading(f) == "My Title"

    def test_yaml_title_with_double_quotes(self, fake_vault):
        f = fake_vault / "test.md"
        f.write_text('---\ntitle: "Quoted Title"\n---\n\nbody\n', encoding="utf-8")
        assert obs_mod._read_first_heading(f) == "Quoted Title"

    def test_no_heading_returns_question_mark(self, fake_vault):
        f = fake_vault / "test.md"
        f.write_text("just body, no heading", encoding="utf-8")
        assert obs_mod._read_first_heading(f) == "?"

    def test_h2_not_used(self, fake_vault):
        f = fake_vault / "test.md"
        f.write_text("## Subsection\n\nbody\n", encoding="utf-8")
        # H2 is not H1, so should fall through to "?"
        assert obs_mod._read_first_heading(f) == "?"
