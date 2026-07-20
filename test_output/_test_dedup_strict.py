"""Unit + e2e tests for pa_cli.dedup_strict ([P2-10])."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, '.')

from pa_cli.dedup_strict import (
    _normalize_title, _normalize_author, _extract_arxiv_id,
    fuzzy_title_match, title_similarity, dedup_key,
    find_dup_groups, write_deduped_bibtex, build_report, run_dedup,
)


SAMPLE_BIB = """@article{key1,
  title = {AI Tutoring Effects on K-12 Students},
  author = {Smith, John and Doe, Jane},
  year = {2023},
  doi = {10.1234/jml.2023.001}
}

@article{key2,
  title = {AI Tutoring Effects on K-12 Students},
  author = {Smith, J. and Doe, J.},
  year = {2023},
  doi = {10.1234/jml.2023.001}
}

@article{key3,
  title = {AI Tutoring Effects on K-12 Students (Preprint)},
  author = {Smith, John},
  year = {2023},
  doi = {10.5678/other.2023.002}
}

@article{key4,
  title = {ChatGPT in Higher Education},
  author = {Jones, Alice},
  year = {2024},
  doi = {10.5678/chi.2024.003}
}

@article{key5,
  title = {A Completely Unrelated Paper},
  author = {Lonely, Author},
  year = {2020},
  doi = {10.9999/lonely.2020.001}
}
"""


class TestNormalizeTitle(unittest.TestCase):
    def test_lowercase(self):
        self.assertEqual(_normalize_title('Hello WORLD'), 'hello world')

    def test_strip_punctuation(self):
        self.assertEqual(_normalize_title('Hello, World!'), 'hello world')

    def test_collapse_whitespace(self):
        self.assertEqual(_normalize_title('Hello   World'), 'hello world')

    def test_drop_latex_commands(self):
        self.assertEqual(_normalize_title('\\textbf{Bold} Title'), 'bold title')

    def test_drop_math_mode(self):
        self.assertEqual(_normalize_title('Result: $x^2$ is large'), 'result is large')

    def test_empty(self):
        self.assertEqual(_normalize_title(''), '')

    def test_curly_braces(self):
        self.assertEqual(_normalize_title('{Hello} {World}'), 'hello world')


class TestNormalizeAuthor(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(_normalize_author('Smith, John'), {'smithjohn'})

    def test_multiple_and(self):
        self.assertEqual(
            _normalize_author('Smith, John and Doe, Jane'),
            {'smithjohn', 'doejane'}
        )

    def test_empty(self):
        self.assertEqual(_normalize_author(''), set())


class TestExtractArxiv(unittest.TestCase):
    def test_modern_arxiv_id(self):
        e = {'eprint': '2507.02259'}
        self.assertEqual(_extract_arxiv_id(e), '2507.02259')

    def test_arxiv_prefix(self):
        e = {'eprint': 'arXiv:2507.02259'}
        self.assertEqual(_extract_arxiv_id(e), '2507.02259')

    def test_old_style_arxiv(self):
        e = {'eprint': 'math.AG/0501234'}
        self.assertEqual(_extract_arxiv_id(e), 'math.AG/0501234')

    def test_journal_arxiv(self):
        e = {'journal': 'arXiv preprint arXiv:2507.02259'}
        self.assertEqual(_extract_arxiv_id(e), '2507.02259')

    def test_no_arxiv(self):
        e = {'doi': '10.1234/abc'}
        self.assertIsNone(_extract_arxiv_id(e))

    def test_versioned(self):
        e = {'eprint': '2507.02259v2'}
        self.assertEqual(_extract_arxiv_id(e), '2507.02259v2')


class TestFuzzyTitleMatch(unittest.TestCase):
    def test_exact_match(self):
        self.assertTrue(fuzzy_title_match('Hello World', 'Hello World'))

    def test_case_insensitive(self):
        self.assertTrue(fuzzy_title_match('Hello World', 'hello world'))

    def test_close_match(self):
        # 'AI Tutoring Effects on K-12 Students' vs '... (Preprint)'
        # Difference is " (Preprint)" (11 chars); ratio should be >= 0.85
        self.assertTrue(fuzzy_title_match(
            'AI Tutoring Effects on K-12 Students',
            'AI Tutoring Effects on K-12 Students (Preprint)'
        ))

    def test_very_different(self):
        self.assertFalse(fuzzy_title_match(
            'AI Tutoring Effects on K-12 Students',
            'Quantum Chromodynamics at Finite Temperature'
        ))

    def test_with_punctuation_diff(self):
        self.assertTrue(fuzzy_title_match(
            'Hello, World: A Study',
            'Hello World A Study'
        ))

    def test_custom_threshold(self):
        # At 0.95 these two should NOT match
        self.assertFalse(fuzzy_title_match(
            'Hello World A',
            'Hello World B',
            threshold=0.95
        ))


class TestTitleSimilarity(unittest.TestCase):
    def test_identical(self):
        self.assertAlmostEqual(title_similarity('hello', 'hello'), 1.0)

    def test_completely_different(self):
        sim = title_similarity('hello', 'xyz')
        self.assertLess(sim, 0.5)

    def test_empty(self):
        self.assertEqual(title_similarity('', ''), 0.0)


class TestFindDupGroups(unittest.TestCase):
    def setUp(self):
        from pa_cli.scaffold import load_bibtex
        self.tmpdir = Path(tempfile.mkdtemp())
        self.bib = self.tmpdir / 'refs.bib'
        self.bib.write_text(SAMPLE_BIB, encoding='utf-8')
        self.entries = load_bibtex(self.bib)

    def test_finds_doi_duplicates(self):
        # key1 and key2 have same DOI; key3 fuzzy title also matches key1
        # So all 3 should be in one group
        groups = find_dup_groups(self.entries, fuzzy_threshold=0.85)
        # Find the group containing key1
        doi_groups = [g for g in groups if any(e.get('key') == 'key1' for e in g.entries)
                      and any(e.get('key') == 'key2' for e in g.entries)]
        self.assertEqual(len(doi_groups), 1, "key1 and key2 should be in same group")
        # Group has all 3 (key1, key2 by DOI; key3 by fuzzy title)
        self.assertEqual(len(doi_groups[0]), 3)

    def test_finds_fuzzy_title_duplicates(self):
        # key1 and key3 have different DOIs but similar titles
        groups = find_dup_groups(self.entries, fuzzy_threshold=0.85)
        # Find the group containing key1 and key3
        fuzzy_groups = [g for g in groups
                        if any(e.get('key') == 'key1' for e in g.entries)
                        and any(e.get('key') == 'key3' for e in g.entries)]
        self.assertEqual(len(fuzzy_groups), 1, "key1 and key3 should be grouped by fuzzy title")

    def test_unique_entries_kept_separate(self):
        # key4 and key5 are different from key1, key2, key3
        groups = find_dup_groups(self.entries, fuzzy_threshold=0.85)
        # All 5 should be in some group
        all_keys = [e.get('key') for g in groups for e in g.entries]
        self.assertEqual(sorted(all_keys), ['key1', 'key2', 'key3', 'key4', 'key5'])
        # Total should be 5 entries
        self.assertEqual(sum(len(g) for g in groups), 5)

    def test_lower_threshold_merges_more(self):
        # Higher threshold = stricter = fewer merges = MORE groups
        # Lower threshold = looser = more merges = FEWER groups
        groups_strict = find_dup_groups(self.entries, fuzzy_threshold=0.95)
        groups_loose = find_dup_groups(self.entries, fuzzy_threshold=0.5)
        self.assertGreater(len(groups_strict), len(groups_loose))


class TestWriteDedupedBibtex(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.bib = self.tmpdir / 'refs.bib'
        self.bib.write_text(SAMPLE_BIB, encoding='utf-8')
        self.out = self.tmpdir / 'deduped.bib'

    def test_writes_only_unique_entries(self):
        from pa_cli.scaffold import load_bibtex
        entries = load_bibtex(self.bib)
        groups = find_dup_groups(entries, fuzzy_threshold=0.85)
        n = write_deduped_bibtex(groups, self.bib.read_text(encoding='utf-8'), self.out)
        # 5 entries: key1/key2/key3 merge (DOI + fuzzy); key4, key5 alone
        # So unique = 3 groups: {key1,key2,key3} + {key4} + {key5} = 3
        self.assertEqual(n, 3)

    def test_output_is_valid_bibtex(self):
        from pa_cli.scaffold import parse_bibtex
        entries = load_bibtex_(self.bib)
        groups = find_dup_groups(entries, fuzzy_threshold=0.85)
        write_deduped_bibtex(groups, self.bib.read_text(encoding='utf-8'), self.out)
        # Re-parse the output
        out_text = self.out.read_text(encoding='utf-8')
        re_parsed = parse_bibtex(out_text)
        self.assertEqual(len(re_parsed), 3)


def load_bibtex_(path):
    from pa_cli.scaffold import load_bibtex
    return load_bibtex(path)


class TestBuildReport(unittest.TestCase):
    def test_report_includes_dup_groups(self):
        from pa_cli.scaffold import load_bibtex
        tmpdir = Path(tempfile.mkdtemp())
        bib = tmpdir / 'refs.bib'
        bib.write_text(SAMPLE_BIB, encoding='utf-8')
        entries = load_bibtex(bib)
        groups = find_dup_groups(entries, fuzzy_threshold=0.85)
        report = build_report(groups)
        self.assertIn('n_total_entries', report)
        self.assertIn('n_unique_entries', report)
        self.assertIn('n_duplicate_groups', report)
        self.assertIn('n_removed', report)
        self.assertIn('duplicate_groups', report)
        self.assertGreater(report['n_duplicate_groups'], 0)
        self.assertGreater(report['n_removed'], 0)


class TestRunDedupE2E(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.bib = self.tmpdir / 'refs.bib'
        self.bib.write_text(SAMPLE_BIB, encoding='utf-8')
        self.out = self.tmpdir / 'deduped.bib'
        self.report = self.tmpdir / 'report.json'

    def test_e2e_basic(self):
        result = run_dedup(self.bib, self.out)
        self.assertEqual(result['n_total_entries'], 5)
        self.assertGreater(result['n_removed'], 0)
        self.assertTrue(self.out.exists())

    def test_e2e_with_report(self):
        run_dedup(self.bib, self.out, report_path=self.report)
        self.assertTrue(self.report.exists())
        report = json.loads(self.report.read_text(encoding='utf-8'))
        self.assertIn('duplicate_groups', report)
        self.assertGreater(len(report['duplicate_groups']), 0)

    def test_e2e_deduped_bib_is_valid(self):
        from pa_cli.scaffold import parse_bibtex
        run_dedup(self.bib, self.out)
        out_text = self.out.read_text(encoding='utf-8')
        re_parsed = parse_bibtex(out_text)
        self.assertGreater(len(re_parsed), 0)
        # All re-parsed entries should have a key
        for e in re_parsed:
            self.assertIn('key', e)


class TestRealE2E(unittest.TestCase):
    """End-to-end with realistic bib that includes arxiv ID-based dup."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.bib = self.tmpdir / 'arxiv.bib'
        self.bib.write_text("""@article{arxiv1,
  title = {Attention is All You Need},
  author = {Vaswani, Ashish and Shazeer, Noam},
  year = {2017},
  eprint = {1706.03762},
  journal = {NeurIPS}
}

@inproceedings{arxiv1_dup,
  title = {Attention Is All You Need},
  author = {Vaswani, A. and Shazeer, N.},
  year = {2017},
  booktitle = {NeurIPS},
  doi = {10.5555/3295222.3295349}
}

@article{unrelated,
  title = {BERT: Pre-training of Deep Bidirectional Transformers},
  author = {Devlin, Jacob},
  year = {2018},
  doi = {10.18653/v1/N19-1423}
}
""", encoding='utf-8')
        self.out = self.tmpdir / 'deduped.bib'

    def test_arxiv_dedup_works(self):
        result = run_dedup(self.bib, self.out)
        # arxiv1 and arxiv1_dup should merge (same arxiv ID + similar title)
        # So unique = 2 (one merged pair + 1 unrelated)
        self.assertEqual(result['n_unique_entries'], 2)
        self.assertEqual(result['n_removed'], 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
