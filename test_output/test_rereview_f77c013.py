"""Regression test suite for GPT 7th re-review issues (commit f77c013).

Covers:
1. Finding 1 (P2): String macro literals preserve leading and trailing whitespace (e.g. suffix=" Suppl", prefix={Journal }).
2. Secondary Limitation (P2): Empty string macro aliases (@string{blank=""}, @string{alias=blank}) evaluate to empty string rather than falling back to macro name text.
3. Extended String Fidelity: Quoted/braced prefix, suffix, empty string, and whitespace-only macro combinations in screening export.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pa_cli.export_screening import build_screening_dict
from pa_cli.scaffold import load_bibtex, parse_bibtex, resolve_bibtex_value


class TestRereviewF77c013Fixes(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_suffix_leading_space_preserved_in_screening_export(self):
        """@string{suffix=" Suppl"} preserves leading space when concatenated in screening venue."""
        bib_text = (
            '@string{suffix=" Suppl"}\n'
            '@article{k, title={Title}, journal="Journal" # suffix}\n'
        )
        bib_file = self.tmpdir / "test_suffix.bib"
        bib_file.write_text(bib_text, encoding="utf-8")

        out = build_screening_dict(bib_file)
        self.assertEqual(out["k"]["venue"], "Journal Suppl")

    def test_prefix_trailing_space_preserved_in_screening_export(self):
        """@string{prefix={Journal }} preserves trailing space when concatenated in screening venue."""
        bib_text = (
            '@string{prefix={Journal }}\n'
            '@article{k, title={Title}, journal=prefix # "Suppl"}\n'
        )
        bib_file = self.tmpdir / "test_prefix.bib"
        bib_file.write_text(bib_text, encoding="utf-8")

        out = build_screening_dict(bib_file)
        self.assertEqual(out["k"]["venue"], "Journal Suppl")

    def test_empty_string_macro_and_alias_resolution(self):
        """@string{blank=""} and @string{alias=blank} evaluate to empty string, not macro identifier text."""
        bib_text = (
            '@string{blank=""}\n'
            '@string{alias=blank}\n'
            '@article{k, title={Title}, journal="Journal" # alias}\n'
        )
        bib_file = self.tmpdir / "test_blank_alias.bib"
        bib_file.write_text(bib_text, encoding="utf-8")

        out = build_screening_dict(bib_file)
        self.assertEqual(out["k"]["venue"], "Journal")

    def test_whitespace_only_macro_definitions(self):
        """Pure whitespace macros (@string{space=" "}, @string{spaces="   "}) are preserved verbatim."""
        bib_text = (
            '@string{space=" "}\n'
            '@string{spaces={   }}\n'
            '@article{k1, title={T1}, journal="Journal" # space # "A"}\n'
            '@article{k2, title={T2}, journal="Journal" # spaces # "B"}\n'
        )
        bib_file = self.tmpdir / "test_spaces.bib"
        bib_file.write_text(bib_text, encoding="utf-8")

        out = build_screening_dict(bib_file)
        self.assertEqual(out["k1"]["venue"], "Journal A")
        self.assertEqual(out["k2"]["venue"], "Journal   B")

    def test_prefix_and_suffix_multi_token_macro_chain(self):
        """Multi-token concatenation with prefix and suffix macros preserves all spacing."""
        bib_text = (
            '@string{pre="IEEE "}\n'
            '@string{post=" Letters"}\n'
            '@article{k, title={T}, journal=pre # "Trans" # post}\n'
        )
        bib_file = self.tmpdir / "test_chain.bib"
        bib_file.write_text(bib_text, encoding="utf-8")

        out = build_screening_dict(bib_file)
        self.assertEqual(out["k"]["venue"], "IEEE Trans Letters")


if __name__ == "__main__":
    unittest.main()
