"""Local dispatch preflight and explicit interactive approval for one request."""
from datetime import datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
import sys

import click

from .evidence import _hash
from .jev import Budget, Price, prepare_request
from .jev_dispatch import Approval, ENDPOINT, dispatch, validate_routing_policy
from .provenance import inspect_artifact
from .shadow import _check_packet


def _interactive_terminal():
    return sys.stdin.isatty() and sys.stdout.isatty()


def prepare_job(job_path, db_path):
    """Load once and validate locally; dispatch rechecks artifacts after approval."""
    from .jev_cli import _read_object
    job_path = Path(job_path).resolve(strict=True)
    job = _read_object(job_path)
    required = {'pdf', 'index', 'packet', 'questions', 'fetch_result', 'price', 'run_id',
                'estimated_input_tokens', 'rubric_version', 'data_class',
                'high_stakes', 'conflicting_evidence'}
    optional = {'max_papers', 'max_input_tokens', 'max_cost_usd', 'timeout',
                'expected_title', 'score_boundaries', 'critical_score_levels', 'retry_of'}
    if not required <= set(job) or set(job) - required - optional:
        raise ValueError('invalid job fields; keys and transport overrides are forbidden')
    retry_of=job.get('retry_of')
    if retry_of is not None and (not isinstance(retry_of,str) or not retry_of.strip() or len(retry_of)>200):
        raise ValueError('bounded retry parent ID required')
    paths = {}
    for name in ('pdf', 'index', 'packet', 'questions', 'fetch_result'):
        if not isinstance(job[name], str) or not job[name].strip():
            raise ValueError('input path required')
        paths[name] = (job_path.parent / job[name]).resolve(strict=True)
        if not paths[name].is_file():
            raise ValueError('input must be a file')
    database = Path(db_path).resolve()
    if not database.parent.is_dir() or database.is_dir():
        raise ValueError('database parent must exist')
    for source in [job_path, *paths.values()]:
        if database == source or (database.exists() and database.samefile(source)):
            raise ValueError('database cannot overwrite an input')
    args = {name: _read_object(paths[name]) for name in ('index', 'packet', 'questions', 'fetch_result')}
    price_data = job['price']
    if not isinstance(price_data, dict) or set(price_data) != {'model', 'usd_per_million_input', 'checked_at', 'source_url'}:
        raise ValueError('complete explicit price metadata required')
    price = Price(price_data['model'], price_data['usd_per_million_input'],
                  datetime.fromisoformat(price_data['checked_at']), price_data['source_url'])
    caps = {name: job.get(name, default) for name, default in
            (('max_papers', 25), ('max_input_tokens', 100000), ('max_cost_usd', '0.01'))}
    budget = Budget(price, **caps)
    budget.reserve('local-preflight', job['estimated_input_tokens'])
    for name in ('run_id', 'rubric_version'):
        if not isinstance(job[name], str) or not job[name].strip() or len(job[name]) > 200:
            raise ValueError('bounded run and rubric identifiers required')
    for name in ('high_stakes', 'conflicting_evidence'):
        if job[name] is not False:
            raise ValueError('explicit low-risk, non-conflicting review required')
    if job['data_class'] != 'public':
        raise ValueError('only confirmed public material can be submitted')
    timeout = job.get('timeout', 30)
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 120:
        raise ValueError('invalid timeout')
    _check_packet(args['index'], args['packet'])
    request = prepare_request(args['packet'], args['questions'], price.model)
    routing = validate_routing_policy(args['questions'], job.get('score_boundaries'),
                                      job.get('critical_score_levels'))
    source = args['fetch_result'].get('via_channel', '').removeprefix('cache:')
    provenance = inspect_artifact(paths['pdf'], args['fetch_result']['doi'], source,
                                  args['fetch_result'].get('via_url'),
                                  expected_title=job.get('expected_title'), data_class='public')
    if (not provenance['external_evaluation_candidate']
            or provenance['artifact_sha256'] != args['index']['artifact_sha256']
            or args['packet'].get('status') != 'ready_for_local_review'
            or args['packet'].get('missing_sections')
            or any(p['status'] != 'text_extracted' for p in args['index']['pages'])):
        raise ValueError('artifact, rights metadata or evidence completeness gate failed')
    args.update(pdf=paths['pdf'], db_path=database, price=price, timeout=timeout,
                **caps, **{name: job[name] for name in
                          ('run_id', 'rubric_version', 'estimated_input_tokens', 'data_class',
                           'high_stakes', 'conflicting_evidence')})
    for name in ('expected_title', 'score_boundaries', 'critical_score_levels', 'retry_of'):
        if name in job:
            args[name] = job[name]
    review = dict(request=request, request_hash=_hash(request), endpoint=ENDPOINT, retry_of=retry_of,
                  run_id=job['run_id'], rubric_version=job['rubric_version'], limits=caps,
                  price=price_data, estimated_input_tokens=job['estimated_input_tokens'],
                  estimated_input_cost_usd=str(budget.cost_committed),
                  data_class='public', artifact_sha256=provenance['artifact_sha256'],
                  routing_policy=routing,
                  local_preflight_passed=True, ledger_checked=False,
                  upload_authorized=False, network_called=False,
                  limitation='Metadata allowlist only, not a legal determination. Estimates are not invoice caps; M5 evaluation and pilot approval are required before live use.')
    return args, review


@click.command('dispatch')
@click.option('--job', required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option('--db', required=True, type=click.Path(dir_okay=False, path_type=Path))
@click.option('--send', is_flag=True, help='Request one live call after terminal approval; default is local preflight.')
@click.option('--pilot-approved', is_flag=True, help='Attest required human evaluation and pilot approval are complete; not automatically verified.')
def dispatch_command(job, db, send, pilot_approved):
    """Preflight one job; optionally review and approve its live upload and cost.

    Live calls read TYPESAFE_API_KEY from the environment, never from job files or
    command arguments. No unattended approval flag or alternate endpoint exists.
    """
    try:
        args, review = prepare_job(job, db)
    except Exception as exc:
        raise click.ClickException(f'Local preflight failed ({type(exc).__name__}); no request sent. Check job schema, artifact, provenance and price.') from None
    if not send:
        click.echo(json.dumps(review, ensure_ascii=True, indent=2, allow_nan=False))
        return
    if not pilot_approved:
        raise click.ClickException('Live dispatch requires --pilot-approved after required human evaluation and pilot approval.')
    if not _interactive_terminal():
        raise click.ClickException('Live approval requires an interactive terminal with visible output.')
    api_key = os.environ.get('TYPESAFE_API_KEY', '')
    if not api_key.strip() or any(c in api_key for c in '\r\n'):
        raise click.ClickException('Set TYPESAFE_API_KEY in your local environment; never place it in the job or command arguments.')
    # Escaped JSON prevents passage content from acting as terminal control text.
    click.echo(json.dumps(review, ensure_ascii=True, indent=2, allow_nan=False))
    click.echo('Review the exact request above. SEND authorizes this public-OA passage upload to TypeSafe and accepts the displayed estimated caps and possible actual-cost overrun. It does not authorize GPT calls.')
    answer = click.prompt('Type SEND to approve, or anything else to cancel', default='', show_default=False)
    if answer != 'SEND':
        click.echo('Cancelled; no request sent.')
        return
    approval = Approval(args['run_id'], review['request_hash'], True, True,
                        datetime.now(timezone.utc) + timedelta(minutes=5),
                        pilot_approval_attested=True, retry_of=review['retry_of'], **review['limits'])
    try:
        result = dispatch(**args, api_key=api_key, approval=approval)
        click.echo(json.dumps(result, ensure_ascii=True, indent=2, allow_nan=False))
    except Exception as exc:
        raise click.ClickException(f'Dispatch did not finish normally ({type(exc).__name__}). Inspect the ledger before any retry; an interrupted request may have incurred usage.') from None
    if result.get('status') != 'completed':
        raise click.ClickException('Request is not completed; inspect its recorded status before further action. No automatic retry was made.')
