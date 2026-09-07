"""Opt-in, sequential health probes for public paper search engines."""

from __future__ import annotations

import math
import time
from typing import Any, Callable, Iterable

PUBLIC_SEARCH_ENGINES = (
    "crossref", "openalex", "arxiv", "aminer", "pubmed", "clinicaltrials",
)

def _redact_message(message: object) -> str:
    """Emit only fixed diagnostics: provider exceptions may contain secrets."""
    if not message:
        return ""
    text = str(message).lower()
    if "timed out" in text or "timeout" in text:
        return "Engine timed out; retry later or increase --timeout."
    if "not configured" in text:
        return "Engine credentials are not configured."
    if "429" in text or "rate limit" in text:
        return "Engine rate limit reached; retry later."
    return "Engine request failed; check connectivity and configuration. [REDACTED]"


def probe_search_engines(
    query: str,
    *,
    engines: Iterable[str] = PUBLIC_SEARCH_ENGINES,
    limit: int = 1,
    engine_timeout: float = 10.0,
    runner: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Probe engines one at a time and return a JSON-serializable report."""
    engines = tuple(dict.fromkeys(engines))
    if not engines or any(engine not in PUBLIC_SEARCH_ENGINES for engine in engines):
        raise ValueError("Choose one or more public engines: " + ", ".join(PUBLIC_SEARCH_ENGINES))
    if not query.strip():
        raise ValueError("Query must not be empty")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 5:
        raise ValueError("Limit must be an integer from 1 to 5")
    if not math.isfinite(engine_timeout) or engine_timeout < 0.1:
        raise ValueError("Timeout must be finite and at least 0.1 seconds")
    if runner is None:
        from .search import run_search
        runner = run_search
    rows = []
    for engine in engines:
        started = time.monotonic()
        try:
            result = runner(query, engine=engine, limit=limit, engine_timeout=engine_timeout)
            status = result.get("engine_status", {}).get(engine, {})
            rows.append({
                "engine": engine,
                "status": status.get("status") if status.get("status") in {"ok", "error", "skipped", "rate_limited"} else "error",
                "result_count": int(result.get("by_engine", {}).get(engine, 0)),
                "elapsed_sec": round(time.monotonic() - started, 3),
                "message": _redact_message(status.get("message", "")),
            })
        except Exception as exc:
            rows.append({"engine": engine, "status": "error", "result_count": 0,
                         "elapsed_sec": round(time.monotonic() - started, 3),
                         "message": _redact_message(exc)})
    return {"query": query, "limit_per_engine": limit, "engine_timeout": engine_timeout,
            "engines": rows}
