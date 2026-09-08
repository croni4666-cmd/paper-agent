import tempfile
import unittest
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from pa_cli import core_channel, fetch, fetch_batch, jats_to_pdf
from pa_cli.cli import main


PDF = b'%PDF-1.7\nsynthetic paper\n%%EOF'
XML = b'<article><body><p>Retained full text.</p></body></article>'
DOI = '10.1000/fixture'


@contextmanager
def pmc_fixture(root, pdf_source=None, fallback=False):
    """Exercise real PMC/cascade/file code with only provider boundaries replaced."""
    calls = []

    def http(url, **kwargs):
        if '/efetch.fcgi?' in url:
            return 200, XML
        if 'europepmc.org/articles/' in url:
            return (200, PDF) if pdf_source == 'europe' else (503, b'')
        raise AssertionError('Unexpected network request')

    def unpaywall(doi, out_path):
        calls.append('unpaywall')
        if fallback:
            return {'source': 'unpaywall', 'path': fetch._save_pdf(PDF, out_path),
                    'size': len(PDF), 'pdf_url': 'https://example.test/paper.pdf'}
        return {'error': 'fixture_unpaywall_failed'}

    def failed_channel(name):
        def fail(*args, **kwargs):
            calls.append(name)
            return {'error': 'fixture_' + name + '_failed'}
        return fail

    with ExitStack() as stack:
        stack.enter_context(patch.object(fetch, '_pmc_doi_to_pmcid', return_value='PMC123'))
        stack.enter_context(patch.object(fetch, 'JATS_CACHE_DIR', root / 'cache'))
        stack.enter_context(patch.object(fetch, '_http_get_bytes', side_effect=http))
        stack.enter_context(patch.object(fetch.time, 'sleep'))
        stack.enter_context(patch.object(fetch, 'fetch_annas_search', return_value=[]))
        stack.enter_context(patch.object(fetch, 'fetch_unpaywall_doi', side_effect=unpaywall))
        stack.enter_context(patch.object(core_channel, 'fetch_core_doi', side_effect=failed_channel('core')))
        stack.enter_context(patch.object(fetch, 'fetch_scihub_doi', side_effect=failed_channel('scihub')))
        stack.enter_context(patch('pa_cli.channel_stats.record_event'))
        renderer = stack.enter_context(patch.object(jats_to_pdf, 'jats_xml_to_pdf'))
        if pdf_source == 'jats':
            renderer.return_value = PDF
        else:
            renderer.side_effect = RuntimeError('fixture browser unavailable')
        yield calls


class PmcPdfOutcomes(unittest.TestCase):
    def invoke_cli(self, *args, **kwargs):
        # Unit-test provider fixtures stay in this process. Public worker/CLI
        # integration is exercised in test_fetch_deadline.py.
        with patch.object(fetch, 'fetch_doi', fetch._fetch_doi_in_process):
            return CliRunner().invoke(*args, **kwargs)

    def test_both_pdf_paths_expose_canonical_result(self):
        for source in ('europe', 'jats'):
            with self.subTest(source=source), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                with pmc_fixture(root, pdf_source=source):
                    result = fetch.fetch_pmc_doi(DOI, str(root / 'paper.pdf'))
                self.assertNotIn('error', result)
                self.assertEqual(result['path'], result['pdf_path'])
                self.assertEqual(result['size'], result['pdf_size'])
                self.assertEqual(Path(result['path']).read_bytes(), PDF)
                self.assertEqual(Path(result['xml_path']).read_bytes(), XML)
                if source == 'europe':
                    self.assertIn('europepmc.org', result['pdf_url'])

    def test_xml_only_is_failure_with_retained_artifact(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with pmc_fixture(root):
                result = fetch.fetch_pmc_doi(DOI, str(root / 'paper.pdf'))
            self.assertEqual(result.get('error'), 'pmc_pdf_unavailable')
            self.assertEqual(result['source'], 'pmc_xml_only')
            self.assertFalse(result.get('path'))
            self.assertEqual(Path(result['xml_path']).read_bytes(), XML)
            self.assertFalse((root / 'paper.pdf').exists())

    def test_auto_continues_after_xml_and_retains_it_if_all_fail(self):
        for fallback in (False, True):
            with self.subTest(fallback=fallback), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                with pmc_fixture(root, fallback=fallback) as calls:
                    result = fetch.fetch(doi=DOI, out_path=str(root / 'paper.pdf'))
                if fallback:
                    self.assertEqual(calls, ['unpaywall'])
                    self.assertEqual(result['source'], 'unpaywall')
                    self.assertEqual(Path(result['path']).read_bytes(), PDF)
                else:
                    self.assertEqual(calls, ['unpaywall', 'core', 'scihub'])
                    self.assertIn('error', result)
                    self.assertEqual(Path(result['xml_path']).read_bytes(), XML)

    def test_explicit_pmc_failure_does_not_switch_sources(self):
        for prefer in ('pmc', 'pmc-pdf'):
            with self.subTest(prefer=prefer), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                with pmc_fixture(root, fallback=True) as calls:
                    result = fetch.fetch(doi=DOI, out_path=str(root / 'paper.pdf'), prefer=prefer)
                self.assertEqual(calls, [])
                self.assertEqual(result.get('error'), 'pmc_pdf_unavailable')
                self.assertEqual(Path(result['xml_path']).read_bytes(), XML)

    def test_wrapper_retains_xml_and_does_not_claim_stale_pdf(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            stale = root / '10_1000_fixture.pdf'
            stale.write_bytes(PDF)
            with pmc_fixture(root):
                result = fetch._fetch_doi_in_process(DOI, output_dir=temp, channels=['pmc'], use_cache=False)
            self.assertEqual(result['final_status'], 'ALL_FAIL')
            self.assertIsNone(result['saved_as'])
            self.assertEqual(Path(result['xml_path']).read_bytes(), XML)
            self.assertEqual(stale.read_bytes(), PDF)

    def test_batch_does_not_delete_only_fulltext(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with pmc_fixture(root), patch.object(fetch_batch, 'load_bibtex',
                    return_value=[{'key': 'fixture', 'doi': DOI}]):
                summary = fetch_batch.run_fetch_batch(root / 'refs.bib', root, prefer='pmc', clean_xml=True)
            self.assertEqual(summary.n_success, 0)
            self.assertEqual(summary.n_failure, 1)
            self.assertEqual((root / 'fixture.xml').read_bytes(), XML)

    def test_cli_reports_failure_for_xml_only(self):
        with tempfile.TemporaryDirectory() as temp:
            with pmc_fixture(Path(temp)):
                result = self.invoke_cli(main, ['fetch', DOI, '--output-dir', temp,
                                                  '--prefer', 'pmc', '--no-cache', '--quiet'])
            self.assertEqual(result.exit_code, 2, result.output)
            self.assertIn('"saved_as": null', result.output)

    def test_default_cli_continues_to_fallback_pdf(self):
        with tempfile.TemporaryDirectory() as temp:
            with pmc_fixture(Path(temp), fallback=True) as calls:
                result = self.invoke_cli(main, ['fetch', DOI, '--output-dir', temp,
                                                  '--no-cache', '--quiet'])
            self.assertEqual(calls, ['unpaywall'])
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn('"via_channel": "unpaywall"', result.output)

    def test_wrapper_success_includes_real_pdf_details(self):
        with tempfile.TemporaryDirectory() as temp:
            with pmc_fixture(Path(temp), pdf_source='europe'):
                result = fetch._fetch_doi_in_process(DOI, output_dir=temp, channels=['pmc'], use_cache=False)
            self.assertEqual(result['final_status'], 'SUCCESS')
            self.assertEqual(Path(result['saved_as']).read_bytes(), PDF)
            self.assertEqual(result['size_bytes'], len(PDF))
            self.assertIn('europepmc.org', result['via_url'])

    def test_wrapper_rejects_missing_or_invalid_pdf(self):
        for body in (None, b'<html>not a paper</html>', b''):
            with self.subTest(body=body), tempfile.TemporaryDirectory() as temp:
                out = Path(temp) / 'paper.pdf'
                if body is not None:
                    out.write_bytes(body)
                with patch.object(fetch, 'fetch', return_value={'source': 'fixture', 'path': str(out)}), \
                     patch('pa_cli.channel_stats.record_event') as record:
                    result = fetch._fetch_doi_in_process(DOI, output_dir=temp, use_cache=False)
                self.assertEqual(result['final_status'], 'ALL_FAIL')
                self.assertIsNone(result['saved_as'])
                self.assertFalse(record.call_args.args[2])

    def test_wrapper_does_not_guess_path_for_incomplete_result(self):
        with tempfile.TemporaryDirectory() as temp:
            (Path(temp) / '10_1000_fixture.pdf').write_bytes(PDF)
            with patch.object(fetch, 'fetch', return_value={'source': 'fixture'}), \
                 patch('pa_cli.channel_stats.record_event') as record:
                result = fetch._fetch_doi_in_process(DOI, output_dir=temp, use_cache=False)
            self.assertEqual(result['final_status'], 'ALL_FAIL')
            self.assertIsNone(result['saved_as'])
            self.assertFalse(record.call_args.args[2])

    def test_cache_hit_still_avoids_cascade(self):
        hit = {'pdf_path': 'fixture-cache.pdf', 'channel': 'pmc', 'sha256': 'fixture-hash'}
        with patch('pa_cli.cache.cache_get', return_value=hit), \
             patch.object(fetch, 'fetch') as cascade:
            result = fetch._fetch_doi_in_process(DOI)
        self.assertEqual(result['final_status'], 'SUCCESS_CACHE_HIT')
        self.assertEqual(result['saved_as'], hit['pdf_path'])
        cascade.assert_not_called()


if __name__ == '__main__':
    unittest.main()
