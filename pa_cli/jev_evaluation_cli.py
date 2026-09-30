"""Explicit local evaluation coordination commands."""
from pathlib import Path
import json
import sqlite3

import click

from .jev_evaluation import freeze_plan, assign_review, record_exposure, evaluation_status


def _emit(action, *args, **kwargs):
    try:
        result = action(*args, **kwargs)
    except (OSError, sqlite3.Error, ValueError, TypeError, KeyError, RecursionError):
        raise click.ClickException('Evaluation operation refused. Check the frozen plan, source bundle, identifiers, exposure history and required attestations. Existing records are not replaced.') from None
    click.echo(json.dumps(result, ensure_ascii=True, indent=2))


@click.command('evaluation-freeze')
@click.option('--plan', required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option('--db', required=True, type=click.Path(path_type=Path), help='New dedicated evaluation database.')
@click.option('--operator', required=True)
@click.option('--confirm-study-grouping', is_flag=True)
def freeze_command(plan, db, operator, confirm_study_grouping):
    """Freeze explicit study groups and splits from exported M3 review bundles."""
    from .jev_cli import _read_object
    def run():
        return freeze_plan(_read_object(plan), plan.resolve().parent, db,
                           operator=operator, grouping_confirmed=confirm_study_grouping)
    _emit(run)


@click.command('review-assign')
@click.option('--db', required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option('--review-id', required=True)
@click.option('--reviewer', required=True)
@click.option('--operator', required=True)
@click.option('--confirm-no-prior-exposure', is_flag=True)
def assign_command(db, review_id, reviewer, operator, confirm_no_prior_exposure):
    """Record an assignment after the reviewer's no-exposure attestation."""
    _emit(assign_review, db, review_id, reviewer=reviewer, operator=operator,
          no_prior_exposure=confirm_no_prior_exposure)


@click.command('review-expose')
@click.option('--db', required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option('--study-id', required=True)
@click.option('--operator', required=True)
@click.option('--evidence-reference', required=True)
def expose_command(db, study_id, operator, evidence_reference):
    """Record known answer exposure; exclude this study from blind review."""
    _emit(record_exposure, db, study_id, operator=operator,
          evidence_reference=evidence_reference)


@click.command('evaluation-status')
@click.option('--db', required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
def status_command(db):
    """Read frozen split counts and assignment exposure flags without passages."""
    _emit(evaluation_status, db)


@click.command('review-submit')
@click.option('--db', required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option('--entry', required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option('--confirm-human-judgment', is_flag=True)
def submit_command(db, entry, confirm_human_judgment):
    """Record an explicit human judgment or a linked correction."""
    from .jev_cli import _read_object
    from .jev_judgments import submit_judgment
    def run():
        return submit_judgment(db, _read_object(entry), human_confirmed=confirm_human_judgment)
    _emit(run)


@click.command('judgments-freeze')
@click.option('--db', required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option('--operator', required=True)
@click.option('--evidence-reference', required=True)
@click.option('--confirm-human-review', is_flag=True)
def judgments_freeze_command(db, operator, evidence_reference, confirm_human_review):
    """Freeze completed, consistent judgments and retain exposure exclusions."""
    from .jev_judgments import freeze_judgments
    _emit(freeze_judgments, db, operator=operator, evidence_reference=evidence_reference,
          human_review_confirmed=confirm_human_review)


@click.command('review-resolve')
@click.option('--db', required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option('--entry', required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option('--confirm-human-judgment', is_flag=True)
@click.option('--confirm-no-prior-exposure', is_flag=True)
def resolve_command(db, entry, confirm_human_judgment, confirm_no_prior_exposure):
    """Record independent human resolution without altering reviewer judgments."""
    from .jev_cli import _read_object
    from .jev_adjudication import resolve_disagreement
    def run():
        return resolve_disagreement(db, _read_object(entry), human_confirmed=confirm_human_judgment,
                                    no_prior_exposure=confirm_no_prior_exposure)
    _emit(run)


@click.command('evaluation-score')
@click.option('--eval-db', required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path), help='Frozen evaluation database.')
@click.option('--pred', required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path), help='Prediction source (M3 shadow database or JSON).')
@click.option('--target-fnr', type=float, default=0.10, show_default=True, help='Maximum acceptable false negative rate on calibration split.')
@click.option('--allow-synthetic', is_flag=True, help='Permit scoring with synthetic fixture predictions (prominently flagged in report).')
@click.option('--confidence', type=float, default=0.95, show_default=True, help='Confidence level for Wilson score intervals.')
def score_command(eval_db, pred, target_fnr, allow_synthetic, confidence):
    """Join predictions to frozen cases, calibrate threshold and score holdout with 95% CIs."""
    from .jev_eval_join import evaluate_run
    _emit(evaluate_run, eval_db, pred, target_fnr=target_fnr,
          allow_synthetic=allow_synthetic, confidence=confidence)


COMMANDS = (freeze_command, assign_command, expose_command, status_command,
            submit_command, judgments_freeze_command, resolve_command, score_command)

