"""pa_cli.mcp_setup — One-shot setup helper for the public paper-search-mcp.

This module does NOT contain an MCP server. It exists so that `pa mcp install`
can install the public `paper-search-mcp` package (PyPI, MIT, 22 free sources)
and print the JSON config block the user pastes into their MCP client
(Claude Code / Cursor / OpenCode / etc.).

Why this exists (vs the user doing it manually):
  - Discoverability: `pa mcp install` is on the same `pa --help` tree as
    the rest of the project, so users finding paper-agent know about it.
  - One-shot: don't make the user context-switch to read a README just
    to learn the magic config block.
  - Per Global Rule (ROADMAP.md "Global Rule" section), this is in scope:
    it does not commit the user to a hosted service, runs for $0, and the
    user can always uninstall the package to remove the integration.

What it does NOT do (intentional, per Global Rule + user sovereignty):
  - Does NOT auto-edit `claude_desktop_config.json` or any other MCP
    client config file. User pastes the printed JSON themselves, with
    full visibility into what changed in their config.
  - Does NOT install a global package outside the user's existing
    Python env. Uses `python -m pip install --user` so it goes to the
    user site-packages and can be removed cleanly with `pip uninstall`.
  - Does NOT register the MCP server in any auto-start location.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from typing import Optional, Tuple


# Public MCP package metadata (verified 2026-07-04 against openags/paper-search-mcp)
PUBLIC_MCP_PKG = "paper-search-mcp"
PUBLIC_MCP_DESCRIPTION = (
    "Academic paper search/download via MCP. Free-first, 22 sources "
    "(arXiv, PubMed, Semantic Scholar, Crossref, OpenAlex, CORE, etc.), "
    "MIT-licensed, no API keys required (Unpaywall email optional)."
)


def _print_config_block(method: str = "pip") -> None:
    """Print the JSON config block the user pastes into their MCP client.

    method: 'pip' or 'uvx' — selects the run command in the JSON.
    """
    if method == "uvx":
        # uvx runs the package without a permanent install.
        config = {
            "mcpServers": {
                "paper-search-mcp": {
                    "command": "uvx",
                    "args": ["paper-search-mcp"],
                }
            }
        }
        install_cmd = "uv tool install paper-search-mcp  (or use uvx without install)"
    else:
        # pip install (default, more universally available).
        config = {
            "mcpServers": {
                "paper-search-mcp": {
                    "command": "python",
                    "args": ["-m", "paper_search_mcp.server"],
                }
            }
        }
        install_cmd = "python -m pip install --user paper-search-mcp"

    print("=" * 60)
    print("MCP client config (paste into your client's config file):")
    print("=" * 60)
    print(json.dumps(config, indent=2, ensure_ascii=False))
    print()
    print("=" * 60)
    print(f"Install command used: {install_cmd}")
    print("=" * 60)


def _is_installed() -> bool:
    """Check if paper-search-mcp is importable in the current Python env."""
    try:
        import importlib
        importlib.import_module("paper_search_mcp")
        return True
    except ImportError:
        return False


def _have_uvx() -> bool:
    """Check if uvx is on PATH (would skip the install step)."""
    return shutil.which("uvx") is not None


def install(use_uvx: bool = False, dry_run: bool = False) -> dict:
    """Install paper-search-mcp and print config block.

    Args:
        use_uvx: if True, prefer uvx (no install needed) and skip pip.
        dry_run: if True, don't actually run pip; just print what would happen.

    Returns:
        dict with keys:
          "status": "ok" | "already_installed" | "installed" | "uvx_recommended" | "install_failed"
          "method": "pip" | "uvx"
          "config_json": str (the JSON block, always populated)
          "stderr": str (only on install_failed)
    """
    if use_uvx and _have_uvx():
        # uvx runs the package on-demand without permanent install
        _print_config_block(method="uvx")
        return {"status": "uvx_recommended", "method": "uvx",
                "config_json": json.dumps({
                    "mcpServers": {"paper-search-mcp": {
                        "command": "uvx", "args": ["paper-search-mcp"]}}}, indent=2)}

    if _is_installed():
        _print_config_block(method="pip")
        return {"status": "already_installed", "method": "pip",
                "config_json": json.dumps({
                    "mcpServers": {"paper-search-mcp": {
                        "command": "python", "args": ["-m", "paper_search_mcp.server"]}}}, indent=2)}

    # Need to install. Use --user so it goes to user site-packages and can
    # be cleanly uninstalled later.
    if dry_run:
        print("[pa-mcp] DRY-RUN: would run `python -m pip install --user paper-search-mcp`")
        _print_config_block(method="pip")
        return {"status": "dry_run", "method": "pip",
                "config_json": json.dumps({
                    "mcpServers": {"paper-search-mcp": {
                        "command": "python", "args": ["-m", "paper_search_mcp.server"]}}}, indent=2)}

    print(f"[pa-mcp] installing {PUBLIC_MCP_PKG} via pip (user site-packages) ...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--user", PUBLIC_MCP_PKG],
        capture_output=True, text=True, encoding="utf-8",
    )
    if result.returncode != 0:
        print(f"[pa-mcp] ❌ pip install failed (rc={result.returncode})", file=sys.stderr)
        print(result.stderr[-500:], file=sys.stderr)
        _print_config_block(method="uvx")
        return {"status": "install_failed", "method": "pip",
                "stderr": result.stderr[-500:],
                "config_json": json.dumps({
                    "mcpServers": {"paper-search-mcp": {
                        "command": "uvx", "args": ["paper-search-mcp"]}}}, indent=2)}

    print(f"[pa-mcp] ✅ {PUBLIC_MCP_PKG} installed successfully")
    _print_config_block(method="pip")
    return {"status": "installed", "method": "pip",
            "config_json": json.dumps({
                "mcpServers": {"paper-search-mcp": {
                    "command": "python", "args": ["-m", "paper_search_mcp.server"]}}}, indent=2)}
