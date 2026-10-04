"""Unit tests for Statistical Report Consistency & Verification Engine [P1-24].

Tests:
1. Mathematical CDF precision for t, F, chi2, z, and r.
2. Comprehensive text extraction across all standard test signatures.
3. Decision error detection (significance flips across alpha=0.05).
4. One-tailed hypothesis detection.
5. Inequality operator matching (<, <=, >, >=).
6. Unicode and full-width punctuation normalization.
7. PDF extraction with PyMuPDF synthetic document.
8. CLI command invocation and output formatting (table, markdown, json).
"""

import json
import math
import tempfile
import unittest
from pathlib import Path
from click.testing import CliRunner

from pa_cli.cli import main
from pa_cli.stats_check import (
    compute_p_value,
    check_p_consistency,
    extract_stats_from_text,
    extract_stats_from_pdf,
    summarize_findings,
    format_stats_report,
)


class TestStatsCheckP124(unittest.TestCase):
    def test_cdf_math_precision(self):
        """Verify mathematical precision against known exact values."""
        # 1. Standard normal z=1.959964 -> two-tailed p = 0.05
        p_two, p_one = compute_p_value("z", 1.959964)
        self.assertAlmostEqual(p_two, 0.05, places=5)
        self.assertAlmostEqual(p_one, 0.025, places=5)

        # 2. Student's t(148) = 2.45 -> p approx 0.01545
        p_two_t, _ = compute_p_value("t", 2.45, df1=148)
        self.assertAlmostEqual(p_two_t, 0.01545, places=4)

        # Negative t value should give same two-tailed p
        p_two_neg, _ = compute_p_value("t", -2.45, df1=148)
        self.assertAlmostEqual(p_two_t, p_two_neg, places=6)

        # 3. F(1, 40) = 4.25 -> p approx 0.04579
        p_f, _ = compute_p_value("f", 4.25, df1=1, df2=40)
        self.assertAlmostEqual(p_f, 0.04579, places=4)

        # 4. Chi2(4) = 9.88 -> p approx 0.04250
        p_chi, _ = compute_p_value("chi2", 9.88, df1=4)
        self.assertAlmostEqual(p_chi, 0.04250, places=4)

        # 5. Pearson r(85) = 0.32 -> p approx 0.00252
        p_r, _ = compute_p_value("r", 0.32, df1=85)
        self.assertAlmostEqual(p_r, 0.00252, places=4)

    def test_text_extraction_all_distributions(self):
        """Verify extraction of t, F, chi2, z, and r from academic prose."""
        prose = (
            "We found a significant effect, t(28) = 2.45, p = 0.021. "
            "ANOVA revealed F(1, 40) = 4.25, p = 0.046 for main factor. "
            "Chi-square test was χ²(4) = 9.88, p = 0.042. "
            "Z-test showed z = 2.33, p = .020. "
            "Correlation was positive, r(85) = 0.32, p = 0.003."
        )
        items = extract_stats_from_text(prose, source="paper1")
        self.assertEqual(len(items), 5)

        stat_types = {it.stat_type for it in items}
        self.assertEqual(stat_types, {"t", "F", "chi2", "z", "r"})

        summary = summarize_findings(items)
        self.assertEqual(summary.total_tests, 5)
        self.assertEqual(summary.consistent_count, 5)
        self.assertEqual(summary.decision_error_count, 0)

    def test_decision_error_detection(self):
        """Flag gross inconsistency when significance flips across alpha=0.05."""
        # t(50) = 1.96 has true two-tailed p = 0.0556.
        # Claiming p = .03 or p < .05 is a Decision Error (false positive claim)
        text = "The effect was statistically significant, t(50) = 1.96, p = .03."
        items = extract_stats_from_text(text)
        self.assertEqual(len(items), 1)
        it = items[0]
        self.assertFalse(it.is_consistent)
        self.assertTrue(it.is_decision_error)
        self.assertEqual(it.status, "decision_error")
        self.assertIn("DECISION ERROR", it.explanation)

    def test_one_tailed_hypothesis_detection(self):
        """Detect when reported p matches one-tailed test."""
        # t(50) = 1.96 has one-tailed p = 0.0278, which rounds to 0.03
        text = "Directional hypothesis supported, t(50) = 1.96, p = 0.028."
        items = extract_stats_from_text(text)
        self.assertEqual(len(items), 1)
        it = items[0]
        self.assertFalse(it.is_consistent)  # Not consistent for two-tailed (0.0556)
        self.assertTrue(it.is_consistent_one_tailed)  # Matches one-tailed (0.0278)
        self.assertIn("matches one-tailed", it.explanation)

    def test_inequality_reporting(self):
        """Verify handling of inequality operators (<, <=, >, >=)."""
        text = (
            "Model 1 was highly significant, t(150) = -3.12, p < .01. "
            "Model 2 was not significant, F(2, 60) = 1.15, p > .05."
        )
        items = extract_stats_from_text(text)
        self.assertEqual(len(items), 2)
        self.assertTrue(items[0].is_consistent)
        self.assertTrue(items[1].is_consistent)

    def test_unicode_and_fullwidth_normalization(self):
        """Normalize full-width punctuation, Unicode math symbols, and minus signs."""
        text = (
            "回归检验结果显示，t（28）＝2.45，p＝0.021；"
            "另外，F（1，40）＝4.25，p＜0.05；"
            "负相关检验为 𝑡(100) = −2.65, 𝑝 = .009。"
        )
        items = extract_stats_from_text(text)
        self.assertEqual(len(items), 3)
        for it in items:
            self.assertTrue(it.is_consistent)

    def test_pdf_stats_extraction(self):
        """Extract statistical tests from synthetic PDF file."""
        import fitz

        with tempfile.TemporaryDirectory() as tmp_dir:
            pdf_path = Path(tmp_dir) / "stats_paper.pdf"
            doc = fitz.open()
            page = doc.new_page(width=600, height=800)
            rect = fitz.Rect(50, 50, 550, 750)
            page.insert_textbox(
                rect,
                "Section 4. Empirical Results\n\n"
                "In our primary specification, the coefficient was positive and significant, "
                "t(28) = 2.45, p = 0.021. ANOVA indicated F(1, 40) = 4.25, p = 0.046. "
                "Furthermore, chi-square test yielded chi2(4) = 9.88, p = 0.042.\n"
            )
            doc.save(str(pdf_path))
            doc.close()

            summary = extract_stats_from_pdf(pdf_path)
            self.assertEqual(summary.total_tests, 3)
            self.assertEqual(summary.consistent_count, 3)
            self.assertEqual(summary.decision_error_count, 0)
            self.assertIn("stats_paper.pdf:p1", summary.items[0].source)

    def test_cli_stats_check_invocations(self):
        """Verify Click CLI commands with --text, --json, and --format markdown."""
        runner = CliRunner()

        # 1. Text input with JSON output
        res_json = runner.invoke(
            main,
            [
                "stats-check",
                "--text",
                "t(28) = 2.45, p = 0.021; F(1, 40) = 4.25, p = 0.046; t(50) = 1.96, p = .03",
                "--json",
            ],
        )
        self.assertEqual(res_json.exit_code, 0)
        # Parse output JSON (ignoring stderr warnings)
        out_str = res_json.stdout
        # Find json object start
        json_start = out_str.find("{")
        self.assertGreaterEqual(json_start, 0)
        data = json.loads(out_str[json_start:])
        self.assertEqual(data["total_tests"], 3)
        self.assertEqual(data["consistent_count"], 2)
        self.assertEqual(data["decision_error_count"], 1)

        # 2. Markdown output
        res_md = runner.invoke(
            main,
            [
                "stats-check",
                "--text",
                "t(28) = 2.45, p = 0.021",
                "--format",
                "markdown",
            ],
        )
        self.assertEqual(res_md.exit_code, 0)
        self.assertIn("# Statistical Report Consistency Verification Report", res_md.stdout)
        self.assertIn("Consistent", res_md.stdout)


if __name__ == "__main__":
    unittest.main()
