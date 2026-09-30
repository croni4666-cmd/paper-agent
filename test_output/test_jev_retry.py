"""Explicit resume and deterministic linked retries with synthetic transport."""
from pathlib import Path
import json
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import sqlite3

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import test_jev_dispatch as fixture
from pa_cli.evidence import _hash
from pa_cli.jev import prepare_request
from pa_cli.jev_dispatch import Approval, Ledger
from pa_cli.jev_cli import ledger_status
from pa_cli.jev_recovery import reconcile_usage, quarantine_request
import pa_cli.jev_recovery as recovery
from click.testing import CliRunner
from pa_cli.cli import main


class RetryTests(unittest.TestCase):
    def setUp(self):
        fixture.DispatchTests.setUp(self)
        self.db = self.root / 'dispatch.sqlite'

    def dispatch(self, **updates):
        if updates.get('retry_of') is not None and 'approval' not in updates:
            updates['approval'] = Approval('run-1', _hash(prepare_request(self.packet, self.q, 'jev-test')),
                                          True, True, datetime.now(timezone.utc)+timedelta(minutes=5),
                                          max_input_tokens=200, retry_of=updates['retry_of'])
        return fixture.DispatchTests.dispatch(self, **updates)

    def unknown(self):
        def failed(*args):
            self.calls += 1
            raise TimeoutError('synthetic')
        return self.dispatch(transport=failed)['request_id']

    def reconcile(self, request_id, tokens=80):
        return reconcile_usage(self.db, 'run-1', request_id, actual_input_tokens=tokens,
                               confirmed_model='jev-test', operator='op', evidence_reference='receipt',
                               final_usage_confirmed=True)

    def resume(self, **updates):
        args = dict(operator='op', evidence_reference='review', workers_stopped_confirmed=True,
                    final_usage_confirmed=True)
        args.update(updates)
        return recovery.resume_run(self.db, 'run-1', **args)

    def test_unresolved_or_unattested_resume_is_refused(self):
        parent = self.unknown()
        with self.assertRaises(ValueError):
            self.resume()
        self.reconcile(parent)
        with self.assertRaises(ValueError):
            self.resume(workers_stopped_confirmed=False)
        with self.assertRaises(ValueError):
            self.resume(final_usage_confirmed=False)
        self.assertTrue(ledger_status(self.db, 'run-1')['halted'])

    def test_resume_preserves_limits_usage_and_appends_event(self):
        parent = self.unknown()
        self.reconcile(parent)
        before = ledger_status(self.db, 'run-1')
        self.resume()
        after = ledger_status(self.db, 'run-1')
        self.assertFalse(after['halted'])
        self.assertEqual(before['limits'], after['limits'])
        self.assertEqual(after['accounted_input_tokens'], 80)
        self.assertEqual(after['request_count'], 1)
        with sqlite3.connect(self.db) as conn:
            event = json.loads(conn.execute('SELECT status FROM events ORDER BY event_id DESC LIMIT 1').fetchone()[0])
        conn.close()
        self.assertEqual(event['event'], 'operator_resumed_run')

    def test_linked_retry_is_deduplicated_and_keeps_parent_cost(self):
        parent = self.unknown()
        self.reconcile(parent)
        self.resume()
        child = self.dispatch(retry_of=parent)
        again = self.dispatch(retry_of=parent)
        self.assertEqual(child, again)
        self.assertEqual(self.calls, 2)
        self.assertNotEqual(child['request_id'], parent)
        self.assertEqual(child['retry_of'], parent)
        state = ledger_status(self.db, 'run-1', True)
        self.assertEqual(state['accounted_input_tokens'], 160)
        self.assertEqual(state['request_count'], 2)
        row = next(r for r in state['requests'] if r['request_id'] == child['request_id'])
        self.assertEqual(row['retry_of'], parent)

    def test_retry_requires_retry_specific_approval(self):
        parent = self.unknown()
        self.reconcile(parent)
        self.resume()
        approval = Approval('run-1', _hash(prepare_request(self.packet, self.q, 'jev-test')),
                            True, True, self.now+timedelta(minutes=5), max_input_tokens=200)
        with self.assertRaises(ValueError):
            self.dispatch(retry_of=parent, approval=approval)
        self.assertEqual(self.calls, 1)

    def test_completed_parent_and_changed_payload_are_refused(self):
        complete = self.dispatch()['request_id']
        with self.assertRaises(ValueError):
            self.dispatch(retry_of=complete)
        self.q['support']['instructions'] = 'Changed question'
        with self.assertRaises(ValueError):
            self.dispatch(retry_of=complete)
        self.assertEqual(self.calls, 1)

    def test_retry_cannot_exceed_remaining_budget(self):
        parent = self.unknown()
        self.reconcile(parent, 150)
        self.resume()
        with self.assertRaises(ValueError):
            self.dispatch(retry_of=parent)
        self.assertEqual(self.calls, 1)
        self.assertEqual(ledger_status(self.db, 'run-1')['accounted_input_tokens'], 150)

    def test_eligible_parent_cannot_retry_changed_payload_or_other_run(self):
        parent = self.unknown()
        self.reconcile(parent)
        self.resume()
        old = self.q['support']['instructions']
        self.q['support']['instructions'] = 'Changed rubric content'
        with self.assertRaises(ValueError):
            self.dispatch(retry_of=parent)
        self.q['support']['instructions'] = old
        approval = Approval('run-2', _hash(prepare_request(self.packet, self.q, 'jev-test')),
                            True, True, self.now+timedelta(minutes=5), max_input_tokens=200, retry_of=parent)
        with self.assertRaises(ValueError):
            self.dispatch(retry_of=parent, run_id='run-2', approval=approval)
        self.assertEqual(self.calls, 1)
        with sqlite3.connect(self.db) as conn:
            self.assertIsNone(conn.execute("SELECT 1 FROM runs WHERE run_id='run-2'").fetchone())
        conn.close()

    def test_retry_link_is_immutable_and_child_can_form_a_chain(self):
        parent = self.unknown()
        self.reconcile(parent, 0)
        self.resume()
        def failed(*args):
            self.calls += 1
            raise TimeoutError('synthetic')
        child = self.dispatch(retry_of=parent, transport=failed)['request_id']
        self.reconcile(child, 0)
        self.resume()
        final = self.dispatch(retry_of=child)
        self.assertEqual(final['retry_of'], child)
        self.assertEqual(self.calls, 3)
        self.assertEqual(ledger_status(self.db, 'run-1')['request_count'], 3)
        with sqlite3.connect(self.db) as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute('DELETE FROM retry_links')
        conn.close()

    def test_concurrent_retry_creates_one_child(self):
        parent = self.unknown()
        self.reconcile(parent)
        self.resume()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.dispatch(retry_of=parent), range(2)))
        self.assertEqual(len({r['request_id'] for r in results}), 1)
        self.assertEqual(self.calls, 2)

    def test_resume_event_failure_rolls_back(self):
        parent = self.unknown()
        self.reconcile(parent)
        with sqlite3.connect(self.db) as conn:
            conn.execute("CREATE TRIGGER no_resume BEFORE INSERT ON events BEGIN SELECT RAISE(ABORT,'blocked'); END")
        conn.close()
        before = self.db.read_bytes()
        with self.assertRaises(sqlite3.IntegrityError):
            self.resume()
        self.assertEqual(before, self.db.read_bytes())

    def test_stale_price_blocks_resume(self):
        parent = self.unknown()
        self.reconcile(parent)
        with patch('pa_cli.jev_recovery.datetime', wraps=datetime) as clock:
            clock.now.return_value = self.now + timedelta(days=8)
            with self.assertRaises(ValueError):
                self.resume()

    def test_late_result_after_resume_halts_again(self):
        def interrupted_transport(*args):
            with sqlite3.connect(self.db) as conn:
                parent = conn.execute('SELECT request_id FROM requests').fetchone()[0]
            conn.close()
            quarantine_request(self.db, 'run-1', parent, operator='op', evidence_reference='incident',
                               interruption_confirmed=True)
            self.reconcile(parent, 0)
            self.resume()
            return self.response
        result = self.dispatch(transport=interrupted_transport)
        self.assertEqual(result['status'], 'late_result_review')
        self.assertTrue(ledger_status(self.db, 'run-1')['halted'])

    def test_cli_resume_requires_attestation(self):
        parent = self.unknown()
        self.reconcile(parent)
        args = ['jev', 'resume', '--db', str(self.db), '--run-id', 'run-1',
                '--operator', 'op', '--evidence-reference', 'review']
        with patch('pa_cli.keys.load_env_into_environ', return_value=0), patch('pa_cli.keys.cmd_remind'):
            self.assertNotEqual(CliRunner().invoke(main, args).exit_code, 0)
            result = CliRunner().invoke(main, args+['--confirm-workers-stopped', '--confirm-final-usage'])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertFalse(json.loads(result.output)['network_called'])


if __name__ == '__main__':
    unittest.main()
