"""Offline accounting recovery, using real SQLite transactions."""
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from click.testing import CliRunner
from pa_cli.cli import main
from pa_cli.jev_dispatch import Ledger
from pa_cli.jev_cli import ledger_status
from pa_cli.jev_recovery import reconcile_usage


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / 'dispatch.sqlite'
        self.config = dict(model='jev-test', mode='injected-test-transport', rate='0.000001',
                           max_papers=25, max_input_tokens=1000, max_cost_usd='0.01')
        ledger = Ledger(self.db)
        ledger.claim('run', self.config, 'req', {'request': 'PRIVATE_PASSAGE'}, 100)
        ledger.settle('req', {'status': 'unknown', 'error_type': 'TimeoutError'})
        ledger.close()

    def recover(self, **updates):
        args = dict(actual_input_tokens=80, confirmed_model='jev-test', operator='operator-1',
                    evidence_reference='receipt-1', final_usage_confirmed=True)
        args.update(updates)
        return reconcile_usage(self.db, 'run', 'req', **args)

    def test_known_usage_keeps_halt_and_original_audit(self):
        result = self.recover()
        self.assertEqual(result['status'], 'usage_reconciled')
        self.assertEqual(result['error_type'], 'TimeoutError')
        status = ledger_status(self.db, 'run', True)
        self.assertTrue(status['halted'])
        self.assertFalse(status['has_unresolved_requests'])
        self.assertEqual(status['accounted_input_tokens'], 80)
        self.assertEqual(status['requests'][0]['request_id'], 'req')
        with sqlite3.connect(self.db) as conn:
            events = conn.execute('SELECT status FROM events ORDER BY event_id').fetchall()
            self.assertEqual([r[0] for r in events[:2]], ['reserved_before_dispatch', 'unknown'])
            self.assertEqual(json.loads(events[-1][0])['previous_accounted_tokens'], 100)
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute('DELETE FROM events')
        conn.close()
        ledger = Ledger(self.db)
        self.addCleanup(ledger.close)
        with self.assertRaises(ValueError):
            ledger.claim('run', self.config, 'new', {}, 1)
        self.assertEqual(ledger.claim('run', self.config, 'req', {}, 100)['status'], 'usage_reconciled')

    def test_zero_and_overrun_do_not_reopen_run(self):
        for value in (0, 5000):
            # Use independent fixtures without reinitializing test cleanup state.
            db = self.db.parent / f'{value}.sqlite'
            ledger = Ledger(db)
            ledger.claim('run', self.config, 'req', {}, 100)
            ledger.settle('req', {'status': 'unknown'})
            ledger.close()
            reconcile_usage(db, 'run', 'req', actual_input_tokens=value, confirmed_model='jev-test',
                            operator='op', evidence_reference='receipt', final_usage_confirmed=True)
            self.assertTrue(ledger_status(db, 'run')['halted'])
            self.assertEqual(ledger_status(db, 'run')['accounted_input_tokens'], value)

    def test_invalid_attestation_and_model_leave_db_unchanged(self):
        before = self.db.read_bytes()
        for update in ({'final_usage_confirmed': False}, {'actual_input_tokens': True},
                       {'actual_input_tokens': -1}, {'actual_input_tokens': 2**63},
                       {'confirmed_model': 'other'}, {'operator': ''}, {'evidence_reference': 'x\ny'}):
            with self.assertRaises(ValueError):
                self.recover(**update)
            self.assertEqual(before, self.db.read_bytes())

    def test_pending_and_completed_cannot_be_reconciled(self):
        for state in ('pending', 'completed'):
            db = self.db.parent / f'{state}.sqlite'
            ledger = Ledger(db)
            ledger.claim('run', self.config, 'req', {}, 100)
            if state == 'completed':
                ledger.settle('req', {'status': state}, 70)
            ledger.close()
            with self.assertRaises(ValueError):
                reconcile_usage(db, 'run', 'req', actual_input_tokens=80, confirmed_model='jev-test',
                                operator='op', evidence_reference='receipt', final_usage_confirmed=True)

    def test_concurrent_reconciliation_records_one_event(self):
        def attempt(_):
            try:
                self.recover()
                return True
            except ValueError:
                return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sum(pool.map(attempt, range(2))), 1)
        with sqlite3.connect(self.db) as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM events').fetchone()[0], 3)
        conn.close()

    def test_event_failure_rolls_back_usage_and_status(self):
        with sqlite3.connect(self.db) as conn:
            conn.execute("CREATE TRIGGER block_recovery BEFORE INSERT ON events BEGIN SELECT RAISE(ABORT,'blocked'); END")
        conn.close()
        before = self.db.read_bytes()
        with self.assertRaises(sqlite3.IntegrityError):
            self.recover()
        self.assertEqual(before, self.db.read_bytes())

    def test_cli_confirmation_and_redacted_request_listing(self):
        runner = CliRunner()
        args = ['jev', 'reconcile', '--db', str(self.db), '--run-id', 'run', '--request-id', 'req',
                '--actual-input-tokens', '80', '--confirmed-model', 'jev-test', '--operator', 'op',
                '--evidence-reference', 'receipt']
        with patch('pa_cli.keys.load_env_into_environ', return_value=0), \
             patch('pa_cli.keys.cmd_remind'), \
             patch('pa_cli.jev_dispatch.send_request', side_effect=AssertionError('network forbidden')):
            self.assertNotEqual(runner.invoke(main, args).exit_code, 0)
            result = runner.invoke(main, args + ['--confirm-final-usage'])
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertFalse(json.loads(result.output)['network_called'])
            result = runner.invoke(main, ['jev', 'status', '--db', str(self.db), '--run-id', 'run', '--requests'])
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertNotIn('PRIVATE_PASSAGE', result.output)

    def test_wrong_run_and_missing_database_fail(self):
        args = dict(actual_input_tokens=1, confirmed_model='jev-test', operator='op',
                    evidence_reference='receipt', final_usage_confirmed=True)
        with self.assertRaises(ValueError):
            reconcile_usage(self.db, 'wrong-run', 'req', **args)
        missing = self.db.parent / 'missing.sqlite'
        with self.assertRaises(FileNotFoundError):
            reconcile_usage(missing, 'run', 'req', **args)
        self.assertFalse(missing.exists())


if __name__ == '__main__':
    unittest.main()
