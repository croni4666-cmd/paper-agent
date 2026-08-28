#!/usr/bin/env python3
"""scripts/version.py — Show paper-agent version + dep status.

Prints the installed paper-agent version, Python version, and key
optional dependency status (playwright for JATS→PDF, etc.).
Useful for first-time setup validation.

Usage:
    python scripts/version.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
PA_ROOT = SKILL_ROOT.parent.parent.parent


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Show paper-agent version + dep status (Codex Skill wrapper).",
    )
    parser.add_argument("--as-json", action="store_true", default=True, help="Output as JSON (default)")
    args = parser.parse_args()

    import platform
    import importlib

    info = {
        "skill": "paper-agent",
        "skill_version": "3.9.27.0",
        "python": platform.python_version(),
        "platform": platform.system(),
    }

    # Try to import pa_cli to get its version
    try:
        sys.path.insert(0, str(PA_ROOT))
        from pa_cli import __version__ as pa_version
        info["pa_cli_version"] = pa_version
    except Exception as e:
        info["pa_cli_version"] = None
        info["pa_cli_error"] = str(e)

    # Check optional deps
    deps = ["playwright", "requests", "bibtexparser", "fitz", "yaml"]
    info["optional_deps"] = {}
    for dep in deps:
        try:
            mod = importlib.import_module(dep)
            version = getattr(mod, "__version__", "unknown")
            info["optional_deps"][dep] = {"installed": True, "version": version}
        except ImportError:
            info["optional_deps"][dep] = {"installed": False}

    # Compute overall status
    playwright_ok = info["optional_deps"].get("playwright", {}).get("installed", False)
    info["jats_to_pdf_available"] = playwright_ok
    info["recommendation"] = (
        "OK" if info["pa_cli_version"] else
        "paper-agent not installed. Run: pip install -e ."
    )
    if info["pa_cli_version"] and not playwright_ok:
        info["recommendation"] = (
            "paper-agent installed. For JATS→PDF rendering, also: "
            "pip install playwright && python -m playwright install chromium"
        )

    print(json.dumps(info, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
