"""Regression test suite for GPT 6th re-review issues (commit dd26466).

Covers:
1. Finding 1 (P2): project_enrich preserves bare year macro (year=ym) when OpenAlex/S2 metadata lacks publication_year.
2. Finding 2 (P2): Pure string concatenation in screening export evaluated correctly without @string macros, with empty macros, and with irrelevant macros.
3. Extended Macro Fidelity: @string definitions support nested braces, '#' concatenation, and alias resolution.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pa_cli.export_screening import build_screening_dict
from pa_cli.project import init_project, project_enrich
from pa_cli.scaffold import load_bibtex, parse_bibtex, resolve_bibtex_value


class TestRereviewDd26466Fixes(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.root = self.tmpdir / "projects"
        self.root.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    # ---------- Finding 1: project_enrich fallback preserves year macro ----------

    def test_enrich_preserves_bare_year_macro_when_publication_year_missing(self):
        """When enrich API returns metadata without publication_year, existing year=ym macro is preserved."""
        init_project("test_ym", root=self.root, title="Year Macro Test")
        bib_text = (
            '@string{ym="2024"}\n'
            '@article{k,\n'
            '  title = {Paper 10.1234/fake},\n'
            '  year = ym,\n'
            '  doi = {10.1234/fake}\n'
            '}\n'
        )
        (self.root / "test_ym" / "refs.bib").write_text(bib_text, encoding="utf-8")

        mock_work = {
            "title": "Enriched Paper Title",
            "authorships": [{"author": {"display_name": "Jane Doe"}}],
            "publication_year": None,  # Missing publication_year from API
            "host_venue": {"name": "Science"},
            "type": "journal-article",
        }

        with patch("pa_cli.citations.get_work_by_doi", return_value=mock_work):
            res = project_enrich("test_ym", root=self.root, force=True)

        self.assertEqual(res["enriched"], 1)
        enriched_text = (self.root / "test_ym" / "refs.bib").read_text(encoding="utf-8")
        # Title, author, journal updated with braces
        self.assertIn("title = {Enriched Paper Title}", enriched_text)
        self.assertIn("author = {Doe, Jane}", enriched_text)
        self.assertIn("journal = {Science}", enriched_text)
        # Year macro ym preserved WITHOUT braces
        self.assertIn("year = ym", enriched_text)
        self.assertNotIn("year = {ym}", enriched_text)

        entries = load_bibtex(self.root / "test_ym" / "refs.bib")
        self.assertIn("year", entries[0].get("_bare_fields", ()))

    def test_enrich_updates_year_and_clears_bare_when_publication_year_present(self):
        """When enrich API supplies publication_year, entry['year'] is updated and cleared from _bare_fields."""
        init_project("test_new_yr", root=self.root, title="New Year Test")
        bib_text = (
            '@string{ym="2024"}\n'
            '@article{k,\n'
            '  title = {Paper 10.1234/fake},\n'
            '  year = ym,\n'
            '  doi = {10.1234/fake}\n'
            '}\n'
        )
        (self.root / "test_new_yr" / "refs.bib").write_text(bib_text, encoding="utf-8")

        mock_work = {
            "title": "Enriched Paper Title",
            "authorships": [{"author": {"display_name": "Jane Doe"}}],
            "publication_year": 2025,
            "host_venue": {"name": "Science"},
            "type": "journal-article",
        }

        with patch("pa_cli.citations.get_work_by_doi", return_value=mock_work):
            res = project_enrich("test_new_yr", root=self.root, force=True)

        self.assertEqual(res["enriched"], 1)
        enriched_text = (self.root / "test_new_yr" / "refs.bib").read_text(encoding="utf-8")
        self.assertIn("year = {2025}", enriched_text)
        self.assertNotIn("year = ym", enriched_text)

        entries = load_bibtex(self.root / "test_new_yr" / "refs.bib")
        self.assertNotIn("year", entries[0].get("_bare_fields", ()))

    # ---------- Finding 2: Pure string concatenation evaluation in screening export ----------

    def test_screening_export_concatenation_without_any_macros(self):
        """Screening export evaluates pure string concatenation even when bib has zero @string definitions."""
        bib_text = (
            '@article{k,\n'
            '  title = {Study},\n'
            '  author = {Doe, Jane},\n'
            '  year = 2024,\n'
            '  journal = "Journal" # " Suppl"\n'
            '}\n'
        )
        bib_file = self.tmpdir / "test_no_macros.bib"
        bib_file.write_text(bib_text, encoding="utf-8")

        out = build_screening_dict(bib_file)
        self.assertEqual(out["k"]["venue"], "Journal Suppl")

    def test_screening_export_concatenation_with_empty_and_irrelevant_macros(self):
        """Equivalence across no macros, empty macros, and irrelevant macros for string concatenation."""
        # 1. Direct resolver call with None and empty dict
        val = '"Journal" # " Suppl"'
        self.assertEqual(resolve_bibtex_value(val, is_bare=True, macros=None), "Journal Suppl")
        self.assertEqual(resolve_bibtex_value(val, is_bare=True, macros={}), "Journal Suppl")
        self.assertEqual(resolve_bibtex_value(val, is_bare=True, macros={"unused": "Unused"}), "Journal Suppl")

        # 2. Bib file with irrelevant macro definition
        bib_text = (
            '@string{unused="Unused"}\n'
            '@article{k,\n'
            '  title = {Study},\n'
            '  author = {Doe, Jane},\n'
            '  year = 2024,\n'
            '  journal = "Journal" # " Suppl"\n'
            '}\n'
        )
        bib_file = self.tmpdir / "test_irrelevant_macro.bib"
        bib_file.write_text(bib_text, encoding="utf-8")

        out = build_screening_dict(bib_file)
        self.assertEqual(out["k"]["venue"], "Journal Suppl")

    def test_screening_export_braced_first_concatenation_without_macros(self):
        """Braced-first concatenation {Journal} # " Suppl" resolves to Journal Suppl without macros."""
        bib_text = (
            '@article{k,\n'
            '  title = {Study},\n'
            '  author = {Doe, Jane},\n'
            '  year = 2024,\n'
            '  journal = {Journal} # " Suppl"\n'
            '}\n'
        )
        bib_file = self.tmpdir / "test_braced_concat.bib"
        bib_file.write_text(bib_text, encoding="utf-8")

        out = build_screening_dict(bib_file)
        self.assertEqual(out["k"]["venue"], "Journal Suppl")

    # ---------- Extended Macro Fidelity: @string definitions support ----------

    def test_string_definitions_nested_braces_and_concatenation(self):
        """@string definitions handle nested braces, '#' concatenation, and alias references."""
        bib_text = (
            '@string{base = "Journal"}\n'
            '@string{jconcat = "Journal" # " Suppl"}\n'
            '@string{jnested = {Journal of {Testing}}}\n'
            '@string{jalias = base # " Suppl"}\n'
            '@article{k1, title={T1}, journal=jconcat}\n'
            '@article{k2, title={T2}, journal=jnested}\n'
            '@article{k3, title={T3}, journal=jalias}\n'
        )
        bib_file = self.tmpdir / "test_macros_extended.bib"
        bib_file.write_text(bib_text, encoding="utf-8")

        out = build_screening_dict(bib_file)
        self.assertEqual(out["k1"]["venue"], "Journal Suppl")
        self.assertEqual(out["k2"]["venue"], "Journal of {Testing}")
        self.assertEqual(out["k3"]["venue"], "Journal Suppl")


if __name__ == "__main__":
    unittest.main()
