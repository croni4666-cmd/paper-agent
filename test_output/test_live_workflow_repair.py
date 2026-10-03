"""Offline regressions for the independently reproduced live-workflow defects."""
import datetime
import json
import os
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pymupdf
import pa_cli.search as search_module
from pa_cli.bibtex import clean_markup_text, to_bibtex, unescape_bibtex
from pa_cli.evidence import build_index, build_packet, _validate
from pa_cli.export_screening import build_screening_dict
from pa_cli.scaffold import parse_bibtex


# Top-level functions are genuinely spawned on Windows as well as POSIX.
def _slow_provider(*args, **kwargs):
    time.sleep(3.5)
    return []


def _fast_provider(*args, **kwargs):
    return [{'doi': '10.1234/fast', 'title': 'Fast result', 'year': 2024}]


def _late_writer(query, *args, **kwargs):
    time.sleep(3.5)
    Path(query).write_text('late write', encoding='utf-8')
    return []


def _large_provider(*args, **kwargs):
    return [{'doi': '10.1234/large', 'title': 'Large result', 'abstract': 'x' * 200000}]


def _failing_provider(*args, **kwargs):
    raise RuntimeError('controlled provider failure')


class DeadlineTests(unittest.TestCase):
    def search(self, first, engines='arxiv', query='controlled fixture'):
        with patch.object(search_module, 'SEARCH_ENGINE_TIMEOUT', 1.5, create=True), \
             patch.object(search_module, 'search_arxiv', first), \
             patch.object(search_module, 'search_openalex', _fast_provider):
            return search_module.run_search(query, engine=engines)

    def test_slow_engine_is_stopped_and_next_engine_runs(self):
        started = time.monotonic()
        result = self.search(_slow_provider, engines='arxiv,openalex')
        self.assertLess(time.monotonic() - started, 3.2)
        self.assertEqual(result['engine_status'], {'arxiv': 'error', 'openalex': 'ok'})
        self.assertIn('timed out', result['engine_errors']['arxiv'])
        self.assertEqual(result['by_engine'], {'arxiv': 0, 'openalex': 1})

    def test_timeout_leaves_no_late_worker_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            marker = Path(temp) / 'late.txt'
            result = self.search(_late_writer, query=str(marker))
            self.assertEqual(result['engine_status']['arxiv'], 'error')
            time.sleep(2.3)
            self.assertFalse(marker.exists())

    def test_receive_large_payload_before_joining_worker(self):
        result = self.search(_large_provider)
        self.assertEqual(result['engine_status']['arxiv'], 'ok')
        self.assertEqual(len(result['results'][0]['abstract']), 200000)

    def test_provider_exception_is_an_engine_error(self):
        result = self.search(_failing_provider)
        self.assertEqual(result['engine_status']['arxiv'], 'error')
        self.assertIn('controlled provider failure', result['engine_errors']['arxiv'])


class MarkupTests(unittest.TestCase):
    def test_comparisons_survive_raw_and_encoded_input(self):
        raw = 'Outcomes with HbA1c < 7% versus > 8%'
        encoded = 'Outcomes with HbA1c &lt; 7% versus &gt; 8%'
        self.assertEqual(clean_markup_text(raw), raw)
        self.assertEqual(clean_markup_text(encoded), raw)

    def test_known_markup_removed_before_entity_decoding(self):
        raw = '<jats:p data-x="a > b">x &lt; y <italic>and</italic> z &gt; w</jats:p>'
        self.assertEqual(clean_markup_text(raw), 'x < y and z > w')

    def test_programming_generics_are_text(self):
        raw = 'std::vector<int> and <T> typed values </T>'
        self.assertEqual(clean_markup_text(raw), raw)

    def test_whitespace_and_latex_escapes_preserved(self):
        self.assertEqual(unescape_bibtex('  A\\&B  '), '  A&B  ')
        self.assertEqual(clean_markup_text('<b>A</b> &amp; B'), 'A & B')


class ArxivTests(unittest.TestCase):
    def paper(self, **extra):
        return {'title': 'Software workflow', 'authors': ['Ulfsnes, Rasmus'],
                'year': 2024, 'type': 'preprint', 'arxiv_id': '2405.01543v1', **extra}

    def test_search_does_not_invent_a_doi(self):
        result = types.SimpleNamespace(doi=None, entry_id='http://arxiv.org/abs/2405.01543v1',
            title='Software workflow', authors=[types.SimpleNamespace(name='Rasmus Ulfsnes')],
            published=datetime.datetime(2024, 5, 2), pdf_url='https://arxiv.org/pdf/2405.01543v1')
        fake = types.SimpleNamespace(Client=lambda **kw: types.SimpleNamespace(results=lambda request: iter([result])),
            Search=lambda **kw: kw, SortCriterion=types.SimpleNamespace(Relevance='relevance'))
        with patch.dict(sys.modules, {'arxiv': fake}):
            papers = search_module.search_arxiv('software')
        self.assertFalse(papers[0].get('doi'))
        self.assertEqual(papers[0]['arxiv_id'], '2405.01543v1')

    def test_bibtex_and_screening_keep_typed_arxiv_reference(self):
        for legacy in ('', 'arXiv:2405.01543v1'):
            with self.subTest(legacy=legacy), tempfile.TemporaryDirectory() as temp:
                bib = to_bibtex(self.paper(doi=legacy))
                entry = parse_bibtex(bib)[0]
                self.assertFalse(entry.get('doi'))
                self.assertEqual(entry.get('eprint'), '2405.01543v1')
                self.assertEqual(entry.get('archiveprefix', '').lower(), 'arxiv')
                self.assertEqual(entry.get('url'), 'https://arxiv.org/abs/2405.01543v1')
                path = Path(temp) / 'refs.bib'
                path.write_text(bib, encoding='utf-8')
                row = next(iter(build_screening_dict(path).values()))
                self.assertFalse(row['doi'])
                self.assertEqual(row['bib_url'], 'https://arxiv.org/abs/2405.01543v1')

    def test_historical_pseudo_doi_in_screening_has_working_url(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'legacy.bib'
            path.write_text('@article{legacy,title={Paper},doi={arXiv:2405.01543v1}}', encoding='utf-8')
            row = build_screening_dict(path)['legacy']
            self.assertFalse(row['doi'])
            self.assertEqual(row['bib_url'], 'https://arxiv.org/abs/2405.01543v1')

    def test_real_doi_and_arxiv_id_both_retained(self):
        entry = parse_bibtex(to_bibtex(self.paper(doi='10.1145/3709354')))[0]
        self.assertEqual(entry.get('doi'), '10.1145/3709354')
        self.assertEqual(entry.get('eprint'), '2405.01543v1')

    def test_batch_fetch_routes_eprint_without_fake_doi(self):
        from pa_cli.fetch_batch import _fetch_one_entry
        with tempfile.TemporaryDirectory() as temp:
            entry = {'key': 'software', 'title': 'Software workflow',
                     'eprint': '2405.01543v1', 'archiveprefix': 'arXiv'}
            with patch('pa_cli.fetch.fetch', return_value={'source': 'arxiv', 'size': 100, 'path': str(Path(temp) / 'software.pdf')}) as fetch:
                result = _fetch_one_entry(entry, Path(temp), prefer='arxiv')
            self.assertTrue(result.success)
            self.assertEqual(fetch.call_args.kwargs.get('doi'), 'arXiv:2405.01543v1')
            self.assertEqual(result.doi, '')


class HeadingTests(unittest.TestCase):
    def test_numbered_subheading_retains_known_parent_section(self):
        with tempfile.TemporaryDirectory() as temp:
            pdf = Path(temp) / 'study.pdf'
            with pymupdf.open() as doc:
                doc.new_page().insert_text((72, 72), '4\nMain Results\n4.1\nProductivity Metrics\nSoftware productivity increased.')
                doc.save(pdf)
            index = build_index(pdf)
            finding = next(s for s in index['spans'] if 'Software productivity increased.' in s['text'])
            self.assertEqual(finding['section'], 'results')

    def test_inline_abstract_and_split_method_heading_roundtrip(self):
        with tempfile.TemporaryDirectory() as temp:
            pdf = Path(temp) / 'study.pdf'
            with pymupdf.open() as doc:
                doc.new_page().insert_text((72, 72), 'Title\nAbstract. Software workflow study.')
                doc.new_page().insert_text((72, 72), '3\nResearch Method and Analysis\nSoftware development was studied in interviews.')
                doc.new_page().insert_text((72, 72), '4\nResults\nSoftware workflow improvements were reported.')
                doc.save(pdf)
            index = build_index(pdf)
            _validate(index)
            self.assertTrue(any(s['section'] == 'abstract' for s in index['spans'] if s['page'] == 1))
            self.assertTrue(any(s['section'] == 'methods' for s in index['spans'] if s['page'] == 2))
            packet = build_packet(index, 'software workflow development', required_sections=('methods', 'results'))
            self.assertEqual(packet['status'], 'ready_for_local_review')
            self.assertFalse(packet['external_upload_allowed'])

    def test_unclassified_split_heading_ends_methods(self):
        with tempfile.TemporaryDirectory() as temp:
            pdf = Path(temp) / 'study.pdf'
            with pymupdf.open() as doc:
                doc.new_page().insert_text((72, 72), 'Methods\nWe interviewed developers.\n4\nWhat Is AI Used for in Software Development?\nWe report the findings.')
                doc.save(pdf)
            index = build_index(pdf)
            findings = next(s for s in index['spans'] if 'We report the findings.' in s['text'])
            self.assertEqual(findings['section'], 'unknown')


if __name__ == '__main__':
    unittest.main(verbosity=2)
