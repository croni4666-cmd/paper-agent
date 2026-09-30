"""Interactive dispatch UI checked with real PDF/ledger and injected transport."""
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pymupdf
from click.testing import CliRunner
from pa_cli.cli import main
from pa_cli.evidence import build_index, build_packet
from pa_cli.jev_dispatch import dispatch as real_dispatch


class SubmitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.pdf = self.root / 'paper.pdf'
        with pymupdf.open() as doc:
            doc.new_page().insert_text((72, 72), 'Results\nEmployment increased.')
            doc.set_xml_metadata('''<x:xmpmeta xmlns:x="adobe:ns:meta/" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><rdf:RDF><rdf:Description xmlns:prism="http://prismstandard.org/namespaces/basic/2.0/" xmlns:cc="http://creativecommons.org/ns#"><prism:doi>10.1234/study</prism:doi><cc:license rdf:resource="https://creativecommons.org/licenses/by/4.0/"/></rdf:Description></rdf:RDF></x:xmpmeta>''')
            doc.save(self.pdf)
        self.index = build_index(self.pdf)
        self.packet = build_packet(self.index, 'employment')
        for name, value in {
            'index': self.index, 'packet': self.packet,
            'questions': {'support': {'type': 'noul', 'instructions': 'Does employment increase?'}},
            'fetch': {'doi': '10.1234/study', 'via_channel': 'pmc', 'via_url': 'https://europepmc.org/articles/PMC1?pdf=render'},
        }.items():
            (self.root / f'{name}.json').write_text(json.dumps(value), encoding='utf-8')
        self.job = dict(pdf='paper.pdf', index='index.json', packet='packet.json', questions='questions.json',
                        fetch_result='fetch.json', run_id='run-1', estimated_input_tokens=100, rubric_version='pilot-1',
                        data_class='public', high_stakes=False, conflicting_evidence=False,
                        price=dict(model='jev-test', usd_per_million_input='0.042',
                                   checked_at=datetime.now(timezone.utc).isoformat(), source_url='https://typesafe.ai/'))
        self.job_path = self.root / 'job.json'
        self.db = self.root / 'dispatch.sqlite'
        self.runner = CliRunner()
        self.calls = 0
        for target in ('pa_cli.keys.load_env_into_environ', 'pa_cli.keys.cmd_remind'):
            p = patch(target, return_value=0)
            p.start()
            self.addCleanup(p.stop)

    def invoke(self, flags=(), answer='', tty=False):
        self.job_path.write_text(json.dumps(self.job), encoding='utf-8')
        with patch('sys.stdin.isatty', return_value=tty):
            return self.runner.invoke(main, ['jev', 'dispatch', '--job', str(self.job_path), '--db', str(self.db), *flags], input=answer)

    def offline_dispatch(self, **kwargs):
        def transport(*args):
            self.calls += 1
            return {'model': 'jev-test', 'answers': {'support': {'type': 'noul', 'noul': 0.95}},
                    'usage': {'input_tokens': 80, 'output_tokens': 1}}
        return real_dispatch(**kwargs, transport=transport)

    def test_default_preflight_needs_no_key_and_creates_no_ledger(self):
        with patch.dict(os.environ, {}, clear=True):
            result = self.invoke()
        self.assertEqual(result.exit_code, 0, result.output)
        data = json.loads(result.output)
        self.assertFalse(data['upload_authorized'])
        self.assertFalse(data['ledger_checked'])
        self.assertIn('Employment increased.', result.output)
        self.assertEqual(data['request']['model'], 'jev-test')
        self.assertFalse(self.db.exists())

    def test_private_stale_and_overbudget_jobs_fail_before_prompt(self):
        for changes in ({'data_class': 'unpublished'}, {'estimated_input_tokens': 100001}, {'high_stakes': True}):
            old = self.job.copy()
            self.job.update(changes)
            self.assertNotEqual(self.invoke().exit_code, 0)
            self.job = old
        self.job['price']['checked_at'] = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
        self.assertNotEqual(self.invoke().exit_code, 0)
        self.assertFalse(self.db.exists())

    def test_unknown_fields_and_tampered_artifact_fail(self):
        self.job['api_key'] = 'SECRET_KEY'
        result = self.invoke()
        self.assertNotEqual(result.exit_code, 0)
        self.assertNotIn('SECRET_KEY', result.output)
        del self.job['api_key']
        self.pdf.write_bytes(b'changed PDF')
        self.assertNotEqual(self.invoke().exit_code, 0)

    def test_send_requires_pilot_attestation_terminal_and_key(self):
        for flags in (('--send',), ('--send', '--pilot-approved')):
            result = self.invoke(flags, answer='SEND\n')
            self.assertNotEqual(result.exit_code, 0)
        self.assertFalse(self.db.exists())

    def test_declining_does_not_dispatch(self):
        with patch.dict(os.environ, {'TYPESAFE_API_KEY': 'TEST_SECRET'}), \
             patch('pa_cli.jev_submit._interactive_terminal', return_value=True), \
             patch('pa_cli.jev_submit.dispatch', side_effect=AssertionError('must not dispatch')):
            result = self.invoke(('--send', '--pilot-approved'), answer='NO\n')
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertFalse(self.db.exists())
        self.assertNotIn('TEST_SECRET', result.output)

    def test_approval_dispatches_one_synthetic_request(self):
        with patch.dict(os.environ, {'TYPESAFE_API_KEY': 'TEST_SECRET'}), \
             patch('pa_cli.jev_submit._interactive_terminal', return_value=True), \
             patch('pa_cli.jev_submit.dispatch', side_effect=self.offline_dispatch):
            result = self.invoke(('--send', '--pilot-approved'), answer='SEND\n')
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(self.calls, 1)
        self.assertTrue(self.db.exists())
        self.assertNotIn('TEST_SECRET', result.output)
        self.assertNotIn(b'TEST_SECRET', self.db.read_bytes())
        with sqlite3.connect(self.db) as conn:
            snapshot = json.loads(conn.execute('SELECT snapshot FROM requests').fetchone()[0])
            self.assertTrue(snapshot['pilot_approval_attested'])
        conn.close()

    def test_missing_key_fails_in_interactive_mode(self):
        with patch.dict(os.environ, {}, clear=True), \
             patch('pa_cli.jev_submit._interactive_terminal', return_value=True):
            result = self.invoke(('--send', '--pilot-approved'), answer='SEND\n')
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn('TYPESAFE_API_KEY', result.output)
        self.assertFalse(self.db.exists())

    def test_bad_routing_policy_fails_during_preflight(self):
        for policy in ([], {'support': 0.5}, {'missing': 1}):
            self.job['score_boundaries'] = policy
            self.assertNotEqual(self.invoke().exit_code, 0)
        self.assertFalse(self.db.exists())

    def test_unknown_outcome_is_error_and_retains_budget(self):
        def unknown_dispatch(**kwargs):
            def timeout(*unused):
                self.calls += 1
                raise TimeoutError('TEST_SECRET')
            return real_dispatch(**kwargs, transport=timeout)
        with patch.dict(os.environ, {'TYPESAFE_API_KEY': 'TEST_SECRET'}), \
             patch('pa_cli.jev_submit._interactive_terminal', return_value=True), \
             patch('pa_cli.jev_submit.dispatch', side_effect=unknown_dispatch):
            result = self.invoke(('--send', '--pilot-approved'), answer='SEND\n')
        self.assertNotEqual(result.exit_code, 0)
        self.assertEqual(self.calls, 1)
        self.assertNotIn('TEST_SECRET', result.output)
        with sqlite3.connect(self.db) as conn:
            self.assertEqual(conn.execute('SELECT tokens,status FROM requests').fetchone(), (100, 'unknown'))
            self.assertEqual(conn.execute('SELECT halted FROM runs').fetchone()[0], 1)
        conn.close()

    def test_pdf_change_after_review_is_rejected_by_dispatch(self):
        def change_then_dispatch(**kwargs):
            self.pdf.write_bytes(b'changed after review')
            return self.offline_dispatch(**kwargs)
        with patch.dict(os.environ, {'TYPESAFE_API_KEY': 'TEST_SECRET'}), \
             patch('pa_cli.jev_submit._interactive_terminal', return_value=True), \
             patch('pa_cli.jev_submit.dispatch', side_effect=change_then_dispatch):
            result = self.invoke(('--send', '--pilot-approved'), answer='SEND\n')
        self.assertNotEqual(result.exit_code, 0)
        self.assertEqual(self.calls, 0)

    def test_job_cannot_overwrite_input_artifact_with_database(self):
        self.db = self.root / 'packet.json'
        before = self.db.read_bytes()
        self.assertNotEqual(self.invoke().exit_code, 0)
        self.assertEqual(before, self.db.read_bytes())

    def test_retry_target_is_displayed_and_bound_to_new_approval(self):
        self.job['retry_of'] = 'parent-request-id'
        result = self.invoke()
        self.assertEqual(json.loads(result.output)['retry_of'], 'parent-request-id')
        def inspect_approval(**kwargs):
            self.assertEqual(kwargs['retry_of'], 'parent-request-id')
            self.assertEqual(kwargs['approval'].retry_of, 'parent-request-id')
            return {'status': 'completed', 'request_id': 'synthetic-child'}
        with patch.dict(os.environ, {'TYPESAFE_API_KEY': 'TEST_SECRET'}), \
             patch('pa_cli.jev_submit._interactive_terminal', return_value=True), \
             patch('pa_cli.jev_submit.dispatch', side_effect=inspect_approval):
            result = self.invoke(('--send', '--pilot-approved'), answer='SEND\n')
        self.assertEqual(result.exit_code, 0, result.output)


if __name__ == '__main__':
    unittest.main()
