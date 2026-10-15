"""Generated records only: RIS structure, metadata and failure preservation."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from click.testing import CliRunner

from pa_cli.cli import main
from pa_cli.export_research import export_research
from pa_cli.project import init_project, project_export
from pa_cli.ris import render_ris, write_ris


class RISExportTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def test_unicode_repeated_authors_and_optional_fields(self):
        content = render_ris([{
            "type": "article", "key": "sample", "title": "中文 α study",
            "author": "王, 明 and Doe, Jane and {Research and Development Group}",
            "year": "2025", "journal": "Fixture Journal", "volume": "2",
            "number": "3", "pages": "10--19", "doi": "10.1000/fixture",
            "abstract": "Generated example",
        }])
        self.assertEqual(content.count('TY  - JOUR'), 1)
        self.assertEqual(content.count('AU  - '), 3)
        for expected in ('TI  - 中文 α study', 'AU  - {Research and Development Group}',
                         'SP  - 10', 'EP  - 19', 'DO  - 10.1000/fixture', 'ER  - '):
            self.assertIn(expected, content)

    def test_identifiers_and_types_do_not_invent_journal_or_doi(self):
        content = render_ris([
            {"type": "misc", "title": "Preprint", "doi": "arXiv:2401.12345"},
            {"type": "inproceedings", "title": "Conference"},
            {"type": "book", "title": "Book"},
            {"type": "phdthesis", "title": "Thesis"},
        ])
        self.assertNotIn('DO  - ', content)
        self.assertIn('UR  - https://arxiv.org/abs/2401.12345', content)
        self.assertIn('N1  - arXiv:2401.12345', content)
        for typ in ('GEN', 'CPAPER', 'BOOK', 'THES'):
            self.assertIn('TY  - ' + typ, content)
        self.assertNotIn('PY  - ', content)

    def test_field_line_breaks_cannot_create_records_or_tags(self):
        content = render_ris([{"title": "Title\rER  - \nTY  - JOUR\u2028AU  - Fake\x00", "abstract": "A\r\nB"}])
        self.assertEqual(sum(line.startswith('TY  - ') for line in content.splitlines()), 1)
        self.assertEqual(sum(line.startswith('ER  - ') for line in content.splitlines()), 1)
        self.assertEqual(sum(line.startswith('AU  - ') for line in content.splitlines()), 0)
        self.assertNotIn('\x00', content)

    def test_bibtex_file_macros_and_output_preserve_input(self):
        source = self.root / 'refs.bib'
        original = '@string{j = "Fixture"}\n@article{one,title={中文},author={A and B},journal=j,year=2024}'
        source.write_text(original, encoding='utf-8')
        out = self.root / 'refs.ris'
        result = export_research(source, target='ris', out_file=out)
        self.assertEqual(result['n_papers'], 1)
        self.assertIn('T2  - Fixture', out.read_text(encoding='utf-8'))
        self.assertEqual(source.read_text(encoding='utf-8'), original)
        self.assertIsNone(result['n_pdfs'])

    def test_search_json_and_author_objects(self):
        source = self.root / 'search.json'
        source.write_text(json.dumps({'results': [{
            'title': 'Fixture', 'authors': [{'name': '王明'}, {'given': 'Jane', 'family': 'Doe'}],
            'publication_date': '2024-04-01',
        }]}), encoding='utf-8')
        content = export_research(source, target='ris')['content']
        self.assertIn('AU  - 王明', content)
        self.assertIn('AU  - Jane Doe', content)
        self.assertIn('PY  - 2024', content)

    def test_invalid_json_schema_does_not_replace_output(self):
        source, out = self.root / 'bad.json', self.root / 'prior.ris'
        out.write_bytes(b'previous export')
        for payload in ({'unrecognized': []}, {'results': 'wrong'}, {'papers': [None]}):
            source.write_text(json.dumps(payload), encoding='utf-8')
            with self.assertRaises(ValueError):
                export_research(source, target='ris', out_file=out)
            self.assertEqual(out.read_bytes(), b'previous export')

    def test_output_cannot_alias_source(self):
        source = self.root / 'refs.bib'
        source.write_text('@article{one,title={Fixture}}', encoding='utf-8')
        before = source.read_bytes()
        with self.assertRaises(ValueError):
            export_research(source, target='ris', out_file=source)
        self.assertEqual(source.read_bytes(), before)

    def test_atomic_io_failure_preserves_old_export_and_cleans_temporary(self):
        out = self.root / 'prior.ris'
        out.write_bytes(b'previous export')
        for operation in ('fsync', 'replace'):
            with patch('pa_cli.ris.os.' + operation, side_effect=OSError('injected failure')):
                with self.assertRaises(OSError):
                    write_ris(out, 'new export')
            self.assertEqual(out.read_bytes(), b'previous export')
            self.assertEqual(list(self.root.glob('.ris-*')), [])

    def test_project_export_without_pdf_or_topics_reads_and_source_alias(self):
        projects = self.root / 'projects'
        init_project('fixture', title='Fixture', root=projects)
        refs = projects / 'fixture' / 'refs.bib'
        refs.write_text('@book{one,title={Fixture}}', encoding='utf-8')
        (projects / 'fixture' / 'topics.json').write_text('not json', encoding='utf-8')
        with patch('pathlib.Path.glob', side_effect=AssertionError('PDF inventory is out of scope')):
            result = project_export('fixture', format='ris', root=projects)
        self.assertIn('TY  - BOOK', result['content'])
        with self.assertRaises(ValueError):
            project_export('fixture', format='ris', out_file=refs, root=projects)

    def test_cli_export_is_local_and_emits_ris(self):
        source = self.root / 'refs.bib'
        source.write_text('@misc{one,title={Fixture}}', encoding='utf-8')
        with patch('pa_cli.keys.load_env_into_environ', side_effect=AssertionError('credentials')), patch(
            'socket.socket.connect', side_effect=AssertionError('network')
        ):
            result = CliRunner().invoke(main, ['export', str(source), '--target', 'ris'])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn('TY  - GEN', result.output)

    def test_cli_project_format_and_empty_collection(self):
        projects = self.root / 'projects'
        init_project('fixture', title='Fixture', root=projects)
        result = CliRunner().invoke(main, ['project', 'export', 'fixture', '--format', 'ris', '--root', str(projects)])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(export_research([], target='ris')['content'], '')


if __name__ == '__main__':
    unittest.main()
