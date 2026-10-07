"""Unit tests for Evolutionary Citation and Methodology Lineage [P1-23].

Tests:
1. Methodology fingerprinting across causal econometrics, macro, and machine learning.
2. Paradigm role classification (foundational, critique, extension, application).
3. Chronological lineage DAG construction and parent/child relationship resolution.
4. Mermaid diagram formatting.
5. Terminal ASCII tree rendering.
6. JSON DAG serialization.
7. Click CLI command invocations.
"""

import json
import tempfile
import unittest
from pathlib import Path
from click.testing import CliRunner

from pa_cli.cli import main
from pa_cli.methodology_lineage import (
    detect_methodologies,
    detect_paradigm_role,
    build_lineage_graph,
    format_lineage_tree,
    format_lineage_mermaid,
    format_lineage_markdown,
    format_lineage_json,
)


class TestMethodologyLineageP123(unittest.TestCase):
    def test_detect_methodologies(self):
        """Detect econometric and structural modeling methodology fingerprints."""
        text = (
            "We examine the treatment effect using a staggered difference-in-differences estimator "
            "(Callaway and Sant'Anna, 2021) to correct for two-way fixed effects (TWFE) bias. "
            "For robustness, we employ synthetic control methods (Abadie) and regression discontinuity (RDD)."
        )
        keys, names, family = detect_methodologies(text)
        self.assertIn("staggered_did", keys)
        self.assertIn("twfe", keys)
        self.assertIn("synthetic_control", keys)
        self.assertIn("rdd", keys)
        self.assertEqual(family, "causal_inference")

    def test_paradigm_role_detection(self):
        """Classify paradigm roles: critique, foundational, extension, application."""
        t_critique = "We show that negative weights in two-way fixed effects lead to substantial bias and failure."
        self.assertEqual(detect_paradigm_role(t_critique, ["twfe"], 2021), "critique")

        t_foundational = "We propose a novel framework for causal identification using quarter of birth."
        self.assertEqual(detect_paradigm_role(t_foundational, ["iv_2sls"], 1991), "foundational")

        t_extension = "We extend the difference-in-differences estimator to allow for multiple time periods."
        self.assertEqual(detect_paradigm_role(t_extension, ["staggered_did"], 2021), "extension")

    def test_lineage_graph_construction(self):
        """Build chronological DAG and verify evolutionary paths."""
        papers = [
            {
                "paper_id": "paper_ols",
                "title": "Empirical Returns to Education via OLS",
                "authors": "Becker",
                "year": 1964,
                "role": "foundational",
                "content": "Ordinary least squares regression of earnings on schooling.",
            },
            {
                "paper_id": "paper_twfe",
                "title": "Panel Data Fixed Effects in Labor Markets",
                "authors": "Ashenfelter",
                "year": 1985,
                "role": "foundational",
                "content": "Two-way fixed effects model controlling for individual unobservables.",
            },
            {
                "paper_id": "paper_critique",
                "title": "Difference-in-Differences with Variation in Timing",
                "authors": "Goodman-Bacon",
                "year": 2021,
                "role": "critique",
                "content": "Two-way fixed effects estimator contains negative weights and bias.",
            },
            {
                "paper_id": "paper_did",
                "title": "Difference-in-Differences with Multiple Periods",
                "authors": "Callaway & Sant'Anna",
                "year": 2021,
                "role": "extension",
                "content": "Robust staggered difference-in-differences estimator.",
            },
        ]

        lineage = build_lineage_graph(papers)
        self.assertEqual(lineage.total_papers, 4)
        self.assertIn("causal_inference", lineage.families_detected)

        # Early papers should have late papers as children
        node_twfe = lineage.nodes["paper_twfe"]
        self.assertIn("paper_critique", node_twfe.children)
        self.assertIn("paper_did", node_twfe.children)

        # Late papers should have early papers as parents
        node_did = lineage.nodes["paper_did"]
        self.assertIn("paper_twfe", node_did.parents)

    def test_mermaid_formatting(self):
        """Format lineage graph into valid Mermaid flowchart markdown."""
        papers = [
            {"paper_id": "p1", "title": "Base Model", "authors": "Author A", "year": 2010, "content": "twfe"},
            {"paper_id": "p2", "title": "Extension Model", "authors": "Author B", "year": 2020, "content": "staggered did"},
        ]
        lineage = build_lineage_graph(papers)
        mermaid = format_lineage_mermaid(lineage)
        self.assertTrue(mermaid.startswith("```mermaid\ngraph TD"))
        self.assertIn("p1 -->", mermaid)
        self.assertTrue(mermaid.endswith("```"))

    def test_tree_formatting(self):
        """Format lineage graph as ASCII terminal tree."""
        papers = [
            {"paper_id": "p1", "title": "Foundational Model", "authors": "Smith", "year": 2000, "content": "twfe"},
            {"paper_id": "p2", "title": "Critique Model", "authors": "Jones", "year": 2015, "content": "twfe bias critique"},
        ]
        lineage = build_lineage_graph(papers)
        tree = format_lineage_tree(lineage)
        self.assertIn("Methodology Evolution Lineage Tree", tree)
        self.assertIn("[2000] Smith", tree)
        self.assertIn("[2015] Jones", tree)

    def test_json_formatting(self):
        """Serialize lineage graph to JSON."""
        papers = [
            {"paper_id": "p1", "title": "RBC Model", "authors": "Kydland & Prescott", "year": 1982, "content": "real business cycle RBC"},
            {"paper_id": "p2", "title": "DSGE Model", "authors": "Smets & Wouters", "year": 2007, "content": "DSGE model"},
        ]
        lineage = build_lineage_graph(papers)
        json_str = format_lineage_json(lineage)
        data = json.loads(json_str)
        self.assertEqual(data["total_papers"], 2)
        self.assertIn("p1", data["nodes"])
        self.assertIn("p2", data["nodes"])

    def test_cli_lineage_invocations(self):
        """Test Click CLI command with a synthetic test file."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "paper_method.txt"
            file_path.write_text(
                "In our empirical analysis, we employ a staggered difference-in-differences estimator "
                "following Callaway and Sant'Anna (2021) to overcome TWFE limitations.",
                encoding="utf-8",
            )

            # 1. Tree output
            res_tree = runner.invoke(main, ["lineage", str(file_path), "--format", "tree"])
            self.assertEqual(res_tree.exit_code, 0)
            self.assertIn("Methodology Evolution Lineage Tree", res_tree.stdout)

            # 2. JSON output
            res_json = runner.invoke(main, ["lineage", str(file_path), "--json"])
            self.assertEqual(res_json.exit_code, 0)
            out_str = res_json.stdout
            json_start = out_str.find("{")
            self.assertGreaterEqual(json_start, 0)
            data = json.loads(out_str[json_start:])
            self.assertEqual(data["total_papers"], 1)

            # 3. Mermaid output
            res_mmd = runner.invoke(main, ["lineage", str(file_path), "--format", "mermaid"])
            self.assertEqual(res_mmd.exit_code, 0)
            self.assertIn("```mermaid", res_mmd.stdout)


if __name__ == "__main__":
    unittest.main()
