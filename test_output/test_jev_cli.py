"""Offline CLI checks: no provider account, credentials, PDF or network needed."""
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
from pa_cli.evidence import _hash
from pa_cli.jev_dispatch import Ledger


class JevCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.runner = CliRunner()
        for target in ('pa_cli.keys.load_env_into_environ', 'pa_cli.keys.cmd_remind'):
            p = patch(target, return_value=0)
            p.start()
            self.addCleanup(p.stop)
        p = patch('pa_cli.jev_dispatch.send_request', side_effect=AssertionError('network forbidden'))
        p.start()
        self.addCleanup(p.stop)
        self.packet = {'evidence': [{'evidence_id': 'page1-span1', 'text': 'Employment increased.'}],
                       'local_path': 'PRIVATE_LOCAL_PATH'}
        self.packet['packet_hash'] = _hash(self.packet)
        self.questions = {'support': {'type': 'noul', 'instructions': 'Does employment increase?'}}
        self.p = self.root / 'packet.json'
        self.q = self.root / 'questions.json'
        self.p.write_text(json.dumps(self.packet), encoding='utf-8')
        self.q.write_text(json.dumps(self.questions), encoding='utf-8')

    def preview(self):
        return self.runner.invoke(main, ['jev', 'preview', '--packet', str(self.p),
                                         '--questions', str(self.q), '--model', 'jev-test'])

    def make_db(self):
        db = self.root / 'dispatch.sqlite'
        ledger = Ledger(db)
        config = {'model': 'jev-test', 'mode': 'injected-test-transport', 'rate': '0.000001',
                  'max_papers': 25, 'max_input_tokens': 1000, 'max_cost_usd': '0.01'}
        ledger.claim('run-1', config, 'r1', {'request': 'PRIVATE_PASSAGE'}, 100)
        ledger.close()
        return db

    def test_preview_minimizes_payload_and_does_not_authorize(self):
        result = self.preview()
        self.assertEqual(result.exit_code, 0, result.output)
        data = json.loads(result.output)
        self.assertEqual(data['request_hash'], _hash(data['request']))
        self.assertFalse(data['upload_authorized'])
        self.assertFalse(data['network_called'])
        self.assertNotIn('PRIVATE_LOCAL_PATH', result.output)
        self.assertIn('Employment increased.', result.output)

    def test_preview_rejects_changed_packet(self):
        self.packet['evidence'][0]['text'] = 'Changed'
        self.p.write_text(json.dumps(self.packet), encoding='utf-8')
        self.assertNotEqual(self.preview().exit_code, 0)

    def test_preview_rejects_invalid_json_without_echoing_text(self):
        for text in ('{"secret":"SECRET", "secret":2}', '[1,2]', '{"secret":NaN}', '{SECRET'):
            self.q.write_text(text, encoding='utf-8')
            result = self.preview()
            self.assertNotEqual(result.exit_code, 0)
            self.assertNotIn('SECRET', result.output)

    def test_status_preserves_database_and_redacts_snapshots(self):
        db = self.make_db()
        before = db.read_bytes()
        result = self.runner.invoke(main, ['jev', 'status', '--db', str(db), '--run-id', 'run-1'])
        self.assertEqual(result.exit_code, 0, result.output)
        data = json.loads(result.output)
        self.assertTrue(data['has_unresolved_requests'])
        self.assertEqual(data['accounted_input_tokens'], 100)
        self.assertFalse(data['halted'])
        self.assertNotIn('PRIVATE_PASSAGE', result.output)
        self.assertEqual(before, db.read_bytes())

    def test_status_unknown_retains_reservation_and_halt(self):
        db = self.make_db()
        ledger = Ledger(db)
        ledger.settle('r1', {'status': 'unknown'})
        ledger.close()
        result = self.runner.invoke(main, ['jev', 'status', '--db', str(db), '--run-id', 'run-1'])
        data = json.loads(result.output)
        self.assertTrue(data['halted'])
        self.assertEqual(data['states']['unknown']['accounted_input_tokens'], 100)

    def test_status_rejects_unrelated_and_missing_databases(self):
        db = self.root / 'unrelated.sqlite'
        with sqlite3.connect(db) as conn:
            conn.execute('CREATE TABLE secrets(value TEXT)')
        conn.close()
        before = db.read_bytes()
        for path in (db, self.root / 'absent.sqlite'):
            result = self.runner.invoke(main, ['jev', 'status', '--db', str(path), '--run-id', 'run-1'])
            self.assertNotEqual(result.exit_code, 0)
        self.assertEqual(before, db.read_bytes())
        self.assertFalse((self.root / 'absent.sqlite').exists())

    def test_status_missing_run_fails_and_help_is_registered(self):
        db = self.make_db()
        result = self.runner.invoke(main, ['jev', 'status', '--db', str(db), '--run-id', 'unknown'])
        self.assertNotEqual(result.exit_code, 0)
        result = self.runner.invoke(main, ['jev', '--help'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('preview', result.output)
        self.assertIn('status', result.output)


if __name__ == '__main__':
    unittest.main()
