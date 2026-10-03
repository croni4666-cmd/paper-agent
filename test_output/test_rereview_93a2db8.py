"""Regression test suite for GPT 3rd re-review issues (commit 93a2db8).

Covers:
1. Finding 1 (P1): Preservation of @string, @preamble, and @comment during corpus_merge and project_enrich.
2. Finding 2 (P1): Quoted field scanner handling of braces within quotes (title="A {"quoted"} study").
3. Finding 3 (P1): MCP 1.x version bound constraint verification in pyproject.toml and Server.list_tools.
4. Finding 4 (P2): Crossref remapping on target stub updated from source when parent cite-key collides.
5. Finding 5 (P2): Intra-source alias deduplication resolving to collision-disambiguated cite-keys.
"""
from __future__ import annotations

import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pa_cli.bibtex import format_bibtex_entry
from pa_cli.project import init_project, corpus_merge, project_enrich
from pa_cli.scaffold import load_bibtex, parse_bibtex


class TestRereview93a2db8Fixes(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.root = self.tmpdir / "projects"
        self.root.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    # ---------- Finding 1: @string and @preamble Preservation ----------

    def test_merge_preserves_string_and_preamble(self):
        """corpus_merge must not drop @string and @preamble when rewriting target bibtex."""
        init_project("target_proj", root=self.root, title="Target Project")
        target_refs = self.root / "target_proj" / "refs.bib"
        target_bib_content = (
            '@string{jmacro = "Journal of Testing"}\n'
            '@preamble{"\\makeatletter"}\n\n'
            '@article{stub1,\n'
            '  title = {Paper 10.1234/stub},\n'
            '  doi = {10.1234/stub}\n'
            '}\n\n'
            '@article{untouched,\n'
            '  title = {A Solid Study},\n'
            '  author = {Smith, John},\n'
            '  year = {2021},\n'
            '  journal = jmacro,\n'
            '  doi = {10.1234/solid}\n'
            '}\n'
        )
        target_refs.write_text(target_bib_content, encoding="utf-8")

        init_project("source_proj", root=self.root, title="Source Project")
        source_refs = self.root / "source_proj" / "refs.bib"
        source_bib_content = (
            '@article{rich_stub,\n'
            '  title = {Real Enriched Stub Title},\n'
            '  author = {Rich, Richard},\n'
            '  year = {2023},\n'
            '  journal = {Journal of Enrichment},\n'
            '  doi = {10.1234/stub}\n'
            '}\n'
        )
        source_refs.write_text(source_bib_content, encoding="utf-8")

        res = corpus_merge("target_proj", "source_proj", root=self.root)
        self.assertEqual(res["updated"], 1)

        merged_text = target_refs.read_text(encoding="utf-8")
        self.assertIn('@string{jmacro = "Journal of Testing"}', merged_text)
        self.assertIn('@preamble{"\\makeatletter"}', merged_text)
        self.assertIn("Real Enriched Stub Title", merged_text)
        self.assertIn("jmacro", merged_text)

        # Re-parse target refs to verify structure
        parsed = parse_bibtex(merged_text, include_special=True)
        special_types = [e.get("type") for e in parsed if e.get("_is_special")]
        self.assertIn("string", special_types)
        self.assertIn("preamble", special_types)

    def test_enrich_preserves_string_and_preamble(self):
        """project_enrich must not drop @string and @preamble when rewriting refs.bib."""
        init_project("enrich_proj", root=self.root, title="Enrich Project")
        refs = self.root / "enrich_proj" / "refs.bib"
        bib_content = (
            '@string{jmacro = "Journal of Testing"}\n'
            '@preamble{"\\makeatletter"}\n\n'
            '@article{stub_to_enrich,\n'
            '  title = {Paper 10.1038/nature12373},\n'
            '  doi = {10.1038/nature12373}\n'
            '}\n'
        )
        refs.write_text(bib_content, encoding="utf-8")

        fake_work = {
            "title": "A Great Nature Paper",
            "publication_year": 2013,
            "authorships": [{"author": {"display_name": "Nature Author"}}],
            "primary_location": {"source": {"display_name": "Nature"}},
            "type": "article",
        }

        with patch("pa_cli.citations.get_work_by_doi", return_value=fake_work):
            res = project_enrich("enrich_proj", root=self.root)

        self.assertEqual(res["enriched"], 1)
        enriched_text = refs.read_text(encoding="utf-8")
        self.assertIn('@string{jmacro = "Journal of Testing"}', enriched_text)
        self.assertIn('@preamble{"\\makeatletter"}', enriched_text)
        self.assertIn("A Great Nature Paper", enriched_text)

    # ---------- Finding 2: Quoted Field Scanner with Nested Braces ----------

    def test_quoted_field_scanner_nested_braces(self):
        """Quoted field scanner must not truncate strings with braces inside quotes."""
        bib_text = (
            '@article{nested_quote,\n'
            '  title="A {"quoted"} study",\n'
            '  author="Doe, Jane and Smith, John",\n'
            '  year="2024"\n'
            '}\n'
        )
        parsed = parse_bibtex(bib_text)
        self.assertEqual(len(parsed), 1)
        entry = parsed[0]
        self.assertEqual(entry["title"], 'A {"quoted"} study')
        self.assertEqual(entry["author"], "Doe, Jane and Smith, John")
        self.assertEqual(entry["year"], "2024")

        # Roundtrip through format_bibtex_entry and parse_bibtex
        formatted = format_bibtex_entry(entry)
        re_parsed = parse_bibtex(formatted)
        self.assertEqual(len(re_parsed), 1)
        self.assertEqual(re_parsed[0]["title"], 'A {"quoted"} study')
        self.assertEqual(re_parsed[0]["author"], "Doe, Jane and Smith, John")

    def test_quoted_field_merge_roundtrip(self):
        """Merging entries with title="A {"quoted"} study" preserves all fields upon re-read."""
        init_project("target_empty", root=self.root, title="Target Empty")
        init_project("source_quote", root=self.root, title="Source Quote")

        source_refs = self.root / "source_quote" / "refs.bib"
        source_refs.write_text(
            '@article{quoted_entry,\n'
            '  title="A {"quoted"} study",\n'
            '  author="Doe, Jane",\n'
            '  year="2024",\n'
            '  doi="10.1234/quoted"\n'
            '}\n',
            encoding="utf-8",
        )

        res = corpus_merge("target_empty", "source_quote", root=self.root)
        self.assertEqual(res["added"], 1)

        target_refs = self.root / "target_empty" / "refs.bib"
        loaded = load_bibtex(target_refs)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["title"], 'A {"quoted"} study')
        self.assertEqual(loaded[0]["author"], "Doe, Jane")
        self.assertEqual(loaded[0]["year"], "2024")

    # ---------- Finding 3: MCP 1.x Version Bound and API Compatibility ----------

    def test_mcp_version_bound_in_pyproject(self):
        """pyproject.toml must bound mcp to <2.0.0 to prevent incompatible Server API breakage."""
        pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
        content = pyproject_path.read_text(encoding="utf-8")
        m = re.search(r'"mcp([^"]+)"', content)
        self.assertIsNotNone(m, "mcp dependency not found in pyproject.toml")
        spec = m.group(1)
        self.assertIn("<2", spec, f"mcp dependency specifier '{spec}' does not bound <2.0.0")

    def test_mcp_server_build_has_list_tools(self):
        """_build_server must return an MCP Server with callable list_tools (MCP 1.x protocol)."""
        from pa_cli.mcp_fetch import _build_server
        server = _build_server()
        self.assertTrue(hasattr(server, "list_tools"), "Server object missing list_tools attribute")
        self.assertTrue(callable(getattr(server, "list_tools")))

    # ---------- Finding 4: Crossref Remapping on Updated Target Stub ----------

    def test_crossref_remapping_on_updated_stub(self):
        """When target stub is updated from source, copied crossref must remap to collision key."""
        init_project("target_stub_proj", root=self.root, title="Target Stub Proj")
        target_refs = self.root / "target_stub_proj" / "refs.bib"
        target_refs.write_text(
            # Target has unrelated 'parent' book
            '@book{parent,\n'
            '  title = {Unrelated Target Book},\n'
            '  year = {2010},\n'
            '  doi = {10.9999/unrelated}\n'
            '}\n\n'
            # Target has stub for child chapter
            '@incollection{child_stub,\n'
            '  title = {Paper 10.1234/child},\n'
            '  doi = {10.1234/child}\n'
            '}\n',
            encoding="utf-8",
        )

        init_project("source_rich_proj", root=self.root, title="Source Rich Proj")
        source_refs = self.root / "source_rich_proj" / "refs.bib"
        source_refs.write_text(
            # Source has relevant 'parent' book
            '@book{parent,\n'
            '  title = {Relevant Source Book},\n'
            '  year = {2023},\n'
            '  doi = {10.1234/book}\n'
            '}\n\n'
            # Source has rich child pointing to source's 'parent'
            '@incollection{child_rich,\n'
            '  title = {Chapter 1: Deep Learning},\n'
            '  author = {Goodfellow, Ian},\n'
            '  crossref = {parent},\n'
            '  doi = {10.1234/child}\n'
            '}\n',
            encoding="utf-8",
        )

        res = corpus_merge("target_stub_proj", "source_rich_proj", root=self.root)
        self.assertEqual(res["added"], 1)  # source's parent added as parent_v2
        self.assertEqual(res["updated"], 1)  # child_stub updated

        target_entries = load_bibtex(target_refs)
        by_key = {e["key"]: e for e in target_entries}

        # Verify target's original parent was not renamed
        self.assertIn("parent", by_key)
        self.assertEqual(by_key["parent"]["doi"], "10.9999/unrelated")

        # Verify added book got collision key 'parent_v2'
        self.assertIn("parent_v2", by_key)
        self.assertEqual(by_key["parent_v2"]["doi"], "10.1234/book")

        # Verify updated child_stub points to 'parent_v2', NOT 'parent'
        self.assertIn("child_stub", by_key)
        self.assertEqual(by_key["child_stub"]["crossref"], "parent_v2")
        self.assertEqual(by_key["child_stub"]["title"], "Chapter 1: Deep Learning")

    # ---------- Finding 5: Sequential Dedup Before Collision Resolves Aliases ----------

    def test_alias_dedup_resolves_to_collision_key(self):
        """Intra-source alias deduplicated against collided parent maps child crossref to parent_v2."""
        init_project("target_coll_proj", root=self.root, title="Target Coll Proj")
        target_refs = self.root / "target_coll_proj" / "refs.bib"
        target_refs.write_text(
            '@book{parent,\n'
            '  title = {Unrelated Existing Book},\n'
            '  year = {2005},\n'
            '  doi = {10.9999/unrelated}\n'
            '}\n',
            encoding="utf-8",
        )

        init_project("source_alias_proj", root=self.root, title="Source Alias Proj")
        source_refs = self.root / "source_alias_proj" / "refs.bib"
        source_refs.write_text(
            # Source has parent book
            '@book{parent,\n'
            '  title = {Source Book Title},\n'
            '  year = {2022},\n'
            '  doi = {10.1234/book}\n'
            '}\n\n'
            # Source also has alias record with identical DOI
            '@book{alias,\n'
            '  title = {Source Book Title Alias},\n'
            '  year = {2022},\n'
            '  doi = {10.1234/book}\n'
            '}\n\n'
            # Child in source points to 'alias'
            '@incollection{child,\n'
            '  title = {Chapter citing alias},\n'
            '  crossref = {alias},\n'
            '  doi = {10.1234/child}\n'
            '}\n',
            encoding="utf-8",
        )

        res = corpus_merge("target_coll_proj", "source_alias_proj", root=self.root)
        self.assertEqual(res["added"], 2)  # parent (as parent_v2) and child
        self.assertEqual(res["duplicates_skipped"], 1)  # alias skipped

        target_entries = load_bibtex(target_refs)
        by_key = {e["key"]: e for e in target_entries}

        self.assertIn("parent", by_key)
        self.assertEqual(by_key["parent"]["doi"], "10.9999/unrelated")

        self.assertIn("parent_v2", by_key)
        self.assertEqual(by_key["parent_v2"]["doi"], "10.1234/book")

        self.assertIn("child", by_key)
        # Crucial check: crossref must point to parent_v2, NOT parent
        self.assertEqual(by_key["child"]["crossref"], "parent_v2")


if __name__ == "__main__":
    unittest.main()
