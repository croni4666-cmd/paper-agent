"""Read-only local capability inventory; no imports of optional integrations."""

import importlib.util
import os
import shutil
from typing import Any, Dict


def _package(module: str, label: str) -> Dict[str, str]:
    try:
        present = importlib.util.find_spec(module) is not None
    except Exception:
        # Broken import hooks are isolated to this check; never print their text.
        return {"status": "unknown", "summary": f"Cannot inspect {label}."}
    return {
        "status": "ready" if present else "unavailable",
        "summary": f"{label} package found." if present else f"{label} package missing.",
    }


def build_report() -> Dict[str, Any]:
    """Inventory discoverability/configuration, not runtime or service health.

    Do not load dotenv, key registries, cookie files, paper collections or a
    gateway database. Do not import SDKs, launch browsers, or contact providers.
    Only report fixed text, never credential values or exception messages.
    """
    checks = {
        "pdf": _package("fitz", "PyMuPDF"),
        "arxiv": _package("arxiv", "arXiv"),
        "playwright": _package("playwright", "Playwright"),
        "zotero": _package("pyzotero", "pyzotero"),
    }
    checks["playwright"]["next_action"] = (
        "Browser installation and launch are not checked; use pa cnki status for channel details."
    )
    try:
        pandoc = shutil.which("pandoc") is not None
        checks["pandoc"] = {
            "status": "ready" if pandoc else "unavailable",
            "summary": "Pandoc executable found on PATH." if pandoc else "Pandoc missing from PATH.",
        }
    except Exception:
        checks["pandoc"] = {"status": "unknown", "summary": "Cannot inspect Pandoc on PATH."}
    for name, variables in {
        "aminer": ("AMINER_API_KEY", "AM_API_KEY"),
        "semantic_scholar": ("S2_API_KEY",),
        "pubmed": ("NCBI_API_KEY",),
    }.items():
        configured = any(os.environ.get(key, "").strip() for key in variables)
        checks[name] = {
            "status": "ready" if configured else "attention",
            "summary": "Credential present in process environment; validity not checked."
            if configured else "Credential absent from process environment; service access not checked.",
        }
    return {
        "schema_version": 1,
        "mode": "offline",
        "overall_status": "ready" if all(c["status"] == "ready" for c in checks.values()) else "attention",
        "scope": "Local package discovery, PATH and process environment only; optional gaps do not disable the CLI.",
        "checks": checks,
    }
