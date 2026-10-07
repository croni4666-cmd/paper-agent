"""Unit tests for [P2-21] Manuscript Citation Fidelity & Hallucination Audit (pa cite-audit)."""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from click.testing import CliRunner

from pa_cli.cite_audit import (
    extract_citation_markers,
    split_sentences_academic,
    detect_claim_direction,
    extract_numbers_from_claim,
    audit_manuscript,
    format_audit_table,
    format_audit_markdown,
    format_audit_json,
)
from pa_cli.cli import main


class TestCiteAuditP221(unittest.TestCase):
    """Test suite covering citation marker parsing, claim direction, fidelity checks, and CLI."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="test_cite_audit_")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_citation_marker_extraction(self):
        """Test extraction of diverse academic citation styles and line numbers."""
        text = (
            "Line 1: Recent studies [@smith2020; @jones2021] investigate ESG disclosure.\n"
            "Line 2: Furthermore, \\cite{angrist1991} and \\citep[p. 15]{imbens2004} show causal identification.\n"
            "Line 3: In Typst syntax, @vaswani2017 introduced the transformer architecture.\n"
            "Line 4: A footnote reference is also present [^footref2019].\n"
            "Line 5: As Acemoglu et al. (2001) argued, institutions rule.\n"
        )
        markers = extract_citation_markers(text)
        keys = [m.key.lower() for m in markers]

        self.assertIn("smith2020", keys)
        self.assertIn("jones2021", keys)
        self.assertIn("angrist1991", keys)
        self.assertIn("imbens2004", keys)
        self.assertIn("vaswani2017", keys)
        self.assertIn("footref2019", keys)
        self.assertIn("acemoglu2001", keys)

        # Check line numbers
        smith_marker = next(m for m in markers if m.key.lower() == "smith2020")
        self.assertEqual(smith_marker.line_number, 1)

        angrist_marker = next(m for m in markers if m.key.lower() == "angrist1991")
        self.assertEqual(angrist_marker.line_number, 2)

    def test_academic_sentence_splitting(self):
        """Test that abbreviations like e.g., et al., and decimals do not cause false sentence splits."""
        text = (
            "Acemoglu et al. (2001) analyzed colonial origins, e.g., settler mortality rates. "
            "They estimated a coefficient of 0.45. Did the results hold? "
            "Yes, robustness checks confirmed the main findings."
        )
        sentences = split_sentences_academic(text)
        # Should NOT split on "et al." or "e.g." or "0.45"
        self.assertGreaterEqual(len(sentences), 3)
        first_sentence = sentences[0][0]
        self.assertIn("settler mortality rates", first_sentence)
        self.assertIn("et al.", first_sentence)

    def test_direction_and_number_extraction(self):
        """Test detection of causal/empirical assertion directions and numerical values."""
        pos_claim = "Corporate ESG practices significantly promote firm financial performance by 14.5%."
        self.assertEqual(detect_claim_direction(pos_claim), "positive")
        nums = extract_numbers_from_claim(pos_claim)
        self.assertIn("14.5%", nums)

        neg_claim = "Strict environmental regulations decrease short-term manufacturing output by 8.2 bps."
        self.assertEqual(detect_claim_direction(neg_claim), "negative")
        nums_neg = extract_numbers_from_claim(neg_claim)
        self.assertTrue(any("8.2" in n for n in nums_neg))

        null_claim = "We find no significant effect of board gender diversity on leverage."
        self.assertEqual(detect_claim_direction(null_claim), "neutral")

    def test_bibtex_abstract_faithful_audit(self):
        """Test faithful claim verification against local BibTeX abstract metadata."""
        bib_path = Path(self.tmp_dir) / "refs.bib"
        bib_content = """@article{smith2020esg,
  title = {Environmental Social Governance and Firm Performance},
  author = {Smith, John and Doe, Jane},
  journal = {Journal of Corporate Finance},
  year = {2020},
  doi = {10.1016/j.jcorpfin.2020.101500},
  abstract = {We examine how ESG disclosure impacts corporate financial outcomes. Using a difference-in-differences design, empirical results demonstrate that proactive ESG disclosure significantly increases corporate profitability and enhances firm return on assets.}
}
"""
        bib_path.write_text(bib_content, encoding="utf-8")

        manuscript = (
            "Prior literature underscores the economic benefits of sustainability. "
            "Smith and Doe [@smith2020esg] demonstrate that proactive ESG disclosure significantly increases corporate profitability. "
            "This forms the basis of our analytical framework."
        )

        report = audit_manuscript(
            manuscript_text=manuscript,
            bib_path=bib_path,
            threshold=0.60,
        )

        self.assertEqual(report.total_citations, 1)
        item = report.items[0]
        self.assertEqual(item.citation_key, "smith2020esg")
        self.assertEqual(item.verdict, "VERIFIED_FAITHFUL")
        self.assertGreaterEqual(item.fidelity_score, 0.70)
        self.assertIn("DIRECTION_CONFIRMED", item.flags)
        self.assertTrue(report.pass_status)

    def test_misattribution_opposite_polarity(self):
        """Test detection of polarity reversal (claiming positive when source found negative/null)."""
        bib_path = Path(self.tmp_dir) / "refs.bib"
        bib_content = """@article{brown2021debt,
  title = {Debt Overhang and Capital Expenditure},
  author = {Brown, Robert},
  year = {2021},
  abstract = {Our empirical findings show that high debt leverage significantly decreases firm investment and reduces physical capital expenditures.}
}
"""
        bib_path.write_text(bib_content, encoding="utf-8")

        # Draft incorrectly claims positive effect
        manuscript = "As shown by \\cite{brown2021debt}, excessive corporate debt promotes firm investment and capital expenditure."

        report = audit_manuscript(
            manuscript_text=manuscript,
            bib_path=bib_path,
        )

        self.assertEqual(report.total_citations, 1)
        item = report.items[0]
        self.assertEqual(item.verdict, "MISATTRIBUTION")
        self.assertIn("OPPOSITE_DIRECTION", item.flags)
        self.assertLess(item.fidelity_score, 0.50)
        self.assertFalse(report.pass_status)

    def test_numerical_hallucination_detection(self):
        """Test detection of fabricated statistics not present in the source paper."""
        bib_path = Path(self.tmp_dir) / "refs.bib"
        bib_content = """@article{lee2022rd,
  title = {Tax Subsidies and Research Expenditure},
  author = {Lee, David},
  year = {2022},
  abstract = {R&D tax credits stimulate patent filings and private innovation expenditures among high-technology firms.}
}
"""
        bib_path.write_text(bib_content, encoding="utf-8")

        # Draft introduces hallucinated numerical percentage 88.5%
        manuscript = "Lee [@lee2022rd] documented an astonishing 88.5% increase in private innovation expenditures."

        report = audit_manuscript(
            manuscript_text=manuscript,
            bib_path=bib_path,
        )

        self.assertEqual(report.total_citations, 1)
        item = report.items[0]
        self.assertTrue(
            item.verdict == "NUMERICAL_DISCREPANCY" or any("NUMERICAL_DISCREPANCY" in f for f in item.flags)
        )
        self.assertEqual(report.numerical_discrepancy_count, 1)

    def test_hallucinated_citation_key(self):
        """Test detection of completely ungrounded citations missing from bibliography and cache."""
        bib_path = Path(self.tmp_dir) / "refs.bib"
        bib_path.write_text("@article{known2020, title={Existing}, year={2020}}\n", encoding="utf-8")

        # Cite a non-existent fake paper
        manuscript = "Recent revolutionary breakthroughs [@ghost_hallucinated_paper_2099] completely solved quantum teleportation."

        report = audit_manuscript(
            manuscript_text=manuscript,
            bib_path=bib_path,
        )

        self.assertEqual(report.total_citations, 1)
        item = report.items[0]
        self.assertEqual(item.verdict, "HALLUCINATED_CITATION")
        self.assertEqual(item.fidelity_score, 0.0)
        self.assertIn("UNGROUNDED_REFERENCE", item.flags)
        self.assertFalse(report.pass_status)
        self.assertEqual(report.hallucinated_count, 1)

    def test_pdf_fulltext_auditing(self):
        """Test extraction and verification using local PDF full-text with PyMuPDF."""
        try:
            import fitz
        except ImportError:
            self.skipTest("PyMuPDF not installed")

        pdf_path = Path(self.tmp_dir) / "taylor1993.pdf"
        doc = fitz.open()

        # Page 1: Abstract
        page1 = doc.new_page()
        page1.insert_text((50, 72), "Discretion versus policy rules in practice.\nMacroeconomic policy and monetary stabilization.")

        # Page 2: Empirical Rule
        page2 = doc.new_page()
        page2.insert_text(
            (50, 72),
            "The proposed interest rate reaction rule specifies that the central bank increases "
            "the nominal interest rate when inflation rises above the 2.0% target."
        )
        doc.save(str(pdf_path))
        doc.close()

        bib_path = Path(self.tmp_dir) / "refs.bib"
        bib_path.write_text(f"""@article{{taylor1993,
  title = {{Discretion Versus Policy Rules}},
  year = {{1993}},
  file = {{{pdf_path.name}}}
}}
""", encoding="utf-8")

        manuscript = "Taylor [@taylor1993] specified that central banks increase the nominal interest rate when inflation rises."
        m_file = Path(self.tmp_dir) / "manuscript.md"
        m_file.write_text(manuscript, encoding="utf-8")

        report = audit_manuscript(
            manuscript_text=manuscript,
            bib_path=bib_path,
            pdf_dir=self.tmp_dir,
            manuscript_path=m_file,
        )

        self.assertEqual(report.total_citations, 1)
        item = report.items[0]
        self.assertIn(item.verdict, ("VERIFIED_FAITHFUL", "PARTIALLY_SUPPORTED"))
        self.assertIsNotNone(item.evidence_passage)
        self.assertEqual(item.evidence_passage.page, 2)
        self.assertIn("interest rate", item.evidence_passage.text.lower())

    def test_report_formatting(self):
        """Test formatting in table, markdown, and json modes."""
        bib_path = Path(self.tmp_dir) / "refs.bib"
        bib_path.write_text("@article{test2020, title={A Study}, abstract={We find positive gains.}}\n", encoding="utf-8")
        manuscript = "We observe positive gains [@test2020]."

        report = audit_manuscript(manuscript_text=manuscript, bib_path=bib_path)

        # ASCII table
        tbl = format_audit_table(report)
        self.assertIn("PAPER AGENT MANUSCRIPT CITATION FIDELITY AUDIT", tbl)
        self.assertIn("test2020", tbl)

        # Markdown
        md = format_audit_markdown(report)
        self.assertIn("# Manuscript Citation Fidelity & Hallucination Audit Report", md)
        self.assertIn("| Line | Citation Key |", md)

        # JSON
        js_str = format_audit_json(report)
        data = json.loads(js_str)
        self.assertEqual(data["total_citations"], 1)
        self.assertEqual(data["items"][0]["citation_key"], "test2020")

    def test_cli_command(self):
        """Test Click CLI command execution via CliRunner."""
        runner = CliRunner()
        bib_path = Path(self.tmp_dir) / "refs.bib"
        bib_path.write_text("@article{key1, title={Title 1}, abstract={Productivity increases.}}\n", encoding="utf-8")

        # 1. Inline text invocation with json output
        result = runner.invoke(
            main,
            [
                "cite-audit",
                "--text", "Previous work shows productivity increases [@key1].",
                "--bib", str(bib_path),
                "--json",
            ],
        )
        self.assertEqual(result.exit_code, 0)
        data = json.loads(result.stdout)
        self.assertEqual(data["total_citations"], 1)
        self.assertEqual(data["items"][0]["citation_key"], "key1")

        # 2. Strict check failure on hallucinated reference
        result_strict = runner.invoke(
            main,
            [
                "cite-audit",
                "--text", "A fictional claim [@fake_ghost_2099].",
                "--bib", str(bib_path),
                "--strict",
            ],
        )
        self.assertNotEqual(result_strict.exit_code, 0)
        self.assertIn("Strict check failed", result_strict.output)


if __name__ == "__main__":
    unittest.main()
