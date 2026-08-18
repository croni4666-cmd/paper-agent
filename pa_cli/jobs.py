"""pa_cli.jobs - Job manager for pa fetch-pdf-batch (v3.9.14.1, [P2-15])

Adds a `pa jobs` Click group with 4 subcommands:
    - list:      show all jobs
    - status:    show progress + last error
    - tail:      tail log.txt
    - resume:    re-run only failed entries (uses --skip-existing)

Inspired by `instsci jobs status/tail/resume` (Round 14 / 2026-08-18
coupling, see ROADMAP "Competitor coupling" section).

**Design**:
- Self-contained: `pa jobs start` wraps `pa fetch-pdf-batch` via
  subprocess and writes manifest.json. No changes needed in
  fetch_batch.py.
- Per-job directory: `~/.paper-agent/jobs/<job_id>/{manifest.json, log.txt}`
- Manifest is updated after subprocess exits (parses log for counts).
- `pa jobs resume` calls `pa fetch-pdf-batch --skip-existing` to
  re-fetch only failed/missing entries.

**No network** in any `pa jobs` subcommand except `start` / `resume`
(which internally call `pa fetch-pdf-batch`).

**No state** lives outside `~/.paper-agent/jobs/` — fully local,
fully deletable.

**No new dep**: pure stdlib (json, subprocess, pathlib, datetime).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# Default job storage root. Override via $PA_JOBS_DIR env var.
DEFAULT_JOBS_DIR = Path.home() / ".paper-agent" / "jobs"


# Status enum (per ROADMAP [P2-15] spec)
STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_INTERRUPTED = "interrupted"
STATUS_FAILED = "failed"

# ─────────────────────────────────────────────────────────────────
# Manifest dataclass
# ─────────────────────────────────────────────────────────────────
@dataclass
class JobManifest:
    job_id: str
    input_file: str
    output_dir: str
    prefer: str = "auto"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    status: str = STATUS_PENDING
    n_total: int = 0
    n_success: int = 0
    n_failed: int = 0
    n_skipped: int = 0
    last_error: Optional[str] = None
    pid: Optional[int] = None  # process ID if running

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict) -> "JobManifest":
        # Tolerate unknown fields (forward compat)
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in known})


# ─────────────────────────────────────────────────────────────────
# Path helpers
# ─────────────────────────────────────────────────────────────────
def get_jobs_root() -> Path:
    """Return the jobs root dir. Override via $PA_JOBS_DIR."""
    import os
    env_root = os.environ.get("PA_JOBS_DIR", "").strip()
    if env_root:
        return Path(env_root)
    return DEFAULT_JOBS_DIR


def get_job_dir(job_id: str) -> Path:
    """Return the per-job dir. Does NOT check if it exists."""
    if not job_id or not re.match(r"^[a-zA-Z0-9_\-]+$", job_id):
        raise ValueError(
            f"invalid job_id: {job_id!r}. "
            f"Must match [a-zA-Z0-9_-]+ (alphanumeric, underscore, dash). "
            f"Got: {job_id!r}"
        )
    return get_jobs_root() / job_id


def get_manifest_path(job_id: str) -> Path:
    return get_job_dir(job_id) / "manifest.json"


def get_log_path(job_id: str) -> Path:
    return get_job_dir(job_id) / "log.txt"


# ─────────────────────────────────────────────────────────────────
# Manifest read / write
# ─────────────────────────────────────────────────────────────────
def read_manifest(job_id: str) -> Optional[JobManifest]:
    """Read job manifest.json. Returns None if not found."""
    p = get_manifest_path(job_id)
    if not p.exists():
        return None
    try:
        return JobManifest.from_dict(json.loads(p.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, KeyError, ValueError):
        return None


def write_manifest(manifest: JobManifest) -> None:
    """Write job manifest.json atomically (via temp file + rename)."""
    p = get_manifest_path(manifest.job_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    tmp.replace(p)  # atomic on POSIX; near-atomic on Windows


def list_jobs() -> List[Tuple[str, JobManifest]]:
    """List all jobs in jobs root. Returns [(job_id, manifest), ...] sorted by created_at desc."""
    root = get_jobs_root()
    if not root.exists():
        return []
    out = []
    for d in root.iterdir():
        if not d.is_dir():
            continue
        m = read_manifest(d.name)
        if m is not None:
            out.append((d.name, m))
    # Sort by created_at desc (newest first)
    out.sort(key=lambda x: x[1].created_at, reverse=True)
    return out


# ─────────────────────────────────────────────────────────────────
# Log parsing
# ─────────────────────────────────────────────────────────────────
def parse_log_counts(log_text: str) -> Dict[str, int]:
    """Parse the log.txt for n_total / n_success / n_failed / n_skipped counts.

    Looks for the lines written by `pa fetch-pdf-batch` failure report:
        - Total entries: N
        - Success: N
        - Failure: N
        - Skipped (timeout): N

    Returns dict with 0 defaults if not found.
    """
    out = {"n_total": 0, "n_success": 0, "n_failed": 0, "n_skipped": 0}
    patterns = {
        "n_total": re.compile(r"^\s*-\s*Total entries:\s*(\d+)", re.MULTILINE),
        "n_success": re.compile(r"^\s*-\s*Success:\s*(\d+)", re.MULTILINE),
        "n_failed": re.compile(r"^\s*-\s*Failure:\s*(\d+)", re.MULTILINE),
        "n_skipped": re.compile(r"^\s*-\s*Skipped\s*\(timeout\):\s*(\d+)", re.MULTILINE),
    }
    for key, pat in patterns.items():
        m = pat.search(log_text)
        if m:
            out[key] = int(m.group(1))
    return out


def extract_last_error(log_text: str) -> Optional[str]:
    """Extract last error line from the failure report table.

    Looks for `| key | doi | error | time |` rows. Returns last non-empty error.
    """
    # Find rows like: | 1 | `key` | 10.1234/... | some error message | 1.2 |
    pattern = re.compile(r"^\|\s*\d+\s*\|\s*`[^`]+`\s*\|\s*[^|]+\|\s*([^|]+?)\s*\|\s*[\d.]+\s*\|", re.MULTILINE)
    matches = pattern.findall(log_text)
    for err in reversed(matches):
        err = err.strip()
        if err and err != "unknown":
            return err[:200]
    return None


# ─────────────────────────────────────────────────────────────────
# Subprocess wrappers
# ─────────────────────────────────────────────────────────────────
def start_job(
    job_id: str,
    input_file: Path,
    output_dir: Path,
    prefer: str = "auto",
    max_total_sec: int = 1800,
) -> int:
    """Start a job. Returns the subprocess returncode.

    Side effects:
        - Creates ~/.paper-agent/jobs/<job_id>/{manifest.json, log.txt}
        - Updates manifest as it goes (created_at -> running -> completed/failed)
        - log.txt captures stdout + stderr from pa fetch-pdf-batch

    Sync: this is a blocking call. For long-running jobs, the user
    runs it in a terminal and `pa jobs tail/status/resume` in another.
    """
    job_dir = get_job_dir(job_id)
    job_dir.mkdir(parents=True, exist_ok=True)

    # Initial manifest
    manifest = JobManifest(
        job_id=job_id,
        input_file=str(input_file),
        output_dir=str(output_dir),
        prefer=prefer,
        status=STATUS_RUNNING,
        started_at=datetime.now().isoformat(timespec="seconds"),
    )
    write_manifest(manifest)

    # Run pa fetch-pdf-batch in subprocess
    log_path = get_log_path(job_id)
    cmd = [
        sys.executable, "-m", "pa_cli.cli", "fetch-pdf-batch",
        str(input_file), "--out", str(output_dir),
    ]
    if prefer != "auto":
        cmd.extend(["--prefer", prefer])
    cmd.extend(["--skip-existing"])  # default behavior for jobs

    manifest.pid = None  # subprocess.Popen is not used; we run sync
    write_manifest(manifest)

    log_fh = log_path.open("w", encoding="utf-8", errors="replace")
    log_fh.write(f"# pa jobs: {job_id}\n")
    log_fh.write(f"# command: {' '.join(cmd)}\n")
    log_fh.write(f"# started_at: {manifest.started_at}\n")
    log_fh.write(f"---\n")
    log_fh.flush()

    try:
        result = subprocess.run(
            cmd,
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            timeout=max_total_sec,
            cwd=str(Path.cwd()),
        )
        returncode = result.returncode
    except subprocess.TimeoutExpired:
        log_fh.write(f"\n[pa jobs] TIMEOUT after {max_total_sec}s\n")
        returncode = -1
        manifest.status = STATUS_INTERRUPTED
    except KeyboardInterrupt:
        log_fh.write(f"\n[pa jobs] INTERRUPTED by user (Ctrl+C)\n")
        returncode = -2
        manifest.status = STATUS_INTERRUPTED
    finally:
        log_fh.close()

    # Final manifest update from log
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    counts = parse_log_counts(log_text)
    manifest.n_total = counts["n_total"]
    manifest.n_success = counts["n_success"]
    manifest.n_failed = counts["n_failed"]
    manifest.n_skipped = counts["n_skipped"]
    manifest.last_error = extract_last_error(log_text)
    manifest.finished_at = datetime.now().isoformat(timespec="seconds")

    if manifest.status != STATUS_INTERRUPTED:
        if returncode == 0 and manifest.n_failed == 0:
            manifest.status = STATUS_COMPLETED
        elif returncode == 0 and manifest.n_failed > 0:
            # Returned 0 but had failures — mark completed with failures
            manifest.status = STATUS_COMPLETED
        else:
            manifest.status = STATUS_FAILED

    write_manifest(manifest)
    return returncode


def resume_job(job_id: str) -> int:
    """Re-run a job. Same args, but `--skip-existing` will skip entries
    that already have a PDF on disk (so only failed/missing are retried).

    Returns the subprocess returncode. Updates manifest in place.
    """
    m = read_manifest(job_id)
    if m is None:
        raise FileNotFoundError(f"job not found: {job_id}")
    if m.status == STATUS_RUNNING:
        raise RuntimeError(f"job {job_id} is currently running; cannot resume")

    return start_job(
        job_id=job_id,
        input_file=Path(m.input_file),
        output_dir=Path(m.output_dir),
        prefer=m.prefer,
    )


# ─────────────────────────────────────────────────────────────────
# Display helpers
# ─────────────────────────────────────────────────────────────────
def format_status_line(job_id: str, m: JobManifest) -> str:
    """One-line summary for `pa jobs list`."""
    pct = (m.n_success / m.n_total * 100) if m.n_total else 0.0
    return (
        f"{job_id:30s}  {m.status:11s}  "
        f"n={m.n_success:3d}/{m.n_total:3d} ({pct:5.1f}%)  "
        f"failed={m.n_failed:3d}  skipped={m.n_skipped:3d}  "
        f"created={m.created_at[:19]}"
    )


def format_status_block(m: JobManifest) -> str:
    """Multi-line status block for `pa jobs status <id>`."""
    pct = (m.n_success / m.n_total * 100) if m.n_total else 0.0
    lines = [
        f"job_id:     {m.job_id}",
        f"status:     {m.status}",
        f"input_file: {m.input_file}",
        f"output_dir: {m.output_dir}",
        f"prefer:     {m.prefer}",
        f"created_at: {m.created_at}",
        f"started_at: {m.started_at or '-'}",
        f"finished_at:{m.finished_at or '-'}",
        "",
        f"progress:   {m.n_success}/{m.n_total}  ({pct:.1f}%)",
        f"failed:     {m.n_failed}",
        f"skipped:    {m.n_skipped}",
        f"last_error: {m.last_error or '-'}",
    ]
    return "\n".join(lines)


def tail_log(job_id: str, n: int = 50) -> List[str]:
    """Return last N lines of log.txt. Empty list if log doesn't exist."""
    p = get_log_path(job_id)
    if not p.exists():
        return []
    # Read last N lines efficiently (avoids loading huge logs)
    try:
        # Read all lines and slice (acceptable for typical log sizes)
        with p.open("r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        return [line.rstrip("\n") for line in lines[-n:]]
    except OSError:
        return []
