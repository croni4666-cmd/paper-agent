"""
test_output/test_empirical_design_p0_18.py — Unit & integration tests for [P0-18] empirical design & variable extractor.

Verifies:
  1. extract_empirical_design correctly extracts data sources (CSMAR, Wind, Compustat, etc.).
  2. extract_empirical_design extracts sample period (e.g. 2012-2021).
  3. extract_empirical_design extracts sample filtering rules (ST, financial, winsorize).
  4. extract_empirical_design extracts identification strategies (DID, Fixed Effects, 2SLS) and clustering.
  5. extract_empirical_design extracts dependent, independent, and control variables.
  6. extract_project_empirical_designs extracts across multi-paper project corpora.
  7. render_design_markdown renders structured cross-paper comparative matrix.
  8. CLI pa extract-design invocation for single PDF and project slug.
"""

import json
import tempfile
import unittest
from pathlib import Path
from click.testing import CliRunner

try:
    import pymupdf as fitz
except ImportError:
    import fitz

from pa_cli.cli import main
from pa_cli.empirical_design import (
    extract_empirical_design,
    extract_project_empirical_designs,
    render_design_markdown,
)
from pa_cli.project import init_project


def create_sample_empirical_pdf(pdf_path: Path, title: str, text: str):
    """Create a synthetic PDF with empirical methodology text for offline testing."""
    doc = fitz.open()
    page1 = doc.new_page()
    page1.insert_textbox(fitz.Rect(50, 50, 550, 750), f"Title: {title}\nAbstract: An empirical study.\n\n1. Introduction\nBackground text.")
    
    page2 = doc.new_page()
    page2.insert_textbox(fitz.Rect(50, 50, 550, 750), f"3. Data and Empirical Methodology\n\n{text}")
    doc.save(str(pdf_path))
    doc.close()


class TestEmpiricalDesignP018(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.root = self.tmpdir / "projects"
        self.root.mkdir(parents=True, exist_ok=True)

        self.pdf1_path = self.tmpdir / "paper_chinese_fin.pdf"
        create_sample_empirical_pdf(
            self.pdf1_path,
            "Digital Transformation and Corporate Performance",
            "Our sample covers 2012 to 2021. Financial and corporate governance data are obtained from CSMAR and Wind databases.\n"
            "Following convention, we exclude financial institutions and ST companies, and eliminate firms with missing observations.\n"
            "All continuous variables are winsorized at the 1% and 99% levels.\n\n"
            "We employ a staggered Difference-in-Differences (DID) model with firm and year fixed effects. "
            "Standard errors are clustered at the firm level.\n\n"
            "Our dependent variable is ROA (return on assets). The key explanatory variable is DigitalTransformation. "
            "Control variables include Size, Lev, Cash, Age, Growth, and Board size."
        )

        self.pdf2_path = self.tmpdir / "paper_us_econ.pdf"
        create_sample_empirical_pdf(
            self.pdf2_path,
            "Monetary Policy and Investment Dynamics",
            "The sample period spans 2005 through 2018. We collect firm accounting data from Compustat and stock returns from CRSP.\n"
            "Macroeconomic series are retrieved from FRED.\n"
            "We exclude financial firms and utility companies. Outliers are winsorized at the 1% level.\n\n"
            "We estimate a Two-way Fixed Effects (TWFE) regression and use Instrumental Variables (2SLS) for identification.\n"
            "We use Investment as the dependent variable. The main independent variable is InterestRateShock.\n"
            "Control variables: Size, Leverage, TobinQ, Cash, and ROE."
        )

    def test_extract_chinese_empirical_paper(self):
        res = extract_empirical_design(self.pdf1_path)
        self.assertEqual(res["file_name"], "paper_chinese_fin.pdf")

        # 1. Data sources
        sources = set(res["data_sources"])
        self.assertIn("CSMAR", sources)
        self.assertIn("Wind", sources)

        # 2. Sample period
        self.assertEqual(res["sample_period"], "2012–2021")

        # 3. Sample filtering
        filters = " ".join(res["sample_filtering"])
        self.assertIn("financial", filters)
        self.assertIn("ST", filters)
        self.assertIn("Winsorized", filters)

        # 4. Identification & clustering
        strats = res["identification_strategies"]
        self.assertTrue(any("Difference-in-Differences" in s for s in strats))
        self.assertTrue(any("Fixed Effects" in s for s in strats))
        self.assertTrue(any("firm level" in s for s in res["fixed_effects_and_clustering"]))

        # 5. Variables
        dv_names = [d["name"] for d in res["dependent_variables"]]
        self.assertTrue(any("ROA" in name for name in dv_names))

        iv_names = [i["name"] for i in res["independent_variables"]]
        self.assertTrue(any("DigitalTransformation" in name for name in iv_names))

        # Controls
        ctrls = set(res["control_variables"])
        self.assertIn("Firm Size (Size)", ctrls)
        self.assertIn("Leverage (Lev)", ctrls)
        self.assertIn("Cash Holdings (Cash)", ctrls)

    def test_extract_us_empirical_paper(self):
        res = extract_empirical_design(self.pdf2_path)
        self.assertEqual(res["file_name"], "paper_us_econ.pdf")

        # Data sources
        sources = set(res["data_sources"])
        self.assertIn("Compustat", sources)
        self.assertIn("CRSP", sources)
        self.assertIn("FRED", sources)

        # Sample period
        self.assertEqual(res["sample_period"], "2005–2018")

        # Identification
        strats = set(res["identification_strategies"])
        self.assertIn("Fixed Effects (FE / TWFE)", strats)
        self.assertIn("Instrumental Variables (IV / 2SLS)", strats)

        # Variables
        dv_names = [d["name"] for d in res["dependent_variables"]]
        self.assertTrue(any("Investment" in name for name in dv_names))

        iv_names = [i["name"] for i in res["independent_variables"]]
        self.assertTrue(any("InterestRateShock" in name for name in iv_names))

    def test_extract_project_empirical_designs(self):
        # Set up a project with multiple PDFs
        slug = "emp_proj"
        init_project(slug, title="Empirical Research Corpus", root=self.root)
        proj_dir = self.root / slug
        pdf_dir = proj_dir / "pdfs"

        # Copy synthetic PDFs into project pdfs folder
        (pdf_dir / "paper1.pdf").write_bytes(self.pdf1_path.read_bytes())
        (pdf_dir / "paper2.pdf").write_bytes(self.pdf2_path.read_bytes())

        proj_res = extract_project_empirical_designs(slug, root=self.root)
        self.assertEqual(proj_res["slug"], slug)
        self.assertEqual(proj_res["n_pdfs"], 2)
        self.assertEqual(len(proj_res["designs"]), 2)

    def test_render_design_markdown(self):
        d1 = extract_empirical_design(self.pdf1_path)
        d2 = extract_empirical_design(self.pdf2_path)
        md = render_design_markdown([d1, d2])

        self.assertIn("# Empirical Design Specifications", md)
        self.assertIn("Cross-Paper Comparative Matrix", md)
        self.assertIn("CSMAR", md)
        self.assertIn("Compustat", md)
        self.assertIn("2012–2021", md)
        self.assertIn("Difference-in-Differences", md)

    def test_cli_extract_design_file(self):
        runner = CliRunner()
        out_file = self.tmpdir / "single_design.md"

        result = runner.invoke(main, [
            "extract-design", str(self.pdf1_path),
            "--format", "markdown",
            "-o", str(out_file)
        ])
        self.assertEqual(result.exit_code, 0, result.stderr)
        self.assertTrue(out_file.exists())
        content = out_file.read_text(encoding="utf-8")
        self.assertIn("CSMAR", content)
        self.assertIn("ROA", content)

    def test_cli_extract_design_project_json(self):
        slug = "cli_proj"
        init_project(slug, root=self.root)
        pdf_dir = self.root / slug / "pdfs"
        (pdf_dir / "paper1.pdf").write_bytes(self.pdf1_path.read_bytes())

        runner = CliRunner()
        result = runner.invoke(main, [
            "extract-design", slug,
            "--format", "json",
            "--root", str(self.root)
        ])
        self.assertEqual(result.exit_code, 0, result.stderr)
        parsed = json.loads(result.stdout)
        self.assertEqual(parsed["slug"], slug)
        self.assertEqual(parsed["n_pdfs"], 1)
        self.assertEqual(parsed["designs"][0]["sample_period"], "2012–2021")


if __name__ == "__main__":
    unittest.main()
