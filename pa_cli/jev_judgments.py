"""Explicit human submissions and immutable adjudication snapshots. No inference."""
from contextlib import closing
import json

from .evidence import _hash
from .jev_evaluation import _connect, _now, _text
from .jev_adjudication import latest_resolution, validate_resolution_basis


def submit_judgment(db_path, entry, *, human_confirmed=False):
    required = {'submission_id', 'assignment_id', 'reviewer', 'operator', 'outcome',
                'label', 'evidence_ids', 'reason_reference', 'supersedes'}
    if human_confirmed is not True or not isinstance(entry, dict) or set(entry) != required:
        raise ValueError('explicit human submission and exact entry fields required')
    # Own the input before validation/persistence; callers cannot change it mid-write.
    entry = json.loads(json.dumps(entry, allow_nan=False))
    for key in ('submission_id', 'assignment_id', 'reviewer', 'operator', 'reason_reference'):
        _text(entry[key])
    if entry['supersedes'] is not None:
        _text(entry['supersedes'])
    if entry['outcome'] not in ('label', 'abstain'):
        raise ValueError('label or abstain required')
    refs = entry['evidence_ids']
    if not isinstance(refs, list) or len(refs) > 6 or any(not isinstance(r, str) for r in refs) or len(refs) != len(set(refs)):
        raise ValueError('bounded unique evidence IDs required')
    payload = {**entry, 'source': 'human', 'human_confirmed': True}
    with closing(_connect(db_path)) as conn, conn:
        prior = conn.execute('SELECT payload FROM judgments WHERE submission_id=?', (entry['submission_id'],)).fetchone()
        if prior:
            if json.loads(prior[0]) != payload:
                raise ValueError('submission ID reused with changed content')
            return {'submission_id': entry['submission_id'], 'reused': True,
                    'human_label_written': False, 'network_called': False}
        if conn.execute('SELECT 1 FROM judgment_freeze').fetchone():
            raise ValueError('judgments are frozen')
        row = conn.execute('SELECT a.reviewer,c.study_id,c.details FROM assignments a JOIN cases c ON c.case_id=a.case_id WHERE a.assignment_id=?', (entry['assignment_id'],)).fetchone()
        if row is None or row[0] != entry['reviewer']:
            raise ValueError('reviewer does not match assignment')
        if conn.execute('SELECT 1 FROM exposures WHERE study_id=? LIMIT 1', (row[1],)).fetchone():
            raise ValueError('known exposure blocks blind judgment')
        case = json.loads(row[2])
        if any(r not in case['evidence_ids'] for r in refs):
            raise ValueError('evidence outside frozen case')
        if entry['outcome'] == 'label':
            if entry['label'] not in case['rubric']['labels'] or not refs:
                raise ValueError('allowed label and evidence reference required')
        elif entry['label'] is not None:
            raise ValueError('abstention must have null label')
        latest = conn.execute('SELECT j.submission_id FROM judgments j WHERE j.assignment_id=? AND NOT EXISTS(SELECT 1 FROM judgments child WHERE child.supersedes=j.submission_id)', (entry['assignment_id'],)).fetchone()
        if entry['supersedes'] != (latest[0] if latest else None):
            raise ValueError('correction must name current judgment')
        conn.execute('INSERT INTO judgments VALUES(?,?,?,?,?)',
                     (entry['submission_id'], entry['assignment_id'], entry['supersedes'],
                      json.dumps(payload, sort_keys=True), _now()))
    return {'submission_id': entry['submission_id'], 'reused': False,
            'human_label_written': entry['outcome'] == 'label',
            'human_judgment_written': True, 'network_called': False}


def freeze_judgments(db_path, *, operator, evidence_reference, human_review_confirmed=False):
    _text(operator); _text(evidence_reference)
    if human_review_confirmed is not True:
        raise ValueError('explicit human review confirmation required')
    with closing(_connect(db_path)) as conn, conn:
        if conn.execute('SELECT 1 FROM judgment_freeze').fetchone():
            raise ValueError('judgments already frozen')
        snapshot, eligible = [], 0
        for case_id, study_id, split in conn.execute('SELECT case_id,study_id,split FROM cases ORDER BY case_id').fetchall():
            exposures = [r[0] for r in conn.execute('SELECT event_id FROM exposures WHERE study_id=? ORDER BY event_id', (study_id,))]
            assignment_ids = [r[0] for r in conn.execute('SELECT assignment_id FROM assignments WHERE case_id=? ORDER BY assignment_id', (case_id,))]
            current = []
            for assignment_id in assignment_ids:
                row = conn.execute('SELECT j.payload FROM judgments j WHERE j.assignment_id=? AND NOT EXISTS(SELECT 1 FROM judgments child WHERE child.supersedes=j.submission_id)', (assignment_id,)).fetchone()
                if row is None:
                    if not exposures:
                        raise ValueError('unfinished assignment')
                else:
                    current.append(json.loads(row[0]))
            resolution = latest_resolution(conn, case_id)
            if not exposures:
                if not assignment_ids:
                    raise ValueError('unassigned case')
                outcomes = {(r['outcome'], r['label']) for r in current}
                if resolution:
                    validate_resolution_basis(resolution, current)
                elif len(outcomes) != 1:
                    raise ValueError('unresolved reviewer disagreement')
                eligible += 1
            snapshot.append({'case_id': case_id, 'study_id': study_id, 'split': split,
                             'exposure_events_at_freeze': exposures,
                             'excluded_at_freeze': bool(exposures), 'judgments': current,
                             'resolution': resolution})
        if not eligible:
            raise ValueError('no unexposed completed cases')
        digest = _hash(snapshot)
        conn.execute('INSERT INTO judgment_freeze VALUES(1,?,?,?,?,?)',
                     (operator, evidence_reference, _now(), json.dumps(snapshot, sort_keys=True), digest))
    return {'judgments_frozen': True, 'snapshot_hash': digest,
            'unexposed_completed_cases': eligible, 'network_called': False,
            'note': 'Includes abstentions. No model quality or holdout adequacy established; later exposure must still be checked.'}
