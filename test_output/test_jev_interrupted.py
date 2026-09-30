"""Interrupted request quarantine and late settlement races, entirely local."""
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from click.testing import CliRunner
from pa_cli.cli import main
from pa_cli.jev_cli import ledger_status
from pa_cli.jev_dispatch import Ledger
from pa_cli.jev_recovery import reconcile_usage
import pa_cli.jev_recovery as recovery


class InterruptedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / 'dispatch.sqlite'
        self.config = dict(model='jev-test', mode='injected-test-transport', rate='0.000001',
                           max_papers=25, max_input_tokens=1000, max_cost_usd='0.01')
        self.ledger = Ledger(self.db)
        self.addCleanup(self.ledger.close)
        self.ledger.claim('run', self.config, 'req', {'request': 'PRIVATE_TEXT'}, 100)

    def quarantine(self, **updates):
        args = dict(operator='op', evidence_reference='incident-1', interruption_confirmed=True)
        args.update(updates)
        return recovery.quarantine_request(self.db, 'run', 'req', **args)

    def reconcile(self, tokens):
        return reconcile_usage(self.db, 'run', 'req', actual_input_tokens=tokens,
                               confirmed_model='jev-test', operator='op', evidence_reference='receipt-1',
                               final_usage_confirmed=True)

    def test_quarantine_keeps_reservation_and_blocks_new_dispatch(self):
        self.assertEqual(self.quarantine()['status'], 'interrupted')
        state = ledger_status(self.db, 'run')
        self.assertTrue(state['halted'])
        self.assertTrue(state['has_unresolved_requests'])
        self.assertEqual(state['accounted_input_tokens'], 100)
        self.assertEqual(self.ledger.claim('run', self.config, 'req', {}, 100)['status'], 'interrupted')
        with self.assertRaises(ValueError):
            self.ledger.claim('run', self.config, 'other', {}, 1)
        self.assertEqual(self.ledger.begin_send('req')['status'], 'interrupted')

    def test_requires_attestation_and_pending_state(self):
        before = self.db.read_bytes()
        for update in ({'interruption_confirmed': False}, {'operator': ''}, {'evidence_reference': ''}):
            with self.assertRaises(ValueError):
                self.quarantine(**update)
            self.assertEqual(before, self.db.read_bytes())
        self.ledger.settle('req', {'status': 'completed'}, 80)
        with self.assertRaises(ValueError):
            self.quarantine()

    def test_late_known_result_requires_review(self):
        self.quarantine()
        result = self.ledger.settle('req', {'status': 'completed',
                                          'routes': {'support': {'route': 'triage_suggestion'}}}, 80)
        self.assertEqual(result['status'], 'late_result_review')
        self.assertEqual(result['routes']['support']['route'], 'human_review')
        self.assertEqual(result['late_result']['reported_input_tokens'], 80)
        self.assertTrue(ledger_status(self.db, 'run')['halted'])
        self.assertEqual(ledger_status(self.db, 'run')['accounted_input_tokens'], 80)
        self.assertTrue(ledger_status(self.db, 'run')['has_unresolved_requests'])
        self.reconcile(80)
        self.assertFalse(ledger_status(self.db, 'run')['has_unresolved_requests'])

    def test_late_unknown_result_keeps_reservation(self):
        self.quarantine()
        result = self.ledger.settle('req', {'status': 'unknown'})
        self.assertEqual(result['status'], 'late_result_review')
        self.assertEqual(ledger_status(self.db, 'run')['accounted_input_tokens'], 100)

    def test_late_result_after_human_reconciliation_does_not_erase_evidence(self):
        self.quarantine()
        self.reconcile(0)
        result = self.ledger.settle('req', {'status': 'completed'}, 120)
        self.assertEqual(result['status'], 'late_result_review')
        self.assertEqual(result['prior_reconciliation']['actual_input_tokens'], 0)
        self.assertEqual(ledger_status(self.db, 'run')['accounted_input_tokens'], 120)
        events = self.ledger.conn.execute('SELECT status FROM events ORDER BY event_id').fetchall()
        self.assertEqual(json.loads(events[-2][0])['event'], 'operator_usage_reconciled')
        self.assertEqual(json.loads(events[-1][0])['event'], 'late_result_after_quarantine')

    def test_late_smaller_usage_does_not_reduce_verified_accounting(self):
        self.quarantine()
        self.reconcile(120)
        self.ledger.settle('req', {'status': 'completed'}, 80)
        self.assertEqual(ledger_status(self.db, 'run')['accounted_input_tokens'], 120)

    def test_late_unknown_after_zero_restores_original_reservation(self):
        self.quarantine()
        self.reconcile(0)
        self.ledger.settle('req', {'status': 'unknown'})
        self.assertEqual(ledger_status(self.db, 'run')['accounted_input_tokens'], 100)

    def test_quarantine_event_failure_rolls_back(self):
        with self.ledger.conn:
            self.ledger.conn.execute("CREATE TRIGGER block_event BEFORE INSERT ON events BEGIN SELECT RAISE(ABORT,'blocked'); END")
        before = self.db.read_bytes()
        with self.assertRaises(sqlite3.IntegrityError):
            self.quarantine()
        self.assertEqual(before, self.db.read_bytes())

    def test_normal_reconciled_unknown_cannot_receive_duplicate_settlement(self):
        self.ledger.settle('req', {'status': 'unknown'})
        self.reconcile(80)
        with self.assertRaises(ValueError):
            self.ledger.settle('req', {'status': 'completed'}, 90)

    def test_late_event_failure_rolls_back_accounting(self):
        self.quarantine()
        self.reconcile(0)
        with self.ledger.conn:
            self.ledger.conn.execute("CREATE TRIGGER block_late BEFORE INSERT ON events BEGIN SELECT RAISE(ABORT,'blocked'); END")
        before = self.db.read_bytes()
        with self.assertRaises(sqlite3.IntegrityError):
            self.ledger.settle('req', {'status': 'completed'}, 120)
        self.assertEqual(before, self.db.read_bytes())

    def test_cli_quarantine_does_not_leak_payload(self):
        args = ['jev', 'quarantine', '--db', str(self.db), '--run-id', 'run', '--request-id', 'req',
                '--operator', 'op', '--evidence-reference', 'incident-1']
        runner = CliRunner()
        with patch('pa_cli.keys.load_env_into_environ', return_value=0), patch('pa_cli.keys.cmd_remind'):
            self.assertNotEqual(runner.invoke(main, args).exit_code, 0)
            result = runner.invoke(main, args + ['--confirm-interrupted'])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertNotIn('PRIVATE_TEXT', result.output)
        self.assertEqual(json.loads(result.output)['status'], 'interrupted')


if __name__ == '__main__':
    unittest.main()
