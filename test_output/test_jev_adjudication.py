"""Synthetic independent adjudication checks; no real human labels or network."""
import json
import sqlite3
import unittest
from contextlib import closing
from unittest.mock import patch
import test_jev_evaluation as fixture
from click.testing import CliRunner
from pa_cli.cli import main
from pa_cli.jev_adjudication import resolve_disagreement
from pa_cli.jev_evaluation import assign_review, record_exposure
from pa_cli.jev_judgments import submit_judgment, freeze_judgments


class AdjudicationTests(unittest.TestCase):
    setUp = fixture.JevEvaluationTests.setUp
    _freeze_ledger = fixture.JevEvaluationTests._freeze_ledger
    _entry = fixture.JevEvaluationTests._entry

    def dispute(self):
        self.assignments = []
        for reviewer, label, sid in [('r1', 'yes', 's1'), ('r2', 'no', 's2')]:
            a = assign_review(self.evaluation, self.review_id, reviewer=reviewer,
                              operator='op', no_prior_exposure=True)['assignment_id']
            self.assignments.append(a)
            submit_judgment(self.evaluation, self._entry(sid, a, reviewer=reviewer, label=label), human_confirmed=True)
        return dict(resolution_id='resolution-1', review_id=self.review_id, adjudicator='independent',
                    operator='op', based_on=['s1', 's2'], outcome='label', label='yes',
                    evidence_ids=[self.evidence_id], reason_reference='synthetic-reason', supersedes=None)

    def resolve(self, entry):
        return resolve_disagreement(self.evaluation, entry, human_confirmed=True, no_prior_exposure=True)

    def freeze(self):
        return freeze_judgments(self.evaluation, operator='op', evidence_reference='synthetic', human_review_confirmed=True)

    def test_resolution_preserves_disagreement_and_deduplicates(self):
        entry = self.dispute()
        self.assertFalse(self.resolve(entry)['reused'])
        self.assertTrue(self.resolve(entry)['reused'])
        self.freeze()
        with closing(sqlite3.connect(self.evaluation)) as conn:
            snapshot = json.loads(conn.execute('SELECT snapshot FROM judgment_freeze').fetchone()[0])
            self.assertEqual(conn.execute('SELECT count(*) FROM judgments').fetchone()[0], 2)
        self.assertEqual({j['label'] for j in snapshot[0]['judgments']}, {'yes', 'no'})
        self.assertEqual(snapshot[0]['resolution']['resolution_id'], 'resolution-1')
        with self.assertRaises(ValueError):
            self.resolve({**entry, 'resolution_id': 'late', 'supersedes': 'resolution-1'})

    def test_independence_basis_and_consent(self):
        entry = self.dispute()
        for changed in ({'adjudicator': 'r1'}, {'based_on': ['s1']}, {'label': 'invalid'},
                        {'evidence_ids': ['bad']}, {'based_on': ['s1', 's1']}):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                self.resolve({**entry, **changed})
        with self.assertRaises(ValueError):
            resolve_disagreement(self.evaluation, entry, human_confirmed=True)
        record_exposure(self.evaluation, 'synthetic-study', operator='op', evidence_reference='incident')
        with self.assertRaises(ValueError):
            self.resolve(entry)

    def test_reviewer_correction_stales_resolution_until_reissued(self):
        entry = self.dispute()
        self.resolve(entry)
        submit_judgment(self.evaluation, self._entry('s3', self.assignments[1], reviewer='r2',
                                                   label='yes', supersedes='s2'), human_confirmed=True)
        with self.assertRaises(ValueError):
            self.freeze()
        corrected = {**entry, 'resolution_id': 'resolution-2', 'based_on': ['s1', 's3'],
                     'supersedes': 'resolution-1', 'outcome': 'abstain', 'label': None, 'evidence_ids': []}
        self.resolve(corrected)
        self.freeze()

    def test_added_reviewer_invalidates_basis(self):
        entry = self.dispute()
        self.resolve(entry)
        a = assign_review(self.evaluation, self.review_id, reviewer='r3', operator='op', no_prior_exposure=True)
        with self.assertRaises(ValueError):
            self.freeze()
        submit_judgment(self.evaluation, self._entry('s3', a['assignment_id'], reviewer='r3'), human_confirmed=True)
        with self.assertRaises(ValueError):
            self.freeze()

    def test_cli(self):
        entry = self.dispute()
        path = self.root / 'resolution.json'
        path.write_text(json.dumps(entry), encoding='utf-8')
        with patch('pa_cli.keys.load_env_into_environ', return_value=0), patch('pa_cli.keys.cmd_remind', return_value=0):
            result = CliRunner().invoke(main, ['jev', 'review-resolve', '--db', str(self.evaluation),
                '--entry', str(path), '--confirm-human-judgment', '--confirm-no-prior-exposure'])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue(json.loads(result.output)['original_judgments_preserved'])


if __name__ == '__main__':
    unittest.main()
