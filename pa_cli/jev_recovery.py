"""Local operator accounting and explicit run resumption. Never sends requests."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from .jev_dispatch import APP_ID
from .jev import Budget, Price


def resume_run(db_path, run_id, *, operator, evidence_reference,
               workers_stopped_confirmed=False, final_usage_confirmed=False):
    """Explicit operator resume with preserved caps/usage; never sends a request."""
    if workers_stopped_confirmed is not True or final_usage_confirmed is not True:
        raise ValueError('worker-stop and final-usage attestations required')
    for value in (run_id, operator, evidence_reference):
        if not isinstance(value, str) or not value.strip() or len(value)>200 or any(ord(c)<32 for c in value):
            raise ValueError('bounded identifiers and review reference required')
    path=Path(db_path).resolve(strict=True)
    conn=sqlite3.connect(path.as_uri()+'?mode=rw', uri=True, timeout=10)
    try:
        with conn:
            conn.execute('BEGIN IMMEDIATE')
            if conn.execute('PRAGMA application_id').fetchone()[0] != APP_ID:
                raise ValueError('not a dispatch database')
            run=conn.execute('SELECT config,halted FROM runs WHERE run_id=?',(run_id,)).fetchone()
            if not run or not run[1]:
                raise ValueError('existing halted run required')
            config=json.loads(run[0])
            from decimal import Decimal
            price=Price(config['model'],str(Decimal(config['rate'])*1000000),
                        datetime.fromisoformat(config['checked_at']),config['price_source'])
            budget=Budget(price, max_papers=config['max_papers'], max_input_tokens=config['max_input_tokens'],
                          max_cost_usd=config['max_cost_usd'], now=datetime.now(timezone.utc))
            rows=conn.execute('SELECT request_id,status,tokens FROM requests WHERE run_id=? ORDER BY rowid',(run_id,)).fetchall()
            allowed={'completed','invalid_response','usage_reconciled','preflight_expired'}
            if not rows or any(r[1] not in allowed for r in rows):
                raise ValueError('unresolved outcomes, overruns or unverified models block resumption')
            tokens=sum(r[2] for r in rows)
            if len(rows)>=config['max_papers'] or tokens>=config['max_input_tokens'] or budget.rate*tokens>=budget.max_cost:
                raise ValueError('no remaining run budget')
            record=dict(event='operator_resumed_run', run_id=run_id, operator=operator,
                        evidence_reference=evidence_reference, workers_stopped_confirmed=True,
                        final_usage_confirmed=True, request_count=len(rows), accounted_input_tokens=tokens,
                        limits_changed=False)
            conn.execute('INSERT INTO events(request_id,created_at,status) VALUES(?,?,?)',
                         (rows[-1][0],datetime.now(timezone.utc).isoformat(),json.dumps(record,sort_keys=True)))
            conn.execute('UPDATE runs SET halted=0 WHERE run_id=?',(run_id,))
        return dict(run_id=run_id, halted=False, accounted_input_tokens=tokens,
                    request_count=len(rows), limits_changed=False, network_called=False)
    finally:
        conn.close()


def quarantine_request(db_path, run_id, request_id, *, operator, evidence_reference,
                       interruption_confirmed=False):
    """Quarantine suspected interrupted work; this does not stop an active worker."""
    if interruption_confirmed is not True:
        raise ValueError('explicit interruption attestation required')
    for value in (run_id, request_id, operator, evidence_reference):
        if not isinstance(value, str) or not value.strip() or len(value) > 200 or any(ord(c) < 32 for c in value):
            raise ValueError('bounded identifiers and incident reference required')
    path = Path(db_path).resolve(strict=True)
    conn = sqlite3.connect(path.as_uri() + '?mode=rw', uri=True, timeout=10)
    try:
        with conn:
            conn.execute('BEGIN IMMEDIATE')
            if conn.execute('PRAGMA application_id').fetchone()[0] != APP_ID:
                raise ValueError('not a dispatch database')
            row = conn.execute('SELECT status,tokens FROM requests WHERE run_id=? AND request_id=?',
                               (run_id, request_id)).fetchone()
            if row is None or row[0] != 'pending':
                raise ValueError('only pending requests can be quarantined')
            record = dict(event='operator_quarantined', operator=operator,
                          evidence_reference=evidence_reference, previous_status='pending',
                          reserved_input_tokens=row[1], worker_stop_verified=False)
            result = dict(request_id=request_id, status='interrupted', interruption=record,
                          automatic_decision_allowed=False, run_halted=True)
            conn.execute('UPDATE requests SET status=?,result=? WHERE request_id=?',
                         ('interrupted', json.dumps(result, allow_nan=False), request_id))
            conn.execute('UPDATE runs SET halted=1 WHERE run_id=?', (run_id,))
            conn.execute('INSERT INTO events(request_id,created_at,status) VALUES(?,?,?)',
                         (request_id, datetime.now(timezone.utc).isoformat(),
                          json.dumps(record, sort_keys=True, allow_nan=False)))
        return result
    finally:
        conn.close()


def reconcile_usage(db_path, run_id, request_id, *, actual_input_tokens,
                    confirmed_model, operator, evidence_reference,
                    final_usage_confirmed=False):
    """Record operator-verified final usage for an unresolved review outcome.

    Pending requests may still have an active worker and cannot be reconciled.
    The caller's attestation is not automatic verification of a provider invoice.
    """
    if final_usage_confirmed is not True:
        raise ValueError('explicit final-usage confirmation required')
    if type(actual_input_tokens) is not int or not 0 <= actual_input_tokens < 2**63:
        raise ValueError('invalid actual input usage')
    for value in (run_id, request_id, confirmed_model, operator, evidence_reference):
        if not isinstance(value, str) or not value.strip() or len(value) > 200 or any(ord(c) < 32 for c in value):
            raise ValueError('bounded identifiers and evidence reference required')
    path = Path(db_path).resolve(strict=True)
    conn = sqlite3.connect(path.as_uri() + '?mode=rw', uri=True, timeout=10)
    try:
        with conn:
            conn.execute('BEGIN IMMEDIATE')
            if conn.execute('PRAGMA application_id').fetchone()[0] != APP_ID:
                raise ValueError('not a dispatch database')
            row = conn.execute(
                'SELECT q.status,q.tokens,q.result,r.config FROM requests q JOIN runs r ON r.run_id=q.run_id '
                'WHERE q.run_id=? AND q.request_id=?', (run_id, request_id)).fetchone()
            if row is None or row[0] not in ('unknown', 'interrupted', 'late_result_review'):
                raise ValueError('only an unresolved review outcome can be reconciled')
            config = json.loads(row[3])
            if confirmed_model != config['model']:
                raise ValueError('confirmed model must match the priced model')
            previous = json.loads(row[2])
            if not isinstance(previous, dict):
                raise ValueError('invalid prior result')
            record = {
                'event': 'operator_usage_reconciled', 'operator': operator,
                'evidence_reference': evidence_reference,
                'previous_status': row[0], 'previous_accounted_tokens': row[1],
                'actual_input_tokens': actual_input_tokens, 'confirmed_model': confirmed_model,
                'final_usage_confirmed': True,
            }
            result = {**previous, 'request_id': request_id, 'status': 'usage_reconciled',
                      'input_tokens': actual_input_tokens, 'reconciliation': record,
                      'automatic_decision_allowed': False, 'run_halted': True}
            # Do not retain an old estimate as though it were a confirmed invoice.
            result.pop('input_cost_usd', None)
            conn.execute('UPDATE requests SET tokens=?,status=?,result=? WHERE request_id=?',
                         (actual_input_tokens, 'usage_reconciled', json.dumps(result, allow_nan=False), request_id))
            conn.execute('UPDATE runs SET halted=1 WHERE run_id=?', (run_id,))
            conn.execute('INSERT INTO events(request_id,created_at,status) VALUES(?,?,?)',
                         (request_id, datetime.now(timezone.utc).isoformat(),
                          json.dumps(record, sort_keys=True, allow_nan=False)))
        return result
    finally:
        conn.close()
