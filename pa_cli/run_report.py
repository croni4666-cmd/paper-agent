"""Bounded, offline summaries of explicit result snapshots (not evidence validation)."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import stat
import tempfile

MAX_INPUT_BYTES = 8 * 1024 * 1024
KINDS = ("search", "fetch", "review")
ADAPTERS = {kind: f"pa-v4-{kind}-legacy/1" for kind in KINDS}
SCOPE = "Reported state of supplied JSON snapshots only; artifacts and evidence are not verified."


def _count(value):
    if type(value) is not int or value < 0:
        raise ValueError("invalid_count")
    return value


def _object(value):
    if not isinstance(value, dict):
        raise ValueError("unsupported_structure")
    # Current source contracts are unversioned. Do not guess a future schema.
    if any(key in value for key in ("schema", "schema_version", "version")):
        raise ValueError("unsupported_version")
    return value


def _state(ok, failed):
    return "partial" if ok and failed else "failed" if failed else "success"


def _search(data):
    if any(key in data for key in ("status", "exit_code", "error")):
        raise ValueError("inconsistent_search")
    statuses, counts, errors = (data.get(key) for key in ("engine_status", "by_engine", "engine_errors"))
    rows = data.get("results")
    if (not isinstance(statuses, dict) or not statuses or not isinstance(counts, dict)
            or not isinstance(errors, dict) or set(statuses) != set(counts)
            or any(value not in ("ok", "error") for value in statuses.values())
            or set(errors) != {key for key, value in statuses.items() if value == "error"}
            or not isinstance(rows, list) or not all(isinstance(row, dict) and "error" not in row for row in rows)):
        raise ValueError("inconsistent_search")
    total = sum(_count(value) for value in counts.values())
    if _count(data.get("dedup_count")) != len(rows) or len(rows) > total:
        raise ValueError("inconsistent_search")
    ok = sum(value == "ok" for value in statuses.values())
    failed = len(statuses) - ok
    return _state(ok or bool(rows), failed), {"engines_ok": ok, "engines_failed": failed, "results": len(rows)}


def _fetch(data):
    envelope = data if "summary" in data else None
    if envelope is None and any(key in data for key in ("status", "exit_code", "error")):
        raise ValueError("inconsistent_fetch")
    summary = _object(data["summary"]) if envelope is not None else data
    rows = summary.get("results")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError("inconsistent_fetch")
    success = failure = skipped = available = timed_out = 0
    for row in rows:
        if type(row.get("success")) is not bool:
            raise ValueError("inconsistent_fetch")
        error = row.get("error", "")
        if not isinstance(error, str):
            raise ValueError("inconsistent_fetch")
        if row["success"]:
            if error not in ("", "skipped-existing"):
                raise ValueError("inconsistent_fetch")
            available += 1
            if error == "skipped-existing":
                skipped += 1
            else:
                success += 1
        elif error == "global-timeout":
            skipped += 1
            timed_out += 1
        elif error == "skipped-existing":
            raise ValueError("inconsistent_fetch")
        else:
            failure += 1
    expected = dict(n_total=len(rows), n_success=success, n_failure=failure, n_skipped=skipped)
    if any(_count(summary.get(key)) != value for key, value in expected.items()):
        raise ValueError("inconsistent_fetch")
    state = _state(available, len(rows) - available) if rows else "unknown"
    if envelope is not None:
        declared = envelope.get("status")
        if declared not in ("success", "partial", "failed"):
            raise ValueError("inconsistent_fetch")
        # A failing child can downgrade a seemingly complete batch.
        exits = [envelope.get("exit_code"), envelope.get("cli_exit_code")]
        if any(type(code) is not int for code in exits) or exits[0] < 0:
            raise ValueError("inconsistent_fetch")
        if any(exits) and available:
            state = "partial"
        if rows and declared != state:
            raise ValueError("inconsistent_fetch")
        if declared == "success" and any(exits):
            raise ValueError("inconsistent_fetch")
    return state, {**expected, "reported_available": available, "timed_out": timed_out}


def _review(data):
    # These are wrapper receipts, not review manifests or validated outputs.
    if data.get("status") == "completed":
        if (data.get("mode") not in ("synthesis", "clustering")
                or not all(isinstance(data.get(key), str) and data[key] for key in ("corpus", "output"))
                or "error" in data or ("exit_code" in data and (type(data["exit_code"]) is not int or data["exit_code"] != 0))):
            raise ValueError("inconsistent_review")
        return "success", {"completion_receipt": True, "artifact_verified": False}
    if data.get("error") in ("pa_review_failed", "review_timeout", "corpus_not_found", "pa_cli_not_found", "runtime_error"):
        if "status" in data and data["status"] != "failed":
            raise ValueError("inconsistent_review")
        if "exit_code" in data and (type(data["exit_code"]) is not int or data["exit_code"] == 0):
            raise ValueError("inconsistent_review")
        return "failed", {"completion_receipt": False, "artifact_verified": False}
    raise ValueError("unsupported_review")


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate_key")
        result[key] = value
    return result


def _constant(_value):
    raise ValueError("non_finite_number")


def _float(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("non_finite_number")
    return number


def _snapshot(path):
    # Open a single descriptor; refuse special files before reading (FIFO-safe on POSIX).
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NONBLOCK", 0))
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("not_regular_file")
        if info.st_size > MAX_INPUT_BYTES:
            raise ValueError("input_too_large")
        raw = stream.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError("input_too_large")
    return raw


def build_report(inputs):
    """Read only kind->path selections; retain hashes of exact parsed JSON bytes."""
    if not inputs or set(inputs) - set(KINDS):
        raise ValueError("Select at least one supported result kind")
    stages = []
    adapters = {"search": _search, "fetch": _fetch, "review": _review}
    for kind in KINDS:
        if kind not in inputs:
            continue
        stage = {"kind": kind, "adapter": ADAPTERS[kind], "status": "unknown",
                 "source_ref": kind, "artifact_verification": "not_performed"}
        try:
            raw = _snapshot(inputs[kind])
            stage.update(snapshot_sha256=hashlib.sha256(raw).hexdigest(), snapshot_bytes=len(raw))
            data = _object(json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_pairs,
                                      parse_constant=_constant, parse_float=_float))
            stage["status"], stage["counts"] = adapters[kind](data)
            if stage["status"] == "unknown":
                stage["reason"] = "empty_run"
        except OSError:
            stage["reason"] = "input_unreadable"
        except (ValueError, RecursionError):
            # Never copy exception messages, paths, keys, queries or result text.
            stage["reason"] = "unsupported_or_inconsistent_input"
        stages.append(stage)
    statuses = {stage["status"] for stage in stages}
    overall = ("unknown" if "unknown" in statuses else "partial" if "partial" in statuses
               or len(statuses) > 1 else next(iter(statuses)))
    return {"schema": "paper-agent-run-report", "schema_version": 1, "scope": SCOPE,
            "overall_status": overall, "omitted_stages": [kind for kind in KINDS if kind not in inputs],
            "stages": stages}


def render_markdown(report):
    lines = ["# Paper Agent local run report", "", report["scope"], "",
             f"Overall (supplied stages only): **{report['overall_status']}**", "",
             "| Stage | Reported status | Snapshot SHA-256 |", "| --- | --- | --- |"]
    for stage in report["stages"]:
        lines.append(f"| {stage['kind']} | {stage['status']} | {stage.get('snapshot_sha256', 'unavailable')} |")
    lines.append("")
    for stage in report["stages"]:
        if "counts" in stage:
            lines.append(f"{stage['kind']} counts: " + json.dumps(stage["counts"], sort_keys=True))
            lines.append("")
    lines.extend(["", "Omitted stages: " + (", ".join(report["omitted_stages"]) or "none"), ""])
    lines.append("Report schema: paper-agent-run-report/1. Input adapters: "
                 + ", ".join(stage["adapter"] for stage in report["stages"]) + ".")
    lines.append("")
    for stage in report["stages"]:
        if "reason" in stage:
            lines.append(f"- {stage['kind']}: {stage['reason']}")
    return "\n".join(lines) + "\n"


def write_report(path, content, inputs):
    """Publish via same-directory replacement; reject input paths and aliases."""
    path = Path(path)
    for source in inputs:
        source = Path(source)
        if path.resolve() == source.resolve() or (path.exists() and source.exists() and os.path.samefile(path, source)):
            raise ValueError("Report output must not overwrite a supplied input")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=path.parent,
                                         prefix=".pa-run-report-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
