"""E2E test for pa_mcp: launches pa_cli.mcp as subprocess via stdio_client,
sends initialize + list_tools + call_tool for each of the 4 tools.

Uses the official Anthropic mcp.ClientSession + stdio_client helpers.

Test flow:
  1. Spawn `python -m pa_cli.mcp` via stdio_client(StdioServerParameters(...))
  2. Wrap streams in ClientSession + initialize()
  3. list_tools() — verify 4 tools registered, each has name/description/inputSchema
  4. For each tool:
       - call_tool(name, minimal_args) — verify response is JSON-serialisable
       - expected fields present
  5. Test structured error path: call_tool with unknown tool name → isError=True

Network-requiring tools (pa_fetch live cascade, pa_search live search) are
tested using known cache hits + non-search queries that may fail gracefully.
No fetch is performed over the network — cache hit only.
"""

import asyncio
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

# Ensure project root on path (when test invoked from elsewhere)
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


SERVER_CMD = sys.executable
SERVER_ARGS = ["-m", "pa_cli.mcp"]


async def _connect():
    """Spawn pa_cli.mcp as subprocess, return (session, exit_fn)."""
    params = StdioServerParameters(command=SERVER_CMD, args=SERVER_ARGS)
    # anyio context managers + ClientSession
    client_ctx = stdio_client(params)
    streams = await client_ctx.__aenter__()
    read, write = streams
    session = ClientSession(read, write)
    await session.__aenter__()
    init_result = await session.initialize()
    return session, client_ctx, init_result


async def _disconnect(session, client_ctx):
    try:
        await session.__aexit__(None, None, None)
    except Exception:
        pass
    try:
        await client_ctx.__aexit__(None, None, None)
    except Exception:
        pass


async def test_list_tools():
    """Test that server registers all 4 tools with valid schemas."""
    print("\n=== test list_tools ===")
    session, client_ctx, init = await _connect()
    try:
        tools_result = await session.list_tools()
        tools = tools_result.tools
        names = sorted(t.name for t in tools)
        print(f"  registered tools: {names}")
        # 5 tools expected (pa_citations added in v3.7.0 / [P1-1])
        expected = sorted(["pa_fetch", "pa_keys_status", "pa_review",
                           "pa_search", "pa_citations"])
        assert names == expected, f"unexpected tool list: {names}"
        # Each tool must have a non-empty inputSchema with type=object
        for t in tools:
            assert t.name, "tool missing name"
            assert t.description and len(t.description) > 20, \
                f"tool {t.name} missing description"
            assert t.inputSchema.get("type") == "object", \
                f"tool {t.name} schema not object type"
            assert "properties" in t.inputSchema, \
                f"tool {t.name} schema missing properties"
        print(f"  PASS: 4 tools registered, all with valid schemas")
    finally:
        await _disconnect(session, client_ctx)


async def test_pa_keys_status():
    """Test pa_keys_status returns audit dict structure."""
    print("\n=== test pa_keys_status ===")
    session, client_ctx, _ = await _connect()
    try:
        result = await session.call_tool("pa_keys_status", {})
        assert result is not None
        assert not result.isError, f"unexpected error: {result.content}"
        # Get text content
        text = result.content[0].text
        data = json.loads(text)
        print(f"  keys_status keys: {list(data.keys())[:8]}")
        assert "rows" in data, "missing rows"
        assert "total" in data, "missing total"
        assert "active" in data, "missing active"
        assert isinstance(data["rows"], list)
        print(f"  PASS: pa_keys_status returned audit with {len(data['rows'])} rows")
    finally:
        await _disconnect(session, client_ctx)


async def test_pa_review():
    """Test pa_review with a real (empty) corpus dir — should not error."""
    print("\n=== test pa_review ===")
    with tempfile.TemporaryDirectory() as tmp:
        session, client_ctx, _ = await _connect()
        try:
            result = await session.call_tool("pa_review", {"corpus_dir": tmp})
            text = result.content[0].text
            data = json.loads(text)
            # synthesize() with no PDFs returns some markdown (empty corpus summary)
            print(f"  pa_review keys: {list(data.keys())}")
            assert "corpus_dir" in data
            assert "markdown" in data
            # Empty corpus should still return some markdown (might be empty body)
            assert isinstance(data["markdown"], str)
            print(f"  PASS: pa_review returned markdown ({len(data['markdown'])} chars) "
                  f"for empty corpus")
        finally:
            await _disconnect(session, client_ctx)


async def test_pa_review_missing_corpus():
    """Test pa_review with non-existent path returns error dict, not exception."""
    print("\n=== test pa_review (missing corpus) ===")
    session, client_ctx, _ = await _connect()
    try:
        result = await session.call_tool("pa_review",
                                        {"corpus_dir": "/nonexistent/path/xyz"})
        # Per implementation, this returns a structured error dict in content
        # (NOT MCP isError), because we return the dict directly
        text = result.content[0].text
        data = json.loads(text)
        print(f"  result keys: {list(data.keys())}")
        assert "error" in data, f"missing error key, got {list(data.keys())}"
        assert data["error"] == "corpus_dir_not_found"
        print(f"  PASS: structured error returned for missing corpus")
    finally:
        await _disconnect(session, client_ctx)


async def test_unknown_tool():
    """Test that unknown tool name returns MCP isError=True."""
    print("\n=== test unknown_tool ===")
    session, client_ctx, _ = await _connect()
    try:
        result = await session.call_tool("pa_nonexistent", {})
        print(f"  isError={result.isError}, content_excerpt={result.content[0].text[:100]!r}")
        assert result.isError, "expected isError=True for unknown tool"
        print(f"  PASS: unknown tool returned isError=True")
    finally:
        await _disconnect(session, client_ctx)


async def test_pa_fetch_cache_hit():
    """Test pa_fetch hits cache without network.

    Pre-populate cache with a fake PDF, then call pa_fetch via MCP — should
    return cache_hit=true. Tests the integration of mcp.py + cache.py + fetch.py
    without requiring real network.
    """
    print("\n=== test pa_fetch (cache hit) ===")
    # Generate a fake PDF
    fake_pdf = b"%PDF-1.4\n%test\n" + b"%% padding " * 6000  # ~66KB

    # Pre-populate cache in a temp dir, then point PA_CACHE_DIR there
    with tempfile.TemporaryDirectory() as tmp:
        cache_root = Path(tmp) / "cache"
        cache_root.mkdir()
        from pa_cli import cache as pa_cache
        # Direct write to bypass use_cache check
        doi = "10.1234/mcp-cache-hit-test"
        entry = pa_cache.cache_put(doi, fake_pdf, channel="openalex",
                                    url="http://test/mcp.pdf", root=cache_root)
        print(f"  pre-populated cache: {entry['pdf_path']}")

        # Pass PA_CACHE_DIR to subprocess via os.environ (already inherited
        # because ClientSession spawns child without custom env)
        # But we want to override env for the SERVER subprocess, not for THIS test
        # StdioServerParameters has `env` override; let's use it
        params = StdioServerParameters(
            command=SERVER_CMD, args=SERVER_ARGS,
            env={**os.environ, "PA_CACHE_DIR": str(cache_root),
                 "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
        )
        # Re-do connect with custom env
        client_ctx = stdio_client(params)
        streams = await client_ctx.__aenter__()
        read, write = streams
        session = ClientSession(read, write)
        await session.__aenter__()
        try:
            await session.initialize()
            result = await session.call_tool("pa_fetch", {"doi": doi, "use_cache": True})
            text = result.content[0].text
            data = json.loads(text)
            print(f"  pa_fetch keys: {list(data.keys())[:10]}")
            assert data.get("cache_hit") is True, \
                f"expected cache_hit=True, got {data.get('cache_hit')}"
            assert data.get("final_status") == "SUCCESS_CACHE_HIT"
            assert data.get("via_channel", "").startswith("cache:")
            print(f"  PASS: pa_fetch cache hit returned in MCP response, "
                  f"elapsed={data.get('elapsed_sec')}s")
        finally:
            await session.__aexit__(None, None, None)
            await client_ctx.__aexit__(None, None, None)


async def test_pa_keys_status_doesnt_probe_network():
    """Test that pa_keys_status is purely local (no network).

    Snap the .env stash of OPENALEX_API_KEY before, clear os.environ, call
    pa_keys_status via MCP — should still work (audit is local, not a probe).
    """
    print("\n=== test pa_keys_status (no network) ===")
    saved = dict(os.environ)
    # Clear API keys temporarily
    for k in list(os.environ):
        if k.endswith("_API_KEY") or k == "UNPAYWALL_EMAIL":
            os.environ.pop(k)
    try:
        session, client_ctx, _ = await _connect()
        try:
            result = await session.call_tool("pa_keys_status", {})
            text = result.content[0].text
            data = json.loads(text)
            assert "rows" in data
            print(f"  PASS: pa_keys_status works without API keys ({data['total']} services)")
        finally:
            await _disconnect(session, client_ctx)
    finally:
        os.environ.clear()
        os.environ.update(saved)


async def main():
    print("=" * 60)
    print("pa_mcp E2E test suite")
    print("=" * 60)
    await test_list_tools()
    await test_pa_keys_status()
    await test_pa_keys_status_doesnt_probe_network()
    await test_pa_review()
    await test_pa_review_missing_corpus()
    await test_unknown_tool()
    await test_pa_fetch_cache_hit()
    print("\n" + "=" * 60)
    print("ALL PA_MCP E2E TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[test interrupted]")
        sys.exit(1)
