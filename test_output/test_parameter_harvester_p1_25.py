"""Unit tests for Simulation Calibration Parameter Harvester [P1-25].

Tests:
1. Extraction of canonical macroeconomic parameters (beta, gamma, alpha, delta, rho, sigma).
2. Extraction of microeconomic and empirical priors (MPC, price elasticity, treatment effect).
3. Category filtering (macro, micro, empirical).
4. Standard error, 95% CI, and frequency detection.
5. Parameter prior distributions (min, mean, max) across multiple values.
6. PDF document extraction with PyMuPDF synthetic fixture.
7. CLI command invocations (--text, --json, --format markdown, --format python).
"""

import json
import tempfile
import unittest
from pathlib import Path
from click.testing import CliRunner

from pa_cli.cli import main
from pa_cli.parameter_harvester import (
    harvest_parameters_from_text,
    harvest_parameters_from_pdf,
    summarize_parameters,
    format_parameters_report,
)


class TestParameterHarvesterP125(unittest.TestCase):
    def test_harvest_macro_parameters(self):
        """Harvest canonical structural macro parameters."""
        text = (
            "In our benchmark calibration, we set the discount factor to beta = 0.99 (quarterly), "
            "corresponding to an annual risk-free rate of 4%. "
            "The coefficient of relative risk aversion is set to gamma = 2.0 (standard in macro literature). "
            "The capital share is alpha = 0.36, and the quarterly depreciation rate of capital is delta = 0.025. "
            "The Frisch elasticity of labor supply is calibrated to 0.75. "
            "For technology shocks, the persistence parameter is rho = 0.95 and the innovation volatility is sigma = 0.007 (SE = 0.0012)."
        )
        params = harvest_parameters_from_text(text, source_doc="macro_spec.pdf")
        self.assertGreaterEqual(len(params), 6)

        param_dict = {p.name: p for p in params}
        self.assertIn("discount_factor", param_dict)
        self.assertEqual(param_dict["discount_factor"].value, 0.99)
        self.assertEqual(param_dict["discount_factor"].unit_frequency, "quarterly")

        self.assertIn("risk_aversion", param_dict)
        self.assertEqual(param_dict["risk_aversion"].value, 2.0)

        self.assertIn("capital_share", param_dict)
        self.assertEqual(param_dict["capital_share"].value, 0.36)

        self.assertIn("depreciation_rate", param_dict)
        self.assertEqual(param_dict["depreciation_rate"].value, 0.025)

        self.assertIn("shock_persistence", param_dict)
        self.assertEqual(param_dict["shock_persistence"].value, 0.95)

        self.assertIn("shock_volatility", param_dict)
        self.assertEqual(param_dict["shock_volatility"].value, 0.007)
        self.assertEqual(param_dict["shock_volatility"].std_err, 0.0012)

    def test_harvest_micro_and_empirical_parameters(self):
        """Harvest microeconomic elasticities and empirical effect sizes."""
        text = (
            "We estimate a price elasticity of demand theta = 1.8. "
            "The marginal propensity to consume is MPC = 0.32. "
            "In our baseline specification, the average treatment effect was beta = 0.142 (95% CI: 0.085, 0.199; SE = 0.029)."
        )
        params = harvest_parameters_from_text(text, source_doc="empirical_paper")
        param_dict = {p.name: p for p in params}

        self.assertIn("price_elasticity", param_dict)
        self.assertEqual(param_dict["price_elasticity"].value, 1.8)

        self.assertIn("marginal_propensity_consume", param_dict)
        self.assertEqual(param_dict["marginal_propensity_consume"].value, 0.32)

        self.assertIn("treatment_effect", param_dict)
        self.assertEqual(param_dict["treatment_effect"].value, 0.142)
        self.assertEqual(param_dict["treatment_effect"].std_err, 0.029)
        self.assertEqual(param_dict["treatment_effect"].ci_lower, 0.085)
        self.assertEqual(param_dict["treatment_effect"].ci_upper, 0.199)

    def test_category_filtering(self):
        """Filter parameters by domain category."""
        text = (
            "We calibrate beta = 0.99 and gamma = 2.0 for macro agents. "
            "The baseline treatment effect was beta = 0.25 (empirical)."
        )
        macro_only = harvest_parameters_from_text(text, category_filter="macro")
        empirical_only = harvest_parameters_from_text(text, category_filter="empirical")

        self.assertTrue(all(p.category == "macro" for p in macro_only))
        self.assertTrue(all(p.category == "empirical" for p in empirical_only))

    def test_confidence_interval_and_se_extraction(self):
        """Verify extraction of negative and positive confidence interval bounds."""
        text = (
            "Parameter gamma = 2.5 with 95% CI [-0.15, 3.45]. "
            "Another parameter theta = 1.25 (95% CI: 0.85 to 1.65; SE = 0.18)."
        )
        params = harvest_parameters_from_text(text)
        param_dict = {p.name: p for p in params}

        self.assertIn("risk_aversion", param_dict)
        self.assertEqual(param_dict["risk_aversion"].ci_lower, -0.15)
        self.assertEqual(param_dict["risk_aversion"].ci_upper, 3.45)

        self.assertIn("price_elasticity", param_dict)
        self.assertEqual(param_dict["price_elasticity"].ci_lower, 0.85)
        self.assertEqual(param_dict["price_elasticity"].ci_upper, 1.65)
        self.assertEqual(param_dict["price_elasticity"].std_err, 0.18)

    def test_distribution_bounds_summary(self):
        """Verify cross-paper distribution aggregation (min, mean, max)."""
        text = (
            "Paper A calibrated discount factor to beta = 0.98. "
            "Paper B set the discount factor to beta = 0.99. "
            "Paper C assumed discount factor is set to beta = 0.96."
        )
        params = harvest_parameters_from_text(text)
        summary = summarize_parameters(params)

        self.assertIn("discount_factor", summary.distributions)
        df_dist = summary.distributions["discount_factor"]
        self.assertEqual(df_dist["count"], 3)
        self.assertEqual(df_dist["min"], 0.96)
        self.assertEqual(df_dist["max"], 0.99)
        self.assertAlmostEqual(df_dist["mean"], (0.98 + 0.99 + 0.96) / 3, places=3)

    def test_pdf_parameter_harvesting(self):
        """Harvest calibration parameters from synthetic PDF file."""
        import fitz

        with tempfile.TemporaryDirectory() as tmp_dir:
            pdf_path = Path(tmp_dir) / "calibration_paper.pdf"
            doc = fitz.open()
            page = doc.new_page(width=600, height=800)
            rect = fitz.Rect(50, 50, 550, 750)
            page.insert_textbox(
                rect,
                "Section 5. Quantitative Calibration\n\n"
                "In our baseline model, we calibrate the quarterly discount factor to beta = 0.99. "
                "The coefficient of relative risk aversion is set to gamma = 2.0. "
                "The depreciation rate is delta = 0.025, and capital share is alpha = 0.36.\n"
            )
            doc.save(str(pdf_path))
            doc.close()

            summary = harvest_parameters_from_pdf(pdf_path)
            self.assertEqual(summary.total_parameters, 4)
            param_names = {p.name for p in summary.parameters}
            self.assertEqual(
                param_names,
                {"discount_factor", "risk_aversion", "depreciation_rate", "capital_share"},
            )
            self.assertIn("calibration_paper.pdf:p1", summary.parameters[0].source_doc)

    def test_cli_extract_parameters_invocations(self):
        """Test Click CLI commands with --text, --json, --format python, --format markdown."""
        runner = CliRunner()

        text_arg = "We set the discount factor to beta = 0.99 (quarterly) and gamma = 2.0."

        # 1. JSON format
        res_json = runner.invoke(main, ["extract-parameters", "--text", text_arg, "--json"])
        self.assertEqual(res_json.exit_code, 0)
        out_str = res_json.stdout
        json_start = out_str.find("{")
        self.assertGreaterEqual(json_start, 0)
        data = json.loads(out_str[json_start:])
        self.assertEqual(data["total_parameters"], 2)

        # 2. Python code format
        res_py = runner.invoke(main, ["extract-parameters", "--text", text_arg, "--format", "python"])
        self.assertEqual(res_py.exit_code, 0)
        self.assertIn("CALIBRATION_PRIORS = {", res_py.stdout)
        self.assertIn('"discount_factor"', res_py.stdout)
        self.assertIn('"risk_aversion"', res_py.stdout)

        # 3. Markdown format
        res_md = runner.invoke(main, ["extract-parameters", "--text", text_arg, "--format", "markdown"])
        self.assertEqual(res_md.exit_code, 0)
        self.assertIn("# Simulation Calibration Parameters", res_md.stdout)
        self.assertIn("Discount Factor", res_md.stdout)


if __name__ == "__main__":
    unittest.main()
