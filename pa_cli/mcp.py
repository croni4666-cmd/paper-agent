"""pa_cli.mcp — Model Context Protocol server exposing pa_cli commands as MCP tools.

Architecture:
  - Uses official Anthropic mcp Python SDK (already installed, v1.27.2)
  - 4 tools registered: pa_fetch, pa_search, pa_review, pa_keys_status
  - Stdio transport (json-RPC over stdin/stdout), no HTTP server
  - All tool results are JSON-serialisable (fetch path is str, search is dict,
    review markdown is str, keys audit is dict — no raw bytes anywhere)

Usage:
  # Start the server (called via `pa mcp-serve` from CLI):
  python -m pa_cli.mcp
  # or:
  pa mcp-serve

After running the server, configure your MCP client (Claude Code, Cursor,
OpenCode, etc.) to launch it. Example claude-desktop-config.json entry:

  {
    "mcpServers": {
      "pa": {
        "command": "python",
        "args": ["-m", "pa_cli.mcp"]
      }
    }
  }

Why MCP, why stdio:
  - User preference: "one-time investment, long-term reuse" (memory: agent-behavior-lessons §3)
  - Stdio transport is sufficient for single-machine use; HTTP is overkill
  - Anthropic's official SDK handles JSON-RPC framing, error mapping,
    schema validation — no hand-roll JSON-RPC
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, TextContent, Tool


# Server-wide stderr log (suppresses noisy output that would break stdio JSON-RPC)
log = logging.getLogger("pa_mcp")
log.setLevel(logging.WARNING)
if not log.handlers:
    h = logging.StreamHandler(stream=sys.stderr)
    h.setFormatter(logging.Formatter("[pa-mcp] %(levelname)s %(message)s"))
    log.addHandler(h)


# =============== Tool schemas (JSON Schema format) ===============

PA_FETCH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "doi": {"type": "string", "description": "DOI to fetch (e.g. '10.1016/j.xxxx')"},
        "output_dir": {"type": "string", "default": ".",
                       "description": "Where to save PDF if not in cache."},
        "proxy": {"type": "string",
                  "description": "HTTP proxy URL (e.g. http://127.0.0.1:7897)"},
        "channels": {
            "type": "array", "items": {"type": "string"},
            "description": "Optional list of channel names to try in order.",
        },
        "use_cache": {"type": "boolean", "default": True,
                      "description": "Check cache first; skip on hit."},
    },
    "required": ["doi"],
    "additionalProperties": False,
}

PA_SEARCH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "Free-text search query."},
        "year_min": {"type": "integer", "minimum": 1900, "maximum": 2099,
                     "description": "Earliest publication year to include."},
        "year_max": {"type": "integer", "minimum": 1900, "maximum": 2099,
                     "description": "Latest publication year to include."},
        "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 50,
                  "description": "Max results per engine."},
        "engine": {
            "type": "string",
            "default": "all",
            "description": "all or comma-separated engine list "
                           "(crossref, openalex, arxiv, semanticscholar, core).",
        },
        "format": {"type": "string", "enum": ["json", "bibtex"], "default": "json",
                   "description": "Output format. bibtex returns formatted text."},
    },
    "required": ["query"],
    "additionalProperties": False,
}

PA_REVIEW_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "corpus_dir": {"type": "string",
                       "description": "Path to directory of PDFs to review."},
        "template": {"type": "string", "default": "v32",
                     "description": "Lit review template version."},
        "word_count_min": {"type": "integer", "minimum": 0, "default": 1000,
                           "description": "Min words extracted to count as full-text."},
    },
    "required": ["corpus_dir"],
    "additionalProperties": False,
}

PA_KEYS_STATUS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}


# =============== Server instance + handlers ===============

server: Server = Server("paper-agent")


@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """Return the 4 paper-agent tools to MCP clients."""
    return [
        Tool(
            name="pa_fetch",
            description=(
                "Fetch a single paper PDF by DOI via 8 cascade channels "
                "(openalex, arxiv, unpaywall, doi_redirect, scihub, playwright) "
                "with cache-first skip. Returns structured dict with saved_as path, "
                "via_channel, cache_hit flag, and (on total failure) "
                "handoff.user_action_required field per paper-agent v4 principle."
            ),
            inputSchema=PA_FETCH_SCHEMA,
        ),
        Tool(
            name="pa_search",
            description=(
                "Run 5-engine academic paper search (Crossref / OpenAlex / "
                "arXiv / Semantic Scholar / CORE) with dedup. Returns dict with "
                "results list and by_engine count; if format=bibtex returns "
                "BibTeX-formatted text in 'bibtex' field."
            ),
            inputSchema=PA_SEARCH_SCHEMA,
        ),
        Tool(
            name="pa_review",
            description=(
                "Synthesise a lit review markdown from a corpus_dir of PDFs. "
                "Returns {markdown: str, corpus_dir: str}; markdown is the full "
                "lit review text."
            ),
            inputSchema=PA_REVIEW_SCHEMA,
        ),
        Tool(
            name="pa_keys_status",
            description=(
                "Return audit of registered API keys (active / expiring / "
                "expired / missing counts + per-row breakdown). Pure local, "
                "no HTTP probe — call pa_keys_check CLI separately for live probes."
            ),
            inputSchema=PA_KEYS_STATUS_SCHEMA,
        ),
    ]


def _txt(payload: Any) -> list[TextContent]:
    """Wrap a JSON-serialisable object into a TextContent list."""
    return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False, indent=2))]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> CallToolResult:
    """Dispatch tool calls to pa_cli handlers.

    Returns CallToolResult with content=[TextContent(json)]. On error,
    sets isError=True and returns error dict — client decides how to surface.
    """
    try:
        if name == "pa_fetch":
            result = await _call_pa_fetch(arguments)
        elif name == "pa_search":
            result = await _call_pa_search(arguments)
        elif name == "pa_review":
            result = await _call_pa_review(arguments)
        elif name == "pa_keys_status":
            result = await _call_pa_keys_status(arguments)
        else:
            return CallToolResult(
                content=_txt({"error": "unknown_tool", "available": [
                    "pa_fetch", "pa_search", "pa_review", "pa_keys_status"]}),
                isError=True,
            )
        return CallToolResult(content=_txt(result), structuredContent=result)
    except Exception as e:
        log.exception(f"tool {name} failed")
        return CallToolResult(
            content=_txt({"error": type(e).__name__, "message": str(e)[:500],
                          "tool": name}),
            isError=True,
        )


# =============== Tool implementations ===============

async def _call_pa_fetch(args: dict) -> dict:
    """pa_fetch(doi, output_dir?, proxy?, channels?, use_cache?) → dict."""
    from .fetch import fetch_doi  # local import — pa_mcp shouldn't pull cascade deps at import time
    doi = args["doi"]
    output_dir = args.get("output_dir", ".")
    proxy = args.get("proxy") or None
    channels_arg = args.get("channels")
    channels = channels_arg if channels_arg else None
    use_cache = args.get("use_cache", True)

    result = fetch_doi(
        doi=doi,
        output_dir=output_dir,
        proxy=proxy,
        channels=channels,
        use_cache=use_cache,
    )
    # fetch_doi returns dict — JSON-serialisable; saved_as is a str path
    return result


async def _call_pa_search(args: dict) -> dict:
    """pa_search(query, year_min?, year_max?, limit?, engine?, format?) → dict."""
    from .search import run_search
    from .bibtex import write_bibtex as _write_bib
    import re as _re
    import tempfile
    import os as _os

    query = args["query"]
    year_min = args.get("year_min")
    year_max = args.get("year_max")
    limit = args.get("limit", 50)
    engine = args.get("engine", "all")
    out_format = args.get("format", "json")

    results = run_search(query, year_min, year_max, limit, engine)

    if out_format == "bibtex":
        # Write to a temp file, read back as text. Could also build the
        # bibtex in-memory but the existing `write_bibtex` API takes a path.
        with tempfile.NamedTemporaryFile(mode="w", suffix=".bib",
                                         delete=False, encoding="utf-8") as tmp:
            tmp_path = tmp.name
        try:
            _write_bib(results["results"], tmp_path)
            with open(tmp_path, "r", encoding="utf-8") as f:
                bib_text = f.read()
        finally:
            try:
                _os.unlink(tmp_path)
            except OSError:
                pass
        return {
            "format": "bibtex",
            "query": query,
            "count": results["dedup_count"],
            "by_engine": results["by_engine"],
            "bibtex": bib_text,
        }
    return results


async def _call_pa_review(args: dict) -> dict:
    """pa_review(corpus_dir, template?, word_count_min?) → {markdown, corpus_dir}."""
    from pathlib import Path as _Path
    from .review import synthesize  # local import — keep mcp dep-light

    corpus_dir = args["corpus_dir"]
    template = args.get("template", "v32")
    word_count_min = args.get("word_count_min", 1000)
    p = _Path(corpus_dir)
    if not p.exists() or not p.is_dir():
        return {
            "error": "corpus_dir_not_found",
            "corpus_dir": str(p),
            "markdown": "",
        }
    md = synthesize(p, template, word_count_min)
    return {"corpus_dir": str(p), "markdown": md}


async def _call_pa_keys_status(args: dict) -> dict:
    """pa_keys_status() → audit dict."""
    from .keys import cmd_audit
    return cmd_audit()


# =============== Server lifecycle ===============

async def serve() -> None:
    """Run the MCP server using stdio transport. Blocks until stdin closes."""
    async with stdio_server() as (read_stream, write_stream):
        init_opts = server.create_initialization_options()
        await server.run(read_stream, write_stream, init_opts)


def main() -> None:
    """CLI entry point — `python -m pa_cli.mcp` or `pa mcp-serve`."""
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        log.info("pa mcp-serve interrupted, exiting cleanly")
        sys.exit(0)
    except BrokenPipeError:
        # stdin closed by client; expected on disconnect
        sys.exit(0)


if __name__ == "__main__":
    main()
