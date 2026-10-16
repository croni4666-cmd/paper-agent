#!/usr/bin/env python3
"""Check or install paper-agent in the same runtime used by the wrappers."""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pa_root import find_pa_python, find_pa_root


def check_runtime(python, root):
    try:
        result = subprocess.run([python, '-m', 'pa_cli.cli', '--help'],
            cwd=str(root), capture_output=True, text=True, encoding='utf-8', timeout=30)
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', help='Explicit source checkout to check/install')
    parser.add_argument('--check', action='store_true', help='Check only; never installs')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    root = Path(args.repo).expanduser().resolve() if args.repo else find_pa_root()
    result = {'step': 'check', 'repo_found': str(root) if root else None}
    if root is None or not (root / 'pa_cli/__init__.py').is_file():
        result.update(status='repo_not_found', message='Set a valid --repo or runtime.local.json root.')
        print(json.dumps(result, indent=2))
        return 1
    python = find_pa_python(root)
    result['runtime_python'] = python
    ready = check_runtime(python, root)
    result['pa_cli_importable'] = ready
    if ready or args.check:
        result['status'] = 'ok' if ready else 'runtime_unavailable'
        print(json.dumps(result, indent=2))
        return 0 if ready else 1
    if not any((root / name).is_file() for name in ('pyproject.toml', 'setup.py')):
        result['status'] = 'not_installable'
        print(json.dumps(result, indent=2))
        return 1
    command = [python, '-m', 'pip', 'install', '-e', str(root)]
    result.update(step='install', install_command=command)
    try:
        install = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', timeout=300)
        result['install_success'] = install.returncode == 0
        if install.returncode:
            result.update(status='install_failed', install_output_tail=(install.stdout + install.stderr)[-1000:])
            print(json.dumps(result, indent=2))
            return 2
    except (OSError, subprocess.SubprocessError) as exc:
        result.update(status='install_failed', message=str(exc))
        print(json.dumps(result, indent=2))
        return 2
    ready = check_runtime(python, root)
    result.update(status='ok' if ready else 'import_failed', pa_cli_importable_after=ready)
    print(json.dumps(result, indent=2))
    return 0 if ready else 3


if __name__ == '__main__':
    raise SystemExit(main())
