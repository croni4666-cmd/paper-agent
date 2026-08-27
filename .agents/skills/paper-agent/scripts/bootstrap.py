#!/usr/bin/env python3
"""scripts/bootstrap.py — Auto-install paper-agent (pa_cli) for the skill.

When the user installs the paper-agent Skill in Codex CLI, the wrapper
scripts need the paper-agent Python package (pa_cli) to be importable.
This script:

  1. Checks if pa_cli is already importable (success path)
  2. Tries to find the paper-agent repo at common locations
  3. If found, runs `pip install -e <repo>` to install in editable mode
  4. Verifies the install succeeded

Usage:
  python scripts/bootstrap.py
  python scripts/bootstrap.py --repo <custom-path>
  python scripts/bootstrap.py --check   # check only, no install

Exit codes:
  0 — pa_cli is importable (already or just installed)
  1 — pa_cli not found and no install attempted
  2 — install attempted but failed
  3 — install succeeded but pa_cli still not importable
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


# Common locations where paper-agent repo might be cloned
DEFAULT_SEARCH_PATHS = [
    Path.home() / "minimax - workspace" / "Paper agent",
    Path.home() / "Minmax - workspace" / "Paper agent",
    Path.home() / "Documents" / "GitHub" / "paper-agent",
    Path.home() / "code" / "paper-agent",
    Path.home() / "src" / "paper-agent",
    Path.home() / "projects" / "paper-agent",
    Path.cwd(),
    Path.cwd().parent,
    Path.cwd().parent.parent,
    # If skill is at .agents/skills/paper-agent/, repo is 2 levels up
    Path(__file__).resolve().parent.parent.parent.parent,  # skill at .agents/skills/paper-agent/scripts/
    Path(__file__).resolve().parent.parent.parent.parent.parent,  # skill at .agents/skills/paper-agent/
]


def find_pa_repo(custom_path: str = None) -> Path | None:
    """Find the paper-agent repo (must contain pa_cli/__init__.py + pyproject.toml or setup.py)."""
    if custom_path:
        p = Path(custom_path).expanduser().resolve()
        if (p / "pa_cli" / "__init__.py").is_file() and (
            (p / "pyproject.toml").is_file() or (p / "setup.py").is_file()
        ):
            return p
        return None

    for candidate in DEFAULT_SEARCH_PATHS:
        try:
            c = candidate.expanduser().resolve()
        except (OSError, RuntimeError):
            continue
        if (c / "pa_cli" / "__init__.py").is_file() and (
            (c / "pyproject.toml").is_file() or (c / "setup.py").is_file()
        ):
            return c
    return None


def is_pa_cli_importable() -> bool:
    """Check if pa_cli is importable in the current Python environment."""
    try:
        import pa_cli  # noqa: F401
        return True
    except ImportError:
        return False


def is_pa_cli_importable_in_subprocess() -> bool:
    """Run a fresh subprocess to check pa_cli import. Use after pip install
    since the current process has cached sys.path from when it started.
    """
    try:
        result = subprocess.run(
            [sys.executable, "-c", "import pa_cli; print(pa_cli.__version__)"],
            capture_output=True, text=True, timeout=15,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, Exception):
        return False


def pip_install_editable(repo_path: Path) -> tuple[bool, str]:
    """Run `pip install -e <repo>`. Returns (success, output)."""
    cmd = [sys.executable, "-m", "pip", "install", "-e", str(repo_path)]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300,
        )
        success = result.returncode == 0
        output = (result.stdout or "") + (result.stderr or "")
        return success, output
    except subprocess.TimeoutExpired:
        return False, "pip install timed out after 300s"
    except Exception as e:
        return False, f"pip install failed: {e}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bootstrap paper-agent (pa_cli) for the Codex Skill.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    # auto-detect repo and install
  %(prog)s --repo ~/myrepo    # use specific repo path
  %(prog)s --check            # check only, no install
        """,
    )
    parser.add_argument("--repo", help="Path to paper-agent repo (default: auto-detect)")
    parser.add_argument("--check", action="store_true", help="Check if pa_cli is importable, no install")
    parser.add_argument("--json", action="store_true", default=True, help="Output JSON (default: true)")
    args = parser.parse_args()

    result = {
        "step": "init",
        "pa_cli_importable": is_pa_cli_importable(),
    }

    if result["pa_cli_importable"]:
        result["status"] = "ok"
        result["message"] = "pa_cli is already importable. No install needed."
        print(json.dumps(result, indent=2))
        return 0

    if args.check:
        result["status"] = "not_installed"
        result["message"] = "pa_cli is not importable. Run without --check to install."
        print(json.dumps(result, indent=2))
        return 1

    # Find repo
    repo = find_pa_repo(args.repo)
    if not repo:
        result["status"] = "repo_not_found"
        result["message"] = (
            "Could not find paper-agent repo. Please clone it first or pass --repo <path>."
        )
        result["searched_paths"] = [str(p) for p in DEFAULT_SEARCH_PATHS]
        print(json.dumps(result, indent=2))
        return 1

    result["step"] = "install"
    result["repo_found"] = str(repo)
    result["install_command"] = f"{sys.executable} -m pip install -e {repo}"

    # Install
    success, output = pip_install_editable(repo)
    result["install_success"] = success
    result["install_output_tail"] = output[-500:] if output else ""

    if not success:
        result["status"] = "install_failed"
        result["message"] = "pip install -e failed. See install_output_tail for details."
        print(json.dumps(result, indent=2))
        return 2

    # Verify (use fresh subprocess since current process has cached sys.path)
    result["pa_cli_importable_after"] = is_pa_cli_importable_in_subprocess()
    if not result["pa_cli_importable_after"]:
        result["status"] = "import_failed"
        result["message"] = (
            "Install succeeded but pa_cli is still not importable in a fresh subprocess. "
            "Check PYTHONPATH or use a different Python environment. "
            f"Tried: {sys.executable} -c 'import pa_cli'"
        )
        print(json.dumps(result, indent=2))
        return 3

    result["status"] = "ok"
    result["message"] = f"paper-agent installed from {repo}. Skill is now functional."
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
