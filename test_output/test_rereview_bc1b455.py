"""Regression test suite for GPT 4th re-review issues (commit bc1b455).

Covers:
1. Finding 1 (P1): Parenthesis-delimited entry delimiter scanner with nested intervals, parens, and quotes.
2. Finding 2 (P1): Preservation of macro reference syntax (journal = jmacro) and # concatenation without wrapping in braces.
3. Finding 3 (P2): Separation of special bibliography nodes (@string, @preamble) from paper consumers
   (load_bibtex, build_screening_dict, corpus_stats, scaffold_review, cite_check).
4. Minor Observation: Prevention of private internal metadata leaking into formatted BibTeX (_crossref_from_source).
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pa_cli.bibtex import format_bibtex_entry
from pa_cli.cite_check import run_cite_check
from pa_cli.corpus_stats import compute_corpus_stats
from pa_cli.export_screening import build_screening_dict
from pa_cli.project import init_project, corpus_merge
from pa_cli.scaffold import load_bibtex, parse_bibtex, scaffold


class TestRereviewBc1b455Fixes(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.root = self.tmpdir / "projects"
        self.root.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    # ---------- Finding 1: Parenthesis Format Entry Scanner ----------

    def test_parens_entry_format_with_math_intervals(self):
        """Parenthesis-delimited entry with interval (0,1] or [0,1) retains all fields."""
        bib_text = (
            "@article(k,\n"
            "  title={Use the interval (0,1]},\n"
            "  author={Doe, John},\n"
            "  year={2021}\n"
            ")\n"
        )
        parsed = parse_bibtex(bib_text)
        self.assertEqual(len(parsed), 1)
        entry = parsed[0]
        self.assertEqual(entry["key"], "k")
        self.assertEqual(entry["title"], "Use the interval (0,1]")
        self.assertEqual(entry["author"], "Doe, John")
        self.assertEqual(entry["year"], "2021")

    def test_parens_entry_merge_roundtrip(self):
        """Merging @article(k, ...) preserves title with parens, author, and year."""
        init_project("target_p", root=self.root, title="Target P")
        init_project("source_p", root=self.root, title="Source P")

        source_refs = self.root / "source_p" / "refs.bib"
        source_refs.write_text(
            "@article(k,\n"
            "  title={Use the interval (0,1]},\n"
            "  author={Doe, John},\n"
            "  year={2021}\n"
            ")\n",
            encoding="utf-8",
        )

        res = corpus_merge("target_p", "source_p", root=self.root)
        self.assertEqual(res["added"], 1)

        target_refs = self.root / "target_p" / "refs.bib"
        loaded = load_bibtex(target_refs)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["title"], "Use the interval (0,1]")
        self.assertEqual(loaded[0]["author"], "Doe, John")
        self.assertEqual(loaded[0]["year"], "2021")

    def test_parens_entry_quoted_parens_and_reversed_intervals(self):
        """Parenthesis entry scanner handles [0,1) and quoted parentheses gracefully."""
        bib_text = (
            '@article(p2,\n'
            '  title="Study on [0,1) intervals (Part 1)",\n'
            '  author="Doe, (Jane) and Smith, Bob",\n'
            '  year=2022\n'
            ')\n'
        )
        parsed = parse_bibtex(bib_text)
        self.assertEqual(len(parsed), 1)
        entry = parsed[0]
        self.assertEqual(entry["key"], "p2")
        self.assertEqual(entry["title"], "Study on [0,1) intervals (Part 1)")
        self.assertEqual(entry["author"], "Doe, (Jane) and Smith, Bob")
        self.assertEqual(entry["year"], "2022")

    # ---------- Finding 2: Macro References Preserved Without Braces ----------

    def test_macro_reference_preservation_in_formatter(self):
        """Macro references like journal=jmacro must format as bare identifiers, not {jmacro}."""
        bib_text = (
            '@string{jmacro = "Journal of Testing"}\n'
            '@article{paper,\n'
            '  title={A Study},\n'
            '  author={Doe, Jane},\n'
            '  year=2024,\n'
            '  journal=jmacro\n'
            '}\n'
        )
        parsed = parse_bibtex(bib_text, include_special=True)
        article_entry = [e for e in parsed if e.get("type") == "article"][0]
        formatted = format_bibtex_entry(article_entry)

        # Must be bare macro reference, NOT braced
        self.assertIn("journal = jmacro", formatted)
        self.assertNotIn("journal = {jmacro}", formatted)
        self.assertIn("year = 2024", formatted)
        self.assertIn("title = {A Study}", formatted)

    def test_macro_and_concatenation_merge_roundtrip(self):
        """Merging entries with bare macros and # concatenation preserves macro semantics."""
        init_project("target_macro", root=self.root, title="Target Macro")
        init_project("source_macro", root=self.root, title="Source Macro")

        source_refs = self.root / "source_macro" / "refs.bib"
        source_refs.write_text(
            '@string{jmacro = "Journal of Testing"}\n\n'
            '@article{paper,\n'
            '  title={A Study},\n'
            '  author={Doe, Jane},\n'
            '  year=2024,\n'
            '  journal=jmacro\n'
            '}\n\n'
            '@article{paper_concat,\n'
            '  title={Another Study},\n'
            '  author={Smith, Bob},\n'
            '  year=2024,\n'
            '  journal=jmacro # " Suppl 1"\n'
            '}\n',
            encoding="utf-8",
        )

        res = corpus_merge("target_macro", "source_macro", root=self.root)
        self.assertEqual(res["added"], 3)  # 1 special + 2 articles

        target_refs = self.root / "target_macro" / "refs.bib"
        content = target_refs.read_text(encoding="utf-8")
        self.assertIn('@string{jmacro = "Journal of Testing"}', content)
        self.assertIn("journal = jmacro", content)
        self.assertNotIn("journal = {jmacro}", content)
        self.assertIn('journal = jmacro # " Suppl 1"', content)

    # ---------- Finding 3: Special Records Separation from Paper Consumers ----------

    def test_special_records_separation_across_consumers(self):
        """Special records (@string, @preamble) must not pollute paper-level consumers."""
        bib_path = self.tmpdir / "test_separation.bib"
        bib_content = (
            '@string{jmacro = "Journal of Testing"}\n'
            '@preamble{"\\makeatletter"}\n\n'
            '@article{jmacro,\n'
            '  title = {Paper with Key jmacro},\n'
            '  author = {Smith, Alice},\n'
            '  year = {2023},\n'
            '  journal = jmacro,\n'
            '  doi = {10.1234/test}\n'
            '}\n'
        )
        bib_path.write_text(bib_content, encoding="utf-8")

        # 1. load_bibtex: returns only the 1 paper, not 3
        papers = load_bibtex(bib_path)
        self.assertEqual(len(papers), 1)
        self.assertEqual(papers[0]["key"], "jmacro")
        self.assertEqual(papers[0]["type"], "article")

        # 2. build_screening_dict: article is not overwritten by @string, macro resolved
        screen_dict = build_screening_dict(bib_path)
        self.assertEqual(len(screen_dict), 1)
        self.assertIn("jmacro", screen_dict)
        self.assertEqual(screen_dict["jmacro"]["title"], "Paper with Key jmacro")
        self.assertEqual(screen_dict["jmacro"]["authors"], "Smith, Alice")
        self.assertEqual(screen_dict["jmacro"]["venue"], "Journal of Testing")

        # 3. corpus_stats: counts exactly 1 paper
        stats = compute_corpus_stats(bib_path)
        self.assertEqual(stats["n_papers"], 1)
        self.assertEqual(stats["by_type"], {"article": 1})

        # 4. scaffold: renders only 1 heading, no untitled sections for special nodes
        md = scaffold(bib_path)
        self.assertIn("Paper with Key jmacro", md)
        self.assertNotIn("Untitled", md)
        self.assertNotIn("_preamble", md)

        # 5. cite_check: cites [@jmacro], reports 0 missing, 0 orphan
        skeleton_path = self.tmpdir / "skeleton.md"
        skeleton_path.write_text("See study [@jmacro].\n", encoding="utf-8")
        result, report = run_cite_check(bib_path, skeleton_path)
        self.assertEqual(len(result["missing"]), 0)
        self.assertEqual(len(result["orphan"]), 0)
        self.assertNotIn("jmacro", result["orphan"])
        self.assertNotIn("_preamble", result["orphan"])

    # ---------- Minor Observation: No Internal Metadata Leakage ----------

    def test_internal_metadata_not_leaked_into_bibtex(self):
        """_crossref_from_source and internal _ keys must never be written to BibTeX."""
        entry = {
            "key": "child_ch",
            "type": "incollection",
            "title": "Chapter 1",
            "crossref": "parent_v2",
            "_crossref_from_source": True,
            "_was_updated": True,
            "_bare_fields": {"crossref"},
        }
        formatted = format_bibtex_entry(entry)
        self.assertNotIn("_crossref_from_source", formatted)
        self.assertNotIn("_was_updated", formatted)
        self.assertNotIn("_bare_fields", formatted)
        self.assertIn("crossref = parent_v2", formatted)


if __name__ == "__main__":
    unittest.main()
