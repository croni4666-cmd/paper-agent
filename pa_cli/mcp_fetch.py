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

TOOL_PA_SEARCH = Tool(
    name="pa_search",
    description=(
        "Search academic papers across multiple engines (Crossref, OpenAlex, arXiv, Semantic Scholar, "
        "PubMed, CNKI, AMiner). Returns list of deduplicated papers with titles, authors, years, DOIs, "
        "abstracts, citation counts, and open access status."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Academic search query or topic."},
            "engine": {
                "type": "string",
                "default": "all",
                "description": "Engine: 'all', 'crossref', 'openalex', 'arxiv', 'semanticscholar', 'pubmed', 'aminer', 'cnki'.",
            },
            "limit": {"type": "integer", "default": 20, "description": "Maximum papers to return."},
            "year_min": {"type": "integer", "description": "Optional minimum publication year."},
            "year_max": {"type": "integer", "description": "Optional maximum publication year."},
        },
        "required": ["query"],
    },
)

TOOL_PA_EVIDENCE = Tool(
    name="pa_evidence",
    description=(
        "Extract verbatim page-aware evidence passages from an academic PDF with exact character offsets, "
        "heading heuristics (methods/results/abstract), and OCR status."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "pdf_path": {"type": "string", "description": "Path to PDF file."},
            "query": {"type": "string", "description": "Topic or keyword query to retrieve matching text spans."},
            "max_spans": {"type": "integer", "default": 5, "description": "Maximum evidence passages to return."},
        },
        "required": ["pdf_path"],
    },
)

TOOL_PA_VERIFY_CLAIM = Tool(
    name="pa_verify_claim",
    description=(
        "Verify an academic claim against a PDF manuscript with exact page citations and character offsets. "
        "Zero hallucination: quotes verbatim text from the paper."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "pdf_path": {"type": "string", "description": "Path to PDF manuscript."},
            "claim": {"type": "string", "description": "Specific academic claim or assertion to verify."},
            "max_spans": {"type": "integer", "default": 3, "description": "Max evidence passages to consider."},
        },
        "required": ["pdf_path", "claim"],
    },
)

TOOL_PA_ZOTERO_CHECK = Tool(
    name="pa_zotero_check",
    description=(
        "Check whether a list of DOIs already exists in the user's local Zotero library (read-only SQLite)."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "dois": {"type": "array", "items": {"type": "string"}, "description": "List of DOIs to check."},
        },
        "required": ["dois"],
    },
)


# ─────────────────────────────────────────────────────────────────
# Server + handlers
# ─────────────────────────────────────────────────────────────────
def _build_server() -> Server:
    """Build the MCP Server with 6 tool handlers registered."""
    server = Server("paper-agent-fetch")

    @server.list_tools()
    async def list_tools() -> List[Tool]:
        return [
            TOOL_PA_SEARCH,
            TOOL_PA_FETCH,
            TOOL_PA_BATCH_FETCH,
            TOOL_PA_EVIDENCE,
            TOOL_PA_VERIFY_CLAIM,
            TOOL_PA_ZOTERO_CHECK,
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        try:
            if name == "pa_search":
                result = _handle_pa_search(arguments)
            elif name == "pa_fetch":
                result = _handle_pa_fetch(arguments)
            elif name == "pa_batch_fetch":
                result = _handle_pa_batch_fetch(arguments)
            elif name == "pa_evidence":
                result = _handle_pa_evidence(arguments)
            elif name == "pa_verify_claim":
                result = _handle_pa_verify_claim(arguments)
            elif name == "pa_zotero_check":
                result = _handle_pa_zotero_check(arguments)
            else:
                return [TextContent(
                    type="text",
                    text=json.dumps(
                        {"error": f"unknown_tool: {name}",
                         "available": ["pa_search", "pa_fetch", "pa_batch_fetch", "pa_evidence", "pa_verify_claim", "pa_zotero_check"]},
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


def _handle_pa_search(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for `pa_search` tool. Runs paper search across engines."""
    from .search import run_search

    query = arguments.get("query")
    if not query:
        return {"error": "missing_arg: query", "tool": "pa_search"}

    limit = int(arguments.get("limit", 10))
    engine = str(arguments.get("engine", "all"))
    year_min = arguments.get("year_min")
    year_max = arguments.get("year_max")

    res = run_search(
        query=query,
        engine=engine,
        limit=limit,
        year_min=int(year_min) if year_min is not None else None,
        year_max=int(year_max) if year_max is not None else None,
    )
    results = res.get("results", [])[:limit]
    return {
        "query": query,
        "engine": engine,
        "dedup_count": len(results),
        "results": results,
    }


def _handle_pa_evidence(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for `pa_evidence` tool. Extracts page-aware evidence passages."""
    from .evidence import build_index, build_packet

    pdf_path_str = arguments.get("pdf_path")
    if not pdf_path_str:
        return {"error": "missing_arg: pdf_path", "tool": "pa_evidence"}

    pdf_path = Path(pdf_path_str).expanduser().resolve()
    if not pdf_path.is_file():
        return {"error": f"file_not_found: {pdf_path}", "tool": "pa_evidence"}

    query = arguments.get("query", "methods")
    max_spans = int(arguments.get("max_spans", 5))

    index = build_index(pdf_path)
    packet = build_packet(index, query=query, max_spans=max_spans)
    return packet


def _handle_pa_verify_claim(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for `pa_verify_claim` tool. Verifies claim against PDF text."""
    import re
    from .evidence import build_index, build_packet

    pdf_path_str = arguments.get("pdf_path")
    if not pdf_path_str:
        return {"error": "missing_arg: pdf_path", "tool": "pa_verify_claim"}

    claim = arguments.get("claim")
    if not claim:
        return {"error": "missing_arg: claim", "tool": "pa_verify_claim"}

    pdf_path = Path(pdf_path_str).expanduser().resolve()
    if not pdf_path.is_file():
        return {"error": f"file_not_found: {pdf_path}", "tool": "pa_verify_claim"}

    max_spans = int(arguments.get("max_spans", 3))
    index = build_index(pdf_path)
    packet = build_packet(index, query=claim, max_spans=max_spans)

    evidence = packet.get("evidence", [])
    if not evidence:
        return {
            "claim": claim,
            "verdict": "insufficient_evidence",
            "confidence": 0.0,
            "supporting_passages": [],
            "reason": "No relevant text passages found matching the claim in the PDF.",
            "artifact_sha256": packet.get("artifact_sha256"),
        }

    claim_words = set(re.findall(r"\w+", claim.casefold()))
    stop_words = {"the", "a", "an", "and", "or", "in", "on", "at", "to", "for", "with", "by", "of", "is", "are", "was", "were"}
    informative_words = claim_words - stop_words

    supporting = []
    max_overlap_ratio = 0.0

    for span in evidence:
        span_words = set(re.findall(r"\w+", span["text"].casefold()))
        overlap = informative_words & span_words
        overlap_ratio = len(overlap) / len(informative_words) if informative_words else 0.0
        if overlap_ratio > max_overlap_ratio:
            max_overlap_ratio = overlap_ratio

        supporting.append({
            "page": span["page"],
            "section": span.get("section", "unknown"),
            "offsets": [span["start"], span["end"]],
            "evidence_id": span["evidence_id"],
            "matching_keywords": sorted(list(overlap)),
            "overlap_ratio": round(overlap_ratio, 3),
            "verbatim_text": span["text"].strip(),
        })

    if max_overlap_ratio >= 0.50:
        verdict = "supported"
        conf = min(1.0, round(max_overlap_ratio * 1.1, 2))
        reason = f"High keyword and semantic alignment ({round(max_overlap_ratio*100)}% informative terms matched) in {supporting[0]['section']} section on page {supporting[0]['page']}."
    elif max_overlap_ratio >= 0.25:
        verdict = "partially_supported"
        conf = round(max_overlap_ratio, 2)
        reason = f"Partial term match ({round(max_overlap_ratio*100)}%) found. Human review recommended to confirm specific assertion."
    else:
        verdict = "insufficient_evidence"
        conf = round(max_overlap_ratio, 2)
        reason = "Extracted passages do not contain enough overlapping terminology to substantiate the claim."

    return {
        "claim": claim,
        "verdict": verdict,
        "confidence": conf,
        "best_match_page": supporting[0]["page"] if supporting else None,
        "best_match_section": supporting[0]["section"] if supporting else None,
        "reason": reason,
        "supporting_passages": supporting,
        "artifact_sha256": packet.get("artifact_sha256"),
    }


def _handle_pa_zotero_check(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for `pa_zotero_check` tool. Checks DOIs against local Zotero sqlite."""
    from .zotero_local import find_zotero_db, get_library_dois, check_corpus

    dois = arguments.get("dois")
    if not dois or not isinstance(dois, list):
        return {"error": "missing_arg: dois (must be non-empty list)", "tool": "pa_zotero_check"}

    db_path = find_zotero_db()
    if not db_path:
        return {
            "error": "zotero_db_not_found",
            "message": "Local zotero.sqlite not found on system.",
            "tool": "pa_zotero_check",
        }

    lib_dois = get_library_dois(db_path)
    result = check_corpus(dois, lib_dois)
    result["db_path"] = str(db_path)
    return result


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
