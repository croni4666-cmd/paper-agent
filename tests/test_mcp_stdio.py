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
