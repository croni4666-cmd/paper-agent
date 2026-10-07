"""Unit tests for [P3-33] Dual-agent review & adjudication loop (pa review-adjudicate)."""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from click.testing import CliRunner

from pa_cli.review_adjudicate import (
    review_journal_fit,
    review_methodology,
    review_domain_literature,
    review_boundary_conditions,
    review_devils_advocate,
    adjudicate_panel,
    run_drafter_revision,
    run_dual_agent_loop,
    format_adjudication_table,
    format_adjudication_markdown,
    format_adjudication_json,
)
from pa_cli.project import init_project
from pa_cli.cli import main


SAMPLE_DRAFT_FLAWED = """
# Literature Review

ESG disclosure proves that firm performance increases dramatically across all companies.
Everyone knows that green investments have a super important role.
In our view, this completely solves corporate governance issues.
"""

SAMPLE_DRAFT_RIGOROUS = """
# Literature Review on Sustainable Finance

## 1. Theoretical Foundations
Agency theory [@jensen1976] and stakeholder theory [@freeman1984] provide competing predictions regarding corporate sustainability disclosure. While shareholder value models suggest disclosure increases managerial overhead, stakeholder theory posits that transparent reporting mitigates information asymmetry.

## 2. Empirical Identification & Methodological Strategies
Recent empirical studies employ quasi-experimental causal identification designs to address endogeneity. Specifically, [@chen2021] exploits staggered environmental mandate shocks using a difference-in-differences (DID) specification with two-way fixed effects (TWFE), finding a 3.4% increase in return on assets. Similarly, [@wang2022] utilizes an instrumental variable approach based on geographic weather shocks, corroborating the positive effect on capital access.

## 3. Competing Hypotheses & Counter-Evidence
However, divergent findings exist in the literature. In contrast to positive findings, [@garcia2020] documents that mandatory reporting imposes substantial compliance burdens on small firms, leading to null or countervailing profitability impacts.

## 4. Institutional Boundary Conditions & Heterogeneity
The documented effects are conditional on institutional boundary conditions and cross-sectional heterogeneity. The positive association is concentrated in non-state-owned enterprises (non-SOEs) and firms with high external financial constraints [@smith2023], whereas state-owned enterprises show muted responses.

## 5. Unresolved Tensions & Research Gaps
Despite these insights, several open questions remain unaddressed. The dynamic transition path following abrupt regulatory shocks represents a critical unresolved research gap that motivates the present empirical inquiry.
"""


class TestReviewAdjudicateP333(unittest.TestCase):
    """Test suite covering 5-seat reviewer panel, editorial adjudication, and dual-agent loop."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="test_adjudicate_")
        self.root = Path(self.tmp_dir) / "projects"

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_individual_reviewer_evaluations(self):
        """Test each of the 5 reviewer seats on flawed vs rigorous drafts."""
        # 1. Journal Fit
        r_flawed_eic = review_journal_fit(SAMPLE_DRAFT_FLAWED)
        self.assertLess(r_flawed_eic.score, 7.0)
        self.assertTrue(any(c.category == "style" for c in r_flawed_eic.critiques))

        r_rigorous_eic = review_journal_fit(SAMPLE_DRAFT_RIGOROUS)
        self.assertGreaterEqual(r_rigorous_eic.score, 8.0)
        self.assertTrue(any("thematic" in s.lower() for s in r_rigorous_eic.strengths))

        # 2. Methodology & Causal Identification
        r_flawed_meth = review_methodology(SAMPLE_DRAFT_FLAWED)
        self.assertTrue(any(c.severity == "CRITICAL" for c in r_flawed_meth.critiques))
        self.assertTrue(any("overclaim" in c.critique.lower() for c in r_flawed_meth.critiques))

        r_rigorous_meth = review_methodology(SAMPLE_DRAFT_RIGOROUS)
        self.assertGreaterEqual(r_rigorous_meth.score, 8.0)
        self.assertTrue(any("identification" in s.lower() for s in r_rigorous_meth.strengths))

        # 3. Domain Literature & Citations
        r_flawed_dom = review_domain_literature(SAMPLE_DRAFT_FLAWED)
        self.assertTrue(any(c.severity == "CRITICAL" for c in r_flawed_dom.critiques))

        r_rigorous_dom = review_domain_literature(SAMPLE_DRAFT_RIGOROUS)
        self.assertGreaterEqual(r_rigorous_dom.score, 7.5)

        # 4. Boundary Conditions
        r_flawed_bnd = review_boundary_conditions(SAMPLE_DRAFT_FLAWED)
        self.assertTrue(any(c.category == "boundary" for c in r_flawed_bnd.critiques))

        r_rigorous_bnd = review_boundary_conditions(SAMPLE_DRAFT_RIGOROUS)
        self.assertGreaterEqual(r_rigorous_bnd.score, 8.0)

        # 5. Devil's Advocate
        r_flawed_da = review_devils_advocate(SAMPLE_DRAFT_FLAWED)
        self.assertTrue(any(c.severity == "CRITICAL" for c in r_flawed_da.critiques))
        self.assertTrue(any("confirmation bias" in c.critique.lower() for c in r_flawed_da.critiques))

        r_rigorous_da = review_devils_advocate(SAMPLE_DRAFT_RIGOROUS)
        self.assertGreaterEqual(r_rigorous_da.score, 8.0)
        self.assertTrue(any("competing" in s.lower() for s in r_rigorous_da.strengths))

    def test_editorial_adjudication_verdicts(self):
        """Test editorial arbitration and decision outcomes."""
        # Flawed draft should trigger MAJOR REVISION or REJECT due to critical DA/methodology issues
        pkg_flawed = run_dual_agent_loop(SAMPLE_DRAFT_FLAWED, auto_revise=False)
        adj_flawed = pkg_flawed.initial_adjudication
        self.assertIn(adj_flawed.editorial_decision, ["MAJOR_REVISION", "REJECT_AND_RESUBMIT"])
        self.assertGreater(adj_flawed.da_critical_count, 0)
        self.assertTrue(any(item.priority == "MUST-ADDRESS" for item in adj_flawed.revision_roadmap))

        # Rigorous draft should achieve ACCEPT or MINOR REVISION
        pkg_rigorous = run_dual_agent_loop(SAMPLE_DRAFT_RIGOROUS, auto_revise=False)
        adj_rigorous = pkg_rigorous.initial_adjudication
        self.assertIn(adj_rigorous.editorial_decision, ["ACCEPT", "MINOR_REVISION"])
        self.assertEqual(adj_flawed.target_venue_tier, "field_top")

    def test_dual_agent_revision_loop(self):
        """Test drafter refinement loop (--revise) and author response generation."""
        pkg = run_dual_agent_loop(SAMPLE_DRAFT_FLAWED, auto_revise=True)
        self.assertTrue(pkg.has_revision)
        self.assertIsNotNone(pkg.revised_text)
        self.assertIsNotNone(pkg.response_to_reviewers)
        self.assertIsNotNone(pkg.post_revision_adjudication)

        # 1. Causal overclaims removed from revised text
        self.assertNotIn("proves that", pkg.revised_text.lower())
        self.assertIn("empirical evidence", pkg.revised_text.lower())

        # 2. Counter-evidence and boundary conditions added
        self.assertIn("Competing Hypotheses", pkg.revised_text)
        self.assertIn("Boundary Conditions", pkg.revised_text)

        # 3. Score improvement delta verified
        self.assertGreater(pkg.score_delta, 0.0)
        self.assertGreater(pkg.post_revision_adjudication.composite_score, pkg.initial_adjudication.composite_score)

        # 4. Response letter contains point-by-point replies
        self.assertIn("Author Response to Reviewers", pkg.response_to_reviewers)
        self.assertIn("Methodology Reviewer", pkg.response_to_reviewers)
        self.assertIn("Devil's Advocate Reviewer", pkg.response_to_reviewers)

    def test_format_renderers(self):
        """Test formatting in table, markdown, and json modes."""
        pkg = run_dual_agent_loop(SAMPLE_DRAFT_FLAWED, auto_revise=True)

        # ASCII table
        tbl = format_adjudication_table(pkg)
        self.assertIn("DUAL-AGENT PEER REVIEW & ADJUDICATION REPORT", tbl)
        self.assertIn("REFEREE PANEL BREAKDOWN", tbl)
        self.assertIn("REVISION LOOP RESULTS", tbl)

        # Markdown
        md = format_adjudication_markdown(pkg)
        self.assertIn("# Academic Literature Review Peer Review & Adjudication Package", md)
        self.assertIn("## 1. Editorial Decision Letter", md)
        self.assertIn("## 4. Dual-Agent Revision Outcome", md)

        # JSON
        js = format_adjudication_json(pkg)
        data = json.loads(js)
        self.assertIn("initial_adjudication", data)
        self.assertIn("score_delta", data)
        self.assertEqual(len(data["initial_adjudication"]["reviewer_reports"]), 5)

    def test_cli_review_adjudicate(self):
        """Test Click CLI command pa review-adjudicate with various flags."""
        draft_path = Path(self.tmp_dir) / "draft.md"
        draft_path.write_text(SAMPLE_DRAFT_FLAWED, encoding="utf-8")

        runner = CliRunner()

        # 1. JSON output mode
        res_json = runner.invoke(
            main,
            [
                "review-adjudicate",
                "-i", str(draft_path),
                "--json",
            ],
        )
        self.assertEqual(res_json.exit_code, 0)
        data = json.loads(res_json.stdout)
        self.assertEqual(len(data["initial_adjudication"]["reviewer_reports"]), 5)

        # 2. Table output mode with inline text
        res_tbl = runner.invoke(
            main,
            [
                "review-adjudicate",
                "-t", "ESG disclosure proves that firm performance increases.",
                "--format", "table",
            ],
        )
        self.assertEqual(res_tbl.exit_code, 0)
        self.assertIn("REFEREE PANEL BREAKDOWN", res_tbl.stdout)

        # 3. Revision loop with file exports
        out_report = Path(self.tmp_dir) / "adjudication_report.md"
        out_revised = Path(self.tmp_dir) / "revised_draft.md"
        out_response = Path(self.tmp_dir) / "response_letter.md"

        res_rev = runner.invoke(
            main,
            [
                "review-adjudicate",
                "-i", str(draft_path),
                "--revise",
                "--format", "markdown",
                "-o", str(out_report),
                "--output-revised", str(out_revised),
                "--output-response", str(out_response),
            ],
        )
        self.assertEqual(res_rev.exit_code, 0)
        self.assertTrue(out_report.exists())
        self.assertTrue(out_revised.exists())
        self.assertTrue(out_response.exists())

        revised_text = out_revised.read_text(encoding="utf-8")
        self.assertIn("Competing Hypotheses", revised_text)

        response_text = out_response.read_text(encoding="utf-8")
        self.assertIn("Author Response to Reviewers", response_text)

        # 4. Project integration test
        init_project("lit_proj", root=self.root)
        proj_rev = self.root / "lit_proj" / "review.md"
        proj_rev.write_text(SAMPLE_DRAFT_RIGOROUS, encoding="utf-8")

        res_proj = runner.invoke(
            main,
            [
                "review-adjudicate",
                "--project", "lit_proj",
                "--root", str(self.root),
                "--json",
            ],
        )
        self.assertEqual(res_proj.exit_code, 0)
        data_proj = json.loads(res_proj.stdout)
        self.assertIn(data_proj["initial_adjudication"]["editorial_decision"], ["ACCEPT", "MINOR_REVISION"])


if __name__ == "__main__":
    unittest.main()
