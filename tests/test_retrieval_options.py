import os
import importlib.util
import sys
from types import SimpleNamespace
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import MagicMock, patch

from pa_cli import fetch

# Exercise the real handler without requiring the optional MCP transport SDK.
spec = importlib.util.find_spec('pa_cli.mcp_fetch')
mcp_fetch = importlib.util.module_from_spec(spec)
transport_stubs = {name: MagicMock() for name in
                   ('mcp', 'mcp.server', 'mcp.server.stdio', 'mcp.types')}
transport_stubs['mcp.types'].Tool.side_effect = lambda **kwargs: SimpleNamespace(**kwargs)
with patch.dict(sys.modules, transport_stubs):
    spec.loader.exec_module(mcp_fetch)


class RetrievalOptionsTests(unittest.TestCase):
    def test_mcp_schema_matches_supported_sources(self):
        self.assertEqual(mcp_fetch.TOOL_PA_FETCH.inputSchema['properties']['prefer']['enum'],
                         list(fetch.FETCH_PREFERENCES))

    def test_invalid_source_fails_before_cache_or_network(self):
        with patch('pa_cli.cache.cache_get') as cache, patch.object(fetch, 'fetch') as cascade:
            result = fetch.fetch_doi('10.1000/fixture', prefer='unsupported')
        self.assertEqual(result['final_status'], 'ALL_FAIL')
        self.assertEqual(result['error'], 'fetch_invalid_preference')
        cache.assert_not_called()
        cascade.assert_not_called()

    def test_explicit_source_overrides_legacy_channels(self):
        with patch.object(fetch, 'fetch', return_value={'error': 'fixture'}) as cascade, \
             patch('pa_cli.channel_stats.record_event'):
            fetch.fetch_doi('10.1000/fixture', channels=['pmc'], prefer='core', use_cache=False)
        self.assertEqual(cascade.call_args.kwargs['prefer'], 'core')

    def test_proxy_restored_after_outcomes(self):
        for previous in (None, '', 'http://127.0.0.1:9001'):
            for outcome in ('success', 'failure', 'exception'):
                with self.subTest(previous=previous, outcome=outcome), tempfile.TemporaryDirectory() as temp:
                    env = {'HTTP_PROXY': 'http://127.0.0.1:9002'}
                    if previous is not None:
                        env['HTTPS_PROXY'] = previous

                    def cascade(**kwargs):
                        self.assertEqual(os.environ['HTTPS_PROXY'], 'http://127.0.0.1:9003')
                        if outcome == 'exception':
                            raise RuntimeError('fixture failure')
                        if outcome == 'failure':
                            return {'error': 'fixture_failure'}
                        Path(kwargs['out_path']).write_bytes(b'%PDF fixture')
                        return {'path': kwargs['out_path'], 'source': 'fixture'}

                    with patch.dict(os.environ, env, clear=True), \
                         patch.object(fetch, 'fetch', side_effect=cascade), \
                         patch('pa_cli.channel_stats.record_event'), warnings.catch_warnings():
                        warnings.simplefilter('ignore')
                        if outcome == 'exception':
                            with self.assertRaises(RuntimeError):
                                fetch.fetch_doi('10.1000/fixture', temp, proxy='127.0.0.1:9003', use_cache=False)
                        else:
                            fetch.fetch_doi('10.1000/fixture', temp, proxy='127.0.0.1:9003', use_cache=False)
                        self.assertEqual(dict(os.environ), env)

    def test_mcp_preference_reaches_cascade(self):
        for prefer in ('pmc', 'pmc-pdf', 'core', 'unpaywall', 'auto'):
            with self.subTest(prefer=prefer), patch.object(fetch, 'fetch', return_value={'error': 'fixture'}) as cascade, \
                 patch('pa_cli.channel_stats.record_event'):
                mcp_fetch._handle_pa_fetch({'doi': '10.1000/fixture', 'prefer': prefer, 'use_cache': False})
                cascade.assert_called_once()
                self.assertEqual(cascade.call_args.kwargs['prefer'], prefer)

    def test_mcp_does_not_retry_internal_type_error(self):
        with patch.object(fetch, 'fetch_doi', side_effect=TypeError('fixture internal error')) as wrapper:
            with self.assertRaises(TypeError):
                mcp_fetch._handle_pa_fetch({'doi': '10.1000/fixture', 'prefer': 'pmc'})
            wrapper.assert_called_once()

    def test_pmc_pdf_bypasses_europe_and_uses_jats(self):
        for prefer in ('pmc-pdf', 'pmc'):
            with self.subTest(prefer=prefer), tempfile.TemporaryDirectory() as temp:
                path = str(Path(temp) / 'paper.pdf')
                with patch.object(fetch, '_pmc_doi_to_pmcid', return_value='PMC123'), \
                     patch.object(fetch, '_pmc_efetch_xml', return_value={'path': 'fixture.xml', 'size': 12}), \
                     patch.object(fetch, '_pmc_europe_pdf', return_value={'path': path, 'size': 10}) as europe, \
                     patch.object(fetch, '_pmc_jats_to_pdf', return_value={'path': path, 'size': 10}) as jats:
                    result = fetch.fetch(doi='10.1000/fixture', out_path=path, prefer=prefer)
                self.assertNotIn('error', result)
                if prefer == 'pmc-pdf':
                    europe.assert_not_called()
                    jats.assert_called_once()
                    self.assertEqual(result['source'], 'pmc_jats_pdf')
                else:
                    europe.assert_called_once()
                    jats.assert_not_called()


if __name__ == '__main__':
    unittest.main()
