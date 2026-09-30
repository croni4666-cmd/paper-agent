"""Local frozen M5 cases, assignments and study-level exposure history."""
from contextlib import closing
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import uuid

from .evidence import _hash
from .jev_review import _digest, _object, _review_evidence
from .shadow import APP_ID as SHADOW_ID, _check_rubric

APP_ID = 1346458453
VERSION = 'evaluation-m5-3'


def _text(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 200:
        raise ValueError('nonempty bounded identifier required')
    if value != value.strip() or any(ord(c) < 32 for c in value):
        raise ValueError('invalid identifier')
    return value


def _now():
    return datetime.now(timezone.utc).isoformat()


def _file(path):
    with Path(path).open('rb') as stream:
        data = stream.read(256001)
    if len(data) > 256000:
        raise ValueError('oversized review artifact')
    # Exports escape Unicode, so on-disk JSON may exceed the packet byte limit.
    return _object(data.decode('utf-8'), limit=256000)


def _source_case(conn, bundle):
    review, meta = _file(bundle / 'review.json'), _file(bundle / 'coordinator.json')
    if (review.get('schema_version') != 'blind-review-export-1'
            or meta.get('schema_version') != 'blind-review-coordinator-1'
            or review.get('review_id') != meta.get('review_id')
            or _hash(review) != meta.get('review_hash')):
        raise ValueError('bundle integrity mismatch')
    _text(review['review_id'])
    rid = _text(meta.get('request_id'))
    sizes = conn.execute('SELECT length(CAST(packet_json AS BLOB)),length(CAST(rubric_json AS BLOB)) FROM requests WHERE request_id=?', (rid,)).fetchone()
    if sizes is None or any(type(n) is not int or n > 16000 for n in sizes):
        raise ValueError('missing or oversized source case')
    row = conn.execute('SELECT artifact_sha256,packet_json,rubric_json FROM requests WHERE request_id=?', (rid,)).fetchone()
    packet, rubric = _object(row[1]), _object(row[2])
    _check_rubric(rubric)
    artifact = _digest(row[0])
    packet_hash = _digest(packet.get('packet_hash'))
    rubric_hash = _hash(rubric)
    if (packet.get('artifact_sha256') != artifact
            or packet_hash != _hash({k: v for k, v in packet.items() if k != 'packet_hash'})
            or [meta.get(k) for k in ('artifact_sha256', 'packet_hash', 'rubric_hash')]
            != [artifact, packet_hash, rubric_hash]):
        raise ValueError('source binding mismatch')
    spans, completeness = _review_evidence(packet)
    expected = {
        'schema_version': 'blind-review-export-1', 'review_id': review['review_id'],
        'rubric': {k: rubric[k] for k in ('task', 'version', 'question', 'labels')},
        'evidence': spans,
        'completeness': completeness,
        'notice': 'Selected passages only. Current PDF authenticity and completeness are not verified. Answers are masked; independent blinding is not established. Request more context when needed.',
    }
    if review != expected:
        raise ValueError('review content differs from frozen source')
    return {'case_id': _hash([artifact, packet_hash, rubric_hash]),
            'artifact': artifact, 'packet_hash': packet_hash, 'rubric_hash': rubric_hash,
            'review_id': review['review_id'], 'review_hash': _hash(review),
            'request_id': rid, 'rubric': expected['rubric'],
            'evidence_ids': [s['evidence_id'] for s in spans]}


def freeze_plan(plan, base_dir, db_path, *, operator, grouping_confirmed=False):
    """Create a NEW evaluation ledger; never change splits in an existing one."""
    _text(operator)
    if grouping_confirmed is not True:
        raise ValueError('explicit grouping attestation required')
    if set(plan) != {'evaluation_id', 'shadow_db', 'cases'}:
        raise ValueError('invalid plan fields')
    evaluation_id = _text(plan['evaluation_id'])
    entries = plan['cases']
    if not isinstance(entries, list) or not 1 <= len(entries) <= 10000:
        raise ValueError('bounded cases required')
    base = Path(base_dir).resolve(strict=True)
    source = (base / plan['shadow_db']).resolve(strict=True)
    cases, groups, artifacts, seen, reviews = [], {}, {}, set(), set()
    with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True, timeout=5)) as conn:
        conn.execute('PRAGMA query_only=ON')
        conn.execute('BEGIN')
        if conn.execute('PRAGMA application_id').fetchone()[0] != SHADOW_ID:
            raise ValueError('not an M3 database')
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != {'bundle', 'study_id', 'split', 'grouping_reference'}:
                raise ValueError('invalid case fields')
            study = _text(entry['study_id'])
            reference = _text(entry['grouping_reference'])
            split = entry['split']
            if split not in ('development', 'calibration', 'holdout'):
                raise ValueError('invalid split')
            case = _source_case(conn, (base / entry['bundle']).resolve(strict=True))
            if case['case_id'] in seen or case['review_id'] in reviews:
                raise ValueError('duplicate case or export')
            if groups.get(study, split) != split or artifacts.get(case['artifact'], study) != study:
                raise ValueError('study split or artifact grouping conflict')
            seen.add(case['case_id']); reviews.add(case['review_id'])
            groups[study] = split; artifacts[case['artifact']] = study
            cases.append({**case, 'study_id': study, 'split': split, 'grouping_reference': reference})
    target = Path(db_path).absolute()
    # Exclusive creation refuses all existing databases, including empty files.
    fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    try:
        with closing(sqlite3.connect(target)) as conn:
            with conn:
                conn.execute('BEGIN IMMEDIATE')
                conn.execute(f'PRAGMA application_id={APP_ID}')
                statements = [
                    'CREATE TABLE config(version TEXT NOT NULL,evaluation_id TEXT NOT NULL,operator TEXT NOT NULL,created_at TEXT NOT NULL,plan_hash TEXT NOT NULL,grouping_confirmed INTEGER NOT NULL CHECK(grouping_confirmed=1))',
                    'CREATE TABLE cases(case_id TEXT PRIMARY KEY,study_id TEXT NOT NULL,split TEXT NOT NULL,review_id TEXT UNIQUE NOT NULL,details TEXT NOT NULL)',
                    'CREATE TABLE assignments(assignment_id TEXT PRIMARY KEY,case_id TEXT NOT NULL REFERENCES cases(case_id),reviewer TEXT NOT NULL,created_at TEXT NOT NULL,operator TEXT NOT NULL,no_prior_exposure_attested INTEGER NOT NULL CHECK(no_prior_exposure_attested=1),UNIQUE(case_id,reviewer))',
                    'CREATE TABLE exposures(event_id TEXT PRIMARY KEY,study_id TEXT NOT NULL,operator TEXT NOT NULL,reference TEXT NOT NULL,created_at TEXT NOT NULL)',
                    'CREATE TABLE judgments(submission_id TEXT PRIMARY KEY,assignment_id TEXT NOT NULL REFERENCES assignments(assignment_id),supersedes TEXT UNIQUE REFERENCES judgments(submission_id),payload TEXT NOT NULL,created_at TEXT NOT NULL)',
                    'CREATE UNIQUE INDEX initial_judgment ON judgments(assignment_id) WHERE supersedes IS NULL',
                    'CREATE TABLE judgment_freeze(singleton INTEGER PRIMARY KEY CHECK(singleton=1),operator TEXT NOT NULL,reference TEXT NOT NULL,created_at TEXT NOT NULL,snapshot TEXT NOT NULL,snapshot_hash TEXT NOT NULL)',
                    'CREATE TABLE resolutions(resolution_id TEXT PRIMARY KEY,case_id TEXT NOT NULL REFERENCES cases(case_id),supersedes TEXT UNIQUE REFERENCES resolutions(resolution_id),payload TEXT NOT NULL,created_at TEXT NOT NULL)',
                    'CREATE UNIQUE INDEX initial_resolution ON resolutions(case_id) WHERE supersedes IS NULL',
                ]
                for sql in statements:
                    conn.execute(sql)
                conn.execute('INSERT INTO config VALUES(?,?,?,?,?,?)', (VERSION, evaluation_id, operator, _now(), _hash(cases), 1))
                for case in cases:
                    conn.execute('INSERT INTO cases VALUES(?,?,?,?,?)', (case['case_id'], case['study_id'], case['split'], case['review_id'], json.dumps(case, sort_keys=True)))
                for table in ('config', 'cases', 'assignments', 'exposures', 'judgments', 'judgment_freeze', 'resolutions'):
                    for action in ('UPDATE', 'DELETE'):
                        conn.execute(f"CREATE TRIGGER {table}_no_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'append-only evaluation record'); END")
    except BaseException:
        # Keep a failed/partial ledger for inspection; never silently replace it.
        raise
    return {'evaluation_id': evaluation_id, 'cases': len(cases), 'studies': len(groups),
            'splits_frozen': True, 'network_called': False, 'human_label_written': False}


def _connect(path, readonly=False):
    path = Path(path).resolve(strict=True)
    conn = sqlite3.connect(path.as_uri() + ('?mode=ro' if readonly else '?mode=rw'), uri=True, timeout=5)
    try:
        conn.execute('PRAGMA foreign_keys=ON')
        conn.execute('BEGIN' if readonly else 'BEGIN IMMEDIATE')
        if conn.execute('PRAGMA application_id').fetchone()[0] != APP_ID:
            raise ValueError('not an evaluation database')
        config = conn.execute('SELECT version FROM config').fetchall()
        if config not in ([(VERSION,)], [('evaluation-m5-2',)]):
            raise ValueError('unsupported evaluation schema')
        return conn
    except BaseException:
        conn.close()
        raise


def assign_review(db_path, review_id, *, reviewer, operator, no_prior_exposure=False):
    for value in (review_id, reviewer, operator):
        _text(value)
    if no_prior_exposure is not True:
        raise ValueError('reviewer no-prior-exposure attestation required')
    with closing(_connect(db_path)) as conn, conn:
        if conn.execute('SELECT 1 FROM judgment_freeze').fetchone():
            raise ValueError('judgments frozen; assignments closed')
        case = conn.execute('SELECT case_id,study_id,split FROM cases WHERE review_id=?', (review_id,)).fetchone()
        if case is None:
            raise ValueError('review not in frozen plan')
        exposed = conn.execute('SELECT 1 FROM exposures WHERE study_id=? LIMIT 1', (case[1],)).fetchone() is not None
        if exposed:
            raise ValueError('study has recorded exposure; blind assignment refused')
        prior = conn.execute('SELECT assignment_id FROM assignments WHERE case_id=? AND reviewer=?', (case[0], reviewer)).fetchone()
        assignment_id = prior[0] if prior else uuid.uuid4().hex
        if prior is None:
            conn.execute('INSERT INTO assignments VALUES(?,?,?,?,?,?)', (assignment_id, case[0], reviewer, _now(), operator, 1))
    return {'assignment_id': assignment_id, 'review_id': review_id, 'reused': prior is not None,
            'no_prior_exposure_attested': True, 'blinding_verified': False, 'human_label_written': False}


def record_exposure(db_path, study_id, *, operator, evidence_reference):
    for value in (study_id, operator, evidence_reference):
        _text(value)
    with closing(_connect(db_path)) as conn, conn:
        if conn.execute('SELECT 1 FROM cases WHERE study_id=? LIMIT 1', (study_id,)).fetchone() is None:
            raise ValueError('unknown study')
        event_id = uuid.uuid4().hex
        conn.execute('INSERT INTO exposures VALUES(?,?,?,?,?)', (event_id, study_id, operator, evidence_reference, _now()))
    return {'event_id': event_id, 'study_id': study_id, 'blind_eligibility_revoked': True,
            'human_label_written': False}


def evaluation_status(db_path):
    with closing(_connect(db_path, readonly=True)) as conn:
        evaluation_id = conn.execute('SELECT evaluation_id FROM config').fetchone()[0]
        assignments = [dict(assignment_id=a, review_id=r, reviewer=u, split=s,
                            exposure_recorded=bool(e), blind_candidate=not bool(e))
                       for a, r, u, s, e in conn.execute(
                           'SELECT a.assignment_id,c.review_id,a.reviewer,c.split,EXISTS(SELECT 1 FROM exposures e WHERE e.study_id=c.study_id) FROM assignments a JOIN cases c ON c.case_id=a.case_id ORDER BY a.created_at,a.assignment_id')]
        splits = dict(conn.execute('SELECT split,count(*) FROM cases GROUP BY split'))
        exposed = conn.execute('SELECT count(DISTINCT study_id) FROM exposures').fetchone()[0]
        judgment_count = conn.execute('SELECT count(*) FROM judgments').fetchone()[0]
        frozen = conn.execute('SELECT snapshot_hash FROM judgment_freeze').fetchone()
        has_resolutions = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='resolutions'").fetchone()
        resolution_count = conn.execute('SELECT count(*) FROM resolutions').fetchone()[0] if has_resolutions else 0
    return {'evaluation_id': evaluation_id, 'cases_by_split': splits, 'exposed_studies': exposed,
            'assignments': assignments, 'blinding_verified': False, 'human_label_written': False,
            'judgment_records': judgment_count, 'judgments_frozen': frozen is not None,
            'resolution_records': resolution_count,
            'frozen_snapshot_hash': frozen[0] if frozen else None}
