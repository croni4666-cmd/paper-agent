"""Local M3 review export. No predictions, human-label writes or network."""
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import tempfile
import uuid

from .evidence import _hash
from .shadow import APP_ID, _check_rubric


def _object(raw, limit=16000):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate key')
            result[key] = value
        return result
    def constant(value):
        raise ValueError('nonfinite JSON')
    if not isinstance(raw, str) or len(raw.encode('utf-8')) > limit:
        raise ValueError('oversized JSON')
    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    if not isinstance(value, dict):
        raise ValueError('object required')
    return value


def _digest(value):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
        raise ValueError('invalid digest')
    return value


def _review_evidence(packet):
    """Validate the same evidence structure at both export and import boundaries."""
    evidence = packet.get('evidence')
    if not isinstance(evidence, list) or not 1 <= len(evidence) <= 6:
        raise ValueError('nonempty bounded evidence required')
    excerpts, seen = [], set()
    for span in evidence:
        if not isinstance(span, dict):
            raise ValueError('invalid passage')
        eid = _digest(span.get('evidence_id'))
        page, text = span.get('page'), span.get('text')
        if eid in seen or type(page) is not int or page < 1 or not isinstance(text, str) or not text.strip():
            raise ValueError('invalid passage')
        seen.add(eid)
        excerpts.append({'evidence_id': eid, 'page': page, 'text': text})
    missing, pages = packet.get('missing_sections'), packet.get('pages_needing_review')
    if (not isinstance(missing, list) or len(missing) > 20
            or any(not isinstance(s, str) or len(s) > 100 for s in missing)
            or not isinstance(pages, list) or len(pages) > 500
            or any(type(n) is not int or n < 1 for n in pages)):
        raise ValueError('invalid completeness metadata')
    return excerpts, {'missing_sections': missing, 'pages_needing_review': pages}


def export_review(db_path, request_id, output_dir):
    """Publish a new directory containing review and coordinator JSON files."""
    if not isinstance(request_id, str) or not 1 <= len(request_id) <= 200:
        raise ValueError('invalid request ID')
    source = Path(db_path).resolve(strict=True)
    target = Path(output_dir).absolute()
    parent = target.parent.resolve(strict=True)
    target = parent / target.name
    if not source.is_file() or target.exists() or target.is_symlink():
        raise ValueError('existing source and new output required')
    conn = sqlite3.connect(source.as_uri() + '?mode=ro', uri=True, timeout=5)
    try:
        conn.execute('PRAGMA query_only=ON')
        conn.execute('BEGIN')
        if conn.execute('PRAGMA application_id').fetchone()[0] != APP_ID:
            raise ValueError('not an M3 ledger')
        sizes = conn.execute('SELECT length(CAST(packet_json AS BLOB)),length(CAST(rubric_json AS BLOB)) FROM requests WHERE request_id=?', (request_id,)).fetchone()
        if sizes is None or any(type(n) is not int or n > 16000 for n in sizes):
            raise ValueError('missing or oversized request')
        row = conn.execute('SELECT artifact_sha256,packet_json,rubric_json FROM requests WHERE request_id=?', (request_id,)).fetchone()
        artifact = _digest(row[0])
        packet, rubric = _object(row[1]), _object(row[2])
    finally:
        conn.close()
    _check_rubric(rubric)
    digest = _digest(packet.get('packet_hash'))
    if packet.get('artifact_sha256') != artifact or digest != _hash({k: v for k, v in packet.items() if k != 'packet_hash'}):
        raise ValueError('packet integrity mismatch')
    excerpts, completeness = _review_evidence(packet)
    review_id = uuid.uuid4().hex
    review = {'schema_version': 'blind-review-export-1', 'review_id': review_id,
              'rubric': {k: rubric[k] for k in ('task', 'version', 'question', 'labels')},
              'evidence': excerpts,
              'completeness': completeness,
              'notice': 'Selected passages only. Current PDF authenticity and completeness are not verified. Answers are masked; independent blinding is not established. Request more context when needed.'}
    manifest = {'schema_version': 'blind-review-coordinator-1', 'review_id': review_id,
                'request_id': request_id, 'artifact_sha256': artifact,
                'packet_hash': digest, 'rubric_hash': _hash(rubric),
                'review_hash': _hash(review), 'blinding_verified': False,
                'notice': 'Coordinator only. Share review.json alone. No human label or split is created.'}
    # Same-parent directory staging avoids publishing one file without the other.
    # A leftover lock after process termination requires operator inspection.
    lock = target.with_name(target.name + '.export-lock')
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    stage = None
    try:
        os.close(fd)
        if target.exists() or target.is_symlink():
            raise ValueError('output exists')
        stage = Path(tempfile.mkdtemp(prefix='.review-export-', dir=parent))
        for name, value in [('review.json', review), ('coordinator.json', manifest)]:
            with (stage / name).open('x', encoding='utf-8') as stream:
                json.dump(value, stream, ensure_ascii=True, indent=2, allow_nan=False)
                stream.write('\n')
                stream.flush()
                os.fsync(stream.fileno())
        if target.exists() or target.is_symlink():
            raise ValueError('output exists')
        stage.rename(target)
        stage = None
    finally:
        try:
            if stage is not None:
                shutil.rmtree(stage)
        finally:
            lock.unlink()
    return {'review_id': review_id, 'output_dir': str(target), 'network_called': False,
            'human_label_written': False, 'blinding_verified': False}
