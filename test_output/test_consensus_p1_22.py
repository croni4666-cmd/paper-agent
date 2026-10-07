"""Unit tests for Theoretical Proposition Controversy & Consensus Matrix [P1-22].

Tests:
1. Extraction of formalized hypotheses with positive/supported outcome.
2. Extraction of hypotheses with negative/rejected outcome.
3. Cross-paper consensus matrix calculation and debate intensity categorization.
4. Nonlinear (inverted U-shaped) relationship detection.
5. General empirical findings fallback when explicit H1 labels are omitted.
6. Multilingual Chinese hypothesis parsing (假设 1 / 通过检验).
7. PDF document parsing with PyMuPDF synthetic fixture.
8. CLI command invocations (--text, --json, --format markdown).
"""

import json
import tempfile
import unittest
from pathlib import Path
from click.testing import CliRunner

from pa_cli.cli import main
from pa_cli.consensus import (
    extract_hypotheses_from_text,
    extract_consensus_from_pdf,
    build_consensus_matrix,
    format_consensus_report,
)


class TestConsensusP122(unittest.TestCase):
    def test_hypothesis_extraction_supported(self):
        """Extract hypothesis with positive direction and supported outcome."""
        text = (
            "We propose our primary hypothesis based on stakeholder theory:\n"
            "Hypothesis 1 (H1): Corporate ESG performance has a positive impact on firm financial performance.\n"
            "Our empirical baseline regression results indicate that Hypothesis 1 is supported (t = 3.25, p < 0.01)."
        )
        hyps = extract_hypotheses_from_text(text, source_doc="paper1.pdf")
        self.assertEqual(len(hyps), 1)
        h = hyps[0]
        self.assertEqual(h.label, "H1")
        self.assertEqual(h.direction, "positive")
        self.assertEqual(h.outcome, "supported")
        self.assertEqual(h.effective_finding, "positive")
        self.assertEqual(h.relation_key, "esg -> financial_performance")

    def test_hypothesis_extraction_rejected(self):
        """Extract hypothesis with negative direction and rejected outcome."""
        text = (
            "Hypothesis 2 (H2): CEO duality negatively moderates the relationship between ESG performance and firm performance.\n"
            "However, Hypothesis 2 is rejected by our empirical tests."
        )
        hyps = extract_hypotheses_from_text(text, source_doc="paper2.pdf")
        self.assertEqual(len(hyps), 1)
        h = hyps[0]
        self.assertEqual(h.label, "H2")
        self.assertEqual(h.direction, "negative")
        self.assertEqual(h.outcome, "rejected")
        self.assertEqual(h.effective_finding, "neutral")

    def test_cross_paper_consensus_and_debate_calculation(self):
        """Synthesize cross-paper consensus matrix across 3 papers with conflicting findings."""
        text1 = (
            "Hypothesis 1: Corporate ESG performance positively impacts firm financial performance.\n"
            "Hypothesis 1 is supported."
        )
        text2 = (
            "Hypothesis 1: Corporate ESG performance is negatively associated with firm financial performance.\n"
            "Hypothesis 1 is supported."
        )
        text3 = (
            "Hypothesis 1: Corporate ESG performance significantly improves firm financial performance.\n"
            "Hypothesis 1 is supported."
        )
        h1 = extract_hypotheses_from_text(text1, source_doc="paper_a.pdf")
        h2 = extract_hypotheses_from_text(text2, source_doc="paper_b.pdf")
        h3 = extract_hypotheses_from_text(text3, source_doc="paper_c.pdf")

        report = build_consensus_matrix(h1 + h2 + h3)
        self.assertEqual(report.total_papers, 3)
        self.assertEqual(len(report.relationships), 1)

        rel = report.relationships[0]
        self.assertEqual(rel.relation_key, "esg -> financial_performance")
        self.assertEqual(len(rel.positive_papers), 2)
        self.assertEqual(len(rel.negative_papers), 1)
        self.assertEqual(rel.total_papers, 3)
        self.assertAlmostEqual(rel.consensus_score, 2 / 3, places=2)
        self.assertEqual(rel.debate_level, "Moderate Debate")
        self.assertEqual(rel.dominant_direction, "positive")

    def test_nonlinear_hypothesis_extraction(self):
        """Extract quadratic / inverted U-shaped propositions."""
        text = (
            "Proposition 1: We hypothesize an inverted U-shaped relationship between debt leverage and corporate innovation.\n"
            "Empirical results indicate that Proposition 1 is supported."
        )
        hyps = extract_hypotheses_from_text(text)
        self.assertEqual(len(hyps), 1)
        h = hyps[0]
        self.assertEqual(h.direction, "inverted_u")
        self.assertEqual(h.effective_finding, "inverted_u")
        self.assertIn("debt_leverage", h.relation_key)

    def test_fallback_general_findings_without_h_labels(self):
        """Fallback to direct empirical finding statements when formal H1 labels are omitted."""
        text = (
            "In this study, results indicate that digital transformation significantly promotes corporate innovation quality. "
            "Furthermore, empirical results show that environmental regulation reduces green total factor productivity in the short run."
        )
        hyps = extract_hypotheses_from_text(text, source_doc="unlabeled_paper.pdf")
        self.assertGreaterEqual(len(hyps), 2)
        keys = {h.relation_key for h in hyps}
        self.assertIn("digital_transformation -> innovation", keys)

    def test_chinese_hypothesis_extraction(self):
        """Extract Chinese academic hypotheses and verification outcomes."""
        text = (
            "基于利益相关者理论，本文提出假说1：\n"
            "假设 1：企业数字化转型对企业创新绩效具有显著正向影响。\n"
            "基准回归分析表明，假设1通过检验。"
        )
        hyps = extract_hypotheses_from_text(text, source_doc="chinese_paper.pdf")
        self.assertEqual(len(hyps), 1)
        h = hyps[0]
        self.assertEqual(h.direction, "positive")
        self.assertEqual(h.outcome, "supported")
        self.assertEqual(h.effective_finding, "positive")

    def test_pdf_consensus_extraction(self):
        """Extract hypotheses from synthetic PDF fixture."""
        import fitz

        with tempfile.TemporaryDirectory() as tmp_dir:
            pdf_path = Path(tmp_dir) / "hypothesis_paper.pdf"
            doc = fitz.open()
            page = doc.new_page(width=600, height=800)
            rect = fitz.Rect(50, 50, 550, 750)
            page.insert_textbox(
                rect,
                "Section 2. Theoretical Analysis and Hypotheses\n\n"
                "Hypothesis 1 (H1): Corporate ESG performance has a positive impact on firm financial performance.\n\n"
                "Section 5. Empirical Results\n\n"
                "In our baseline model, Hypothesis 1 is supported (t = 2.95, p < 0.01).\n"
            )
            doc.save(str(pdf_path))
            doc.close()

            hyps = extract_consensus_from_pdf(pdf_path)
            self.assertEqual(len(hyps), 1)
            self.assertEqual(hyps[0].label, "H1")
            self.assertEqual(hyps[0].outcome, "supported")
            self.assertEqual(hyps[0].relation_key, "esg -> financial_performance")

    def test_cli_consensus_command(self):
        """Test Click CLI command with --text, --json, and --format markdown."""
        runner = CliRunner()
        text_arg = (
            "Hypothesis 1: Corporate ESG performance positively impacts firm financial performance. "
            "Hypothesis 1 is supported."
        )

        # 1. JSON output
        res_json = runner.invoke(main, ["consensus", "--text", text_arg, "--json"])
        self.assertEqual(res_json.exit_code, 0)
        out_str = res_json.stdout
        json_start = out_str.find("{")
        self.assertGreaterEqual(json_start, 0)
        data = json.loads(out_str[json_start:])
        self.assertEqual(data["total_papers"], 1)
        self.assertEqual(len(data["relationships"]), 1)
        self.assertEqual(data["relationships"][0]["consensus_score"], 1.0)

        # 2. Markdown output
        res_md = runner.invoke(main, ["consensus", "--text", text_arg, "--format", "markdown"])
        self.assertEqual(res_md.exit_code, 0)
        self.assertIn("# Academic Proposition Consensus & Controversy Matrix", res_md.stdout)
        self.assertIn("Corporate ESG Performance", res_md.stdout)


if __name__ == "__main__":
    unittest.main()
