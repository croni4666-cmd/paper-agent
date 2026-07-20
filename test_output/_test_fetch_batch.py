"""Unit + e2e tests for pa_cli.fetch_batch ([P2-11]).

All tests mock pa_cli.fetch.fetch to avoid real network calls.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, '.')

from pa_cli.fetch_batch import (
    FetchResult, FetchSummary,
    _fetch_one_entry, run_fetch_batch,
    write_failure_report, write_summary_json,
)


SAMPLE_BIB = """@article{key1, title = {Paper One}, doi = {10.1234/test.001}, year = {2023}}
@article{key2, title = {Paper Two}, doi = {10.1234/test.002}, year = {2024}}
@article{key3, title = {No DOI Paper}, year = {2020}}
@article{key4, title = {Paper Four}, doi = {10.1234/test.004}, year = {2024}}
"""


def _fake_success(doi, **kwargs):
    return {'source': 'unpaywall', 'path': kwargs.get('out_path', '/tmp/x.pdf'),
            'size': 1024 * 50, 'pdf_url': f'https://example.com/{doi}'}


def _fake_fail(doi, **kwargs):
    return {'error': 'no PDF found'}


def _fake_exception(doi, **kwargs):
    raise RuntimeError("network timeout")


class TestFetchResult(unittest.TestCase):
    def test_to_dict_minimal(self):
        r = FetchResult(key='k1', doi='10.1', title='T', success=False, error='x')
        d = r.to_dict()
        self.assertEqual(d['key'], 'k1')
        self.assertFalse(d['success'])
        self.assertEqual(d['error'], 'x')

    def test_to_dict_truncates_long_title(self):
        long_title = 'x' * 200
        r = FetchResult(key='k1', doi='', title=long_title, success=True)
        d = r.to_dict()
        self.assertEqual(len(d['title']), 100)


class TestFetchOneEntry(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.entry = {'key': 'k1', 'doi': '10.1234/test', 'title': 'Test Paper'}

    @patch('pa_cli.fetch.fetch')
    def test_success_doi(self, mock_fetch):
        mock_fetch.return_value = _fake_success('10.1234/test')
        r = _fetch_one_entry(self.entry, self.tmpdir)
        self.assertTrue(r.success)
        self.assertEqual(r.source, 'unpaywall')
        mock_fetch.assert_called_once()
        # Should be called with doi, not title
        call_kwargs = mock_fetch.call_args.kwargs
        self.assertEqual(call_kwargs.get('doi'), '10.1234/test')

    @patch('pa_cli.fetch.fetch')
    def test_failure_returns_error(self, mock_fetch):
        mock_fetch.return_value = _fake_fail('10.1234/test')
        r = _fetch_one_entry(self.entry, self.tmpdir)
        self.assertFalse(r.success)
        self.assertEqual(r.error, 'no PDF found')

    @patch('pa_cli.fetch.fetch')
    def test_exception_caught(self, mock_fetch):
        mock_fetch.side_effect = _fake_exception
        r = _fetch_one_entry(self.entry, self.tmpdir)
        self.assertFalse(r.success)
        self.assertIn('exception', r.error)
        self.assertIn('network timeout', r.error)

    @patch('pa_cli.fetch.fetch')
    def test_no_doi_no_title_marks_error(self, mock_fetch):
        entry = {'key': 'k2', 'doi': '', 'title': ''}
        r = _fetch_one_entry(entry, self.tmpdir)
        self.assertFalse(r.success)
        self.assertEqual(r.error, 'no doi or title')
        mock_fetch.assert_not_called()

    @patch('pa_cli.fetch.fetch')
    def test_doi_fails_title_succeeds(self, mock_fetch):
        # First call (DOI) fails; second call (title) succeeds
        mock_fetch.side_effect = [
            _fake_fail('10.1234/test'),
            _fake_success('10.1234/test'),
        ]
        r = _fetch_one_entry(self.entry, self.tmpdir)
        self.assertTrue(r.success)
        self.assertEqual(mock_fetch.call_count, 2)


class TestSkipExisting(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.entry = {'key': 'k1', 'doi': '10.1234/test', 'title': 'Test'}

    def test_skip_existing_no_fetch_called(self):
        # Pre-create the PDF
        existing = self.tmpdir / 'k1.pdf'
        existing.write_bytes(b'%PDF-1.4 fake content')
        with patch('pa_cli.fetch.fetch') as mock_fetch:
            r = _fetch_one_entry(self.entry, self.tmpdir, skip_existing=True)
        self.assertTrue(r.success)
        self.assertEqual(r.error, 'skipped-existing')
        mock_fetch.assert_not_called()

    def test_no_skip_calls_fetch(self):
        with patch('pa_cli.fetch.fetch') as mock_fetch:
            mock_fetch.return_value = _fake_success('10.1234/test')
            r = _fetch_one_entry(self.entry, self.tmpdir, skip_existing=False)
        self.assertTrue(r.success)
        self.assertNotEqual(r.error, 'skipped-existing')


class TestRunFetchBatch(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.bib = self.tmpdir / 'refs.bib'
        self.bib.write_text(SAMPLE_BIB, encoding='utf-8')
        self.out_dir = self.tmpdir / 'pdfs'

    @patch('pa_cli.fetch.fetch')
    def test_batch_runs_all_entries(self, mock_fetch):
        mock_fetch.return_value = _fake_success('any')
        summary = run_fetch_batch(self.bib, self.out_dir, max_total_sec=60)
        self.assertEqual(summary.n_total, 4)
        # Should call fetch for key1, key2, key4 (have DOI). key3 has no DOI but has title.
        # So 4 calls expected (3 DOI + 1 title fallback? actually 3 DOI + 1 title)
        # Let's see: key1 doi success, key2 doi success, key3 no-doi-title, key4 doi success
        # All succeed via the mock, so 4 results
        self.assertEqual(len(summary.results), 4)
        self.assertEqual(summary.n_success, 4)
        self.assertEqual(summary.n_failure, 0)

    @patch('pa_cli.fetch.fetch')
    def test_batch_records_mixed_results(self, mock_fetch):
        # Mix: key1 success, key2 fail, key3 success (title), key4 fail
        def fake_fetch(doi=None, title=None, **kwargs):
            if doi == '10.1234/test.001':
                return _fake_success(doi)
            if doi == '10.1234/test.002':
                return _fake_fail(doi)
            if title == 'No DOI Paper':
                return _fake_success('title-fallback')
            if doi == '10.1234/test.004':
                return _fake_fail(doi)
            return _fake_fail(doi or title or 'unknown')
        mock_fetch.side_effect = fake_fetch
        summary = run_fetch_batch(self.bib, self.out_dir, max_total_sec=60)
        self.assertEqual(summary.n_total, 4)
        self.assertEqual(summary.n_success, 2)
        self.assertEqual(summary.n_failure, 2)

    @patch('pa_cli.fetch.fetch')
    def test_batch_global_timeout_marks_remaining_as_skipped(self, mock_fetch):
        # Force each fetch to take 0.05 sec; max_total=0.1 sec
        import time as time_mod
        def slow_fetch(*args, **kwargs):
            time_mod.sleep(0.05)
            return _fake_success(kwargs.get('doi', 'x'))
        mock_fetch.side_effect = slow_fetch
        summary = run_fetch_batch(self.bib, self.out_dir, max_total_sec=0.1)
        self.assertEqual(summary.n_total, 4)
        # Some should be skipped due to timeout
        self.assertGreater(summary.n_skipped, 0)
        # All results should be either success or skipped (with error='global-timeout')
        for r in summary.results:
            if not r.success:
                self.assertIn(r.error, ['global-timeout', 'no doi or title', 'no PDF found'])

    @patch('pa_cli.fetch.fetch')
    def test_batch_progress_callback(self, mock_fetch):
        mock_fetch.return_value = _fake_success('any')
        progress_calls = []
        def cb(i, n, r):
            progress_calls.append((i, n, r.key))
        summary = run_fetch_batch(
            self.bib, self.out_dir, max_total_sec=60, progress_callback=cb
        )
        self.assertEqual(len(progress_calls), 4)
        # Each call should have correct (i, n, key)
        for i, (idx, n, key) in enumerate(progress_calls, start=1):
            self.assertEqual(idx, i)
            self.assertEqual(n, 4)


class TestWriteFailureReport(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.summary = FetchSummary(n_total=3, n_success=1, n_failure=2)
        self.summary.results = [
            FetchResult(key='k1', doi='10.1/a', title='A', success=True, source='unpaywall', size_bytes=1024),
            FetchResult(key='k2', doi='10.1/b', title='B', success=False, error='no PDF found', elapsed_sec=0.5),
            FetchResult(key='k3', doi='10.1/c', title='C', success=False, error='cloudflare block', elapsed_sec=1.2),
        ]

    def test_writes_markdown_with_failures_section(self):
        report_path = self.tmpdir / 'failed.md'
        n = write_failure_report(self.summary, report_path, Path('/tmp/refs.bib'), Path('/tmp/pdfs'))
        self.assertEqual(n, 2)
        content = report_path.read_text(encoding='utf-8')
        self.assertIn('Fetch-batch failure report', content)
        self.assertIn('Failures (2)', content)
        self.assertIn('`k2`', content)
        self.assertIn('`k3`', content)
        self.assertIn('no PDF found', content)
        self.assertIn('cloudflare block', content)

    def test_writes_all_succeeded_message(self):
        self.summary.n_failure = 0
        self.summary.results = [
            FetchResult(key='k1', doi='10.1', title='A', success=True),
        ]
        report_path = self.tmpdir / 'ok.md'
        write_failure_report(self.summary, report_path, Path('/x.bib'), Path('/x'))
        content = report_path.read_text(encoding='utf-8')
        self.assertIn('All downloads succeeded!', content)


class TestWriteSummaryJson(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.summary = FetchSummary(n_total=2, n_success=2, n_failure=0)
        self.summary.results = [
            FetchResult(key='k1', doi='10.1', title='A', success=True, source='unpaywall', size_bytes=1024),
            FetchResult(key='k2', doi='10.2', title='B', success=True, source='arxiv', size_bytes=2048),
        ]

    def test_json_written(self):
        path = self.tmpdir / 'summary.json'
        write_summary_json(self.summary, path, Path('/x.bib'), Path('/x'), max_total_sec=600)
        data = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(data['n_total'], 2)
        self.assertEqual(data['n_success'], 2)
        self.assertIn('results', data)
        self.assertEqual(len(data['results']), 2)
        self.assertEqual(data['results'][0]['key'], 'k1')
        self.assertEqual(data['results'][0]['source'], 'unpaywall')


class TestE2EWithMock(unittest.TestCase):
    """End-to-end: bib → batch → all mocked to succeed."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.bib = self.tmpdir / 'refs.bib'
        self.bib.write_text(SAMPLE_BIB, encoding='utf-8')
        self.out_dir = self.tmpdir / 'pdfs'
        self.report = self.tmpdir / 'failed.md'
        self.summary_json = self.tmpdir / 'summary.json'

    @patch('pa_cli.fetch.fetch')
    def test_e2e_all_succeed(self, mock_fetch):
        mock_fetch.return_value = _fake_success('any')
        summary = run_fetch_batch(self.bib, self.out_dir, max_total_sec=60)
        write_failure_report(summary, self.report, self.bib, self.out_dir)
        write_summary_json(summary, self.summary_json, self.bib, self.out_dir, 60)
        # All reports should exist
        self.assertTrue(self.report.exists())
        self.assertTrue(self.summary_json.exists())
        # Report should have "All downloads succeeded"
        self.assertIn('All downloads succeeded', self.report.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
