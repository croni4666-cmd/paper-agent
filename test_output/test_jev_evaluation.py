"""Offline M5 evaluation-ledger checks; all cases and labels are synthetic."""
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pa_cli.evidence import _hash
from pa_cli.shadow import APP_ID as SHADOW_APP_ID
from pa_cli.jev_evaluation import (
    assign_review, evaluation_status, freeze_plan, record_exposure,
)
from pa_cli.jev_judgments import freeze_judgments, submit_judgment
from pa_cli.jev_review import export_review
from click.testing import CliRunner
from pa_cli.cli import main


class JevEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.shadow = self.root / 'shadow.sqlite'
        self.bundle = self.root / 'bundle'
        self.evaluation = self.root / 'evaluation.sqlite'
        self.artifact = 'a' * 64
        self.evidence_id = 'b' * 64
        self.rubric = {
            'task': 'relevance', 'version': 'synthetic-v1',
            'question': 'Is the synthetic claim supported?',
            'labels': ['yes', 'no'],
        }
        self.packet = {
            'artifact_sha256': self.artifact,
            'evidence': [{'evidence_id': self.evidence_id, 'page': 1,
                          'text': 'Synthetic passage.'}],
            'missing_sections': [], 'pages_needing_review': [],
        }
        self.packet['packet_hash'] = _hash(self.packet)
        conn = sqlite3.connect(self.shadow)
        try:
            conn.execute(f'PRAGMA application_id={SHADOW_APP_ID}')
            conn.execute('CREATE TABLE requests(request_id TEXT PRIMARY KEY, artifact_sha256 TEXT, packet_json TEXT, rubric_json TEXT)')
            conn.execute('INSERT INTO requests VALUES(?,?,?,?)',
                         ('synthetic-request', self.artifact,
                          json.dumps(self.packet), json.dumps(self.rubric)))
            conn.commit()
        finally:
            conn.close()
        export_review(self.shadow, 'synthetic-request', self.bundle)
        self.review_id = json.loads((self.bundle / 'review.json').read_text(encoding='utf-8'))['review_id']
        plan = {
            'evaluation_id': 'synthetic-evaluation', 'shadow_db': self.shadow.name,
            'cases': [{'bundle': self.bundle.name, 'study_id': 'synthetic-study',
                       'split': 'holdout', 'grouping_reference': 'synthetic-grouping-note'}],
        }
        self.plan = plan
        self._freeze_ledger()

    def _freeze_ledger(self):
        return freeze_plan(self.plan, self.root, self.evaluation,
                           operator='synthetic-coordinator', grouping_confirmed=True)

    def _entry(self, submission_id, assignment_id, *, reviewer='synthetic-reviewer',
               label='yes', supersedes=None):
        return {
            'submission_id': submission_id, 'assignment_id': assignment_id,
            'reviewer': reviewer, 'operator': 'synthetic-coordinator',
            'outcome': 'label', 'label': label, 'evidence_ids': [self.evidence_id],
            'reason_reference': 'synthetic-review-note', 'supersedes': supersedes,
        }

    def _forge_bundle(self, packet, review_id):
        packet = json.loads(json.dumps(packet))
        packet['packet_hash'] = _hash({k: v for k, v in packet.items()
                                       if k != 'packet_hash'})
        conn = sqlite3.connect(self.shadow)
        try:
            conn.execute('UPDATE requests SET packet_json=? WHERE request_id=?',
                         (json.dumps(packet), 'synthetic-request'))
            conn.commit()
        finally:
            conn.close()
        review = {
            'schema_version': 'blind-review-export-1', 'review_id': review_id,
            'rubric': {k: self.rubric[k] for k in ('task', 'version', 'question', 'labels')},
            'evidence': [{k: span[k] for k in ('evidence_id', 'page', 'text')}
                         for span in packet['evidence']],
            'completeness': {k: packet[k] for k in ('missing_sections', 'pages_needing_review')},
            'notice': 'Selected passages only. Current PDF authenticity and completeness are not verified. Answers are masked; independent blinding is not established. Request more context when needed.',
        }
        manifest = {
            'schema_version': 'blind-review-coordinator-1', 'review_id': review_id,
            'request_id': 'synthetic-request', 'artifact_sha256': self.artifact,
            'packet_hash': packet['packet_hash'], 'rubric_hash': _hash(self.rubric),
            'review_hash': _hash(review), 'blinding_verified': False,
            'notice': 'Coordinator only. Share review.json alone. No human label or split is created.',
        }
        (self.bundle / 'review.json').write_text(json.dumps(review), encoding='utf-8')
        (self.bundle / 'coordinator.json').write_text(json.dumps(manifest), encoding='utf-8')

    def test_valid_assignment_correction_freeze_and_later_exposure(self):
        assignment = assign_review(
            self.evaluation, self.review_id, reviewer='synthetic-reviewer',
            operator='synthetic-coordinator', no_prior_exposure=True)
        first = self._entry('synthetic-submission-1', assignment['assignment_id'])
        self.assertFalse(submit_judgment(self.evaluation, first, human_confirmed=True)['reused'])
        correction = self._entry('synthetic-submission-2', assignment['assignment_id'],
                                 label='no', supersedes='synthetic-submission-1')
        self.assertFalse(submit_judgment(self.evaluation, correction, human_confirmed=True)['reused'])
        with self.assertRaises(ValueError):
            submit_judgment(self.evaluation, self._entry(
                'synthetic-submission-3', assignment['assignment_id'],
                supersedes='synthetic-submission-1'), human_confirmed=True)
        frozen = freeze_judgments(
            self.evaluation, operator='synthetic-coordinator',
            evidence_reference='synthetic-final-review', human_review_confirmed=True)
        self.assertTrue(frozen['judgments_frozen'])
        self.assertEqual(frozen['unexposed_completed_cases'], 1)
        self.assertTrue(submit_judgment(self.evaluation, correction,
                                        human_confirmed=True)['reused'])
        record_exposure(self.evaluation, 'synthetic-study',
                        operator='synthetic-coordinator',
                        evidence_reference='synthetic-exposure-incident')
        status = evaluation_status(self.evaluation)
        self.assertTrue(status['judgments_frozen'])
        self.assertEqual(status['frozen_snapshot_hash'], frozen['snapshot_hash'])
        self.assertTrue(status['assignments'][0]['exposure_recorded'])
        self.assertFalse(status['assignments'][0]['blind_candidate'])

    def test_exposure_blocks_assignment_and_submission(self):
        assignment = assign_review(
            self.evaluation, self.review_id, reviewer='synthetic-reviewer',
            operator='synthetic-coordinator', no_prior_exposure=True)
        record_exposure(self.evaluation, 'synthetic-study',
                        operator='synthetic-coordinator',
                        evidence_reference='synthetic-exposure-incident')
        with self.assertRaises(ValueError):
            assign_review(self.evaluation, self.review_id, reviewer='synthetic-reviewer',
                          operator='synthetic-coordinator', no_prior_exposure=True)
        with self.assertRaises(ValueError):
            submit_judgment(self.evaluation,
                            self._entry('blocked-after-exposure', assignment['assignment_id']),
                            human_confirmed=True)

    def test_freeze_requires_current_consensus(self):
        first = assign_review(
            self.evaluation, self.review_id, reviewer='synthetic-reviewer',
            operator='synthetic-coordinator', no_prior_exposure=True)
        second = assign_review(
            self.evaluation, self.review_id, reviewer='synthetic-reviewer-2',
            operator='synthetic-coordinator', no_prior_exposure=True)
        submit_judgment(self.evaluation,
                        self._entry('reviewer-1-label', first['assignment_id']),
                        human_confirmed=True)
        submit_judgment(self.evaluation,
                        self._entry('reviewer-2-label', second['assignment_id'],
                                    reviewer='synthetic-reviewer-2', label='no'),
                        human_confirmed=True)
        with self.assertRaises(ValueError):
            freeze_judgments(self.evaluation, operator='synthetic-coordinator',
                             evidence_reference='synthetic-review', human_review_confirmed=True)
        submit_judgment(self.evaluation,
                        self._entry('reviewer-2-correction', second['assignment_id'],
                                    reviewer='synthetic-reviewer-2', supersedes='reviewer-2-label'),
                        human_confirmed=True)
        result = freeze_judgments(
            self.evaluation, operator='synthetic-coordinator',
            evidence_reference='synthetic-review', human_review_confirmed=True)
        self.assertEqual(result['unexposed_completed_cases'], 1)

    def test_freeze_rejects_invalid_source_evidence_and_completeness(self):
        # Hashes are self-consistent: each subtest isolates a field validator.
        bad_packets = [
            ('invalid evidence digest', {**self.packet, 'evidence': [
                {'evidence_id': 'not-a-digest', 'page': 1, 'text': 'Synthetic passage.'}]}),
            ('page zero', {**self.packet, 'evidence': [
                {'evidence_id': self.evidence_id, 'page': 0, 'text': 'Synthetic passage.'}]}),
            ('negative page', {**self.packet, 'evidence': [
                {'evidence_id': self.evidence_id, 'page': -1, 'text': 'Synthetic passage.'}]}),
            ('boolean page', {**self.packet, 'evidence': [
                {'evidence_id': self.evidence_id, 'page': True, 'text': 'Synthetic passage.'}]}),
            ('blank text', {**self.packet, 'evidence': [
                {'evidence_id': self.evidence_id, 'page': 1, 'text': '  '}]}),
            ('duplicate evidence', {**self.packet, 'evidence': [
                {'evidence_id': self.evidence_id, 'page': 1, 'text': 'First.'},
                {'evidence_id': self.evidence_id, 'page': 2, 'text': 'Second.'}]}),
            ('missing sections type', {**self.packet, 'missing_sections': 'not-a-list'}),
            ('pages type', {**self.packet, 'pages_needing_review': 'not-a-list'}),
            ('invalid completeness value', {**self.packet, 'pages_needing_review': [0]}),
        ]
        for index, (name, packet) in enumerate(bad_packets):
            with self.subTest(field=name):
                self._forge_bundle(packet, 'synthetic-review-' + str(index))
                target = self.root / f'bad-evaluation-{index}.sqlite'
                with self.assertRaises(ValueError):
                    freeze_plan(self.plan, self.root, target,
                                operator='synthetic-coordinator', grouping_confirmed=True)

    def test_cli_freeze_assign_submit_freeze_and_status(self):
        runner = CliRunner()
        plan_path = self.root / 'cli-plan.json'
        plan_path.write_text(json.dumps(self.plan), encoding='utf-8')
        cli_db = self.root / 'cli-evaluation.sqlite'
        with patch('pa_cli.keys.load_env_into_environ', return_value=0), \
                patch('pa_cli.keys.cmd_remind', return_value=0):
            result = runner.invoke(main, ['jev', 'evaluation-freeze', '--plan', str(plan_path),
                                          '--db', str(cli_db), '--operator', 'synthetic-coordinator',
                                          '--confirm-study-grouping'])
            self.assertEqual(result.exit_code, 0, result.output)
            result = runner.invoke(main, ['jev', 'review-assign', '--db', str(cli_db),
                                          '--review-id', self.review_id, '--reviewer', 'synthetic-reviewer',
                                          '--operator', 'synthetic-coordinator',
                                          '--confirm-no-prior-exposure'])
            self.assertEqual(result.exit_code, 0, result.output)
            assignment_id = json.loads(result.output)['assignment_id']
            entry_path = self.root / 'cli-entry.json'
            entry_path.write_text(json.dumps(self._entry('cli-submission', assignment_id)), encoding='utf-8')
            result = runner.invoke(main, ['jev', 'review-submit', '--db', str(cli_db),
                                          '--entry', str(entry_path), '--confirm-human-judgment'])
            self.assertEqual(result.exit_code, 0, result.output)
            result = runner.invoke(main, ['jev', 'judgments-freeze', '--db', str(cli_db),
                                          '--operator', 'synthetic-coordinator',
                                          '--evidence-reference', 'synthetic-final-review',
                                          '--confirm-human-review'])
            self.assertEqual(result.exit_code, 0, result.output)
            result = runner.invoke(main, ['jev', 'evaluation-status', '--db', str(cli_db)])
            self.assertEqual(result.exit_code, 0, result.output)
            status = json.loads(result.output)
            self.assertTrue(status['judgments_frozen'])
            self.assertEqual(status['judgment_records'], 1)


if __name__ == '__main__':
    unittest.main()
