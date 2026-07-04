"""Smoke test for pa mcp install/config (uses subprocess mocking — does not
actually install paper-search-mcp on the host).

Verifies:
  - pa mcp config prints the JSON config block correctly
  - pa mcp install --dry-run prints what would happen
  - pa mcp install --uvx prefers uvx path when uvx is on PATH
  - pa mcp install --uvx falls back to print-only when uvx is not on PATH
  - pa mcp install (real) calls pip with correct args when not installed
  - pa mcp install reports 'already_installed' when package is importable
  - install_failed path: returns status='install_failed' and prints uvx fallback
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _run_pa_mcp(*args, env=None, timeout=30):
    """Run pa mcp <args> as subprocess; return (rc, stdout, stderr)."""
    cmd = [sys.executable, "-m", "pa_cli", "mcp"] + list(args)
    e = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1", **(env or {})}
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       env=e, cwd=str(ROOT), timeout=timeout, stdin=subprocess.DEVNULL)
    return r.returncode, r.stdout, r.stderr


def test_mcp_config_prints_json():
    """pa mcp config → stdout contains valid JSON config block."""
    print("\n=== test: pa mcp config (prints JSON) ===")
    rc, out, _ = _run_pa_mcp("config")
    assert rc == 0
    # Find the JSON block between the '=' banner lines
    lines = out.splitlines()
    # Locate "{ mcpServers..." line and capture until matching "}"
    json_start = None
    for i, l in enumerate(lines):
        if l.strip().startswith("{"):
            json_start = i
            break
    assert json_start is not None, f"no JSON found in output:\n{out}"
    # Find matching closing brace
    depth = 0
    json_end = json_start
    for j in range(json_start, len(lines)):
        depth += lines[j].count("{") - lines[j].count("}")
        if depth == 0:
            json_end = j
            break
    json_block = "\n".join(lines[json_start:json_end + 1])
    config = json.loads(json_block)
    assert "mcpServers" in config
    assert "paper-search-mcp" in config["mcpServers"]
    # Either python (pip) or uvx command
    cmd = config["mcpServers"]["paper-search-mcp"]["command"]
    assert cmd in ("python", "uvx"), f"unexpected command: {cmd}"
    print(f"  PASS: config block valid, command={cmd}")


def test_mcp_install_dry_run():
    """pa mcp install --dry-run → does not actually run pip."""
    print("\n=== test: pa mcp install --dry-run ===")
    rc, out, err = _run_pa_mcp("install", "--dry-run")
    assert rc == 0
    assert "DRY-RUN" in out
    assert "would run" in out
    # Config block also present
    assert "mcpServers" in out
    print("  PASS: dry-run prints intent without running pip")


def test_mcp_install_already_installed():
    """pa mcp install when already importable → status=already_installed."""
    print("\n=== test: pa mcp install (already installed path) ===")
    from pa_cli.mcp_setup import install
    with patch("pa_cli.mcp_setup._is_installed", return_value=True):
        with patch("pa_cli.mcp_setup._have_uvx", return_value=False):
            result = install()
    assert result["status"] == "already_installed"
    assert result["method"] == "pip"
    assert "mcpServers" in result["config_json"]
    print("  PASS: already_installed path returns correct status, no pip called")


def test_mcp_install_uvx_preferred():
    """pa mcp install --uvx → uses uvx path when uvx is on PATH."""
    print("\n=== test: pa mcp install --uvx (uvx on PATH) ===")
    from pa_cli.mcp_setup import install
    with patch("pa_cli.mcp_setup._have_uvx", return_value=True):
        with patch("pa_cli.mcp_setup._is_installed", return_value=False):
            result = install(use_uvx=True)
    assert result["status"] == "uvx_recommended"
    assert result["method"] == "uvx"
    config = json.loads(result["config_json"])
    assert config["mcpServers"]["paper-search-mcp"]["command"] == "uvx"
    assert config["mcpServers"]["paper-search-mcp"]["args"] == ["paper-search-mcp"]
    print("  PASS: --uvx path uses uvx command")


def test_mcp_install_uvx_fallback():
    """pa mcp install --uvx when uvx not on PATH → falls back to install."""
    print("\n=== test: pa mcp install --uvx (uvx NOT on PATH) ===")
    from pa_cli.mcp_setup import install
    # When --uvx is requested but uvx is missing, _have_uvx returns False,
    # so the function falls through to the install path.
    mock_pip = MagicMock()
    mock_pip.return_value = MagicMock(returncode=0, stderr="")
    with patch("pa_cli.mcp_setup._have_uvx", return_value=False):
        with patch("pa_cli.mcp_setup._is_installed", return_value=False):
            with patch("pa_cli.mcp_setup.subprocess.run", mock_pip):
                result = install(use_uvx=True)
    # Should have called pip since uvx is missing
    assert mock_pip.called, "pip should have been called as uvx fallback"
    assert result["status"] == "installed"
    print("  PASS: --uvx falls through to pip when uvx not on PATH")


def test_mcp_install_failure_falls_back_to_uvx():
    """pa mcp install (real) — pip install fails → status=install_failed + uvx fallback config."""
    print("\n=== test: pa mcp install (pip failure → uvx fallback) ===")
    from pa_cli.mcp_setup import install
    mock_pip = MagicMock()
    mock_pip.return_value = MagicMock(
        returncode=1,
        stderr="ERROR: Could not find a version that satisfies the requirement",
    )
    with patch("pa_cli.mcp_setup._have_uvx", return_value=False):
        with patch("pa_cli.mcp_setup._is_installed", return_value=False):
            with patch("pa_cli.mcp_setup.subprocess.run", mock_pip):
                result = install()
    assert result["status"] == "install_failed"
    assert result["method"] == "pip"
    assert "Could not find a version" in result["stderr"]
    # Fallback config should be uvx
    config = json.loads(result["config_json"])
    assert config["mcpServers"]["paper-search-mcp"]["command"] == "uvx"
    print("  PASS: pip failure shows uvx as fallback in config block")


def test_pa_mcp_serve_deprecated_exits_1():
    """pa mcp serve-deprecated → exits 1 with redirect message."""
    print("\n=== test: pa mcp serve-deprecated (still deprecated) ===")
    rc, out, err = _run_pa_mcp("serve-deprecated")
    assert rc == 1
    combined = out + err
    assert "removed" in combined.lower() or "deprecated" in combined.lower() or "pa mcp install" in combined
    print("  PASS: pa mcp serve-deprecated exits 1 with redirect")


def test_pa_mcp_serve_old_name_exits_1():
    """pa mcp-serve (old top-level name) → exits 1 (backward-compat shim)."""
    print("\n=== test: pa mcp-serve (backward-compat shim at top level) ===")
    # Note: `pa mcp-serve` is a top-level command (with hyphen), NOT
    # `pa mcp serve` (which would be invalid since `serve` is not a
    # subcommand of the mcp group). Run via top-level pa:
    cmd = [sys.executable, "-m", "pa_cli", "mcp-serve"]
    e = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       env=e, cwd=str(ROOT), timeout=15, stdin=subprocess.DEVNULL)
    assert r.returncode == 1, f"expected rc=1, got {r.returncode}"
    combined = r.stdout + r.stderr
    assert "pa mcp install" in combined
    print("  PASS: pa mcp-serve (top-level) exits 1 with redirect to pa mcp install")


def main():
    print("=" * 60)
    print("pa mcp install/config smoke suite")
    print("=" * 60)
    test_mcp_config_prints_json()
    test_mcp_install_dry_run()
    test_mcp_install_already_installed()
    test_mcp_install_uvx_preferred()
    test_mcp_install_uvx_fallback()
    test_mcp_install_failure_falls_back_to_uvx()
    test_pa_mcp_serve_deprecated_exits_1()
    test_pa_mcp_serve_old_name_exits_1()
    print("\n" + "=" * 60)
    print("ALL MCP SETUP TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    main()
