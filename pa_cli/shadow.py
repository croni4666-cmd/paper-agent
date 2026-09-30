"""M3 local shadow harness. No network provider or human-label writes."""
from __future__ import annotations

import json
import math
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from .evidence import _hash, _validate
from .provenance import inspect_artifact

VERSION = 'shadow-m3-1'
APP_ID = 1346458451
TASKS = {'relevance', 'evidence_support', 'population_match', 'study_design',
         'result_direction', 'field_presence'}


def _dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


class OfflineProvider(Protocol):
    offline: bool

    def identity(self) -> dict: ...

    def evaluate(self, packet: dict, rubric: dict) -> dict: ...


class FixtureProvider:
    """Synthetic answers supplied by the caller; never scientific evidence."""
    offline = True

    def __init__(self, probabilities):
        self.probabilities = dict(probabilities)

    def identity(self):
        return {'name': type(self).__name__, 'module': type(self).__module__,
                'version': 'fixture-1', 'configuration_hash': _hash(self.probabilities)}

    def evaluate(self, packet, rubric):
        return {'probabilities': dict(self.probabilities), 'model': 'offline-fixture-1'}


def _connect(path):
    conn = sqlite3.connect(str(path), timeout=10)
    try:
        app_id = conn.execute('PRAGMA application_id').fetchone()[0]
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        if (tables or app_id) and app_id != APP_ID:
            raise ValueError('use a dedicated M3 database, not an existing application database')
        conn.execute('PRAGMA foreign_keys=ON')
        conn.executescript(f'''
        PRAGMA application_id={APP_ID};
        CREATE TABLE IF NOT EXISTS requests (
            request_id TEXT PRIMARY KEY, created_at TEXT NOT NULL,
            artifact_sha256 TEXT NOT NULL, packet_json TEXT NOT NULL,
            provenance_json TEXT NOT NULL, rubric_json TEXT NOT NULL,
            provider_json TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS events (
            event_id INTEGER PRIMARY KEY, request_id TEXT NOT NULL REFERENCES requests(request_id),
            created_at TEXT NOT NULL, status TEXT NOT NULL,
            details_json TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS suggestions (
            request_id TEXT PRIMARY KEY REFERENCES requests(request_id),
            answer_json TEXT NOT NULL, synthetic INTEGER NOT NULL CHECK(synthetic=1));
        CREATE TABLE IF NOT EXISTS adjudications (
            adjudication_id TEXT PRIMARY KEY, artifact_sha256 TEXT NOT NULL,
            packet_hash TEXT NOT NULL, task TEXT NOT NULL,
            rubric_version TEXT NOT NULL, rubric_hash TEXT NOT NULL,
            label TEXT NOT NULL, reviewer TEXT NOT NULL, created_at TEXT NOT NULL,
            split TEXT NOT NULL CHECK(split IN ('development','calibration','holdout')),
            blinded INTEGER NOT NULL CHECK(blinded IN (0,1)),
            source TEXT NOT NULL CHECK(source='human'),
            CHECK(split!='holdout' OR blinded=1));
        ''')
        for table in ('requests', 'events', 'suggestions', 'adjudications'):
            for action in ('UPDATE', 'DELETE'):
                conn.execute(f'''CREATE TRIGGER IF NOT EXISTS {table}_no_{action.lower()}
                    BEFORE {action} ON {table} BEGIN
                    SELECT RAISE(ABORT, 'append-only shadow record'); END''')
        conn.commit()
        return conn
    except Exception:
        conn.close()
        raise


def _event(conn, request_id, status, details=None):
    conn.execute('INSERT INTO events(request_id,created_at,status,details_json) VALUES(?,?,?,?)',
                 (request_id, datetime.now(timezone.utc).isoformat(), status, _dump(details or {})))


def _outcome(conn, request_id):
    row = conn.execute('SELECT status,details_json FROM events WHERE request_id=? ORDER BY event_id DESC LIMIT 1',
                       (request_id,)).fetchone()
    answer = conn.execute('SELECT answer_json FROM suggestions WHERE request_id=?', (request_id,)).fetchone()
    # A prior process may have crashed after dispatch. Never repeat it automatically.
    status = row[0] if row else 'unknown'
    if status in ('prepared', 'dispatched'):
        status = 'unknown'
    return {'request_id': request_id, 'status': status,
            'details': json.loads(row[1]) if row else {},
            'suggestion': json.loads(answer[0]) if answer else None,
            'external_upload_allowed': False}


def _check_rubric(rubric):
    if rubric.get('task') not in TASKS:
        raise ValueError('unsupported adjudication task')
    for field in ('version', 'question'):
        if not isinstance(rubric.get(field), str) or not rubric[field].strip() or len(rubric[field]) > 4000:
            raise ValueError(f'invalid rubric {field}')
    labels = rubric.get('labels')
    if (not isinstance(labels, list) or not 2 <= len(labels) <= 20
            or any(not isinstance(x, str) or not x.strip() or len(x) > 64 for x in labels)
            or len(set(labels)) != len(labels)):
        raise ValueError('rubric requires unique categorical labels')


def _check_packet(index, packet):
    _validate(index)
    if packet.get('packet_hash') != _hash({k:v for k,v in packet.items() if k != 'packet_hash'}):
        raise ValueError('packet integrity mismatch')
    if (packet.get('artifact_sha256') != index['artifact_sha256']
            or packet.get('index_hash') != index['index_hash']
            or packet.get('extractor') != index['extractor']):
        raise ValueError('packet and index do not describe the same artifact')
    by_id = {s['evidence_id']:s for s in index['spans']}
    if any(by_id.get(s['evidence_id']) != s for s in packet['evidence']):
        raise ValueError('packet contains unindexed evidence')
    if len(_dump(packet).encode('utf-8')) > 16000 or len(packet['evidence']) > 6:
        raise ValueError('M3 packet exceeds local pilot bounds')


def _answer(raw, labels):
    probabilities = raw['probabilities']
    if not isinstance(probabilities, dict) or set(probabilities) != set(labels):
        raise ValueError('answer labels do not match rubric')
    if any(type(p) not in (int, float) or not math.isfinite(p) or not 0 <= p <= 1
           for p in probabilities.values()):
        raise ValueError('invalid probability')
    if abs(sum(probabilities.values()) - 1.0) > 1e-6:
        raise ValueError('probabilities must sum to one')
    if not isinstance(raw.get('model'), str) or not 1 <= len(raw['model']) <= 200:
        raise ValueError('missing returned model')
    return {'label': max(labels, key=lambda label: probabilities[label]),
            'probabilities': probabilities, 'model': raw['model'],
            'synthetic': True, 'usable_as_truth': False}


def run_shadow(*, pdf, index, packet, fetch_result, rubric, db_path,
               provider: OfflineProvider, data_class='unknown', expected_title=None):
    """Persist before offline dispatch; reuse all prior outcomes without retries.

    Caller supplies a local M2 index and packet, fetch source context, a task
    rubric, and a dedicated local DB. Only trusted FixtureProvider instances
    are supported in M3. This is not a sandbox for arbitrary Python plugins.
    """
    if not isinstance(provider, FixtureProvider) or provider.offline is not True:
        raise ValueError('M3 supports only offline fixture providers')
    if Path(pdf).resolve() == Path(db_path).resolve():
        raise ValueError('database must not overwrite the source artifact')
    # Own immutable JSON snapshots; caller/provider mutation cannot change audit data.
    index, packet, rubric = json.loads(_dump([index, packet, rubric]))
    _check_rubric(rubric)
    _check_packet(index, packet)
    source = fetch_result.get('via_channel', '')
    if source.startswith('cache:'):
        source = source[6:]
    provenance = inspect_artifact(pdf, fetch_result['doi'], source, fetch_result.get('via_url'),
                                  data_class=data_class, expected_title=expected_title)
    provenance['identity']['expected_title'] = expected_title
    provenance['source_url_hash'] = _hash(fetch_result.get('via_url'))
    if provenance['artifact_sha256'] != index['artifact_sha256']:
        raise ValueError('source artifact changed; rebuild evidence index and packet')
    reasons = list(provenance['blocking_reasons'])
    if packet.get('status') != 'ready_for_local_review' or not packet['evidence'] or packet.get('missing_sections'):
        reasons.append('insufficient_evidence')
    if any(p['status'] != 'text_extracted' for p in index['pages']):
        reasons.append('extraction_needs_review')
    identity = provider.identity()
    request_id = _hash([VERSION, packet, rubric, provenance, identity])
    with closing(_connect(db_path)) as conn:
        with conn:
            conn.execute('BEGIN IMMEDIATE')
            if conn.execute('SELECT 1 FROM requests WHERE request_id=?', (request_id,)).fetchone():
                return _outcome(conn, request_id)
            conn.execute('INSERT INTO requests VALUES(?,?,?,?,?,?,?)',
                         (request_id, datetime.now(timezone.utc).isoformat(), index['artifact_sha256'],
                          _dump(packet), _dump(provenance), _dump(rubric), _dump(identity)))
            _event(conn, request_id, 'prepared')
            _event(conn, request_id, 'blocked' if reasons else 'dispatched', {'reasons':reasons})
        if reasons:
            return _outcome(conn, request_id)
        try:
            raw = provider.evaluate(json.loads(_dump(packet)), json.loads(_dump(rubric)))
        except Exception as exc:
            with conn:
                _event(conn, request_id, 'unknown', {'error_type':type(exc).__name__})
            return _outcome(conn, request_id)
        try:
            suggestion = _answer(raw, rubric['labels'])
        except (ValueError, TypeError, KeyError, AttributeError):
            with conn:
                _event(conn, request_id, 'invalid_response')
            return _outcome(conn, request_id)
        with conn:
            conn.execute('INSERT INTO suggestions VALUES(?,?,1)', (request_id, _dump(suggestion)))
            _event(conn, request_id, 'completed')
        return _outcome(conn, request_id)
