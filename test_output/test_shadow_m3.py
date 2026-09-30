"""Offline M3 integration tests with real PDF/index/packet and SQLite."""
import sys
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pymupdf
from pa_cli.evidence import build_index, build_packet


class ShadowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.pdf = self.root / 'paper.pdf'
        with pymupdf.open() as doc:
            doc.new_page().insert_text((72,72), 'Results\nEmployment increased among workers.')
            doc.set_xml_metadata('''<x:xmpmeta xmlns:x="adobe:ns:meta/" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><rdf:RDF><rdf:Description xmlns:prism="http://prismstandard.org/namespaces/basic/2.0/" xmlns:cc="http://creativecommons.org/ns#"><prism:doi>10.1234/study</prism:doi><cc:license rdf:resource="https://creativecommons.org/licenses/by/4.0/"/></rdf:Description></rdf:RDF></x:xmpmeta>''')
            doc.save(self.pdf)
        self.index = build_index(self.pdf)
        self.packet = build_packet(self.index, 'employment')
        self.db = self.root / 'shadow.sqlite'
        self.fetch_result = {'doi':'10.1234/study', 'via_channel':'pmc',
                             'via_url':'https://europepmc.org/articles/PMC1?pdf=render'}
        self.rubric = {'task':'evidence_support', 'version':'pilot-1',
                       'question':'Does the passage support employment increasing?',
                       'labels':['supported','unsupported','uncertain']}

    def run_shadow(self, **overrides):
        from pa_cli.shadow import run_shadow, FixtureProvider
        args = dict(pdf=self.pdf, index=self.index, packet=self.packet,
                    fetch_result=self.fetch_result, rubric=self.rubric,
                    db_path=self.db, data_class='public',
                    provider=FixtureProvider({'supported':0.8,'unsupported':0.1,'uncertain':0.1}))
        args.update(overrides)
        return run_shadow(**args)

    def test_offline_result_is_suggestion_and_never_truth(self):
        result = self.run_shadow()
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['suggestion']['label'], 'supported')
        self.assertTrue(result['suggestion']['synthetic'])
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute('select count(*) from suggestions').fetchone()[0], 1)
            self.assertEqual(conn.execute('select count(*) from adjudications').fetchone()[0], 0)
            self.assertEqual([r[0] for r in conn.execute('select status from events order by event_id')], ['prepared','dispatched','completed'])

    def test_private_or_unverified_inputs_are_logged_but_blocked(self):
        result = self.run_shadow(data_class='unpublished')
        self.assertEqual(result['status'], 'blocked')
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute('select count(*) from suggestions').fetchone()[0], 0)

    def test_modified_pdf_rejects_stale_packet(self):
        self.pdf.write_bytes(self.pdf.read_bytes() + b'\n% change')
        with self.assertRaises(ValueError):
            self.run_shadow()

    def test_tampered_packet_rejected(self):
        self.packet['evidence'][0]['text'] = 'invented'
        with self.assertRaises(ValueError):
            self.run_shadow()

    def test_duplicate_request_reuses_stored_outcome(self):
        first = self.run_shadow()
        second = self.run_shadow()
        self.assertEqual(first['request_id'], second['request_id'])
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute('select count(*) from requests').fetchone()[0], 1)
            self.assertEqual(conn.execute('select count(*) from events').fetchone()[0], 3)

    def test_unknown_outcome_is_not_retried(self):
        from pa_cli.shadow import FixtureProvider
        class Broken(FixtureProvider):
            def evaluate(self, packet, rubric):
                with closing(sqlite3.connect(self_db)) as conn:
                    assert conn.execute('select count(*) from requests').fetchone()[0] == 1
                raise TimeoutError('private passage must not enter event logs')
        self_db = self.db
        p = Broken({'supported':0.8,'unsupported':0.1,'uncertain':0.1})
        self.assertEqual(self.run_shadow(provider=p)['status'], 'unknown')
        self.assertEqual(self.run_shadow(provider=p)['status'], 'unknown')
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute('select count(*) from events').fetchone()[0], 3)
            self.assertNotIn('private passage', str(conn.execute('select details_json from events').fetchall()))

    def test_invalid_probabilities_never_become_suggestions(self):
        from pa_cli.shadow import FixtureProvider
        result = self.run_shadow(provider=FixtureProvider({'supported':float('nan'),'unsupported':0.1,'uncertain':0.1}))
        self.assertEqual(result['status'], 'invalid_response')
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute('select count(*) from suggestions').fetchone()[0], 0)

    def test_ledger_rejects_mutation(self):
        self.run_shadow()
        with closing(sqlite3.connect(self.db)) as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("update requests set rubric_json='{}'")
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute('delete from events')

    def test_external_provider_is_rejected(self):
        from pa_cli.shadow import FixtureProvider
        provider = FixtureProvider({})
        provider.offline = False
        with self.assertRaises(ValueError):
            self.run_shadow(provider=provider)
        self.assertFalse(self.db.exists())

    def test_existing_human_database_is_untouched(self):
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute('create table relevance_labels(label text)')
            conn.execute("insert into relevance_labels values ('human label')")
            conn.commit()
        before = self.db.read_bytes()
        with self.assertRaises(ValueError):
            self.run_shadow()
        self.assertEqual(before, self.db.read_bytes())

    def test_title_requirement_is_preserved(self):
        result = self.run_shadow(expected_title='Required title not available in PDF')
        self.assertEqual(result['status'], 'blocked')
        self.assertIn('article_title_missing', result['details']['reasons'])

    def test_empty_page_blocks_dispatch(self):
        replacement = self.root / 'new.pdf'
        with pymupdf.open(self.pdf) as doc:
            doc.new_page()
            doc.save(replacement)
        self.pdf = replacement
        self.index = build_index(self.pdf)
        self.packet = build_packet(self.index, 'employment')
        result = self.run_shadow()
        self.assertEqual(result['status'], 'blocked')
        self.assertIn('extraction_needs_review', result['details']['reasons'])


if __name__ == '__main__':
    unittest.main()
