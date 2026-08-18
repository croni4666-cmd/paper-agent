"""pa_cli.mcp_fetch - Thin MCP wrapper for pa fetch tools (v3.9.14.0, [P0-15])

Exposes 2 paper-agent fetch tools over stdio JSON-RPC, so AI agents
(Codex / Claude Code / OpenCode) can drive the same `pa fetch` and
`pa fetch-pdf-batch` commands that a human would run from the terminal.

**Why this is NOT a [P0-3] resurrection** (per ROADMAP [P0-15] entry):
- [P0-3] (deprecated 2026-07-04) was a 4-tool full-featured MCP server
  with hand-maintained JSON Schemas. Maintenance burden was too high.
- This module: 2 thin wrappers over EXISTING pa CLI functions. No new
  schemas to maintain beyond 2 simple ones. The mcp.Server boilerplate
  is identical; the maintenance tax is the 2 schemas, not the server.
- The MCP tool is opt-in: user adds it to their MCP client config only
  if they want agent-driven fetch. Not auto-installed.

**Tools exposed** (matches `pa fetch` / `pa fetch-pdf-batch` CLI):
  - `pa_fetch(doi, prefer, use_cache) -> {saved_as, via_channel, ...}`
  - `pa_batch_fetch(dois, output_dir, prefer) -> {n_total, n_success, ...}`

**Design constraints** (per Global Rule + 留痕 discipline):
- NO new dependency (mcp SDK is already installed per [P0-3] Round 2)
- NO new server to maintain in a public-facing infra sense
- Stdio transport only (single-machine local use; no HTTP for cross-machine)
- Same trust boundary as `pa fetch` CLI invocation (any path that calls
  `pa fetch` is reachable from this MCP)
- Same留痕 discipline: NO api keys / passwords accepted through MCP
  (they would have to go through the existing CLI env var mechanism)

**Client config example** (paste into Claude Code / Codex / etc.):
```json
{
  "mcpServers": {
    "paper-agent-fetch": {
      "command": "python",
      "args": ["-m", "pa_cli.mcp_fetch"]
    }
  }
}
```
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, TextContent, Tool

# Lazy imports inside handlers to avoid loading the heavy fetch cascade
# module when the MCP server starts (per [P0-3] lesson: local imports
# in handlers cut startup time + reduce surprise module-load side effects).

logger = logging.getLogger("pa.mcp_fetch")
logger.setLevel(logging.WARNING)  # quiet by default; --debug to verbose


# ─────────────────────────────────────────────────────────────────
# Tool schemas (2 tools, hand-maintained but minimal)
# ─────────────────────────────────────────────────────────────────
TOOL_PA_FETCH = Tool(
    name="pa_fetch",
    description=(
        "Fetch a single paper PDF by DOI. Returns the same dict as `pa fetch <doi>` "
        "from the CLI: {saved_as, via_channel, cache_hit, size_bytes, error/handoff}. "
        "Reuses local cache when use_cache=True. Can route through Sci-Hub / annas / "
        "arXiv / CNKI / direct DOI resolver depending on availability."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "doi": {
                "type": "string",
                "description": "Paper DOI (e.g. '10.1038/nature12373' or full URL).",
            },
            "prefer": {
                "type": "string",
                "enum": ["auto", "scihub", "annas", "cnki", "arxiv", "direct"],
                "default": "auto",
                "description": "Preferred fetch channel. Default 'auto' tries all in priority order.",
            },
            "use_cache": {
                "type": "boolean",
                "default": True,
                "description": "If True, return cached PDF without re-downloading (default).",
            },
        },
        "required": ["doi"],
    },
)

TOOL_PA_BATCH_FETCH = Tool(
    name="pa_batch_fetch",
    description=(
        "Fetch a list of paper PDFs by DOI. Returns a summary dict: {n_total, "
        "n_success, n_failed, results: [...]} with per-DOI status. Slower than "
        "single fetch (sequential to avoid rate limits). Same trust boundary as "
        "`pa fetch-pdf-batch <input.txt> --out ./pdfs/`."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "dois": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of DOIs to fetch.",
            },
            "output_dir": {
                "type": "string",
                "default": "./pdfs/",
                "description": "Directory to save PDFs to (created if missing).",
            },
            "prefer": {
                "type": "string",
                "enum": ["auto", "scihub", "annas", "cnki", "arxiv", "direct"],
                "default": "auto",
                "description": "Preferred fetch channel for all entries.",
            },
        },
        "required": ["dois"],
    },
)


# ─────────────────────────────────────────────────────────────────
# Server + handlers
# ─────────────────────────────────────────────────────────────────
def _build_server() -> Server:
    """Build the MCP Server with 2 tool handlers registered."""
    server = Server("paper-agent-fetch")

    @server.list_tools()
    async def list_tools() -> List[Tool]:
        return [TOOL_PA_FETCH, TOOL_PA_BATCH_FETCH]

    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        try:
            if name == "pa_fetch":
                result = _handle_pa_fetch(arguments)
            elif name == "pa_batch_fetch":
                result = _handle_pa_batch_fetch(arguments)
            else:
                return [TextContent(
                    type="text",
                    text=json.dumps(
                        {"error": f"unknown_tool: {name}",
                         "available": ["pa_fetch", "pa_batch_fetch"]},
                        ensure_ascii=False,
                    ),
                )]
        except Exception as e:
            logger.exception("tool %s failed", name)
            return [TextContent(
                type="text",
                text=json.dumps(
                    {"error": type(e).__name__, "message": str(e)[:500],
                     "tool": name},
                    ensure_ascii=False,
                ),
            )]

        # Result is always a dict; serialize as JSON for the agent.
        return [TextContent(
            type="text",
            text=json.dumps(result, ensure_ascii=False, indent=2),
        )]

    return server


def _handle_pa_fetch(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for `pa_fetch` tool. Wraps pa_cli.fetch.fetch_doi()."""
    from .fetch import fetch_doi

    doi = arguments.get("doi")
    if not doi:
        return {"error": "missing_arg: doi", "tool": "pa_fetch"}

    prefer = arguments.get("prefer", "auto")
    use_cache = bool(arguments.get("use_cache", True))

    # fetch_doi already supports prefer param in v3.9.10.x+
    # We pass it through; if old API ignores, behavior is "auto".
    try:
        result = fetch_doi(
            doi=doi,
            output_dir=".",
            prefer=prefer,
            use_cache=use_cache,
        )
    except TypeError:
        # Fallback: older signature without prefer
        result = fetch_doi(doi=doi, output_dir=".", use_cache=use_cache)

    # The CLI version returns the old shape: {doi, saved_as, channels, final_status, ...}
    # The new fetch() returns: {doi, path, source, size, pdf_url, error?, hint?}
    # We standardize to the old shape for backward-compat with downstream code.
    if "path" in result and "saved_as" not in result:
        result = {
            "doi": result.get("doi", doi),
            "saved_as": result.get("path"),
            "via_channel": result.get("source"),
            "cache_hit": False,  # fetch() bypasses cache; use_cache above handles it
            "size_bytes": result.get("size"),
            "via_url": result.get("pdf_url"),
            "error": result.get("error"),
            "hint": result.get("hint"),
        }

    return result


def _handle_pa_batch_fetch(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for `pa_batch_fetch` tool. Wraps pa_cli.fetch_batch.run_fetch_batch()."""
    from .fetch_batch import run_fetch_batch

    dois = arguments.get("dois")
    if not dois or not isinstance(dois, list):
        return {"error": "missing_arg: dois (must be non-empty list)", "tool": "pa_batch_fetch"}

    output_dir = Path(arguments.get("output_dir", "./pdfs/"))
    output_dir.mkdir(parents=True, exist_ok=True)
    prefer = arguments.get("prefer", "auto")

    # Build a temp Bibtex file from the dois list, then run the batch.
    # This is the simplest path that reuses existing batch logic without
    # adding a new "dois-only" entry point in fetch_batch.py.
    import tempfile
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".bib", delete=False, encoding="utf-8"
    ) as f:
        for i, doi in enumerate(dois, start=1):
            # Each entry needs a unique key; use the doi hash + index
            key = f"entry{i}"
            f.write(f"@article{{{key},\n  doi = {{{doi}}}\n}}\n")
        tmp_bib = Path(f.name)

    try:
        summary = run_fetch_batch(
            bib_path=tmp_bib,
            out_dir=output_dir,
            prefer=prefer,
        )
        # Convert FetchSummary dataclass to plain dict
        return {
            "n_total": summary.n_total,
            "n_success": summary.n_success,
            "n_failed": summary.n_failed,
            "n_skipped": summary.n_skipped,
            "elapsed_sec": round(summary.elapsed_sec, 2) if hasattr(summary, "elapsed_sec") else None,
            "output_dir": str(output_dir),
            "results": [
                {
                    "doi": r.doi,
                    "saved_as": r.saved_as,
                    "via_channel": r.via_channel,
                    "size_bytes": r.size_bytes,
                    "error": r.error,
                }
                for r in summary.results
            ],
        }
    finally:
        tmp_bib.unlink(missing_ok=True)


# ─────────────────────────────────────────────────────────────────
# Entry point: `python -m pa_cli.mcp_fetch`
# ─────────────────────────────────────────────────────────────────
async def _serve() -> None:
    """Async entry point: run stdio JSON-RPC server until stdin closes."""
    server = _build_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main() -> None:
    """Synchronous entry point for `python -m pa_cli.mcp_fetch`."""
    try:
        asyncio.run(_serve())
    except KeyboardInterrupt:
        # stdin closed (e.g. agent disconnected); exit cleanly
        sys.exit(0)
    except BrokenPipeError:
        # Same as above; don't print traceback
        sys.exit(0)


if __name__ == "__main__":
    main()
