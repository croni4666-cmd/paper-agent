import asyncio
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from pa_cli import cache
from test_pdf_structure import make_pdf


@unittest.skipUnless(os.environ.get('PA_TEST_MCP') == '1', 'opt-in real MCP transport')
class McpStdioTests(unittest.TestCase):
    def test_real_server_initialize_list_call_and_close(self):
        import anyio
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        async def exercise(root, expected):
            params = StdioServerParameters(
                command=sys.executable, args=['-m', 'pa_cli.mcp_fetch'],
                cwd=str(Path(__file__).resolve().parents[1]),
                env={'PA_CACHE_DIR': str(root)},
            )
            with anyio.fail_after(30):
                async with stdio_client(params) as (read, write):
                    async with ClientSession(read, write) as client:
                        initialized = await client.initialize()
                        self.assertEqual(initialized.serverInfo.name, 'paper-agent-fetch')
                        tools = await client.list_tools()
                        self.assertEqual({t.name for t in tools.tools}, {'pa_fetch', 'pa_batch_fetch'})
                        invalid = await client.call_tool('pa_fetch', {'doi': 123})
                        self.assertTrue(invalid.isError)
                        fetched = await client.call_tool('pa_fetch', {'doi': '10.1000/mcp'})
                        self.assertFalse(fetched.isError)
                        result = json.loads(fetched.content[0].text)
                        self.assertTrue(result['cache_hit'])
                        self.assertEqual(result['saved_as'], expected)
                        empty = await client.call_tool('pa_batch_fetch', {'dois': []})
                        self.assertIn('error', json.loads(empty.content[0].text))
                        await client.send_ping()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entry = cache.cache_put('10.1000/mcp', make_pdf(), root=root)
            asyncio.run(exercise(root, entry['pdf_path']))

    def test_batch_dataclass_results_cross_real_transport(self):
        import anyio
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        # Keep the SDK/server/handler real; replace only external batch retrieval.
        bootstrap = """
from pa_cli import fetch_batch
from pa_cli.scaffold import load_bibtex
from pa_cli.mcp_fetch import main

def fixture(bib_path, out_dir, prefer):
    entries = load_bibtex(bib_path)
    results = []
    for entry in entries:
        good = entry['doi'].endswith('/ok')
        results.append(fetch_batch.FetchResult(
            key=entry['key'], doi=entry['doi'], title='', success=good,
            source='fixture' if good else '', out_path=str(out_dir / 'fixture.pdf') if good else '',
            size_bytes=431 if good else 0, error='' if good else 'fixture_unavailable'))
    return fetch_batch.FetchSummary(n_total=len(results),
        n_success=sum(r.success for r in results), n_failure=sum(not r.success for r in results),
        total_elapsed_sec=1.25, results=results)
fetch_batch.run_fetch_batch = fixture
main()
"""
        async def exercise(directory):
            params = StdioServerParameters(command=sys.executable, args=['-c', bootstrap],
                cwd=str(Path(__file__).resolve().parents[1]), env={'PA_CACHE_DIR': directory})
            with anyio.fail_after(30):
                async with stdio_client(params) as (read, write):
                    async with ClientSession(read, write) as client:
                        await client.initialize()
                        for dois, successes in [(['10.1000/ok'], 1),
                                (['10.1000/ok', '10.1000/fail'], 1), (['10.1000/fail'], 0)]:
                            response = await client.call_tool('pa_batch_fetch',
                                {'dois': dois, 'output_dir': directory})
                            data = json.loads(response.content[0].text)
                            self.assertNotIn('error', data)
                            self.assertEqual(data['n_total'], len(dois))
                            self.assertEqual(data['n_success'], successes)
                            self.assertEqual(data['n_failed'], len(dois) - successes)
                            self.assertEqual(data['elapsed_sec'], 1.25)
                            for doi, result in zip(dois, data['results']):
                                self.assertEqual(result['doi'], doi)
                                if doi.endswith('/ok'):
                                    self.assertEqual(result['saved_as'], str(Path(directory) / 'fixture.pdf'))
                                    self.assertEqual(result['via_channel'], 'fixture')
                                    self.assertEqual(result['size_bytes'], 431)
                                else:
                                    self.assertEqual(result['error'], 'fixture_unavailable')
                                    self.assertFalse(result['saved_as'])
                        await client.send_ping()
        with tempfile.TemporaryDirectory() as directory:
            asyncio.run(exercise(directory))
