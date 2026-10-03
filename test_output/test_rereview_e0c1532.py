"""Regression test suite for GPT 5th re-review issues (commit e0c1532).

Covers:
1. Finding 1 (P1): Syntax marker (_bare_fields) synchronization on field replacement during corpus_merge and project_enrich.
2. Finding 2 (P2): JSON export serialization with bare year/macros and internal field sanitation.
3. Finding 3 (P2): Compound value expression preservation across quoted/braced-first and multiline '#' concatenation.
4. Finding 4 (P2): Accurate venue resolution in screening export (literal vs bare macro vs compound expressions).
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pa_cli.bibtex import format_bibtex_entry
from pa_cli.export_screening import build_screening_dict
from pa_cli.project import init_project, corpus_merge, project_enrich, project_export
from pa_cli.scaffold import load_bibtex, parse_bibtex, resolve_bibtex_value


class TestRereviewE0c1532Fixes(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.root = self.tmpdir / "projects"
        self.root.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    # ---------- Finding 1: Syntax marker (_bare_fields) synchronization ----------

    def test_merge_field_replacement_clears_bare_markers(self):
        """When stub with bare title/year is updated with rich braced values, bare markers are cleared."""
        init_project("target_p", root=self.root, title="Target P")
        init_project("source_p", root=self.root, title="Source P")

        target_bib = (
            "@article{k,\n"
            "  title = oldtitle,\n"
            "  year = 2024,\n"
            "  doi = {10.1234/fake}\n"
            "}\n"
        )
        source_bib = (
            "@article{s,\n"
            "  title = {A Rich Study},\n"
            "  author = {Doe, Jane},\n"
            "  year = {2024},\n"
            "  doi = {10.1234/fake}\n"
            "}\n"
        )

        (self.root / "target_p" / "refs.bib").write_text(target_bib, encoding="utf-8")
        (self.root / "source_p" / "refs.bib").write_text(source_bib, encoding="utf-8")

        res = corpus_merge("target_p", source="source_p", root=self.root)
        self.assertEqual(res["updated"], 1)

        merged_text = (self.root / "target_p" / "refs.bib").read_text(encoding="utf-8")
        self.assertIn("title = {A Rich Study}", merged_text)
        self.assertNotIn("title = A Rich Study", merged_text)
        self.assertIn("author = {Doe, Jane}", merged_text)
        self.assertIn("year = {2024}", merged_text)

        entries = load_bibtex(self.root / "target_p" / "refs.bib")
        self.assertEqual(len(entries), 1)
        self.assertNotIn("title", entries[0].get("_bare_fields", ()))
        self.assertNotIn("year", entries[0].get("_bare_fields", ()))

    def test_merge_unupdated_field_retains_its_own_bare_status(self):
        """Target's preserved custom field does not inherit bare status from source."""
        init_project("target_kw", root=self.root, title="Target KW")
        init_project("source_kw", root=self.root, title="Source KW")

        target_bib = (
            "@article{k,\n"
            "  title = {A Rich Study},\n"
            "  keywords = {alpha beta},\n"
            "  doi = {10.1234/fake}\n"
            "}\n"
        )
        source_bib = (
            "@article{s,\n"
            "  title = {A Rich Study},\n"
            "  author = {Doe, Jane},\n"
            "  keywords = kw,\n"
            "  doi = {10.1234/fake}\n"
            "}\n"
        )

        (self.root / "target_kw" / "refs.bib").write_text(target_bib, encoding="utf-8")
        (self.root / "source_kw" / "refs.bib").write_text(source_bib, encoding="utf-8")

        res = corpus_merge("target_kw", source="source_kw", root=self.root)
        self.assertEqual(res["updated"], 1)

        merged_text = (self.root / "target_kw" / "refs.bib").read_text(encoding="utf-8")
        self.assertIn("keywords = {alpha beta}", merged_text)
        self.assertNotIn("keywords = alpha beta", merged_text)

    def test_merge_target_macro_replaced_by_literal_journal(self):
        """Bare journal macro in target replaced by braced journal literal formats with braces."""
        init_project("target_jm", root=self.root, title="Target JM")
        init_project("source_jm", root=self.root, title="Source JM")

        target_bib = (
            "@article{k,\n"
            "  title = {Paper 10.1234/fake},\n"
            "  journal = jmacro,\n"
            "  doi = {10.1234/fake}\n"
            "}\n"
        )
        source_bib = (
            "@article{s,\n"
            "  title = {Real Paper Title},\n"
            "  author = {Smith, John},\n"
            "  journal = {Journal of Testing},\n"
            "  doi = {10.1234/fake}\n"
            "}\n"
        )

        (self.root / "target_jm" / "refs.bib").write_text(target_bib, encoding="utf-8")
        (self.root / "source_jm" / "refs.bib").write_text(source_bib, encoding="utf-8")

        res = corpus_merge("target_jm", source="source_jm", root=self.root)
        self.assertEqual(res["updated"], 1)

        merged_text = (self.root / "target_jm" / "refs.bib").read_text(encoding="utf-8")
        self.assertIn("journal = {Journal of Testing}", merged_text)
        self.assertNotIn("journal = Journal of Testing\n", merged_text)

    def test_project_enrich_clears_bare_markers_for_enriched_fields(self):
        """project_enrich clears bare markers for title, author, year, and journal."""
        init_project("test_enr", root=self.root, title="Enrich Test")
        bib_text = (
            "@article{k,\n"
            "  title = tm,\n"
            "  author = am,\n"
            "  year = 2024,\n"
            "  journal = jm,\n"
            "  doi = {10.1234/fake}\n"
            "}\n"
        )
        (self.root / "test_enr" / "refs.bib").write_text(bib_text, encoding="utf-8")

        mock_work = {
            "title": "Updated Study",
            "authorships": [{"author": {"display_name": "Jane Doe"}}],
            "publication_year": 2025,
            "host_venue": {"name": "Science"},
            "type": "journal-article",
            "abstract_inverted_index": {"An": [0], "abstract": [1]}
        }

        with patch("pa_cli.citations.get_work_by_doi", return_value=mock_work):
            res = project_enrich("test_enr", root=self.root, force=True)

        self.assertEqual(res["enriched"], 1)
        enriched_text = (self.root / "test_enr" / "refs.bib").read_text(encoding="utf-8")
        self.assertIn("title = {Updated Study}", enriched_text)
        self.assertNotIn("title = Updated Study\n", enriched_text)
        self.assertIn("author = {Doe, Jane}", enriched_text)
        self.assertNotIn("author = Doe, Jane\n", enriched_text)
        self.assertIn("year = {2025}", enriched_text)
        self.assertIn("journal = {Science}", enriched_text)

        entries = load_bibtex(self.root / "test_enr" / "refs.bib")
        self.assertNotIn("title", entries[0].get("_bare_fields", ()))
        self.assertNotIn("author", entries[0].get("_bare_fields", ()))
        self.assertNotIn("year", entries[0].get("_bare_fields", ()))
        self.assertNotIn("journal", entries[0].get("_bare_fields", ()))

    # ---------- Finding 2: JSON export serialization with bare year/macros ----------

    def test_project_export_json_with_bare_year_succeeds(self):
        """project_export with format='json' succeeds on bare year and sanitizes internal fields."""
        init_project("test_json", root=self.root, title="JSON Test")
        bib_text = (
            "@article{k,\n"
            "  title = {Study},\n"
            "  author = {Doe, Jane},\n"
            "  year = 2024\n"
            "}\n"
        )
        (self.root / "test_json" / "refs.bib").write_text(bib_text, encoding="utf-8")

        out = project_export("test_json", format="json", root=self.root)
        self.assertIn("content", out)
        data = json.loads(out["content"])
        self.assertEqual(data["n_papers"], 1)
        paper = data["papers"][0]
        self.assertEqual(paper["year"], "2024")
        self.assertEqual(paper["title"], "Study")
        # Ensure internal metadata starting with '_' is stripped
        for k in paper.keys():
            self.assertFalse(k.startswith("_"), f"Found internal field {k} in JSON export")

    def test_bare_fields_json_serializable_in_entry(self):
        """Parsed entry directly serializes with json.dumps without TypeError."""
        bib_text = "@article{k, title={Study}, author={Doe, Jane}, year=2024}\n"
        parsed = parse_bibtex(bib_text)
        dumped = json.dumps(parsed[0])
        self.assertIn('"year": "2024"', dumped)

    # ---------- Finding 3: Quoted/braced-first and multiline compound expressions ----------

    def test_quoted_and_braced_first_hash_concatenation_roundtrip(self):
        """Compound expressions beginning with quoted or braced tokens preserve the full expression."""
        init_project("test_concat", root=self.root, title="Concat Test")
        bib_text = (
            '@article{k1,\n'
            '  title = {Title 1},\n'
            '  journal = "Journal" # " Suppl",\n'
            '  year = 2024\n'
            '}\n'
            '@article{k2,\n'
            '  title = {Title 2},\n'
            '  journal = {Journal} # " Suppl",\n'
            '  year = 2024\n'
            '}\n'
        )
        (self.root / "test_concat" / "refs.bib").write_text(bib_text, encoding="utf-8")

        entries = load_bibtex(self.root / "test_concat" / "refs.bib")
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["journal"], '"Journal" # " Suppl"')
        self.assertEqual(entries[1]["journal"], '{Journal} # " Suppl"')

        # Format and verify both halves preserved without outer braces
        formatted_1 = format_bibtex_entry(entries[0])
        formatted_2 = format_bibtex_entry(entries[1])
        self.assertIn('journal = "Journal" # " Suppl"', formatted_1)
        self.assertNotIn('journal = {"Journal" # " Suppl"}', formatted_1)
        self.assertIn('journal = {Journal} # " Suppl"', formatted_2)
        self.assertNotIn('journal = {{Journal} # " Suppl"}', formatted_2)

    def test_multiline_hash_concatenation(self):
        """Expressions with '#' across newlines preserve all tokens without hanging '#'."""
        bib_text = (
            '@article{k1,\n'
            '  title = {Title 1},\n'
            '  journal = j #\n'
            '      " Suppl",\n'
            '  year = 2024\n'
            '}\n'
            '@article{k2,\n'
            '  title = {Title 2},\n'
            '  journal =\n'
            '      "Journal"\n'
            '      # " Suppl",\n'
            '  year = 2024\n'
            '}\n'
        )
        parsed = parse_bibtex(bib_text)
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0]["journal"], 'j # " Suppl"')
        self.assertEqual(parsed[1]["journal"], '"Journal" # " Suppl"')

        formatted = format_bibtex_entry(parsed[0])
        self.assertIn('journal = j # " Suppl"', formatted)
        self.assertNotIn('journal = j #\n', formatted)

    # ---------- Finding 4: Accurate venue resolution in screening export ----------

    def test_screening_export_venue_macro_distinction(self):
        """Screening export expands bare macros and concatenations, but keeps quoted/braced literals intact."""
        bib_text = (
            '@string{jmacro = "Journal of Testing"}\n'
            '@article{k_bare,\n'
            '  title = {Bare Macro},\n'
            '  journal = jmacro,\n'
            '  year = 2024\n'
            '}\n'
            '@article{k_braced,\n'
            '  title = {Braced Literal},\n'
            '  journal = {jmacro},\n'
            '  year = 2024\n'
            '}\n'
            '@article{k_quoted,\n'
            '  title = {Quoted Literal},\n'
            '  journal = "jmacro",\n'
            '  year = 2024\n'
            '}\n'
            '@article{k_concat,\n'
            '  title = {Concat Macro},\n'
            '  journal = jmacro # " Suppl",\n'
            '  year = 2024\n'
            '}\n'
            '@article{k_concat_quoted,\n'
            '  title = {Concat Quoted},\n'
            '  journal = "Journal" # " Suppl",\n'
            '  year = 2024\n'
            '}\n'
        )
        bib_file = self.tmpdir / "test_screening.bib"
        bib_file.write_text(bib_text, encoding="utf-8")

        out = build_screening_dict(bib_file)
        self.assertEqual(out["k_bare"]["venue"], "Journal of Testing")
        self.assertEqual(out["k_braced"]["venue"], "jmacro")
        self.assertEqual(out["k_quoted"]["venue"], "jmacro")
        self.assertEqual(out["k_concat"]["venue"], "Journal of Testing Suppl")
        self.assertEqual(out["k_concat_quoted"]["venue"], "Journal Suppl")


if __name__ == "__main__":
    unittest.main()
