"""Local, privacy-minimal fetch channel outcome statistics."""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULT_PATH = Path.home() / ".paper-agent" / "fetch_channel_stats.jsonl"


from .fetch_trace import traced

@traced("statistics")
def record_event(
    doi: str,
    channel: str,
    success: bool,
    elapsed_sec: float,
    *,
    error: Optional[str] = None,
    path: Path = DEFAULT_PATH,
) -> None:
    """Append one fetch outcome without storing titles, URLs, or credentials."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "doi": (doi or "")[:300],
        "channel": channel or "unknown",
        "success": bool(success),
        "elapsed_sec": round(float(elapsed_sec or 0), 3),
    }
    if error:
        event["error"] = str(error)[:200]
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")


def summarize(*, path: Path = DEFAULT_PATH) -> Dict[str, Any]:
    """Return aggregate channel outcomes from the local append-only event log."""
    path = Path(path)
    buckets: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"attempts": 0, "successes": 0, "failures": 0, "elapsed_total": 0.0}
    )
    invalid_records = 0
    if not path.exists():
        return {
            "path": str(path),
            "total_attempts": 0,
            "invalid_records": 0,
            "channels": {},
        }

    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
            channel = str(event["channel"])
            success = bool(event["success"])
            elapsed = float(event.get("elapsed_sec", 0))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            invalid_records += 1
            continue
        bucket = buckets[channel]
        bucket["attempts"] += 1
        bucket["successes" if success else "failures"] += 1
        bucket["elapsed_total"] += elapsed

    channels = {}
    for channel, bucket in sorted(buckets.items()):
        attempts = bucket["attempts"]
        channels[channel] = {
            "attempts": attempts,
            "successes": bucket["successes"],
            "failures": bucket["failures"],
            "success_rate": round(bucket["successes"] / attempts, 3) if attempts else 0.0,
            "avg_elapsed_sec": round(bucket["elapsed_total"] / attempts, 3) if attempts else 0.0,
        }
    return {
        "path": str(path),
        "total_attempts": sum(item["attempts"] for item in channels.values()),
        "invalid_records": invalid_records,
        "channels": channels,
    }