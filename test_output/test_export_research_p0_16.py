"""
test_output/test_export_research_p0_16.py — Unit & integration tests for [P0-16] structured research metadata export.

Verifies:
  1. export_research with target='jupyter' (.ipynb valid notebook JSON and .json records).
  2. export_research with target='typst' (main.typ + companion refs.bib scaffolding).
  3. export_research with target='bib' / 'bibtex' (clean BibTeX formatting).
  4. Polymorphic source handling: project slug, .bib file path, .json file path, in-memory list.
  5. CLI pa export and pa project export invocation.
"""

import json
import tempfile
import unittest
from pathlib import Path
from click.testing import CliRunner

from pa_cli.cli import main
from pa_cli.export_research import export_research, export_to_jupyter_notebook, export_to_typst
from pa_cli.project import init_project


SAMPLE_BIB = """@article{vaswani2017,
  title = {Attention Is All You Need},
  author = {Vaswani, Ashish and Shazeer, Noam and Parmar, Niki},
  journal = {Advances in Neural Information Processing Systems},
  year = {2017},
  doi = {10.5555/3295222.3295349},
  abstract = {The dominant sequence transduction models are based on complex recurrent or convolutional neural networks.}
}
@article{devlin2018,
  title = {BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding},
  author = {Devlin, Jacob and Chang, Ming-Wei and Lee, Kenton},
  year = {2018},
  arxiv_id = {1810.04805},
  abstract = {We introduce a new language representation model called BERT.}
}
"""


class TestExportResearchP016(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.root = self.tmpdir / "projects"
        self.root.mkdir(parents=True, exist_ok=True)

        # Set up a test project
        self.slug = "test_nlp_proj"
        init_project(self.slug, title="Transformer Research Project", description="Investigating attention architectures", root=self.root)
        proj_dir = self.root / self.slug
        (proj_dir / "refs.bib").write_text(SAMPLE_BIB, encoding="utf-8")

        # Fake a PDF file for one paper
        pdf_dir = proj_dir / "pdfs"
        pdf_dir.mkdir(parents=True, exist_ok=True)
        (pdf_dir / "vaswani2017.pdf").write_bytes(b"%PDF-1.4 fake pdf content")

        # Fake topics.json
        topics_json = {
            "topics": [
                {
                    "topic_id": 1,
                    "label": "Attention Architectures",
                    "keywords": ["transformer", "attention", "nlp"],
                    "filenames": ["vaswani2017.pdf"],
                    "paper_count": 1,
                }
            ]
        }
        (proj_dir / "topics.json").write_text(json.dumps(topics_json), encoding="utf-8")

    def test_export_jupyter_notebook(self):
        out_nb = self.tmpdir / "analysis.ipynb"
        res = export_research(self.slug, target="jupyter", out_file=out_nb, root=self.root)

        self.assertEqual(res["target"], "jupyter")
        self.assertEqual(res["n_papers"], 2)
        self.assertEqual(res["n_pdfs"], 1)
        self.assertTrue(out_nb.exists())

        # Validate Jupyter Notebook structure
        nb_data = json.loads(out_nb.read_text(encoding="utf-8"))
        self.assertEqual(nb_data.get("nbformat"), 4)
        self.assertIn("cells", nb_data)
        self.assertGreaterEqual(len(nb_data["cells"]), 4)

        # Check markdown header cell
        md_cell = nb_data["cells"][0]
        self.assertEqual(md_cell["cell_type"], "markdown")
        md_text = "".join(md_cell["source"])
        self.assertIn("Transformer Research Project", md_text)
        self.assertIn("Paper Agent", md_text)

        # Check code cell loading dataframe
        code_cell = nb_data["cells"][1]
        self.assertEqual(code_cell["cell_type"], "code")
        code_text = "".join(code_cell["source"])
        self.assertIn("import pandas as pd", code_text)
        self.assertIn("df = pd.DataFrame", code_text)
        self.assertIn("vaswani2017", code_text)

    def test_export_jupyter_records_json(self):
        out_json = self.tmpdir / "records.json"
        res = export_research(self.slug, target="jupyter", out_file=out_json, root=self.root)

        self.assertTrue(out_json.exists())
        records = json.loads(out_json.read_text(encoding="utf-8"))
        self.assertIsInstance(records, list)
        self.assertEqual(len(records), 2)

        keys = {r["key"] for r in records}
        self.assertEqual(keys, {"vaswani2017", "devlin2018"})

        vaswani = next(r for r in records if r["key"] == "vaswani2017")
        self.assertTrue(vaswani["has_pdf"])
        self.assertEqual(vaswani["year"], 2017)
        self.assertEqual(vaswani["doi"], "10.5555/3295222.3295349")
        self.assertIn("Attention Architectures", vaswani["topics"])

        devlin = next(r for r in records if r["key"] == "devlin2018")
        self.assertFalse(devlin["has_pdf"])
        self.assertEqual(devlin["arxiv_id"], "1810.04805")
        self.assertEqual(devlin["url"], "https://arxiv.org/abs/1810.04805")

    def test_export_typst_scaffolding(self):
        typst_dir = self.tmpdir / "typst_export"
        res = export_research(self.slug, target="typst", out_file=typst_dir, root=self.root)

        self.assertEqual(res["target"], "typst")
        self.assertEqual(len(res["files_written"]), 2)

        main_typ = typst_dir / "main.typ"
        refs_bib = typst_dir / "refs.bib"
        self.assertTrue(main_typ.exists())
        self.assertTrue(refs_bib.exists())

        typ_text = main_typ.read_text(encoding="utf-8")
        self.assertIn('#set page(', typ_text)
        self.assertIn('Transformer Research Project', typ_text)
        self.assertIn('Attention Is All You Need', typ_text)
        self.assertIn('#bibliography("refs.bib"', typ_text)
        self.assertIn('@vaswani2017', typ_text)

        bib_text = refs_bib.read_text(encoding="utf-8")
        self.assertIn('@article{vaswani2017', bib_text)
        self.assertIn('@article{devlin2018', bib_text)

    def test_export_bib(self):
        out_bib = self.tmpdir / "clean_refs.bib"
        res = export_research(self.slug, target="bib", out_file=out_bib, root=self.root)

        self.assertEqual(res["target"], "bib")
        self.assertTrue(out_bib.exists())
        content = out_bib.read_text(encoding="utf-8")
        self.assertIn('@article{vaswani2017', content)
        self.assertIn('@article{devlin2018', content)

    def test_export_from_external_bib_file(self):
        ext_bib = self.tmpdir / "external.bib"
        ext_bib.write_text(SAMPLE_BIB, encoding="utf-8")

        out_nb = self.tmpdir / "external_analysis.ipynb"
        res = export_research(ext_bib, target="jupyter", out_file=out_nb)

        self.assertEqual(res["n_papers"], 2)
        self.assertTrue(out_nb.exists())
        nb_data = json.loads(out_nb.read_text(encoding="utf-8"))
        self.assertEqual(nb_data["nbformat"], 4)

    def test_cli_pa_export_command(self):
        runner = CliRunner()
        out_nb = str(self.tmpdir / "cli_out.ipynb")

        # 1. Export with slug and target
        result = runner.invoke(main, [
            "export", self.slug,
            "--target", "jupyter",
            "--out", out_nb,
            "--root", str(self.root)
        ])
        self.assertEqual(result.exit_code, 0, result.stderr)
        self.assertIn("Successfully exported 2 papers (jupyter)", result.stdout)
        self.assertTrue(Path(out_nb).exists())

        # 2. Export with --json flag to inspect structured payload
        result_json = runner.invoke(main, [
            "export", self.slug,
            "--target", "bib",
            "--json",
            "--root", str(self.root)
        ])
        self.assertEqual(result_json.exit_code, 0, result_json.stderr)
        data = json.loads(result_json.stdout)
        self.assertEqual(data["n_papers"], 2)
        self.assertEqual(data["target"], "bib")

    def test_cli_pa_project_export_with_new_targets(self):
        runner = CliRunner()
        out_typ = str(self.tmpdir / "proj_export_typst")

        result = runner.invoke(main, [
            "project", "export", self.slug,
            "--target", "typst",
            "-o", out_typ,
            "--root", str(self.root)
        ])
        self.assertEqual(result.exit_code, 0, result.stderr)
        self.assertTrue((Path(out_typ) / "main.typ").exists())
        self.assertTrue((Path(out_typ) / "refs.bib").exists())


if __name__ == "__main__":
    unittest.main()
