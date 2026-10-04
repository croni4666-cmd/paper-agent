"""
test_output/test_table_extractor_p0_17.py — Unit & integration tests for [P0-17] offline PDF table extractor.

Verifies:
  1. extract_tables correctly extracts grid tables and text-aligned empirical tables.
  2. Associates Table titles (e.g. Table 1, Table 2) and footnotes/notes.
  3. Classifies tables into descriptive_statistics, baseline_regression, etc.
  4. Renders clean Markdown representation.
  5. Exports tables to CSV files.
  6. Multi-PDF project batch extraction.
  7. CLI pa extract-tables invocation (markdown, json, csv).
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
from pa_cli.project import init_project
from pa_cli.table_extractor import (
    classify_table,
    export_tables_to_csv,
    extract_project_tables,
    extract_tables,
    render_tables_markdown,
)


def create_sample_table_pdf(pdf_path: Path):
    """Create a synthetic PDF with empirical tables for offline testing."""
    doc = fitz.open()

    # Page 1: Text-aligned Descriptive Statistics table (Table 1)
    p1 = doc.new_page()
    table1_text = (
        "Table 1: Descriptive Statistics of Main Variables\n"
        "Variable    N        Mean     Std.Dev.   Min      Max\n"
        "ROA         24510    0.045    0.062     -0.150    0.280\n"
        "Size        24510    22.31    1.24       19.50    26.10\n"
        "Lev         24510    0.421    0.198      0.052    0.890\n"
        "Cash        24510    0.185    0.134      0.012    0.650\n"
        "Notes: Continuous variables are winsorized at the 1% and 99% levels."
    )
    p1.insert_textbox(fitz.Rect(50, 50, 550, 300), table1_text)

    # Page 2: Grid-bordered Baseline Regression table (Table 2)
    p2 = doc.new_page()
    p2.insert_text((50, 45), "Table 2: Baseline Regression Results")
    # Draw a 4x3 grid table
    p2.draw_rect(fitz.Rect(50, 50, 450, 170))
    p2.draw_line(fitz.Point(50, 80), fitz.Point(450, 80))
    p2.draw_line(fitz.Point(50, 110), fitz.Point(450, 110))
    p2.draw_line(fitz.Point(50, 140), fitz.Point(450, 140))
    p2.draw_line(fitz.Point(180, 50), fitz.Point(180, 170))
    p2.draw_line(fitz.Point(320, 50), fitz.Point(320, 170))

    p2.insert_text((60, 70), "Variables")
    p2.insert_text((190, 70), "Model (1)")
    p2.insert_text((330, 70), "Model (2)")

    p2.insert_text((60, 100), "Digital")
    p2.insert_text((190, 100), "0.038***")
    p2.insert_text((330, 100), "0.032***")

    p2.insert_text((60, 130), "Size")
    p2.insert_text((190, 130), "0.015**")
    p2.insert_text((330, 130), "0.012**")

    p2.insert_text((60, 160), "Observations")
    p2.insert_text((190, 160), "24510")
    p2.insert_text((330, 160), "24510")

    p2.insert_text((50, 190), "Notes: Standard errors clustered at the firm level in parentheses. *** p<0.01, ** p<0.05.")

    doc.save(str(pdf_path))
    doc.close()


class TestTableExtractorP017(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.root = self.tmpdir / "projects"
        self.root.mkdir(parents=True, exist_ok=True)
        self.pdf_path = self.tmpdir / "sample_tables.pdf"
        create_sample_table_pdf(self.pdf_path)

    def test_classify_table(self):
        self.assertEqual(classify_table("Table 1: Summary Statistics", ""), "descriptive_statistics")
        self.assertEqual(classify_table("Table 2: Main Baseline Regression", ""), "baseline_regression")
        self.assertEqual(classify_table("Table 3: Robustness and Placebo Tests", ""), "robustness_checks")
        self.assertEqual(classify_table("Table 4: Mechanism Analysis", ""), "mechanism_analysis")
        self.assertEqual(classify_table("Table 5: Subsample Heterogeneity", ""), "heterogeneity")
        self.assertEqual(classify_table("Table 6: Correlation Matrix", ""), "correlation_matrix")

    def test_extract_tables_from_pdf(self):
        data = extract_tables(self.pdf_path)
        self.assertEqual(data["file_name"], "sample_tables.pdf")
        self.assertGreaterEqual(data["total_tables"], 2)

        # Check Table 1
        t1 = data["tables"][0]
        self.assertIn("Table 1", t1["title"])
        self.assertEqual(t1["type"], "descriptive_statistics")
        self.assertEqual(t1["page"], 1)
        self.assertIn("Variable", t1["headers"])
        self.assertIn("ROA", [r[0] for r in t1["rows"]])
        self.assertIn("winsorized", t1["notes"].lower())
        self.assertIn("| Variable |", t1["markdown"])

        # Check Table 2
        t2 = data["tables"][1]
        self.assertIn("Table 2", t2["title"])
        self.assertEqual(t2["type"], "baseline_regression")
        self.assertEqual(t2["page"], 2)
        self.assertIn("Variables", t2["headers"])
        self.assertIn("Digital", [r[0] for r in t2["rows"]])

    def test_render_tables_markdown(self):
        data = extract_tables(self.pdf_path)
        md = render_tables_markdown(data)
        self.assertIn("# Empirical Tables Extracted", md)
        self.assertIn("Table 1: Descriptive Statistics", md)
        self.assertIn("Table 2: Baseline Regression Results", md)
        self.assertIn("| ROA |", md)
        self.assertIn("| Digital |", md)

    def test_export_tables_to_csv(self):
        data = extract_tables(self.pdf_path)
        csv_dir = self.tmpdir / "csv_out"
        saved = export_tables_to_csv(data, csv_dir)
        self.assertGreaterEqual(len(saved), 2)
        for s in saved:
            self.assertTrue(Path(s).exists())

        # Check contents of first CSV
        content = Path(saved[0]).read_text(encoding="utf-8-sig")
        self.assertIn("Variable", content)
        self.assertIn("ROA", content)

    def test_extract_project_tables(self):
        slug = "table_proj"
        init_project(slug, root=self.root)
        pdf_dir = self.root / slug / "pdfs"
        (pdf_dir / "paper_a.pdf").write_bytes(self.pdf_path.read_bytes())

        proj_data = extract_project_tables(slug, root=self.root)
        self.assertEqual(proj_data["slug"], slug)
        self.assertEqual(proj_data["n_pdfs"], 1)
        self.assertGreaterEqual(proj_data["total_tables"], 2)

    def test_cli_extract_tables_markdown(self):
        runner = CliRunner()
        out_md = str(self.tmpdir / "tables.md")

        result = runner.invoke(main, [
            "extract-tables", str(self.pdf_path),
            "--format", "markdown",
            "-o", out_md
        ])
        self.assertEqual(result.exit_code, 0, result.stderr)
        self.assertTrue(Path(out_md).exists())
        content = Path(out_md).read_text(encoding="utf-8")
        self.assertIn("Table 1: Descriptive Statistics", content)

    def test_cli_extract_tables_json(self):
        runner = CliRunner()
        result = runner.invoke(main, [
            "extract-tables", str(self.pdf_path),
            "--format", "json"
        ])
        self.assertEqual(result.exit_code, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["file_name"], "sample_tables.pdf")
        self.assertGreaterEqual(data["total_tables"], 2)

    def test_cli_extract_tables_csv(self):
        runner = CliRunner()
        csv_out_dir = str(self.tmpdir / "cli_csv_out")

        result = runner.invoke(main, [
            "extract-tables", str(self.pdf_path),
            "--format", "csv",
            "-o", csv_out_dir
        ])
        self.assertEqual(result.exit_code, 0, result.stderr)
        self.assertIn("Successfully exported", result.stdout)
        self.assertTrue(Path(csv_out_dir).is_dir())
        csv_files = list(Path(csv_out_dir).glob("*.csv"))
        self.assertGreaterEqual(len(csv_files), 2)


if __name__ == "__main__":
    unittest.main()
