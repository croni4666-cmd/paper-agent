"""Unit + e2e tests for pa_cli.cite_check ([P2-7]).

Run with:
  python -m pytest test_output/_test_cite_check.py -v
or
  python test_output/_test_cite_check.py
"""
import json
import sys
import unittest
import tempfile
from pathlib import Path

# Add repo root to path
sys.path.insert(0, '.')

from pa_cli.cite_check import (
    extract_cite_keys,
    cross_ref,
    format_report,
    run_cite_check,
    suggest_fix,
    _edit_distance_1_or_2,
)


class TestExtractCiteKeys(unittest.TestCase):
    def test_simple_key(self):
        text = "Some text [@smith2023ai] more text."
        keys = extract_cite_keys(text)
        self.assertEqual(len(keys), 1)
        self.assertEqual(keys[0], ('smith2023ai', 1))

    def test_multiple_keys_one_line(self):
        text = "Compare [@smith2023ai] and [@jones2024chatgpt]."
        keys = extract_cite_keys(text)
        self.assertEqual(len(keys), 2)
        self.assertEqual([k for k, _ in keys], ['smith2023ai', 'jones2024chatgpt'])

    def test_keys_with_dashes_colons_dots(self):
        text = "Cite [@smith-2023.ai] and [@author:2023]."
        keys = extract_cite_keys(text)
        self.assertEqual([k for k, _ in keys], ['smith-2023.ai', 'author:2023'])

    def test_keys_with_page_locator(self):
        # [@key, p. 12] should still extract 'key'
        text = "As shown in [@smith2023ai, p. 12]."
        keys = extract_cite_keys(text)
        self.assertEqual([k for k, _ in keys], ['smith2023ai'])

    def test_line_numbers(self):
        text = "Line 1 [@a2023].\nLine 2 [@b2023].\nLine 3 [@c2023]."
        keys = extract_cite_keys(text)
        self.assertEqual([ln for _, ln in keys], [1, 2, 3])

    def test_no_keys(self):
        text = "No citations here."
        keys = extract_cite_keys(text)
        self.assertEqual(keys, [])


class TestEditDistance(unittest.TestCase):
    def test_distance_1(self):
        # 'smith' vs 'smyth' = 1 substitution
        self.assertTrue(_edit_distance_1_or_2('smith', 'smyth'))
        # 'smith' vs 'smih' = 1 deletion
        self.assertTrue(_edit_distance_1_or_2('smith', 'smih'))

    def test_distance_2(self):
        # 'smith2023' vs 'smtih2023' = 2 (transposition counts as 2 in edit dist)
        # Or 1 deletion + 1 insertion
        self.assertTrue(_edit_distance_1_or_2('smith2023', 'smtih2023'))

    def test_distance_3(self):
        # 'abcd' vs 'wxyz' = 4 substitutions
        self.assertFalse(_edit_distance_1_or_2('abcd', 'wxyz'))

    def test_same_string(self):
        # Same string = 0 distance, NOT a typo
        self.assertFalse(_edit_distance_1_or_2('smith', 'smith'))

    def test_too_long_difference(self):
        # Length diff > 2 = distance > 2 (early exit)
        self.assertFalse(_edit_distance_1_or_2('a', 'abcd'))


class TestSuggestFix(unittest.TestCase):
    def test_finds_typo(self):
        bib_keys = {'smith2023ai', 'jones2024chatgpt', 'acemoglu2022'}
        suggests = suggest_fix('smtih2023ai', bib_keys)
        self.assertIn('smith2023ai', suggests)

    def test_no_suggestion_for_far_off(self):
        bib_keys = {'completely_different_key'}
        suggests = suggest_fix('short', bib_keys)
        self.assertEqual(suggests, [])

    def test_max_suggestions(self):
        bib_keys = {'abc2023a', 'abc2023b', 'abc2023c', 'abc2023d'}
        suggests = suggest_fix('abc2023', bib_keys)
        self.assertLessEqual(len(suggests), 3)  # default max_suggestions=3


class TestCrossRef(unittest.TestCase):
    def test_clean(self):
        placeholders = [('smith2023ai', 1), ('jones2024', 2)]
        bib_keys = {'smith2023ai', 'jones2024'}
        result = cross_ref(placeholders, bib_keys)
        self.assertEqual(result['missing'], [])
        self.assertEqual(result['typoed'], [])
        self.assertEqual(result['orphan'], [])

    def test_missing(self):
        placeholders = [('nonexistent2020', 1)]
        bib_keys = {'smith2023ai'}
        result = cross_ref(placeholders, bib_keys)
        self.assertEqual(len(result['missing']), 1)
        self.assertEqual(result['missing'][0]['key'], 'nonexistent2020')
        self.assertEqual(result['missing'][0]['line'], 1)

    def test_typo(self):
        placeholders = [('smtih2023ai', 1)]
        bib_keys = {'smith2023ai'}
        result = cross_ref(placeholders, bib_keys)
        self.assertEqual(result['missing'], [])
        self.assertEqual(len(result['typoed']), 1)
        self.assertEqual(result['typoed'][0]['key'], 'smtih2023ai')
        self.assertIn('smith2023ai', result['typoed'][0]['suggest'])

    def test_orphan(self):
        placeholders = [('smith2023ai', 1)]
        bib_keys = {'smith2023ai', 'orphan2020key'}
        result = cross_ref(placeholders, bib_keys)
        self.assertEqual(len(result['orphan']), 1)
        self.assertEqual(result['orphan'][0]['key'], 'orphan2020key')

    def test_all_three(self):
        placeholders = [
            ('smith2023ai', 1),         # ok
            ('nonexistent2020', 2),     # missing
            ('smtih2023ai', 3),         # typo of smith
        ]
        bib_keys = {'smith2023ai', 'orphan2020key'}
        result = cross_ref(placeholders, bib_keys)
        self.assertEqual(result['missing'][0]['key'], 'nonexistent2020')
        self.assertEqual(result['typoed'][0]['key'], 'smtih2023ai')
        self.assertEqual(result['orphan'][0]['key'], 'orphan2020key')


class TestRunCiteCheckE2E(unittest.TestCase):
    """End-to-end test with real fixture files."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.bib_path = self.tmpdir / 'refs.bib'
        self.bib_path.write_text("""@article{key1,
  title = {Paper One},
  author = {Author, A.},
  year = {2023}
}

@article{key2,
  title = {Paper Two},
  author = {Author, B.},
  year = {2024}
}

@article{orphan_key,
  title = {Never Cited},
  year = {2020}
}
""", encoding='utf-8')

        self.skel_path = self.tmpdir / 'skeleton.md'
        self.skel_path.write_text("""# Lit Review

Some text [@key1] here. Also [@kee1] which is a typo.
And [@totally_missing] has no bib entry.
""", encoding='utf-8')

    def test_e2e_text(self):
        result, report = run_cite_check(self.bib_path, self.skel_path, output_json=False)
        # missing: totally_missing
        self.assertEqual(len(result['missing']), 1)
        self.assertEqual(result['missing'][0]['key'], 'totally_missing')
        # typo: kee1 -> key1
        self.assertEqual(len(result['typoed']), 1)
        self.assertEqual(result['typoed'][0]['key'], 'kee1')
        self.assertIn('key1', result['typoed'][0]['suggest'])
        # orphan: key2 + orphan_key (key1 cited, key2 not, orphan_key not)
        self.assertEqual(len(result['orphan']), 2)
        orphan_keys = {o['key'] for o in result['orphan']}
        self.assertEqual(orphan_keys, {'key2', 'orphan_key'})
        # report has all 3 sections
        self.assertIn('[MISSING]', report)
        self.assertIn('[TYPOED]', report)
        self.assertIn('[ORPHAN]', report)

    def test_e2e_json(self):
        result, report = run_cite_check(self.bib_path, self.skel_path, output_json=True)
        data = json.loads(report)
        self.assertEqual(data['n_bib_keys'], 3)
        self.assertEqual(len(data['missing']), 1)
        self.assertEqual(len(data['typoed']), 1)
        self.assertEqual(len(data['orphan']), 2)

    def test_clean_skeleton(self):
        # Make a clean skeleton
        clean_skel = self.tmpdir / 'clean.md'
        clean_skel.write_text("[@key1] [@key2]\n", encoding='utf-8')
        result, report = run_cite_check(self.bib_path, clean_skel, output_json=False)
        self.assertEqual(result['missing'], [])
        self.assertEqual(result['typoed'], [])
        self.assertEqual(len(result['orphan']), 1)  # orphan_key
        self.assertIn('[ORPHAN]', report)
        self.assertNotIn('[MISSING]', report)


class TestFormatReport(unittest.TestCase):
    def test_clean_report(self):
        result = {'missing': [], 'typoed': [], 'orphan': []}
        report = format_report(result, Path('/tmp/skel.md'), Path('/tmp/refs.bib'))
        self.assertIn('All placeholders resolve', report)
        self.assertNotIn('[MISSING]', report)

    def test_report_includes_line_numbers(self):
        result = {'missing': [{'key': 'k1', 'line': 42}], 'typoed': [], 'orphan': []}
        report = format_report(result, Path('/tmp/skel.md'), Path('/tmp/refs.bib'))
        # format uses 4-wide left-padded line number
        self.assertIn('42', report)
        self.assertIn('k1', report)
        self.assertRegex(report, r'line\s+42:')


if __name__ == '__main__':
    unittest.main(verbosity=2)
