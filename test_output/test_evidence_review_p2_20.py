"""Unit tests for [P2-20] Evidence-grounded literature review section scripter."""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from click.testing import CliRunner

from pa_cli.project import init_project, project_review, DEFAULT_ROOT
from pa_cli.evidence_review import (
    harvest_paper_evidence,
    generate_evidence_backed_review,
    BoundEvidence,
    ReviewClaim,
)
from pa_cli.cli import main


class TestEvidenceReviewP220(unittest.TestCase):
    """Test suite covering evidence harvesting, thematic review generation, and CLI."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="test_ev_review_")
        self.root = Path(self.tmp_dir) / "projects"

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_harvest_paper_evidence_from_bib(self):
        """Test extraction and categorization of evidence passages from BibTeX abstract."""
        entry = {
            "key": "smith2020",
            "title": "Corporate Governance and Agency Costs",
            "year": "2020",
            "doi": "10.1016/j.jcorpfin.2020.101",
            "abstract": (
                "Theoretically posited by agency theory, governance reduces friction. "
                "We implement a staggered difference-in-differences design. "
                "Empirical results indicate that board independence significantly promotes return on assets by 2.4%. "
                "Heterogeneity analysis shows the effect is stronger for non-state-owned enterprises."
            ),
        }
        buckets = harvest_paper_evidence(None, entry)

        self.assertIn("theory", buckets)
        self.assertIn("methods", buckets)
        self.assertIn("results", buckets)
        self.assertIn("heterogeneity", buckets)

        # Method should match Staggered DID
        self.assertTrue(any("difference-in-differences" in ev.excerpt.lower() for ev in buckets["methods"]))

        # Results should match empirical findings
        self.assertTrue(any("promotes return on assets" in ev.excerpt.lower() for ev in buckets["results"]))

        # Check evidence ID formatting
        for ev_list in buckets.values():
            for ev in ev_list:
                self.assertTrue(ev.evidence_id.startswith("ev-"))
                self.assertEqual(ev.page, 0)

    def test_harvest_paper_evidence_from_pdf(self):
        """Test page-aware evidence harvesting directly from PDF full-text with PyMuPDF."""
        try:
            import fitz
        except ImportError:
            self.skipTest("PyMuPDF not installed")

        pdf_path = Path(self.tmp_dir) / "angrist1991.pdf"
        doc = fitz.open()

        # Page 1: Theory & Setup
        p1 = doc.new_page()
        p1.insert_text((50, 72), "Compulsory schooling laws and human capital accumulation.\nAccording to human capital theory, education directly raises labor productivity.")

        # Page 2: Methods
        p2 = doc.new_page()
        p2.insert_text((50, 72), "We exploit quarter of birth as an instrumental variable in a two-stage least squares (2SLS) regression framework.")

        # Page 3: Results
        p3 = doc.new_page()
        p3.insert_text((50, 72), "Empirical results show that compulsory schooling significantly increases annual earnings by approximately 7.5%.")

        doc.save(str(pdf_path))
        doc.close()

        entry = {"key": "angrist1991", "year": "1991", "doi": "10.2307/2937927"}
        buckets = harvest_paper_evidence(pdf_path, entry)

        # Check methods came from Page 2
        methods_ev = next(ev for ev in buckets["methods"] if "2sls" in ev.excerpt.lower())
        self.assertEqual(methods_ev.page, 2)
        self.assertIn("angrist1991.pdf", methods_ev.filename)

        # Check results came from Page 3
        results_ev = next(ev for ev in buckets["results"] if "increases" in ev.excerpt.lower())
        self.assertEqual(results_ev.page, 3)

    def test_generate_evidence_backed_review_end_to_end(self):
        """Test full generation of evidence-backed literature review for a project."""
        init_project("esg_study", title="ESG and Corporate Valuation", root=self.root)
        refs_path = self.root / "esg_study" / "refs.bib"
        refs_content = """@article{paper1,
  title = {Stakeholder Theory and Firm Value},
  author = {Freeman, R.},
  year = {2018},
  doi = {10.1007/s10551-018-001},
  abstract = {Drawing upon stakeholder theory, managerial attention to social expectations creates sustainable corporate advantage.}
}
@article{paper2,
  title = {Empirical Evidence on ESG Performance},
  author = {Bénabou, R. and Tirole, J.},
  year = {2020},
  doi = {10.1093/jeea/jvw020},
  abstract = {We implement two-way fixed effects estimators. Results indicate that proactive sustainability significantly increases equity market valuation.}
}
@article{paper3,
  title = {The Cost of Corporate Virtue},
  author = {Friedman, M.},
  year = {2022},
  doi = {10.1086/260000},
  abstract = {Empirical findings show that mandatory compliance decreases operational efficiency and reduces profit margins. Subsample analysis reveals the penalty is exacerbated in competitive sectors.}
}
"""
        refs_path.write_text(refs_content, encoding="utf-8")

        md_output = project_review(
            "esg_study",
            root=self.root,
            evidence_backed=True,
            with_prisma=False,
        )

        # 1. Check title and provenance section
        self.assertIn("# Evidence-Grounded Literature Review: ESG and Corporate Valuation", md_output)
        self.assertIn("Verifiable PDF Evidence Binding Rate", md_output)
        self.assertIn("100.0%", md_output)

        # 2. Check all 5 thematic sections exist
        self.assertIn("## 1. Theoretical Framework & Conceptual Foundations", md_output)
        self.assertIn("## 2. Core Empirical Debates & Competing Hypotheses", md_output)
        self.assertIn("## 3. Causal Identification Strategies & Methodological Lineage", md_output)
        self.assertIn("## 4. Boundary Conditions & Heterogeneity Dimensions", md_output)
        self.assertIn("## 5. Unresolved Tensions & Empirical Research Gaps", md_output)

        # 3. Check evidence binding block presence
        self.assertIn("> **[Verified Evidence Binding - CLAIM-001]**", md_output)
        self.assertIn("Verbatim Passage", md_output)
        self.assertIn("[@paper1]", md_output)

    def test_evidence_review_json_manifest(self):
        """Test outputting machine-readable evidence provenance manifest as JSON."""
        init_project("fin_proj", title="Financial Literacy", root=self.root)
        refs_path = self.root / "fin_proj" / "refs.bib"
        refs_path.write_text("""@article{lusardi2014,
  title = {The Economic Importance of Financial Literacy},
  author = {Lusardi, Annamaria and Mitchell, Olivia},
  year = {2014},
  doi = {10.1257/jel.52.1.5},
  abstract = {We examine financial literacy using instrumental variables estimation. Empirical evidence demonstrates that financial knowledge promotes wealth accumulation.}
}
""", encoding="utf-8")

        json_str = project_review(
            "fin_proj",
            root=self.root,
            evidence_backed=True,
            as_json=True,
            with_prisma=False,
        )

        data = json.loads(json_str)
        self.assertEqual(data["project_slug"], "fin_proj")
        self.assertGreaterEqual(data["total_claims"], 1)
        self.assertEqual(data["binding_rate"], 1.0)
        claim = data["claims"][0]
        self.assertIn("claim_id", claim)
        self.assertIn("evidence", claim)
        self.assertTrue(claim["evidence"]["evidence_id"].startswith("ev-"))

    def test_cli_project_review_evidence_backed(self):
        """Test CLI execution of pa project review with --evidence-backed and --json."""
        init_project("cli_proj", title="CLI Review Test", root=self.root)
        refs_path = self.root / "cli_proj" / "refs.bib"
        refs_path.write_text("""@article{test2021,
  title = {Testing Evidence Review CLI},
  author = {Tester, A.},
  year = {2021},
  abstract = {Results reveal that automated literature generation increases researcher productivity.}
}
""", encoding="utf-8")

        runner = CliRunner()

        # 1. Markdown review output
        res_md = runner.invoke(
            main,
            [
                "project", "review", "cli_proj",
                "--evidence-backed",
                "--no-prisma",
                "--root", str(self.root),
            ],
        )
        self.assertEqual(res_md.exit_code, 0)
        self.assertIn("Evidence-Grounded Literature Review", res_md.stdout)
        self.assertIn("[Verified Evidence Binding", res_md.stdout)

        # 2. JSON manifest output
        res_json = runner.invoke(
            main,
            [
                "project", "review", "cli_proj",
                "--evidence-backed",
                "--json",
                "--root", str(self.root),
            ],
        )
        self.assertEqual(res_json.exit_code, 0)
        manifest = json.loads(res_json.stdout)
        self.assertEqual(manifest["project_slug"], "cli_proj")
        self.assertEqual(manifest["binding_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
