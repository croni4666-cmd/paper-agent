"""Unit + e2e tests for pa_cli.export_screening ([P2-8]).

Run:
  python -m pytest test_output/_test_export_screening.py -v
or
  python test_output/_test_export_screening.py
"""
import csv
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, '.')

from pa_cli.export_screening import (
    build_screening_dict,
    load_judgements,
    merge_with_bib,
    write_csv,
    run_export_screening,
    CSV_COLUMNS,
)


SAMPLE_BIB = """@article{key1,
  title = {Paper One: AI Tutoring},
  author = {Smith, John and Doe, Jane},
  year = {2023},
  journal = {JML},
  doi = {10.1234/jml.2023.001},
  abstract = {This paper studies AI tutoring effects on K-12 students. We find a 0.3 SD lift.}
}

@inproceedings{key2,
  title = {Paper Two: ChatGPT in HE},
  author = {Jones, Alice and Wang, Bob},
  year = {2024},
  booktitle = {CHI},
  doi = {10.5678/chi.2024.002}
}

@article{key3,
  title = {Paper Three: No Abstract},
  author = {Lonely, Author},
  year = {2020},
  journal = {Orphan}
}
"""


def _setup_judges_db(path: Path) -> None:
    """Create a fresh judgements.sqlite with 3 rows for testing."""
    conn = sqlite3.connect(str(path))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS judgements (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            query        TEXT    NOT NULL,
            paper_key    TEXT    NOT NULL,
            paper_title  TEXT,
            relevance    INTEGER NOT NULL CHECK (relevance IN (0, 1, 2)),
            reason       TEXT,
            source       TEXT    NOT NULL DEFAULT 'manual',
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(query, paper_key)
        );
    """)
    conn.execute(
        "INSERT INTO judgements (query, paper_key, paper_title, relevance, reason, source) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("AI literacy", "key1", "Paper One", 2, "Direct hit on AI + K-12", "manual")
    )
    conn.execute(
        "INSERT INTO judgements (query, paper_key, paper_title, relevance, reason, source) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("AI literacy", "key2", "Paper Two", 1, "Topic adjacent, level wrong", "manual")
    )
    conn.execute(
        "INSERT INTO judgements (query, paper_key, paper_title, relevance, reason, source) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("digital divide", "key2", "Paper Two", 0, "Off-topic for divide query", "bulk-import")
    )
    conn.commit()
    conn.close()


class TestBuildScreeningDict(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.bib = self.tmpdir / 'refs.bib'
        self.bib.write_text(SAMPLE_BIB, encoding='utf-8')

    def test_all_3_papers_extracted(self):
        d = build_screening_dict(self.bib)
        self.assertEqual(set(d.keys()), {'key1', 'key2', 'key3'})

    def test_title_extracted(self):
        d = build_screening_dict(self.bib)
        self.assertIn('AI Tutoring', d['key1']['title'])

    def test_authors_normalized_and_semicolon_joined(self):
        d = build_screening_dict(self.bib)
        # 'Smith, John and Doe, Jane' -> 'Smith, John; Doe, Jane'
        self.assertEqual(d['key1']['authors'], 'Smith, John; Doe, Jane')
        self.assertEqual(d['key2']['authors'], 'Jones, Alice; Wang, Bob')

    def test_year_extracted(self):
        d = build_screening_dict(self.bib)
        self.assertEqual(d['key1']['year'], '2023')
        self.assertEqual(d['key2']['year'], '2024')

    def test_venue_falls_back_to_journal_then_booktitle(self):
        d = build_screening_dict(self.bib)
        self.assertEqual(d['key1']['venue'], 'JML')  # journal
        self.assertEqual(d['key2']['venue'], 'CHI')  # booktitle
        self.assertEqual(d['key3']['venue'], 'Orphan')

    def test_doi_extracted(self):
        d = build_screening_dict(self.bib)
        self.assertEqual(d['key1']['doi'], '10.1234/jml.2023.001')

    def test_bib_url_constructed(self):
        d = build_screening_dict(self.bib)
        self.assertEqual(d['key1']['bib_url'], 'https://doi.org/10.1234/jml.2023.001')
        self.assertEqual(d['key2']['bib_url'], 'https://doi.org/10.5678/chi.2024.002')
        self.assertEqual(d['key3']['bib_url'], '')  # no doi

    def test_abstract_extracted(self):
        d = build_screening_dict(self.bib)
        self.assertIn('AI tutoring effects', d['key1']['abstract'])
        self.assertEqual(d['key2']['abstract'], '')  # no abstract field
        self.assertEqual(d['key3']['abstract'], '')

    def test_type_extracted(self):
        d = build_screening_dict(self.bib)
        self.assertEqual(d['key1']['type'], 'article')
        self.assertEqual(d['key2']['type'], 'inproceedings')


class TestLoadJudgements(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.db = self.tmpdir / 'judges.sqlite'
        _setup_judges_db(self.db)

    def test_load_all(self):
        rows = load_judgements(self.db)
        self.assertEqual(len(rows), 3)

    def test_load_filtered_by_query(self):
        rows = load_judgements(self.db, query='AI literacy')
        self.assertEqual(len(rows), 2)
        for r in rows:
            self.assertEqual(r['query'], 'AI literacy')

    def test_load_nonexistent_db_returns_empty(self):
        rows = load_judgements(self.tmpdir / 'nonexistent.sqlite')
        self.assertEqual(rows, [])

    def test_load_sorted_by_relevance_desc(self):
        rows = load_judgements(self.db, query='AI literacy')
        relevances = [r['relevance'] for r in rows]
        self.assertEqual(relevances, sorted(relevances, reverse=True))


class TestMergeWithBib(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.bib = self.tmpdir / 'refs.bib'
        self.bib.write_text(SAMPLE_BIB, encoding='utf-8')
        self.bib_dict = build_screening_dict(self.bib)

    def test_includes_unrated_by_default(self):
        judge_rows = [
            {'query': 'q1', 'paper_key': 'key1', 'relevance': 2,
             'reason': 'r', 'source': 'manual', 'paper_title': 't1'},
        ]
        merged = merge_with_bib(self.bib_dict, judge_rows, include_unrated=True)
        # 1 judge row + 2 unrated (key2, key3)
        self.assertEqual(len(merged), 3)
        # Unrated rows have empty relevance
        for row in merged:
            if row['paper_key'] in ('key2', 'key3'):
                self.assertEqual(row['relevance'], '')

    def test_excludes_unrated_when_requested(self):
        judge_rows = [
            {'query': 'q1', 'paper_key': 'key1', 'relevance': 2,
             'reason': 'r', 'source': 'manual', 'paper_title': 't1'},
        ]
        merged = merge_with_bib(self.bib_dict, judge_rows, include_unrated=False)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]['paper_key'], 'key1')

    def test_unrated_inherits_bib_metadata(self):
        merged = merge_with_bib(self.bib_dict, [], include_unrated=True)
        # All 3 papers, all with bib metadata
        for row in merged:
            self.assertIn('title', row)
            self.assertIn('authors', row)
            self.assertIn('year', row)


class TestWriteCsv(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.csv_path = self.tmpdir / 'out.csv'

    def test_write_creates_csv_with_header(self):
        rows = [
            {'paper_key': 'k1', 'query': 'q1', 'relevance': 2, 'reason': 'r',
             'source': 'manual', 'title': 'T1', 'authors': 'A1', 'year': '2023',
             'venue': 'V1', 'doi': '10.1/abc', 'abstract': 'abs1', 'type': 'article',
             'bib_url': 'https://doi.org/10.1/abc'},
        ]
        n = write_csv(rows, self.csv_path)
        self.assertEqual(n, 1)
        self.assertTrue(self.csv_path.exists())

    def test_csv_has_13_columns(self):
        rows = [{'paper_key': 'k1', 'query': '', 'relevance': '', 'reason': '',
                 'source': '', 'title': '', 'authors': '', 'year': '',
                 'venue': '', 'doi': '', 'abstract': '', 'type': '', 'bib_url': ''}]
        write_csv(rows, self.csv_path)
        with open(self.csv_path, encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            self.assertEqual(len(reader.fieldnames), 13)
            self.assertEqual(set(reader.fieldnames), set(CSV_COLUMNS))

    def test_csv_properly_quoted_multiline_abstract(self):
        # Abstract with newline + comma should be quoted
        rows = [{
            'paper_key': 'k1', 'query': '', 'relevance': '', 'reason': '',
            'source': '', 'title': 'T1', 'authors': 'A1', 'year': '2023',
            'venue': 'V1', 'doi': '', 'abstract': 'Line 1\nLine 2, with comma',
            'type': '', 'bib_url': '',
        }]
        write_csv(rows, self.csv_path)
        with open(self.csv_path, encoding='utf-8-sig') as f:
            content = f.read()
        # Multiline should be quoted (csv.QUOTE_MINIMAL does it for any value
        # containing newline)
        self.assertIn('"Line 1\nLine 2, with comma"', content)

    def test_csv_utf8_bom_for_excel(self):
        rows = [{'paper_key': 'k1', 'query': '', 'relevance': '', 'reason': '',
                 'source': '', 'title': '', 'authors': '', 'year': '',
                 'venue': '', 'doi': '', 'abstract': '', 'type': '', 'bib_url': ''}]
        write_csv(rows, self.csv_path)
        with open(self.csv_path, 'rb') as f:
            first_3_bytes = f.read(3)
        self.assertEqual(first_3_bytes, b'\xef\xbb\xbf')  # UTF-8 BOM

    def test_csv_handles_chinese(self):
        rows = [{
            'paper_key': 'k1', 'query': '数字普惠金融', 'relevance': 2, 'reason': '直接命中',
            'source': 'manual', 'title': '论文一', 'authors': '张三; 李四', 'year': '2024',
            'venue': '金融研究', 'doi': '', 'abstract': '中文摘要',
            'type': 'article', 'bib_url': '',
        }]
        write_csv(rows, self.csv_path)
        with open(self.csv_path, encoding='utf-8-sig') as f:
            content = f.read()
        self.assertIn('数字普惠金融', content)
        self.assertIn('中文摘要', content)


class TestRunExportScreeningE2E(unittest.TestCase):
    """End-to-end: Bibtex + judge db → CSV"""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.bib = self.tmpdir / 'refs.bib'
        self.bib.write_text(SAMPLE_BIB, encoding='utf-8')
        self.db = self.tmpdir / 'judges.sqlite'
        _setup_judges_db(self.db)
        self.csv = self.tmpdir / 'screening.csv'

    def test_e2e_bib_only(self):
        result = run_export_screening(self.bib, self.csv)
        self.assertEqual(result['n_bib_papers'], 3)
        self.assertEqual(result['n_judge_rows'], 0)
        self.assertEqual(result['n_csv_rows'], 3)
        self.assertEqual(result['n_unrated'], 3)

    def test_e2e_bib_with_all_judges(self):
        result = run_export_screening(self.bib, self.csv, judges_db=self.db)
        self.assertEqual(result['n_bib_papers'], 3)
        self.assertEqual(result['n_judge_rows'], 3)
        self.assertEqual(result['n_csv_rows'], 3 + 1)  # 3 judge rows + 1 unrated (key3)
        self.assertEqual(result['n_unrated'], 1)

    def test_e2e_filter_by_query(self):
        result = run_export_screening(
            self.bib, self.csv, judges_db=self.db, query='AI literacy'
        )
        self.assertEqual(result['n_judge_rows'], 2)
        # CSV has 2 judge rows + 1 unrated (key3) — key2 IS in judge for AI literacy
        # so the unrated set is just key3
        self.assertEqual(result['n_csv_rows'], 3)

    def test_e2e_no_unrated(self):
        result = run_export_screening(
            self.bib, self.csv, judges_db=self.db, include_unrated=False
        )
        # 3 judge rows, no unrated
        self.assertEqual(result['n_csv_rows'], 3)
        self.assertEqual(result['n_unrated'], 0)

    def test_e2e_csv_is_parseable(self):
        run_export_screening(self.bib, self.csv, judges_db=self.db)
        with open(self.csv, encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        self.assertGreater(len(rows), 0)
        # Each row has all 13 columns
        for row in rows:
            self.assertEqual(len(row), 13)
        # First row is one of the judge rows (sorted by query, then relevance desc)
        self.assertEqual(rows[0]['query'], 'AI literacy')
        self.assertEqual(rows[0]['paper_key'], 'key1')  # rel=2, comes first
        self.assertEqual(rows[0]['relevance'], '2')


if __name__ == '__main__':
    unittest.main(verbosity=2)
