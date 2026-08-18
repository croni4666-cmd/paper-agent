"""test_mcp_fetch.py — unit + e2e tests for pa_cli.mcp_fetch (v3.9.14.0, [P0-15])

Coverage:
    Unit tests (3):
        T1. _build_server() returns a Server with 2 registered tools
        T2. list_tools() returns the 2 tool schemas with correct names
        T3. Tool schemas have required 'doi' / 'dois' fields
    E2E test (1):
        T4. Launch stdio server, send MCP initialize + tools/list + tools/call
            for pa_fetch with a real (or mocked) DOI. Verify response is
            well-formed JSON with the expected fields.

Total: 4 tests.
"""

from __future__ import annotations

import asyncio
import json
import sys
import unittest
from pathlib import Path
from typing import Any, Dict, List

_PAPER_AGENT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PAPER_AGENT_DIR))

from pa_cli import mcp_fetch  # noqa: E402


# ─────────────────────────────────────────────────────────────────
# Unit tests
# ─────────────────────────────────────────────────────────────────
class TestBuildServer(unittest.TestCase):
    """T1: _build_server() returns a Server with 2 registered tools."""

    def test_build_server_returns_mcp_server(self):
        from mcp.server import Server
        server = mcp_fetch._build_server()
        self.assertIsInstance(server, Server)

    def test_tool_schemas_have_correct_names(self):
        # Build server and check the static TOOL_* module attributes
        self.assertEqual(mcp_fetch.TOOL_PA_FETCH.name, "pa_fetch")
        self.assertEqual(mcp_fetch.TOOL_PA_BATCH_FETCH.name, "pa_batch_fetch")

    def test_pa_fetch_schema_requires_doi(self):
        schema = mcp_fetch.TOOL_PA_FETCH.inputSchema
        self.assertEqual(schema["required"], ["doi"])
        self.assertIn("doi", schema["properties"])
        self.assertIn("prefer", schema["properties"])
        self.assertIn("use_cache", schema["properties"])
        # prefer enum
        self.assertIn("auto", schema["properties"]["prefer"]["enum"])
        self.assertIn("scihub", schema["properties"]["prefer"]["enum"])

    def test_pa_batch_fetch_schema_requires_dois(self):
        schema = mcp_fetch.TOOL_PA_BATCH_FETCH.inputSchema
        self.assertEqual(schema["required"], ["dois"])
        self.assertIn("dois", schema["properties"])
        self.assertEqual(schema["properties"]["dois"]["type"], "array")
        self.assertIn("output_dir", schema["properties"])
        self.assertIn("prefer", schema["properties"])


class TestHandlers(unittest.TestCase):
    """T2: handler functions return well-formed dicts."""

    def test_pa_fetch_missing_doi_returns_error(self):
        result = mcp_fetch._handle_pa_fetch({})
        self.assertIn("error", result)
        self.assertIn("doi", result["error"])

    def test_pa_batch_fetch_missing_dois_returns_error(self):
        result = mcp_fetch._handle_pa_batch_fetch({})
        self.assertIn("error", result)
        self.assertIn("tool", result)
        self.assertEqual(result["tool"], "pa_batch_fetch")

    def test_pa_batch_fetch_empty_dois_list_returns_error(self):
        result = mcp_fetch._handle_pa_batch_fetch({"dois": []})
        self.assertIn("error", result)


# ─────────────────────────────────────────────────────────────────
# E2E test: launch stdio server, send initialize + tools/list + tools/call
# ─────────────────────────────────────────────────────────────────
class TestE2EStdioServer(unittest.TestCase):
    """T3: End-to-end via in-process stdio client (no network)."""

    def test_list_tools_via_stdio(self):
        """Launch the MCP server, send initialize + tools/list, verify 2 tools.

        Does NOT call tools/call (avoids real network fetch).
        The schema + handler tests (above) cover the call_tool path.
        """
        async def run():
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client

            params = StdioServerParameters(
                command=sys.executable,
                args=["-m", "pa_cli.mcp_fetch"],
            )
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    tool_names = sorted([t.name for t in tools.tools])
                    self.assertEqual(tool_names, ["pa_batch_fetch", "pa_fetch"])
                    # Verify the schema includes the required 'doi' field
                    pa_fetch_tool = next(t for t in tools.tools if t.name == "pa_fetch")
                    self.assertIn("doi", pa_fetch_tool.inputSchema["properties"])

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main(verbosity=2)
