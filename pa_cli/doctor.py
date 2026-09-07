"""Offline readiness checks for paper-agent's optional integrations."""

import importlib.util
import os
from pathlib import Path
from typing import Any, Dict


def _chromium_installed() -> bool:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:
            return Path(playwright.chromium.executable_path).is_file()
    except Exception:
        return False


def _dependency_status() -> Dict[str, bool]:
    has_playwright = importlib.util.find_spec("playwright") is not None
    return {
        "playwright_package": has_playwright,
        "chromium_installed": has_playwright and _chromium_installed(),
        "arxiv": importlib.util.find_spec("arxiv") is not None,
    }


def _aminer_status() -> Dict[str, Any]:
    from .aminer_channel import status_report
    return status_report()


def _cnki_status() -> Dict[str, Any]:
    from .cnki_channel import status_report
    return status_report()


def _check(status: str, summary: str, next_action: str = "") -> Dict[str, str]:
    result = {"status": status, "summary": summary}
    if next_action:
        result["next_action"] = next_action
    return result


def build_report() -> Dict[str, Any]:
    """Build a local-only report without returning credentials or cookie values."""
    dependencies = _dependency_status()
    aminer = _aminer_status()
    cnki = _cnki_status()
    playwright_package = dependencies.get("playwright_package", False)
    chromium_installed = dependencies.get("chromium_installed", False)
    playwright_ready = playwright_package and chromium_installed
    cnki_ready = bool(cnki.get("ready_for_search")) and bool(cnki.get("n_cookies"))

    if not playwright_package:
        playwright_summary = "Playwright is not installed."
        playwright_action = "Install the browser extra, then install Chromium."
    elif not chromium_installed:
        playwright_summary = "Playwright is installed but Chromium is unavailable."
        playwright_action = "Install Chromium with the Playwright installer."
    else:
        playwright_summary = "Playwright and Chromium are ready."
        playwright_action = ""

    checks: Dict[str, Dict[str, str]] = {
        "playwright": _check(
            "ready" if playwright_ready else "unavailable",
            playwright_summary,
            playwright_action,
        ),
        "arxiv": _check(
            "ready" if dependencies.get("arxiv", False) else "unavailable",
            "arXiv client is installed." if dependencies.get("arxiv", False)
            else "arXiv client is not installed.",
            "" if dependencies.get("arxiv", False) else "Install the arXiv dependency to enable arXiv search.",
        ),
        "aminer": _check(
            "ready" if aminer.get("token_set") else "attention",
            "AMiner API token is configured." if aminer.get("token_set")
            else "AMiner API token is not configured; this engine will be skipped.",
            "" if aminer.get("token_set") else "Set AMINER_API_KEY or AM_API_KEY before using AMiner.",
        ),
        "semantic_scholar": _check(
            "ready" if os.environ.get("S2_API_KEY", "").strip() else "attention",
            "Semantic Scholar API key is configured."
            if os.environ.get("S2_API_KEY", "").strip()
            else "Semantic Scholar runs on the shared unauthenticated quota and may rate-limit.",
            "" if os.environ.get("S2_API_KEY", "").strip() else "Set S2_API_KEY for a dedicated quota.",
        ),
        "pubmed": _check(
            "ready" if os.environ.get("NCBI_API_KEY", "").strip() else "attention",
            "NCBI API key is configured."
            if os.environ.get("NCBI_API_KEY", "").strip()
            else "PubMed works without a key but uses the lower public rate limit.",
            "" if os.environ.get("NCBI_API_KEY", "").strip() else "Optionally set NCBI_API_KEY for higher PubMed throughput.",
        ),
        "cnki": _check(
            "ready" if cnki_ready else "attention",
            "CNKI cookies and Playwright are ready."
            if cnki_ready else "CNKI needs fresh, nonempty local cookies and Playwright before searching.",
            "" if cnki_ready else "Run pa cnki status, then refresh cookies if needed.",
        ),
    }
    statuses = [item["status"] for item in checks.values()]
    overall_status = (
        "unavailable" if "unavailable" in statuses
        else "attention" if "attention" in statuses
        else "ready"
    )
    return {
        "overall_status": overall_status,
        "mode": "offline",
        "checks": checks,
    }
