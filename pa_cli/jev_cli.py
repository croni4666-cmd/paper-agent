"""Local Jev preview, ledger inspection and operator accounting reconciliation."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import click

from .evidence import _hash
from .jev import SCHEMA_VERSION, prepare_request

MAX_JSON_BYTES = 2 * 1024 * 1024


def _read_object(path):
    with Path(path).open('rb') as stream:
        raw = stream.read(MAX_JSON_BYTES + 1)
    if len(raw) > MAX_JSON_BYTES:
        raise ValueError('input exceeds size limit')
    def reject_constant(value):
        raise ValueError('nonfinite JSON number')
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result
    value = json.loads(raw.decode('utf-8-sig'), parse_constant=reject_constant,
                       object_pairs_hook=unique_object)
    if not isinstance(value, dict):
        raise ValueError('JSON object required')
    return value


def ledger_status(db_path, run_id, include_requests=False):
    """Read counters only. Never construct Ledger (its constructor writes schema)."""
    from .jev_dispatch import APP_ID
    path = Path(db_path).resolve(strict=True)
    connection = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=5)
    try:
        connection.execute('PRAGMA query_only=ON')
        connection.execute('BEGIN')
        if connection.execute('PRAGMA application_id').fetchone()[0] != APP_ID:
            raise ValueError('not a Jev dispatch database')
        row = connection.execute('SELECT config,halted FROM runs WHERE run_id=?',
                                 (run_id,)).fetchone()
        if row is None:
            raise ValueError('run not found')
        config = json.loads(row[0])
        counters = connection.execute(
            'SELECT status,count(*),sum(tokens) FROM requests WHERE run_id=? GROUP BY status',
            (run_id,)).fetchall()
        states = {status: {'requests': count, 'accounted_input_tokens': tokens}
                  for status, count, tokens in counters}
        result = {
            'run_id': run_id,
            'halted': bool(row[1]),
            'has_unresolved_requests': any(s in states for s in ('pending', 'unknown', 'interrupted', 'late_result_review')),
            'model': config['model'],
            'mode': config['mode'],
            'limits': {key: config[key] for key in
                       ('max_papers', 'max_input_tokens', 'max_cost_usd')},
            'request_count': sum(count for _, count, _ in counters),
            'accounted_input_tokens': sum(tokens for _, _, tokens in counters),
            'states': states,
            'accounting_note': 'Includes reserved tokens for unresolved requests and known usage for settled requests; not a provider invoice. max_papers currently counts requests.',
            'upload_authorized': False,
        }
        if include_requests:
            links = {}
            if connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='retry_links'").fetchone():
                links = dict(connection.execute(
                    'SELECT l.child_request_id,l.parent_request_id FROM retry_links l '
                    'JOIN requests q ON q.request_id=l.child_request_id WHERE q.run_id=?', (run_id,)))
            result['requests'] = [dict(request_id=rid, status=state, accounted_input_tokens=tokens)
                                  for rid, state, tokens in connection.execute(
                                      'SELECT request_id,status,tokens FROM requests WHERE run_id=? ORDER BY request_id',
                                      (run_id,))]
            for row in result['requests']:
                row['retry_of'] = links.get(row['request_id'])
        return result
    finally:
        connection.close()


@click.group('jev')
def jev():
    """Preview, inspect, reconcile or explicitly approve Jev requests."""


@jev.command('review-export')
@click.option('--shadow-db', required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option('--request-id', required=True)
@click.option('--out', required=True, type=click.Path(path_type=Path), help='New directory; share only review.json.')
def review_export(shadow_db, request_id, out):
    """Export masked evidence and a separate coordinator manifest."""
    from .jev_review import export_review
    try:
        result = export_review(shadow_db, request_id, out)
    except (OSError, sqlite3.Error, ValueError, TypeError, KeyError, RecursionError):
        raise click.ClickException('Export refused: check the M3 request, packet and new output directory. No label was written.') from None
    click.echo(json.dumps(result, ensure_ascii=True, indent=2))


@jev.command('preview')
@click.option('--packet', required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option('--questions', required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option('--model', required=True, help='Explicit model identifier; not checked against a live provider.')
def preview(packet, questions, model):
    """Print the minimal payload as JSON for local review, including passage text.

    This validates packet hash and request shape only. It does not verify the PDF,
    source rights, evidence completeness, price, or dispatch consent.
    """
    try:
        request = prepare_request(_read_object(packet), _read_object(questions), model)
        result = {
            'schema_version': SCHEMA_VERSION,
            'request': request,
            'request_hash': _hash(request),
            'validation_scope': 'packet_hash_and_request_schema_only',
            'upload_authorized': False,
            'network_called': False,
        }
        click.echo(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    except (OSError, ValueError, TypeError, AttributeError, KeyError, RecursionError):
        raise click.ClickException('Cannot preview: check bounded JSON objects, packet integrity, questions and model.') from None


@jev.command('status')
@click.option('--db', required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option('--run-id', required=True, help='Existing dispatch run identifier.')
@click.option('--requests', 'include_requests', is_flag=True, help='Include request IDs and counters, without payloads.')
def status(db, run_id, include_requests):
    """Print run limits and accounting counters without stored passages or answers.

    Existing databases are opened read-only; this command never clears a halted
    run, releases a reservation, retries a request, or authorizes dispatch.
    """
    try:
        click.echo(json.dumps(ledger_status(db, run_id, include_requests), ensure_ascii=False,
                              indent=2, allow_nan=False))
    except (OSError, sqlite3.Error, ValueError, TypeError, KeyError):
        raise click.ClickException('Cannot read status: check the dispatch database and run ID.') from None


@jev.command('reconcile')
@click.option('--db', required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option('--run-id', required=True)
@click.option('--request-id', required=True)
@click.option('--actual-input-tokens', required=True, type=click.IntRange(0, 2**63 - 1))
@click.option('--confirmed-model', required=True)
@click.option('--operator', required=True, help='Operator identifier stored in the local audit trail.')
@click.option('--evidence-reference', required=True, help='Local receipt/support reference ID; do not include keys or paper text.')
@click.option('--confirm-final-usage', is_flag=True, help='Attest that final usage and model were independently verified for this request.')
def reconcile(db, run_id, request_id, actual_input_tokens, confirmed_model,
              operator, evidence_reference, confirm_final_usage):
    """Record verified usage for an unresolved review outcome; the run stays halted.

    Changes the local ledger only. No request is resent. Unquarantined pending requests,
    unverified usage, and model mismatches cannot be reconciled by this command.
    """
    from .jev_recovery import reconcile_usage
    try:
        result = reconcile_usage(db, run_id, request_id, actual_input_tokens=actual_input_tokens,
                                 confirmed_model=confirmed_model, operator=operator,
                                 evidence_reference=evidence_reference,
                                 final_usage_confirmed=confirm_final_usage)
        click.echo(json.dumps({'request_id': result['request_id'], 'status': result['status'],
                               'input_tokens': result['input_tokens'], 'run_halted': True,
                               'network_called': False}, indent=2))
    except (OSError, sqlite3.Error, ValueError, TypeError, KeyError):
        raise click.ClickException('Reconciliation refused: verify an unknown/interrupted/late-result review status, matching identifiers/model, and explicit final-usage confirmation. The run is never resumed.') from None


@jev.command('quarantine')
@click.option('--db', required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option('--run-id', required=True)
@click.option('--request-id', required=True)
@click.option('--operator', required=True)
@click.option('--evidence-reference', required=True, help='Local incident reference; no keys or paper text.')
@click.option('--confirm-interrupted', is_flag=True, help='Attest suspected interruption; this does not prove or cause worker termination.')
def quarantine(db, run_id, request_id, operator, evidence_reference, confirm_interrupted):
    """Quarantine a pending request, retain its reservation and halt its run.

    This does not cancel in-flight HTTP or prove zero billing. Late results remain
    auditable and require review. No request is sent or automatically retried.
    """
    from .jev_recovery import quarantine_request
    try:
        result = quarantine_request(db, run_id, request_id, operator=operator,
                                    evidence_reference=evidence_reference,
                                    interruption_confirmed=confirm_interrupted)
        click.echo(json.dumps({'request_id': result['request_id'], 'status': result['status'],
                               'run_halted': True, 'network_called': False}, indent=2))
    except (OSError, sqlite3.Error, ValueError, TypeError, KeyError):
        raise click.ClickException('Quarantine refused: verify a pending request, matching run, operator/incident reference and explicit interruption confirmation.') from None


from .jev_submit import dispatch_command
jev.add_command(dispatch_command)

from .jev_evaluation_cli import COMMANDS as evaluation_commands
for evaluation_command in evaluation_commands:
    jev.add_command(evaluation_command)


@jev.command('resume')
@click.option('--db', required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option('--run-id', required=True)
@click.option('--operator', required=True)
@click.option('--evidence-reference', required=True, help='Local final review reference, without secrets.')
@click.option('--confirm-workers-stopped', is_flag=True)
@click.option('--confirm-final-usage', is_flag=True)
def resume(db, run_id, operator, evidence_reference, confirm_workers_stopped, confirm_final_usage):
    """Resume a reviewed halted run without resetting caps or sending anything.

    Both attestations require independent operator checks; they are not automatic
    detection of worker termination or provider billing. Upload still needs consent.
    """
    from .jev_recovery import resume_run
    try:
        result=resume_run(db,run_id,operator=operator,evidence_reference=evidence_reference,
                          workers_stopped_confirmed=confirm_workers_stopped,
                          final_usage_confirmed=confirm_final_usage)
        click.echo(json.dumps(result,indent=2))
    except (OSError,sqlite3.Error,ValueError,TypeError,KeyError):
        raise click.ClickException('Resume refused: confirm stopped workers/final usage, resolved outcomes, fresh price and remaining budget. Caps and usage are never reset.') from None
