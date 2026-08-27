"""scripts/_pa_root.py — Shared paper-agent root discovery for all 8 wrapper scripts.

When the skill is installed in a different location than the paper-agent
Python source (the common case — user copies `.agents/skills/paper-agent`
to `~/.codex/skills/paper-agent/`), we need to locate where `pa_cli` is
importable from.

Strategy (in priority order):
1. `$PAPER_AGENT_ROOT` env var (explicit override)
2. `import pa_cli` (if already installed in Codex's Python env)
3. Common paths under user home / cwd
4. `pa` CLI on PATH (subprocess `pa --version`)

Returns: Path to paper-agent root, or None if not found.
"""
from __future__ import annotations

import importlib
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional


def find_pa_root() -> Optional[Path]:
    """Find the paper-agent root directory. Returns None if not found."""
    # 1. Explicit env var
    env_root = os.environ.get("PAPER_AGENT_ROOT")
    if env_root:
        p = Path(env_root).expanduser().resolve()
        if (p / "pa_cli" / "__init__.py").is_file():
            return p
        # Maybe the env var points directly to pa_cli package
        if p.name == "pa_cli" and (p / "__init__.py").is_file():
            return p.parent

    # 2. Try import pa_cli (best — works regardless of skill location)
    try:
        spec = importlib.util.find_spec("pa_cli") if hasattr(importlib, "util") else None
        if spec is None:
            import pa_cli  # noqa: F401
        else:
            import pa_cli  # noqa: F401
        # Find the package directory
        pa_cli_path = Path(pa_cli.__file__).resolve()
        # pa_cli.__file__ points to pa_cli/__init__.py; root is one level up
        return pa_cli_path.parent.parent
    except (ImportError, AttributeError):
        pass

    # 3. Common paths under user home
    home = Path.home()
    candidates = [
        home / "minimax - workspace" / "Paper agent",  # User's main repo
        home / "Minmax - workspace" / "Paper agent",
        home / "Documents" / "GitHub" / "paper-agent",
        home / "code" / "paper-agent",
        home / "src" / "paper-agent",
        home / "projects" / "paper-agent",
    ]
    # Also check cwd
    cwd = Path.cwd()
    candidates.extend([
        cwd,
        cwd.parent,
    ])
    # Also check relative to this skill
    # If skill is at .agents/skills/paper-agent/scripts/_pa_root.py,
    # 4 levels up is the paper-agent repo root.
    skill_root = Path(__file__).resolve().parent.parent  # paper-agent/ skill dir
    candidates.extend([
        skill_root.parent.parent.parent,  # if skill is at .agents/skills/paper-agent/
        skill_root.parent.parent.parent.parent,  # if skill is at .agents/skills/paper-agent/scripts/
    ])

    seen = set()
    for c in candidates:
        try:
            c_resolved = c.resolve()
        except (OSError, RuntimeError):
            continue
        if c_resolved in seen:
            continue
        seen.add(c_resolved)
        if (c / "pa_cli" / "__init__.py").is_file():
            return c
        # Also check if c itself is pa_cli
        if c.name == "pa_cli" and (c / "__init__.py").is_file():
            return c.parent

    # 4. Check `pa` CLI on PATH
    pa_exe = shutil.which("pa")
    if pa_exe:
        # pa is usually a script wrapper in Python's bin; trace back
        pa_exe_path = Path(pa_exe).resolve()
        # Common patterns:
        #   ~/.local/bin/pa       → /path/to/site-packages/pa_cli (parent of bin)
        #   C:\Python312\Scripts\pa.exe → C:\Python312
        for parent in pa_exe_path.parents:
            site_packages_candidates = [
                parent / "Lib" / "site-packages" / "pa_cli",
                parent / "lib" / "python3.12" / "site-packages" / "pa_cli",
                parent / "lib" / "python3.11" / "site-packages" / "pa_cli",
                parent / "lib" / "python3.10" / "site-packages" / "pa_cli",
            ]
            for sp in site_packages_candidates:
                if sp.is_dir() and (sp / "__init__.py").is_file():
                    return sp.parent  # site-packages is at the project level

    return None


def find_pa_executable() -> Optional[str]:
    """Find the `pa` executable on PATH. Returns full path or None."""
    return shutil.which("pa")


def get_install_instructions() -> str:
    """Return human-readable install instructions for the user."""
    return """
Paper Agent (pa_cli) is not installed in this Python environment.

To install:

  Option 1: Install from local repo
    cd <path-to-paper-agent-repo>
    pip install -e .
    # Or on Windows PowerShell:
    cd "<path-to-paper-agent-repo>"; pip install -e .

  Option 2: Set PAPER_AGENT_ROOT env var
    # Windows PowerShell:
    $env:PAPER_AGENT_ROOT = "<path-to-paper-agent-repo>"
    # Linux/macOS:
    export PAPER_AGENT_ROOT="<path-to-paper-agent-repo>"

  Option 3: Run the bootstrap script
    python <skill-dir>/scripts/bootstrap.py

  Option 4: Install from PyPI (when published)
    pip install paper-agent

After installation, re-run your command.
"""


if __name__ == "__main__":
    # CLI mode: print where we found pa_cli (or error)
    root = find_pa_root()
    if root:
        print(f"paper-agent root: {root}")
        pa_exe = find_pa_executable()
        if pa_exe:
            print(f"pa executable: {pa_exe}")
        sys.exit(0)
    else:
        print("ERROR: paper-agent (pa_cli) not found.", file=sys.stderr)
        print(get_install_instructions(), file=sys.stderr)
        sys.exit(1)
