import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from pa_cli import fetch_batch
from pa_cli.fetch_deadline import run_fetch

PDF = b'%PDF-1.7\nfixture complete\n%%EOF'


def inline_worker(request, seconds):
    request = dict(request)
    request.pop('_operation')
    request['out_dir'] = Path(request['out_dir'])
    return fetch_batch._fetch_one_entry_in_process(**request).to_dict()


class BatchDeadlineTests(unittest.TestCase):
    def test_timed_out_worker_preserves_old_pdf_discards_partial_and_skips_rest(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            previous = root / 'first.pdf'
            previous.write_bytes(PDF)
            # Exercise actual worker dispatch with a blocked provider, not a
            # fake timeout response. The partial is written inside the stage.
            script = '''
from pathlib import Path
import time
from pa_cli import fetch
from pa_cli.fetch_worker import main

def slow(**kwargs):
    Path(kwargs['out_path']).write_bytes(b'%PDF-partial')
    time.sleep(30)
    return {'path': kwargs['out_path']}
fetch.fetch = slow
main()
'''
            entries = [{'key': 'first', 'doi': '10.1000/a'}, {'key': 'second', 'doi': '10.1000/b'}]
            def real_worker(request, seconds):
                return run_fetch(request, seconds, _command=[sys.executable, '-c', script])
            with patch.object(fetch_batch, 'load_bibtex', return_value=entries), \
                 patch('pa_cli.fetch_deadline.run_fetch', side_effect=real_worker) as worker:
                summary = fetch_batch.run_fetch_batch(root / 'refs.bib', root, max_total_sec=1)
            self.assertEqual(summary.n_failure, 1)
            self.assertEqual(summary.n_skipped, 1)
            self.assertEqual(summary.results[0].error, 'fetch_timeout')
            self.assertEqual(summary.results[1].error, 'global-timeout')
            worker.assert_called_once()
            self.assertEqual(previous.read_bytes(), PDF)
            self.assertEqual(list(root.iterdir()), [previous])
            self.assertLess(summary.total_elapsed_sec, 5)

    def test_successful_real_worker_publishes_named_pdf(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            script = '''
from pathlib import Path
from pa_cli import fetch
from pa_cli.fetch_worker import main

def download(**kwargs):
    Path(kwargs['out_path']).write_bytes(%r)
    return {'path': kwargs['out_path'], 'source': 'fixture'}
fetch.fetch = download
main()
''' % PDF
            def real_worker(request, seconds):
                return run_fetch(request, seconds, _command=[sys.executable, '-c', script])
            with patch('pa_cli.fetch_deadline.run_fetch', side_effect=real_worker):
                result = fetch_batch._fetch_one_entry({'key': 'paper', 'title': 'Fixture'}, root)
            self.assertTrue(result.success, result)
            self.assertEqual(result.out_path, str(root / 'paper.pdf'))
            self.assertEqual((root / 'paper.pdf').read_bytes(), PDF)
            self.assertEqual(len(list(root.iterdir())), 1)

    def test_invalid_success_output_does_not_replace_old_pdf(self):
        for body in (b'', b'<html>error</html>', b'%PDF-1.7 partial'):
            with self.subTest(body=body), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                target = root / 'paper.pdf'
                target.write_bytes(PDF)
                def worker(request, seconds):
                    (Path(request['out_dir']) / 'paper.pdf').write_bytes(body)
                    return {'success': True, 'source': 'fixture'}
                with patch('pa_cli.fetch_deadline.run_fetch', side_effect=worker):
                    result = fetch_batch._fetch_one_entry({'key': 'paper', 'doi': '10.1000/a'}, root)
                self.assertFalse(result.success)
                self.assertEqual(target.read_bytes(), PDF)
                self.assertEqual(len(list(root.iterdir())), 1)

    def test_skip_requires_pdf_markers_and_does_not_clean_existing_xml(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pdf, xml = root / 'paper.pdf', root / 'paper.xml'
            pdf.write_bytes(PDF)
            xml.write_text('<article/>')
            with patch.object(fetch_batch, 'load_bibtex', return_value=[{'key': 'paper', 'doi': '10.1000/a'}]), \
                 patch('pa_cli.fetch_deadline.run_fetch') as worker:
                summary = fetch_batch.run_fetch_batch(root / 'refs.bib', root, skip_existing=True, clean_xml=True)
                worker.assert_not_called()
            self.assertEqual(summary.n_skipped, 1)
            self.assertTrue(xml.exists())
            pdf.write_bytes(b'%PDF-incomplete')
            with patch('pa_cli.fetch_deadline.run_fetch', return_value={'error': 'fixture'}) as worker:
                result = fetch_batch._fetch_one_entry({'key': 'paper'}, root, skip_existing=True)
                worker.assert_called_once()
            self.assertFalse(result.success)

    def test_unsafe_keys_never_launch_worker(self):
        with tempfile.TemporaryDirectory() as temp:
            for key in ('../escape', 'a/b', 'a\\b', 'C:escape', '', '..', 'NUL', 'COM1', 'trail.'):
                with self.subTest(key=key), patch('pa_cli.fetch_deadline.run_fetch') as worker:
                    result = fetch_batch._fetch_one_entry({'key': key}, Path(temp))
                    self.assertEqual(result.error, 'invalid-citation-key')
                    worker.assert_not_called()

    def test_budget_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            for seconds in (0, -1, True, float('nan'), float('inf'), 10 ** 400):
                with self.subTest(seconds=seconds), self.assertRaises(ValueError):
                    fetch_batch.run_fetch_batch(Path(temp) / 'refs.bib', Path(temp), max_total_sec=seconds)

    def test_remaining_budget_is_shared_and_elapsed_uses_wall_time(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            entries = [{'key': 'a'}, {'key': 'b'}]
            budgets = []
            def worker(entry, out_dir, **kwargs):
                budgets.append(kwargs['max_total_sec'])
                return fetch_batch.FetchResult(entry['key'], '', '', False, error='fixture')
            with patch.object(fetch_batch, 'load_bibtex', return_value=entries), \
                 patch.object(fetch_batch, '_fetch_one_entry', side_effect=worker), \
                 patch.object(fetch_batch.time, 'monotonic', side_effect=[100, 101, 103, 104]):
                summary = fetch_batch.run_fetch_batch(root / 'refs.bib', root, max_total_sec=10)
            self.assertEqual(budgets, [9, 7])
            self.assertEqual(summary.total_elapsed_sec, 4)

    def test_clean_xml_only_removes_intermediate_from_current_attempt(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            xml = root / 'paper.xml'
            xml.write_text('<article>previous</article>')
            def worker(request, seconds):
                (Path(request['out_dir']) / 'paper.pdf').write_bytes(PDF)
                return {'success': True}
            with patch.object(fetch_batch, 'load_bibtex', return_value=[{'key': 'paper'}]), \
                 patch('pa_cli.fetch_deadline.run_fetch', side_effect=worker):
                summary = fetch_batch.run_fetch_batch(root / 'refs.bib', root, clean_xml=True)
            self.assertEqual(summary.n_success, 1)
            self.assertEqual(xml.read_text(), '<article>previous</article>')

    def test_partial_xml_write_failure_does_not_replace_previous_xml(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            xml = root / 'paper.xml'
            original = b'<article><body>Previous full text</body></article>'
            xml.write_bytes(original)
            def interrupted(**kwargs):
                Path(kwargs['out_path']).with_suffix('.xml').write_bytes(b'<article><body>partial')
                raise OSError('fixture interrupted XML write')
            with patch('pa_cli.fetch.fetch', side_effect=interrupted), \
                 patch('pa_cli.fetch_deadline.run_fetch', side_effect=inline_worker):
                result = fetch_batch._fetch_one_entry({'key': 'paper', 'doi': '10.1000/a'}, root)
            self.assertFalse(result.success)
            self.assertEqual(result.error, 'fetch-entry-failed')
            self.assertEqual(result.xml_path, '')
            self.assertEqual(xml.read_bytes(), original)
            self.assertEqual(list(root.iterdir()), [xml])
