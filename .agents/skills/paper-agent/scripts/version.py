#!/usr/bin/env python3
"""Probe the configured backend and browser instead of the host interpreter."""
from __future__ import annotations
import argparse
from contextlib import redirect_stdout
import importlib
import json
import platform
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pa_root import find_pa_python, find_pa_root


def runtime_probe():
    info = {"runtime_python_version": platform.python_version(), "optional_deps": {}}
    try:
        from pa_cli import __version__
        info['pa_cli_version'] = __version__
    except ImportError as exc:
        info.update(pa_cli_version=None, pa_cli_error=str(exc))
    for dep in ('playwright', 'requests', 'bibtexparser', 'fitz', 'yaml'):
        try:
            importlib.import_module(dep)
            info['optional_deps'][dep] = {'installed': True}
        except ImportError:
            info['optional_deps'][dep] = {'installed': False}
    info['jats_to_pdf_available'] = False
    if info['optional_deps']['playwright']['installed']:
        try:
            from pa_cli.fetch_deadline import run_fetch
            check=run_fetch({'_operation':'browser_status','render':True},10)
            info['jats_to_pdf_available']=check.get('jats_to_pdf_available') is True
            if check.get('error'):info['browser_error']='Browser check unavailable or timed out.'
        except Exception as exc:
            info['browser_error'] = type(exc).__name__+': browser check unavailable.'
    return info


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--as-json', action='store_true')
    parser.add_argument('--runtime-probe', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.runtime_probe:
        # Optional libraries may print import warnings; keep the JSON channel clean.
        with redirect_stdout(sys.stderr):
            info = runtime_probe()
        print(json.dumps(info))
        return 0
    root = find_pa_root()
    runtime = find_pa_python(root)
    skill = Path(__file__).resolve().parents[1] / 'SKILL.md'
    match = re.search(r'^\s+version:\s*(\S+)', skill.read_text(encoding='utf-8'), re.M)
    info = {'skill': 'paper-agent', 'skill_version': match[1].strip('"\'') if match else None,
            'python': platform.python_version(), 'platform': platform.system(),
            'runtime_python': runtime, 'pa_root': str(root) if root else None}
    try:
        # -c preserves cwd import precedence for a configured source checkout.
        script = Path(__file__).resolve()
        probe = subprocess.run([runtime, '-c',
            'import runpy,sys; sys.argv=[sys.argv[1],"--runtime-probe"]; runpy.run_path(sys.argv[0],run_name="__main__")',
            str(script)], cwd=str(root) if root else None, capture_output=True,
            text=True, encoding='utf-8', timeout=30)
        if probe.returncode:
            raise RuntimeError(probe.stderr[-1000:])
        info.update(json.loads(probe.stdout))
    except (OSError, subprocess.SubprocessError, ValueError, RuntimeError) as exc:
        info.update(pa_cli_version=None, pa_cli_error=str(exc), jats_to_pdf_available=False)
    info['recommendation'] = ('OK' if info.get('jats_to_pdf_available') else
        'Backend available; install or repair Chromium for JATS-to-PDF.' if info.get('pa_cli_version') else
        'Backend unavailable; check runtime.local.json and run bootstrap.py --check.')
    print(json.dumps(info, indent=2))
    return 0 if info.get('pa_cli_version') else 1


if __name__ == '__main__':
    raise SystemExit(main())
