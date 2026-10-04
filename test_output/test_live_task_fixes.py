"""Regression test suite for Live Task Test Report findings (2026-10-03).

Covers:
1. P2: Author formatting reversal prevention (format_authors, corpus_stats, _base_key).
2. P3: Cite-check report placeholder and bib keys count fix.
3. P2: Evidence section recognition, abstract cap (page <= 2), and required sections retrieval.
4. CLI: pa scaffold and pa build support for --out / --output aliases.
5. Markup: JATS / HTML tags and entity unescaping for titles and abstracts.
6. Search: ArXiv missing dependency and engine error reporting.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from click.testing import CliRunner
import pymupdf

from pa_cli.bibtex import (
    format_authors,
    _clean_title,
    clean_markup_text,
    unescape_bibtex,
    to_bibtex,
    make_cite_key,
)
from pa_cli.corpus_stats import _author_short as corpus_author_short, _split_authors
from pa_cli.cite_check import run_cite_check, format_report
from pa_cli.evidence import build_index, build_packet
from pa_cli.cli import main as cli_main
from pa_cli.search import search_arxiv, run_search


class TestLiveTaskFixes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    # ---------- 1. Author Formatting Reversal Prevention ----------

    def test_format_authors_no_double_reversal(self):
        # Crossref format: "Last, First" -> should remain "Last, First"
        raw_authors = ["Brynjolfsson, Erik", "Li, Danielle", "Raymond, Lindsey"]
        formatted = format_authors(raw_authors)
        self.assertEqual(formatted, "Brynjolfsson, Erik and Li, Danielle and Raymond, Lindsey")

        # Standard format: "First Last" -> should convert to "Last, First"
        raw_first_last = ["Erik Brynjolfsson", "Danielle Li"]
        formatted2 = format_authors(raw_first_last)
        self.assertEqual(formatted2, "Brynjolfsson, Erik and Li, Danielle")

        # Dirty format with trailing comma: "Brynjolfsson, Erik,"
        formatted3 = format_authors(["Brynjolfsson, Erik,"])
        self.assertEqual(formatted3, "Brynjolfsson, Erik")

        # Dict format
        formatted_dict = format_authors([{"family": "Brynjolfsson", "given": "Erik"}])
        self.assertEqual(formatted_dict, "Brynjolfsson, Erik")

        # Single name
        formatted_single = format_authors(["Plato"])
        self.assertEqual(formatted_single, "Plato")

    def test_corpus_stats_authors_short_name(self):
        # Once bibtex has "Brynjolfsson, Erik", corpus_stats should extract "Brynjolfsson", not "Erik"
        author_str = "Brynjolfsson, Erik and Li, Danielle"
        authors = _split_authors(author_str)
        self.assertEqual(len(authors), 2)
        short0 = corpus_author_short(authors[0])
        short1 = corpus_author_short(authors[1])
        self.assertEqual(short0, "Brynjolfsson")
        self.assertEqual(short1, "Li")

    def test_bibtex_key_generation_fallback(self):
        paper = {
            "title": "Generative AI at Work",
            "authors": ["Brynjolfsson, Erik"],
            "year": 2023,
        }
        key = make_cite_key(paper, seen=set())
        # Cite key should be based on lastname 'brynjolfsson', not firstname 'erik'
        self.assertTrue(key.startswith("brynjolfsson_2023_generative"))

    # ---------- 2. Cite-Check Report Counts ----------

    def test_cite_check_counts_in_text_and_json(self):
        bib_file = self.tmp_dir / "refs.bib"
        bib_file.write_text(
            "@article{ref1, title={Paper 1}, author={Smith, John}, year={2020}}\n"
            "@article{ref2, title={Paper 2}, author={Doe, Jane}, year={2021}}\n"
            "@article{ref3, title={Paper 3}, author={Lee, Bob}, year={2022}}\n"
            "@article{ref4, title={Paper 4}, author={Brown, Alice}, year={2023}}\n"
            "@article{ref5, title={Paper 5}, author={White, Chris}, year={2024}}\n"
            "@article{ref6, title={Paper 6}, author={Black, Dave}, year={2025}}\n",
            encoding="utf-8",
        )
        skel_file = self.tmp_dir / "skeleton.md"
        skel_file.write_text(
            "# Literature Review\n\n"
            "Studies [@ref1] and [@ref2] show early work.\n"
            "Further [@ref3], [@ref4], [@ref5], and [@ref6] expand this.\n",
            encoding="utf-8",
        )

        # Test text report
        result, report = run_cite_check(bib_file, skel_file, output_json=False)
        self.assertEqual(len(result["missing"]), 0)
        self.assertEqual(len(result["typoed"]), 0)
        self.assertEqual(len(result["orphan"]), 0)
        self.assertEqual(result["n_placeholders"], 6)
        self.assertEqual(result["n_bib_keys"], 6)

        # Text report should display 6 occurrences and 6 bib keys, NOT 0!
        self.assertIn("- Placeholders: 6 occurrences (0 unique missing/typoed)", report)
        self.assertIn("- Bib keys: 6", report)
        self.assertNotIn("Placeholders: 0 occurrences", report)
        self.assertNotIn("Bib keys: 0", report)

        # Test JSON report
        _, json_report_str = run_cite_check(bib_file, skel_file, output_json=True)
        json_report = json.loads(json_report_str)
        self.assertEqual(json_report["n_placeholders"], 6)
        self.assertEqual(json_report["n_bib_keys"], 6)
        self.assertEqual(len(json_report["missing"]), 0)

    # ---------- 3. Evidence Section Recognition & Abstract Capping ----------

    def test_evidence_section_recognition_and_capping(self):
        pdf_path = self.tmp_dir / "nber_paper.pdf"
        with pymupdf.open() as doc:
            # Page 1: Abstract
            p1 = doc.new_page()
            p1.insert_text((72, 72), "Generative AI at Work\nAbstract\nWe examine the impact of AI assistance on customer support.")
            # Page 2: Introduction
            p2 = doc.new_page()
            p2.insert_text((72, 72), "1. Introduction\nRecent advancements in generative artificial intelligence have sparked debate.")
            # Page 3: Our Setting (Methods)
            p3 = doc.new_page()
            p3.insert_text((72, 72), "2. Our Setting: LLMs for Customer Support\nWe analyze customer service interactions and data at a software company.")
            # Page 4: Numbered section (Conversational Change -> reset to unknown, NOT abstract!)
            p4 = doc.new_page()
            p4.insert_text((72, 72), "3. Conversational Change\nAgents handle requests faster and use AI recommendations.")
            # Page 5: Results
            p5 = doc.new_page()
            p5.insert_text((72, 72), "4. Results\nWorker productivity increased by 14 percent on average.")
            # Page 6: Attrition (numbered section -> unknown, NOT abstract!)
            p6 = doc.new_page()
            p6.insert_text((72, 72), "5. Attrition\nEmployee turnover rates dropped substantially among new workers.")
            doc.save(pdf_path)

        index = build_index(pdf_path)
        self.assertEqual(len(index["pages"]), 6)

        # Check section labels
        page1_spans = [s for s in index["spans"] if s["page"] == 1]
        self.assertTrue(any(s["section"] == "abstract" for s in page1_spans))

        page2_spans = [s for s in index["spans"] if s["page"] == 2]
        self.assertTrue(any(s["section"] == "introduction" for s in page2_spans))

        page3_spans = [s for s in index["spans"] if s["page"] == 3]
        self.assertTrue(any(s["section"] == "methods" for s in page3_spans))

        # Abstract must NEVER leak to page 3, 4, 5, or 6
        for p in (3, 4, 5, 6):
            spans_on_page = [s for s in index["spans"] if s["page"] == p]
            self.assertFalse(
                any(s["section"] == "abstract" for s in spans_on_page),
                f"Page {p} contains unexpected abstract label!",
            )

        page4_spans = [s for s in index["spans"] if s["page"] == 4]
        self.assertTrue(any(s["section"] == "unknown" for s in page4_spans))

        page5_spans = [s for s in index["spans"] if s["page"] == 5]
        self.assertTrue(any(s["section"] == "results" for s in page5_spans))

        # Check packet generation with required_sections methods and results
        packet = build_packet(
            index,
            query="productivity customer",
            max_bytes=16000,
            max_spans=6,
            required_sections=["methods", "results"],
        )
        self.assertEqual(packet["status"], "ready_for_local_review")
        self.assertEqual(packet["missing_sections"], [])
        sections_in_packet = {s["section"] for s in packet["evidence"]}
        self.assertIn("methods", sections_in_packet)
        self.assertIn("results", sections_in_packet)

    # ---------- 4. CLI Scaffold & Build --out / --output Aliases ----------

    def test_cli_scaffold_out_option(self):
        bib_file = self.tmp_dir / "test.bib"
        bib_file.write_text(
            "@article{smith2024, title={AI Study}, author={Smith, John}, year={2024}}\n",
            encoding="utf-8",
        )
        out_skel = self.tmp_dir / "out_skel.md"
        runner = CliRunner()
        res = runner.invoke(cli_main, ["scaffold", str(bib_file), "--out", str(out_skel)])
        self.assertEqual(res.exit_code, 0, f"scaffold --out failed: {res.output}")
        self.assertTrue(out_skel.exists())
        self.assertIn("[@smith2024]", out_skel.read_text(encoding="utf-8"))

    # ---------- 5. Markup Cleaning (JATS XML, HTML entities) ----------

    def test_markup_cleaning_in_titles_and_abstracts(self):
        raw_title = "<jats:title>Generative AI &amp; Software: <jats:italic>A Case Study</jats:italic>.</jats:title>"
        clean_title = _clean_title(raw_title)
        self.assertEqual(clean_title, "Generative AI & Software: A Case Study")

        raw_abstract = "<jats:p>We examine the impact of &amp; tools on junior developers.</jats:p>"
        clean_abs = clean_markup_text(raw_abstract)
        self.assertEqual(clean_abs, "We examine the impact of & tools on junior developers.")

        # In to_bibtex, title & abstract should be cleaned and BibTeX-escaped (\&)
        paper = {
            "title": raw_title,
            "abstract": raw_abstract,
            "authors": ["Brynjolfsson, Erik"],
            "year": 2023,
            "doi": "10.1234/test",
        }
        bib_entry = to_bibtex(paper)
        self.assertIn(r"Generative AI \& Software: A Case Study", bib_entry)
        self.assertIn(r"We examine the impact of \& tools", bib_entry)
        self.assertNotIn("<jats:", bib_entry)
        self.assertNotIn("&amp;", bib_entry)

        # In unescape_bibtex (used by export_screening and scaffold), \& becomes &
        roundtrip_title = unescape_bibtex(r"Generative AI \& Software: A Case Study")
        self.assertEqual(roundtrip_title, "Generative AI & Software: A Case Study")

    # ---------- 6. Search ArXiv Missing Dependency & Status ----------

    def test_search_arxiv_missing_dependency_reporting(self):
        with patch.dict("sys.modules", {"arxiv": None}):
            # Simulate arxiv not being importable
            with patch("builtins.__import__", side_effect=ImportError("No module named 'arxiv'")):
                results = search_arxiv("generative AI")
                self.assertEqual(len(results), 1)
                self.assertEqual(results[0].get("error"), "missing_dependency")

    def test_run_search_status_reporting(self):
        # Aggregation test: mock the transport, not an unpicklable provider.
        # Real spawned providers are covered by test_live_workflow_repair.py.
        with patch("pa_cli.search._run_search_engine", return_value=[
                {"error": "missing_dependency", "message": "SDK not installed"}]):
            res = run_search("test query", engine="arxiv")
            self.assertEqual(res["by_engine"]["arxiv"], 0)
            self.assertEqual(res["engine_status"]["arxiv"], "error")
            self.assertIn("SDK not installed", res["engine_errors"]["arxiv"])


if __name__ == "__main__":
    unittest.main()
