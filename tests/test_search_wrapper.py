"""Offline wrapper contract tests: real process arguments and output shaping."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / '.agents/skills/paper-agent/scripts/search.py'
CLI = r'''
import json, sys
args = sys.argv[1:]
if args[0] != 'search':
    raise SystemExit('unexpected command: ' + repr(args))
print(json.dumps({'query': args[1], 'received_args': args[2:], 'results': [
  {'title': 'One', 'doi': '10.1/one', 'found_by': ['openalex', 'crossref'], 'quality_flag': 'ok'},
  {'title': 'Two', 'doi': '10.1/two', 'found_by': ['pubmed'], 'quality_flag': 'low_quality'}
]}))
'''


class SearchWrapperTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / 'fixture-repo'
        package = self.repo / 'pa_cli'
        package.mkdir(parents=True)
        (package / '__init__.py').write_text('')
        (package / 'cli.py').write_text(CLI, encoding='utf-8')
        self.env = dict(os.environ, PAPER_AGENT_ROOT=str(self.repo),
                        PAPER_AGENT_PYTHON=sys.executable, PYTHONDONTWRITEBYTECODE='1')

    def run_search(self, *args):
        return subprocess.run([sys.executable, '-X', 'utf8', str(SCRIPT), 'topic', *args],
                              env=self.env, capture_output=True, encoding='utf-8', timeout=10)

    def test_fast_strategy_selects_fast_sources_and_relevance_sort(self):
        result = self.run_search('--strategy', 'fast')
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data['received_args'], ['--engine', 'openalex,crossref', '--limit', '20', '--quality-mode', 'flag', '--quiet', '--sort-by', 'relevance'])
        self.assertEqual(data['strategy'], 'fast')

    def test_biomedical_strategy_preserves_user_year_and_limit_filters(self):
        result = self.run_search('--strategy', 'biomedical', '--year-min', '2020', '--year-max', '2024', '--limit', '7')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['received_args'], ['--engine', 'pubmed,openalex', '--limit', '7', '--quality-mode', 'flag', '--quiet', '--sort-by', 'relevance', '--year-min', '2020', '--year-max', '2024'])

    def test_explicit_engine_keeps_default_behavior_without_strategy_metadata(self):
        result = self.run_search('--engine', 'arxiv', '--output', 'json')
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertNotIn('strategy', data)
        self.assertEqual(data['received_args'], ['--engine', 'arxiv', '--limit', '20', '--quality-mode', 'flag', '--quiet'])

    def test_quality_summary_reports_results_by_flag_and_source_overlap(self):
        result = self.run_search('--strategy', 'broad')
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data['quality_summary'], {'total': 2, 'by_flag': {'low_quality': 1, 'ok': 1}, 'multi_source': 1})

    def test_custom_quality_mode_is_forwarded(self):
        result = self.run_search('--quality-mode', 'filter')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--quality-mode', json.loads(result.stdout)['received_args'])
        self.assertIn('filter', json.loads(result.stdout)['received_args'])

    def test_source_filter_and_explicit_sort_are_forwarded(self):
        result = self.run_search('--source', 'openalex,pubmed', '--sort-by', 'year')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['received_args'], ['--engine', 'all', '--limit', '20', '--quality-mode', 'flag', '--quiet', '--sort-by', 'year', '--source', 'openalex,pubmed'])

    def test_strategy_and_explicit_non_all_engine_are_rejected(self):
        result = self.run_search('--strategy', 'fast', '--engine', 'arxiv')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('cannot be combined', result.stderr)


if __name__ == '__main__':
    unittest.main()
