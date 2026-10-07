"""Unit tests for [P2-23] Empirical findings literature alignment engine (pa align-findings)."""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from click.testing import CliRunner

from pa_cli.align_findings import (
    parse_user_finding,
    align_empirical_finding,
    format_alignment_table,
    format_alignment_markdown,
    format_alignment_json,
    EmpiricalInput,
)
from pa_cli.project import init_project, DEFAULT_ROOT
from pa_cli.cli import main


class TestAlignFindingsP223(unittest.TestCase):
    """Test suite covering empirical findings extraction, alignment, and CLI."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="test_align_")
        self.root = Path(self.tmp_dir) / "projects"

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_parse_user_finding(self):
        """Test parsing of user natural language finding and structured parameters."""
        # Natural language statement
        res1 = parse_user_finding("Board independence significantly promotes return on assets.")
        self.assertEqual(res1.direction, "positive")
        self.assertIn("independence", res1.var_x.lower())
        self.assertIn("assets", res1.var_y.lower())

        # Structured input with regression coefficients
        res2 = parse_user_finding(
            var_x="Green Credit",
            var_y="Carbon Emissions",
            direction="negative",
            coefficient=-0.045,
            std_err=0.012,
            p_value=0.001,
            sample_context="Chinese heavy-polluting firms",
        )
        self.assertEqual(res2.var_x, "Green Credit")
        self.assertEqual(res2.var_y, "Carbon Emissions")
        self.assertEqual(res2.direction, "negative")
        self.assertEqual(res2.coefficient, -0.045)

    def test_align_supporting_and_contradictory_evidence(self):
        """Test aligning a user finding across supporting, contradictory, and heterogeneity literature."""
        papers = [
            {
                "key": "paper_pos",
                "title": "ESG and Profitability in Global Markets",
                "author": "Smith, J.",
                "year": 2020,
                "abstract": "We find that proactive ESG disclosure significantly increases corporate return on assets and firm performance.",
            },
            {
                "key": "paper_neg",
                "title": "The Compliance Burden of Sustainability",
                "author": "Brown, R.",
                "year": 2021,
                "abstract": "Empirical results show that mandatory ESG reporting decreases short-term profits and reduces financial performance.",
            },
            {
                "key": "paper_het",
                "title": "Ownership Structure and Sustainability",
                "author": "Zhang, L.",
                "year": 2022,
                "abstract": "Heterogeneity analysis shows that the effect of ESG disclosure is more pronounced in non-state-owned enterprises.",
            },
        ]

        user_input = parse_user_finding(
            statement="ESG disclosure significantly increases firm financial performance.",
            coefficient=0.038,
            std_err=0.009,
            p_value=0.005,
        )

        report = align_empirical_finding(user_input, papers)

        # 1. Supporting paper verification
        self.assertGreaterEqual(len(report.supporting_papers), 1)
        self.assertEqual(report.supporting_papers[0].paper_id, "paper_pos")
        self.assertEqual(report.supporting_papers[0].direction, "positive")

        # 2. Contradictory paper verification
        self.assertGreaterEqual(len(report.contradictory_papers), 1)
        self.assertEqual(report.contradictory_papers[0].paper_id, "paper_neg")
        self.assertEqual(report.contradictory_papers[0].direction, "negative")

        # 3. Heterogeneity paper verification
        self.assertGreaterEqual(len(report.heterogeneity_papers), 1)
        self.assertEqual(report.heterogeneity_papers[0].paper_id, "paper_het")
        self.assertIn("non-state-owned", report.heterogeneity_papers[0].reconciling_factor)

        # 4. Novelty verdict
        self.assertIn("Novel Heterogeneity", report.novelty_verdict)

        # 5. Prior distribution benchmark
        self.assertIn("literature_typical_range", report.prior_distribution_benchmark)
        self.assertEqual(report.prior_distribution_benchmark["user_coefficient"], 0.038)

    def test_format_outputs(self):
        """Test formatting in table, markdown, and json modes."""
        papers = [
            {"key": "p1", "title": "Study A", "author": "Alice", "year": 2020, "abstract": "We find positive effect."}
        ]
        user_input = parse_user_finding("Innovation promotes productivity.")
        report = align_empirical_finding(user_input, papers)

        # ASCII table
        tbl = format_alignment_table(report)
        self.assertIn("EMPIRICAL FINDINGS LITERATURE ALIGNMENT", tbl)
        self.assertIn("DIRECT SUPPORTING LITERATURE", tbl)

        # Markdown
        md = format_alignment_markdown(report)
        self.assertIn("# Empirical Findings Literature Alignment & Discussion", md)
        self.assertIn("## 1. Concurring Evidence in the Literature", md)

        # JSON
        js = format_alignment_json(report)
        data = json.loads(js)
        self.assertEqual(data["total_papers_analyzed"], 1)

    def test_cli_align_findings(self):
        """Test Click CLI command pa align-findings."""
        bib_path = Path(self.tmp_dir) / "refs.bib"
        bib_path.write_text("""@article{test2021,
  title = {Credit Constraints and Business Investment},
  author = {Doe, John},
  year = {2021},
  abstract = {Empirical results indicate that credit constraints significantly reduce corporate capital investment.}
}
""", encoding="utf-8")

        runner = CliRunner()

        # 1. Finding alignment with JSON output
        res_json = runner.invoke(
            main,
            [
                "align-findings",
                "-f", "Credit constraints reduce corporate investment",
                "--bib", str(bib_path),
                "--json",
            ],
        )
        self.assertEqual(res_json.exit_code, 0)
        data = json.loads(res_json.stdout)
        self.assertEqual(data["total_papers_analyzed"], 1)
        self.assertEqual(len(data["supporting_papers"]), 1)
        self.assertEqual(data["supporting_papers"][0]["paper_id"], "test2021")

        # 2. Structured X and Y parameter call
        res_xy = runner.invoke(
            main,
            [
                "align-findings",
                "--x", "Credit constraints",
                "--y", "investment",
                "--direction", "negative",
                "--bib", str(bib_path),
                "--format", "markdown",
            ],
        )
        self.assertEqual(res_xy.exit_code, 0)
        self.assertIn("Literature Alignment", res_xy.stdout)
        self.assertIn("[@test2021]", res_xy.stdout)

        # 3. File output with statistical parameters
        out_file = Path(self.tmp_dir) / "alignment_output.md"
        res_file = runner.invoke(
            main,
            [
                "align-findings",
                "-f", "Credit constraints reduce corporate investment",
                "--coef", "-0.045",
                "--se", "0.012",
                "--pval", "0.001",
                "--bib", str(bib_path),
                "--format", "markdown",
                "-o", str(out_file),
            ],
        )
        self.assertEqual(res_file.exit_code, 0)
        self.assertTrue(out_file.exists())
        content = out_file.read_text(encoding="utf-8")
        self.assertIn("Point Estimate", content)
        self.assertIn("-0.045", content)


if __name__ == "__main__":
    unittest.main()

