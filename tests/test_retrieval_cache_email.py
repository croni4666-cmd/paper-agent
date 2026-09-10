import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from click.testing import CliRunner
from pa_cli import cache, fetch
from pa_cli.cli import main

from test_pdf_structure import make_pdf
PDF = make_pdf()
DOI = '10.1000/cache-fixture'


class RetrievalCacheEmailTests(unittest.TestCase):
    def invoke_cli(self, *args, **kwargs):
        # Unit-test provider fixtures stay in this process. Public worker/CLI
        # integration is exercised in test_fetch_deadline.py.
        with patch.object(fetch, 'fetch_doi', fetch._fetch_doi_in_process):
            return CliRunner().invoke(*args, **kwargs)

    def test_cache_accepts_small_header_checked_pdf_and_rejects_other_content(self):
        entry = cache.cache_put(DOI, PDF)
        self.assertEqual(Path(entry['pdf_path']).read_bytes(), PDF)
        for body in (b'', b'%PDF', b'<html>error</html>'):
            with self.subTest(body=body), self.assertRaises(ValueError):
                cache.cache_put('10.1000/invalid', body)

    def test_success_populates_cache_and_second_call_skips_network(self):
        with tempfile.TemporaryDirectory() as temp:
            def download(**kwargs):
                Path(kwargs['out_path']).write_bytes(PDF)
                return {'source': 'fixture', 'path': kwargs['out_path'], 'pdf_url': 'https://example.test/p.pdf'}
            with patch.object(fetch, 'fetch', side_effect=download) as network, \
                 patch('pa_cli.channel_stats.record_event'):
                first = fetch._fetch_doi_in_process(DOI, temp, use_cache=False)
                second = fetch._fetch_doi_in_process(DOI, temp)
            self.assertEqual(first['final_status'], 'SUCCESS')
            self.assertTrue(first['cache_written'])
            self.assertEqual(second['final_status'], 'SUCCESS_CACHE_HIT')
            self.assertEqual(Path(second['saved_as']).read_bytes(), PDF)
            network.assert_called_once()

    def test_cache_failure_does_not_lose_download(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'paper.pdf'
            path.write_bytes(PDF)
            blocked_cache = Path(temp) / 'synthetic-private-detail'
            blocked_cache.write_text('cache root is a file')
            with patch.object(fetch, 'fetch', return_value={'path': str(path), 'source': 'fixture'}), \
                 patch.dict(os.environ, {'PA_CACHE_DIR': str(blocked_cache)}), \
                 patch('pa_cli.channel_stats.record_event'):
                result = fetch._fetch_doi_in_process(DOI, temp, use_cache=False)
            self.assertEqual(result['final_status'], 'SUCCESS')
            self.assertFalse(result['cache_written'])
            self.assertEqual(Path(result['saved_as']).read_bytes(), PDF)
            self.assertNotIn('synthetic-private-detail', json.dumps(result))

    def test_invalid_download_never_reaches_cache(self):
        with patch.object(fetch, 'fetch', return_value={'error': 'fixture'}), \
             patch.object(cache, 'cache_put') as put, patch('pa_cli.channel_stats.record_event'):
            fetch._fetch_doi_in_process(DOI, use_cache=False)
        put.assert_not_called()

    def test_email_option_reaches_api_and_does_not_change_environment(self):
        for explicit in (False, True):
            with self.subTest(explicit=explicit), tempfile.TemporaryDirectory() as temp:
                urls = []
                def http(url, **kwargs):
                    urls.append(url)
                    return 404, b''
                with patch.dict(os.environ, {'UNPAYWALL_EMAIL': 'env@example.test'}), \
                     patch.object(fetch.time, 'sleep'), patch.object(fetch, '_http_get_bytes', side_effect=http), \
                     patch('pa_cli.channel_stats.record_event'):
                    args = ['fetch', DOI, '--output-dir', temp, '--prefer', 'unpaywall', '--no-cache', '--quiet']
                    if explicit:
                        args += ['--unpaywall-email', 'option@example.test']
                    result = self.invoke_cli(main, args)
                    self.assertEqual(result.exit_code, 2, result.output)
                    email = parse_qs(urlparse(urls[0]).query)['email'][0]
                    self.assertEqual(email, 'option@example.test' if explicit else 'env@example.test')
                    self.assertEqual(os.environ['UNPAYWALL_EMAIL'], 'env@example.test')

    def test_email_override_cleared_after_exception(self):
        with patch.dict(os.environ, {'UNPAYWALL_EMAIL': 'env@example.test'}), \
             patch.object(fetch, 'fetch', side_effect=RuntimeError('fixture')):
            with self.assertRaises(RuntimeError):
                fetch._fetch_doi_in_process(DOI, unpaywall_email='option@example.test', use_cache=False)
        urls = []
        with patch.dict(os.environ, {'UNPAYWALL_EMAIL': 'env@example.test'}), \
             patch.object(fetch.time, 'sleep'), \
             patch.object(fetch, '_http_get_bytes', side_effect=lambda url, **kw: (urls.append(url) or (404, b''))):
            fetch.fetch_unpaywall_doi(DOI)
        self.assertEqual(parse_qs(urlparse(urls[0]).query)['email'], ['env@example.test'])

    def test_unpaywall_diagnostics_do_not_echo_email_or_response(self):
        for status, body in ((422, b''), (500, b'private response detail'), (200, b'invalid JSON')):
            with self.subTest(status=status), patch.dict(os.environ, {'UNPAYWALL_EMAIL': 'private@example.test'}), \
                 patch.object(fetch.time, 'sleep'), patch.object(fetch, '_http_get_bytes', return_value=(status, body)):
                result = fetch.fetch_unpaywall_doi(DOI)
                self.assertNotIn('private@example.test', json.dumps(result))
                self.assertNotIn('private response detail', json.dumps(result))
