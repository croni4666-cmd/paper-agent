"""Tests for PRISMA mermaid block in pa search-and-import master note.

v3.9.20 [P2-19.1] - master note auto-embeds a PRISMA flow diagram
after the Downloaded/Failed tables.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pa_cli.search_and_import import _render_master_note, _render_prisma_block


class TestRenderPrismaBlock:
    def test_block_present(self):
        block = _render_prisma_block(
            identified=10, after_screening=8,
            after_eligibility=7, included=7, excluded=3,
        )
        assert block  # non-empty
        # Should contain the mermaid markers
        assert "```mermaid" in block
        assert "flowchart" in block
        # Should mention the count
        assert "10" in block
        assert "8" in block

    def test_block_handles_zero(self):
        block = _render_prisma_block(
            identified=0, after_screening=0,
            after_eligibility=0, included=0, excluded=0,
        )
        # Should still render (0 papers case)
        assert "```mermaid" in block


class TestRenderMasterNoteWithPrisma:
    def test_prisma_in_master_note(self):
        note = _render_master_note(
            project_name="long-term care",
            query="long-term care insurance",
            downloaded=[
                {"key": "a1", "title": "Paper 1", "doi": "10.1/a",
                 "saved_as": "a1.pdf", "size_bytes": 1000},
                {"key": "a2", "title": "Paper 2", "doi": "10.1/b",
                 "saved_as": "a2.pdf", "size_bytes": 2000},
            ],
            failed=[
                {"key": "a3", "title": "Paper 3", "doi": "10.1/c",
                 "error": "Cloudflare block"},
            ],
            coll_key="COLL_KEY_1",
            n_added=2,
        )
        # Should contain a PRISMA flow section
        assert "## PRISMA flow" in note
        assert "```mermaid" in note
        assert "flowchart" in note
        # Counts should reflect: 3 identified (2+1), 2 screened, 2 included
        assert "3 identified" in note  # may appear in the mermaid block
        assert "2 screened" in note

    def test_prisma_handles_no_papers(self):
        # Empty run (no downloaded, no failed)
        note = _render_master_note(
            project_name="empty", query="x",
            downloaded=[], failed=[],
            coll_key="CK", n_added=0,
        )
        # PRISMA section should still be there (with all zeros)
        assert "## PRISMA flow" in note
        assert "```mermaid" in note
