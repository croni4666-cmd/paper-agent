"""Smoke test: import every pa_cli module and report failures.

Run from repo root:
  python test_output/_import_smoke.py
"""
import importlib
import pkgutil
import sys
from pathlib import Path

# Make pa_cli importable when running from test_output/
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pa_cli

failed = []
succeeded = []
for finder, name, ispkg in pkgutil.iter_modules(pa_cli.__path__):
    if name in ('__main__',):
        continue
    mod_name = f'pa_cli.{name}'
    try:
        importlib.import_module(mod_name)
        succeeded.append(mod_name)
    except Exception as e:
        failed.append((mod_name, str(e)[:200]))

print(f'SUCCEEDED ({len(succeeded)}):')
for m in succeeded:
    print(f'  {m}')

print(f'\nFAILED ({len(failed)}):')
for m, e in failed:
    print(f'  {m}: {e}')
