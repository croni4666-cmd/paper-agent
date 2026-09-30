"""Independent human resolution of reviewer disagreement, without rewriting labels."""
from contextlib import closing
import json

from .jev_evaluation import _connect, _now, _text


def current_judgments(conn, case_id):
    rows = conn.execute(
        'SELECT a.assignment_id,j.payload FROM assignments a LEFT JOIN judgments j '
        'ON j.assignment_id=a.assignment_id AND NOT EXISTS '
        '(SELECT 1 FROM judgments child WHERE child.supersedes=j.submission_id) '
        'WHERE a.case_id=? ORDER BY a.assignment_id', (case_id,)).fetchall()
    if not rows or any(payload is None for _, payload in rows):
        raise ValueError('all assigned reviewers must submit before adjudication')
    return [json.loads(payload) for _, payload in rows]


def latest_resolution(conn, case_id):
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='resolutions'").fetchone():
        return None
    row = conn.execute('SELECT r.payload FROM resolutions r WHERE r.case_id=? '
                       'AND NOT EXISTS(SELECT 1 FROM resolutions child WHERE child.supersedes=r.resolution_id)',
                       (case_id,)).fetchone()
    return json.loads(row[0]) if row else None


def validate_resolution_basis(resolution, judgments):
    if (resolution['based_on'] != sorted(j['submission_id'] for j in judgments)
            or resolution['adjudicator'] in {j['reviewer'] for j in judgments}):
        raise ValueError('stale or non-independent adjudication')


def resolve_disagreement(db_path, entry, *, human_confirmed=False, no_prior_exposure=False):
    fields = {'resolution_id', 'review_id', 'adjudicator', 'operator', 'based_on',
              'outcome', 'label', 'evidence_ids', 'reason_reference', 'supersedes'}
    if (human_confirmed is not True or no_prior_exposure is not True
            or not isinstance(entry, dict) or set(entry) != fields):
        raise ValueError('exact resolution fields and explicit human/no-exposure attestations required')
    entry = json.loads(json.dumps(entry, allow_nan=False))
    for key in ('resolution_id', 'review_id', 'adjudicator', 'operator', 'reason_reference'):
        _text(entry[key])
    if entry['supersedes'] is not None:
        _text(entry['supersedes'])
    basis = entry['based_on']
    if not isinstance(basis, list) or not 1 <= len(basis) <= 10000:
        raise ValueError('bounded judgment basis required')
    for value in basis:
        _text(value)
    if len(set(basis)) != len(basis):
        raise ValueError('duplicate basis')
    entry['based_on'] = sorted(basis)
    refs = entry['evidence_ids']
    if not isinstance(refs, list) or len(refs) > 6 or any(not isinstance(r, str) for r in refs) or len(set(refs)) != len(refs):
        raise ValueError('bounded unique evidence references required')
    payload = {**entry, 'source': 'human', 'human_confirmed': True,
               'no_prior_exposure_attested': True}
    with closing(_connect(db_path)) as conn, conn:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='resolutions'").fetchone():
            raise ValueError('adjudication requires schema v3; preserve v2 history')
        prior = conn.execute('SELECT payload FROM resolutions WHERE resolution_id=?', (entry['resolution_id'],)).fetchone()
        if prior:
            if json.loads(prior[0]) != payload:
                raise ValueError('resolution ID reused with changed content')
            return {'resolution_id': entry['resolution_id'], 'reused': True, 'network_called': False}
        if conn.execute('SELECT 1 FROM judgment_freeze').fetchone():
            raise ValueError('judgments frozen')
        case = conn.execute('SELECT case_id,study_id,details FROM cases WHERE review_id=?', (entry['review_id'],)).fetchone()
        if case is None:
            raise ValueError('unknown review')
        if conn.execute('SELECT 1 FROM exposures WHERE study_id=? LIMIT 1', (case[1],)).fetchone():
            raise ValueError('study exposed')
        judgments = current_judgments(conn, case[0])
        validate_resolution_basis(payload, judgments)
        previous = latest_resolution(conn, case[0])
        if entry['supersedes'] != (previous['resolution_id'] if previous else None):
            raise ValueError('correction must name latest resolution')
        if previous is None and len({(j['outcome'], j['label']) for j in judgments}) < 2:
            raise ValueError('no reviewer disagreement to resolve')
        details = json.loads(case[2])
        if any(r not in details['evidence_ids'] for r in refs):
            raise ValueError('evidence outside frozen case')
        if entry['outcome'] == 'label':
            if entry['label'] not in details['rubric']['labels'] or not refs:
                raise ValueError('allowed label and evidence required')
        elif entry['outcome'] != 'abstain' or entry['label'] is not None:
            raise ValueError('label or abstention with null label required')
        conn.execute('INSERT INTO resolutions VALUES(?,?,?,?,?)',
                     (entry['resolution_id'], case[0], entry['supersedes'],
                      json.dumps(payload, sort_keys=True), _now()))
    return {'resolution_id': entry['resolution_id'], 'reused': False,
            'original_judgments_preserved': True, 'network_called': False}
