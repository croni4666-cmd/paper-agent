"""
[P2-5] e2e test: pa scaffold + pa build round-trip on a 3-paper fixture.

Validates:
  1. scaffold() reads bibtex, renders markdown skeleton with cite placeholders
  2. build() invokes pandoc correctly and produces a non-empty output file
  3. GB/T 7714 CSL is bundled and accessible
  4. Bibtex cite keys are resolved in the output (not left as [@key] placeholders)

Run:
  cd "G:\minimax - workspace\Paper agent"
  python test_output\_test_pa_build.py
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

# Make pa_cli importable
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pa_cli.build import build, check_pandoc, find_pdf_engine, DEFAULT_CSL  # noqa: E402
from pa_cli.scaffold import (  # noqa: E402
    scaffold, parse_bibtex, render_skeleton, load_bibtex,
)


# 3-paper fixture (mimics output from `pa search --format bibtex`)
FIXTURE_BIB = r"""
@article{smith2023digital,
  author = {Smith, John and Doe, Jane},
  title = {Digital financial inclusion and household consumption: evidence from China},
  journal = {Journal of Development Economics},
  year = {2023},
  volume = {162},
  pages = {103--118},
  doi = {10.1016/j.jdeveco.2023.103118},
}

@article{li2022fintech,
  author = {Li, Wei and Chen, Hao},
  title = {Fintech development and bank risk-taking: a Chinese perspective},
  journal = {Journal of Financial Stability},
  year = {2022},
  volume = {60},
  pages = {100995},
  doi = {10.1016/j.jfs.2022.100995},
}

@article{wang2024insurance,
  author = {Wang, Fang and Liu, Yang and Zhang, Min},
  title = {Long-term care insurance and population aging in China},
  journal = {China Economic Review},
  year = {2024},
  volume = {85},
  pages = {102--120},
  doi = {10.1016/j.chieco.2024.102120},
}
"""


class TestScaffold(unittest.TestCase):
    def test_parse_bibtex_count(self):
        entries = parse_bibtex(FIXTURE_BIB)
        self.assertEqual(len(entries), 3, f"Expected 3 entries, got {len(entries)}")
        keys = {e["key"] for e in entries}
        self.assertEqual(
            keys,
            {"smith2023digital", "li2022fintech", "wang2024insurance"},
        )

    def test_parse_bibtex_fields(self):
        entries = parse_bibtex(FIXTURE_BIB)
        e = next(e for e in entries if e["key"] == "smith2023digital")
        self.assertEqual(e["type"], "article")
        self.assertIn("Smith", e.get("author", ""))
        self.assertIn("Doe", e.get("author", ""))
        self.assertEqual(e.get("year"), "2023")
        self.assertIn("Digital financial inclusion", e.get("title", ""))

    def test_scaffold_default_group_by_year(self):
        entries = parse_bibtex(FIXTURE_BIB)
        md = render_skeleton(entries, group_by="year", title="测试综述")
        # Has title H1
        self.assertIn("# 测试综述", md)
        # Has 引言 + 结语
        self.assertIn("## 引言", md)
        self.assertIn("## 结语", md)
        # Year sections present
        self.assertIn("## 2024", md)
        self.assertIn("## 2023", md)
        self.assertIn("## 2022", md)
        # Inline cite placeholders for all 3 papers (in meta line OR prompt)
        for key in ("smith2023digital", "li2022fintech", "wang2024insurance"):
            self.assertIn(f"[@{key}]", md, f"Missing inline cite for {key}")
        # Each paper gets an H3
        self.assertIn("### Digital financial inclusion", md)
        self.assertIn("### Fintech development", md)
        self.assertIn("### Long-term care insurance", md)
        # Has prompt blocks
        self.assertIn("> prompt:", md)

    def test_scaffold_group_by_author(self):
        entries = parse_bibtex(FIXTURE_BIB)
        md = render_skeleton(entries, group_by="author", title="Author Grouped")
        self.assertIn("## Li", md)
        self.assertIn("## Smith", md)
        self.assertIn("## Wang", md)

    def test_scaffold_empty_bibtex(self):
        md = render_skeleton([], group_by="year", title="Empty")
        self.assertIn("# Empty", md)
        self.assertIn("Bibtex", md)  # empty warning


class TestBuild(unittest.TestCase):
    def setUp(self):
        # Make sure pandoc is available; skip if not
        try:
            check_pandoc()
        except Exception as e:
            self.skipTest(f"pandoc not available: {e}")

    def test_default_csl_exists(self):
        self.assertTrue(DEFAULT_CSL.is_file(), f"Bundled CSL missing: {DEFAULT_CSL}")
        # CSL is XML; sanity-check
        head = DEFAULT_CSL.read_text(encoding="utf-8")[:200]
        self.assertIn("<style", head, f"CSL doesn't look like XML: {head!r}")
        # Should reference GB/T 7714
        body = DEFAULT_CSL.read_text(encoding="utf-8")
        self.assertTrue(
            "GB/T 7714" in body or "7714" in body,
            f"CSL doesn't reference GB/T 7714 in title/desc. First 200 chars: {head}",
        )

    def test_pdf_engine_detection(self):
        # find_pdf_engine may return None if nothing installed; both outcomes valid
        engine = find_pdf_engine()
        # If anything found, must be one of the known engines
        if engine is not None:
            self.assertIn(engine, {"xelatex", "pdflatex", "lualatex", "weasyprint"})

    def test_e2e_html(self):
        """End-to-end: scaffold -> fill dummy prose -> build HTML."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            bib_path = tmp / "refs.bib"
            bib_path.write_text(FIXTURE_BIB, encoding="utf-8")

            # 1. Scaffold
            skel_path = tmp / "skeleton.md"
            md = scaffold(bibtex_path=bib_path, group_by="year",
                          title="数字普惠金融综述", output_path=skel_path)
            self.assertTrue(skel_path.is_file())
            self.assertGreater(skel_path.stat().st_size, 500)
            # has cite placeholders
            self.assertIn("[@smith2023digital]", md)

            # 2. Insert real prose with [@key] cites so pandoc can format them.
            # Replace each paper's prompt with a sentence that includes the
            # corresponding [@key] cite, and add a short intro paragraph.
            skel_text = skel_path.read_text(encoding="utf-8")
            # Intro: add a sentence with the first paper cited
            skel_text = skel_text.replace(
                "> prompt: 用 1 段",
                "本文综述聚焦数字普惠金融与家庭消费领域，"
                "梳理 2022-2024 年的核心文献，"
                "为相关研究提供参考 [@smith2023digital]。",
                1,
            )
            # Per-paper: replace the "prompt: 用 1-2 句..." line with a real sentence
            # that includes the paper's own [@key] cite
            for key in ("smith2023digital", "li2022fintech", "wang2024insurance"):
                # Find the line for this paper and replace its prompt
                old_pattern = f"prompt: 用 1-2 句总结该论文的核心方法 + 关键发现 + 与本节主题的关系，并在描述其贡献时引用 [@{key}]"
                new_text = (
                    f"该研究表明，数字普惠金融对相关领域有重要影响 [@{key}]；"
                    f"其方法在 2022-2024 年的实证研究中具有代表性。"
                )
                skel_text = skel_text.replace(old_pattern, new_text)
            skel_path.write_text(skel_text, encoding="utf-8")

            # 3. Build to HTML
            out_html = tmp / "manuscript.html"
            result = build(
                bibtex_path=bib_path,
                skeleton_path=skel_path,
                output_path=out_html,
                quiet=True,
            )
            self.assertTrue(result.is_file(), f"HTML output not created: {result}")
            size = result.stat().st_size
            self.assertGreater(size, 1000, f"HTML too small: {size} bytes")

            # 4. Verify HTML contains resolved cites (not [@key] placeholders)
            html = out_html.read_text(encoding="utf-8")
            self.assertNotIn("[@smith2023digital]", html,
                             "Unresolved cite placeholder in output")
            # GB/T 7714 numeric style uses [1], [2], [3] in-text cites
            cite_marks = sum(html.count(f"[{i}]") for i in range(1, 4))
            self.assertGreater(cite_marks, 0,
                               f"No in-text cite marks [1]/[2]/[3] found in HTML. "
                               f"First 500 chars: {html[:500]!r}")
            # bib should have all 3 entries
            for lastname in ("Smith", "Li", "Wang"):
                self.assertIn(lastname, html,
                              f"Reference for {lastname} missing from HTML bibliography")

    def test_e2e_docx(self):
        """End-to-end: scaffold -> build DOCX (no engine needed)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            bib_path = tmp / "refs.bib"
            bib_path.write_text(FIXTURE_BIB, encoding="utf-8")
            skel_path = tmp / "skeleton.md"
            scaffold(bibtex_path=bib_path, group_by="year",
                     title="DOCX Test", output_path=skel_path)

            out_docx = tmp / "manuscript.docx"
            result = build(
                bibtex_path=bib_path,
                skeleton_path=skel_path,
                output_path=out_docx,
                quiet=True,
            )
            self.assertTrue(result.is_file())
            # DOCX is a ZIP; first 4 bytes = 'PK\x03\x04'
            with open(result, "rb") as f:
                magic = f.read(4)
            self.assertEqual(magic, b"PK\x03\x04",
                             f"DOCX doesn't have ZIP magic: {magic!r}")

    def test_e2e_gfm(self):
        """End-to-end: scaffold -> build GFM (Markdown with resolved cites)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            bib_path = tmp / "refs.bib"
            bib_path.write_text(FIXTURE_BIB, encoding="utf-8")
            skel_path = tmp / "skeleton.md"
            scaffold(bibtex_path=bib_path, group_by="year",
                     title="GFM Test", output_path=skel_path)

            out_md = tmp / "manuscript.md"
            build(
                bibtex_path=bib_path,
                skeleton_path=skel_path,
                output_path=out_md,
                quiet=True,
            )
            self.assertTrue(out_md.is_file())
            md = out_md.read_text(encoding="utf-8")
            # Cite should be resolved
            self.assertNotIn("[@smith2023digital]", md)
            # Bibliography section should have entries
            self.assertIn("Smith", md)
            self.assertIn("Li", md)
            self.assertIn("Wang", md)


if __name__ == "__main__":
    print(f"Using pa_cli from: {ROOT}")
    print(f"Default CSL: {DEFAULT_CSL}")
    print()
    unittest.main(verbosity=2)
