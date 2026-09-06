"""Shared process and download-result handling for skill wrappers."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


def find_pa_python(root: Path) -> str:
    """Honor explicit selection, then repository venvs, then this interpreter."""
    override = os.environ.get('PAPER_AGENT_PYTHON')
    if override:
        candidate = Path(override).expanduser().resolve()
        if not candidate.is_file():
            raise FileNotFoundError(f'PAPER_AGENT_PYTHON does not exist: {candidate}')
        return str(candidate)
    for directory in ('.venv-codex', '.venv'):
        for relative in ('Scripts/python.exe', 'bin/python'):
            candidate = root / directory / relative
            if candidate.is_file():
                return str(candidate)
    return sys.executable


def run_pa(cmd, *, cwd, timeout):
    """Use one interpreter and explicit UTF-8 for both ends of the subprocess."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUTF8='1')
    return subprocess.run(
        [find_pa_python(Path(cwd)), *cmd[1:]], cwd=cwd, timeout=timeout,
        capture_output=True, text=True, encoding='utf-8', errors='replace', env=env,
    )


def emit_result(data, status, exit_code=0):
    """Downloads emit exactly one JSON object; non-success goes to stderr."""
    data = dict(data, status=status, exit_code=exit_code)
    print(json.dumps(data, ensure_ascii=True, indent=2),
          file=sys.stdout if exit_code == 0 else sys.stderr)
    return exit_code


def json_object(text):
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError('Expected a JSON object')
    return data


def validate_pdf(raw_path, base: Path):
    """Check file signature and EOF, not document identity or full PDF syntax."""
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ValueError('Download result has no file path')
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = base / path
    path = path.resolve()
    with path.open('rb') as handle:
        if handle.read(5) != b'%PDF-':
            raise ValueError(f'Not a PDF: {path}')
        handle.seek(0, 2)
        size = handle.tell()
        handle.seek(max(0, size - 1024))
        if not handle.read().rstrip().endswith(b'%%EOF'):
            raise ValueError(f'PDF has no final EOF marker: {path}')
    return path, size


def validate_batch(summary, base: Path):
    """Recount outcomes from verified files, including skip-existing results."""
    rows = summary.get('results')
    total = summary.get('n_total')
    if (not isinstance(rows, list) or type(total) is not int or total < 0
            or total != len(rows) or not all(isinstance(row, dict) for row in rows)):
        raise ValueError('Incomplete or invalid batch summary')
    success = failure = skipped = verified = size = 0
    for row in rows:
        if row.get('success') is True:
            try:
                path, actual_size = validate_pdf(row.get('out_path'), base)
                row.update(out_path=str(path), size_bytes=actual_size,
                           validation='signature_and_eof')
                verified += 1
                size += actual_size
                if row.get('error') == 'skipped-existing':
                    skipped += 1
                else:
                    success += 1
                continue
            except (OSError, ValueError) as exc:
                row.update(success=False, error=f'invalid_pdf: {exc}', size_bytes=0)
        # Missing/non-boolean success is not evidence of a successful download.
        row['success'] = False
        if row.get('error') == 'global-timeout':
            skipped += 1
        else:
            failure += 1
    summary.update(n_success=success, n_failure=failure, n_skipped=skipped,
                   total_size_bytes=size)
    status = 'success' if verified == total else ('partial' if verified else 'failed')
    return summary, status
