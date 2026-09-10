"""Bounded, private retrieval progress; never record URLs, paths or exception text."""
import functools
import json
from pathlib import Path
import time

_PATH = None
_STARTED = 0
_COUNT = 0
_EVENTS = []
STAGES = frozenset(('worker', 'arxiv', 'annas_search', 'annas_download', 'pmc',
                    'unpaywall', 'biorxiv', 'core', 'osf', 'chemrxiv', 'scihub', 'http', 'pdf_validation', 'cache_write', 'statistics'))

def configure(path):
    global _PATH, _STARTED, _COUNT, _EVENTS
    _PATH, _STARTED, _COUNT, _EVENTS = path, time.monotonic(), 0, []

def emit(stage, status):
    global _COUNT
    if not _PATH or stage not in STAGES:
        return
    _COUNT += 1
    _EVENTS.append(dict(stage=stage, status=status, sequence=_COUNT,
                        elapsed_sec=round(time.monotonic()-_STARTED, 3)))
    del _EVENTS[:-64]
    try:
        pending = Path(str(_PATH) + '.pending')
        with pending.open('w', encoding='utf-8') as f:
            for event in _EVENTS:
                f.write(json.dumps(event)+'\n')
        pending.replace(_PATH)
    except OSError:
        pass  # Diagnostics must not prevent retrieval.

def traced(stage):
    def decorate(function):
        @functools.wraps(function)
        def call(*args, **kwargs):
            emit(stage, 'started')
            try:
                result = function(*args, **kwargs)
            except Exception:
                emit(stage, 'exception')
                raise
            if isinstance(result, dict):
                status = 'failed' if result.get('error') or result.get('valid') is False else 'completed'
            elif stage == 'http' and isinstance(result, tuple):
                status = ('transport_error' if result[0] == 0 else
                          'http_error' if result[0] >= 400 else 'completed')
            elif isinstance(result, list) and not result:
                status = 'empty'
            else:
                status = 'completed'
            emit(stage, status)
            return result
        return call
    return decorate

def read_trace(path):
    events = []
    try:
        with open(path, 'rb') as stream:
            data = stream.read(16384).decode('utf-8', errors='ignore')
        for line in data.splitlines()[:64]:
            try:
                event = json.loads(line)
                if (event.get('stage') in STAGES and event.get('status') in
                    ('started','completed','failed','exception','transport_error','http_error','empty')
                    and type(event.get('elapsed_sec')) in (float, int)
                    and 0 <= event['elapsed_sec'] < 1e9):
                    clean = {key:event[key] for key in ('stage','status','elapsed_sec')}
                    if type(event.get('sequence')) is int and event['sequence'] > 0:
                        clean['sequence'] = event['sequence']
                    events.append(clean)
            except (ValueError, TypeError, AttributeError):
                continue
    except OSError:
        pass
    return events
