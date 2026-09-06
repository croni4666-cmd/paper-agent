"""Offline integration tests: real wrapper subprocesses against a fixture CLI."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / '.agents/skills/paper-agent/scripts'
# Only the external CLI is replaced. Paths, files, process launch and JSON are real.
CLI = r'''
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
mode = os.environ.get('FIXTURE_MODE', 'valid')
def option(name):
    return args[args.index(name) + 1]
def pdf(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n')
if args[0] == 'fetch':
    p = Path(option('--output-dir')) / 'paper.pdf'
    pdf(p)
    if mode == 'html': p.write_text('<html>Login required</html>')
    if mode == 'truncated': p.write_bytes(b'%PDF-1.4\ntruncated')
    if mode == 'missing': p.unlink()
    if mode == 'malformed': print('not json'); sys.exit(0)
    if mode == 'cli_error': print(json.dumps({'error': 'quota'})); sys.exit(0)
    print(json.dumps({'saved_as': str(p), 'via_channel': 'fixture', 'size_bytes': 999}))
elif args[0] == 'fetch-batch':
    assert Path(args[1]).is_file()
    p = Path(option('--out-dir')) / 'one.pdf'
    pdf(p)
    rows = [{'key':'one', 'doi':'10.1/one', 'success':True, 'out_path':str(p), 'size_bytes':999, 'error':''}]
    if mode == 'html': p.write_text('<html>Not PDF</html>')
    if mode == 'skipped': rows[0]['error'] = 'skipped-existing'
    if mode in ('partial', 'timeout'):
        rows.append({'key':'two','doi':'10.1/two','success':False,'out_path':'','error':'global-timeout' if mode == 'timeout' else 'not found'})
    summary = {'n_total':len(rows),'n_success':1,'n_failure':len(rows)-1,'n_skipped':0,'results':rows}
    if '--summary-json' in args:
        target = Path(option('--summary-json'))
        if mode == 'no_report': pass
        elif mode == 'malformed': target.write_text('not json')
        else: target.write_text(json.dumps(summary))
    print('Downloaded batch')
elif args[0] == 'review':
    assert Path(args[1]).is_file(), args[1]
    Path(option('--output')).write_text('Evidence review', encoding='utf-8')
elif args[0] == 'citations':
    Path(option('--output')).write_text(json.dumps({'count': 1, 'forward':[{}]}))
else:
    print(json.dumps({'title':'中文论文', 'encoding':os.environ.get('PYTHONIOENCODING')}, ensure_ascii=False))
'''


class WrapperTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'fixture repo'
        package = self.repo / 'pa_cli'
        package.mkdir(parents=True)
        (package / '__init__.py').write_text('')
        (package / 'cli.py').write_text(CLI, encoding='utf-8')
        (package / '__main__.py').write_text('from . import cli')
        self.cwd = self.root / 'user workspace'
        self.cwd.mkdir()
        (self.cwd / 'refs.bib').write_text('@article{one,doi={10.1/one}}')
        self.env = dict(os.environ, PAPER_AGENT_ROOT=str(self.repo),
                        PAPER_AGENT_PYTHON=sys.executable, PYTHONIOENCODING='ascii',
                        PYTHONDONTWRITEBYTECODE='1')

    def run_wrapper(self, name, *args, mode='valid'):
        result = subprocess.run([sys.executable, '-X', 'utf8', str(SCRIPTS / name), *args],
                                cwd=self.cwd, env=dict(self.env, FIXTURE_MODE=mode),
                                capture_output=True, encoding='utf-8', timeout=15)
        return result

    def test_fetch_resolves_output_against_caller(self):
        result = self.run_wrapper('fetch.py', '10.1/one', '--output-dir', 'my pdfs')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.cwd / 'my pdfs/paper.pdf').is_file())

    def test_fetch_success_is_verified_and_size_is_actual(self):
        target = self.cwd / 'pdfs'
        result = self.run_wrapper('fetch.py', '10.1/one', '--output-dir', str(target))
        data = json.loads(result.stdout)
        self.assertEqual(data.get('status'), 'success')
        self.assertEqual(data['size_bytes'], (target / 'paper.pdf').stat().st_size)

    def test_fetch_rejects_bad_artifacts_and_bad_payloads(self):
        for mode in ('html', 'truncated', 'missing', 'malformed', 'cli_error'):
            with self.subTest(mode=mode):
                result = self.run_wrapper('fetch.py', '10.1/one', '--output-dir', str(self.cwd / 'pdfs'), mode=mode)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(json.loads(result.stderr).get('status'), 'failed')

    def test_batch_always_collects_report(self):
        result = self.run_wrapper('fetch_batch.py', 'refs.bib', '--output-dir', 'pdfs')
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data.get('status'), 'success')
        self.assertEqual(len(data['summary']['results']), 1)

    def test_batch_partial_and_timeout_are_not_success(self):
        for mode in ('partial', 'timeout'):
            with self.subTest(mode=mode):
                result = self.run_wrapper('fetch_batch.py', 'refs.bib', mode=mode)
                self.assertNotEqual(result.returncode, 0)
                data = json.loads(result.stderr)
                self.assertEqual(data.get('status'), 'partial')
                self.assertEqual(data['summary']['n_success'], 1)

    def test_batch_revalidates_skipped_files(self):
        result = self.run_wrapper('fetch_batch.py', 'refs.bib', '--skip-existing', mode='skipped')
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data.get('status'), 'success')
        self.assertEqual(data['summary']['n_skipped'], 1)

    def test_batch_rejects_invalid_pdf(self):
        result = self.run_wrapper('fetch_batch.py', 'refs.bib', mode='html')
        self.assertNotEqual(result.returncode, 0)
        data = json.loads(result.stderr)
        self.assertEqual(data.get('status'), 'failed')
        self.assertFalse(data['summary']['results'][0]['success'])

    def test_batch_does_not_reuse_stale_user_report(self):
        report = self.cwd / 'report.json'
        report.write_text(json.dumps({'n_total':0, 'results':[]}))
        result = self.run_wrapper('fetch_batch.py', 'refs.bib', '--report', str(report), mode='no_report')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stderr).get('status'), 'failed')

    def test_review_resolves_input_and_output(self):
        result = self.run_wrapper('review.py', 'refs.bib', '--output', 'review.md')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.cwd / 'review.md').read_text(), 'Evidence review')

    def test_citations_resolves_output(self):
        result = self.run_wrapper('citations.py', '10.1/one', '--output', 'cites.json')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.cwd / 'cites.json').is_file())
        self.assertEqual(json.loads((self.cwd / 'cites.json').read_text())['count'], 1)

    def test_utf8_child_output_survives_ascii_parent_environment(self):
        result = self.run_wrapper('search.py', 'query')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['title'], '中文论文')

    def test_invalid_explicit_interpreter_fails_without_fallback(self):
        self.env['PAPER_AGENT_PYTHON'] = str(self.root / 'missing-python')
        result = self.run_wrapper('fetch.py', '10.1/one')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stderr).get('status'), 'failed')

    def test_batch_report_contains_verified_sizes(self):
        result = self.run_wrapper('fetch_batch.py', 'refs.bib', '--report', 'reports/result.json')
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads((self.cwd / 'reports/result.json').read_text())
        self.assertEqual(summary['results'][0]['size_bytes'], (self.cwd / 'pdfs/one.pdf').stat().st_size)

    def test_cache_and_keys_share_utf8_runtime(self):
        for script, command in (('cache.py', 'stats'), ('keys.py', 'list')):
            with self.subTest(script=script):
                result = self.run_wrapper(script, command)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)['title'], '中文论文')

    def test_batch_malformed_summary_fails(self):
        result = self.run_wrapper('fetch_batch.py', 'refs.bib', mode='malformed')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stderr)['status'], 'failed')


if __name__ == '__main__':
    unittest.main()
