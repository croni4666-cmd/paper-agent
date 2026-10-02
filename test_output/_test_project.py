"""Unit + e2e tests for pa_cli.project ([P2-12] Phase 1)."""
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, '.')

from pa_cli.project import (
    validate_slug, project_dir, project_files, load_meta, save_meta,
    init_project, list_projects, project_status, remove_project,
    DEFAULT_ROOT,
)


class TestValidateSlug(unittest.TestCase):
    def test_valid(self):
        # ASCII-only: alphanumeric, _, -, .
        for s in ['finlit', 'foo.bar', 'v1.2.3', 'X', 'a_b_c', 'digit-课题-is-INVALID']:
            # We test only ASCII in test_valid; 中文 part of this string is INVALID
            if '课题' in s or '中文' in s:
                continue
            try:
                validate_slug(s)
            except ValueError:
                self.fail(f"valid slug rejected: {s!r}")

    def test_invalid(self):
        for s in ['', 'has space', 'with/slash', '中文', 'my-课题', 'a*b', 'name?', '.', '..', '../evil', '..\\evil', '.hidden']:
            with self.assertRaises(ValueError, msg=f"invalid slug accepted: {s!r}"):
                validate_slug(s)


class TestInitProject(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.root = self.tmpdir / 'projects'

    def test_init_creates_files(self):
        meta = init_project('finlit', title='数字普惠金融', root=self.root)
        # meta.json exists
        self.assertTrue((self.root / 'finlit' / 'meta.json').exists())
        # refs.bib exists
        self.assertTrue((self.root / 'finlit' / 'refs.bib').exists())
        # judges.sqlite exists
        self.assertTrue((self.root / 'finlit' / 'judges.sqlite').exists())

    def test_init_meta_has_required_fields(self):
        meta = init_project('finlit', title='Test Project', description='A test',
                            root=self.root)
        self.assertEqual(meta['slug'], 'finlit')
        self.assertEqual(meta['title'], 'Test Project')
        self.assertEqual(meta['description'], 'A test')
        self.assertIn('created_at', meta)
        self.assertIn('updated_at', meta)

    def test_init_default_title(self):
        meta = init_project('foo', root=self.root)
        self.assertEqual(meta['title'], 'foo')

    def test_init_duplicate_raises(self):
        init_project('dup', root=self.root)
        with self.assertRaises(FileExistsError):
            init_project('dup', root=self.root)

    def test_init_invalid_slug_raises(self):
        with self.assertRaises(ValueError):
            init_project('has space', root=self.root)

    def test_init_judges_sqlite_has_schema(self):
        init_project('foo', root=self.root)
        db = self.root / 'foo' / 'judges.sqlite'
        conn = sqlite3.connect(str(db))
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='judgements'")
        self.assertIsNotNone(cur.fetchone())
        conn.close()

    def test_init_empty_refs_bib(self):
        init_project('foo', root=self.root)
        refs = self.root / 'foo' / 'refs.bib'
        content = refs.read_text(encoding='utf-8')
        self.assertIn('Bibtex for project', content)
        # No actual entries yet
        self.assertNotIn('@article', content)


class TestListProjects(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.root = self.tmpdir / 'projects'

    def test_list_empty(self):
        self.assertEqual(list_projects(self.root), [])

    def test_list_sorted(self):
        init_project('zebra', root=self.root)
        init_project('alpha', root=self.root)
        init_project('mango', root=self.root)
        projects = list_projects(self.root)
        self.assertEqual([p['slug'] for p in projects], ['alpha', 'mango', 'zebra'])

    def test_list_returns_meta_with_path(self):
        meta = init_project('foo', title='Test', root=self.root)
        projects = list_projects(self.root)
        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0]['slug'], 'foo')
        self.assertEqual(projects[0]['title'], 'Test')
        self.assertIn('_path', projects[0])

    def test_list_skips_invalid_dirs(self):
        # Create a dir without meta.json
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / 'not-a-project').mkdir()
        (self.root / 'not-a-project' / 'random.txt').write_text('x')
        # Should be skipped
        self.assertEqual(list_projects(self.root), [])


class TestStatus(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.root = self.tmpdir / 'projects'

    def test_status_no_papers_no_labels(self):
        init_project('foo', root=self.root)
        s = project_status('foo', root=self.root)
        self.assertEqual(s['slug'], 'foo')
        self.assertEqual(s['n_papers'], 0)
        self.assertEqual(s['n_labels'], 0)

    def test_status_with_papers(self):
        init_project('foo', root=self.root)
        refs = self.root / 'foo' / 'refs.bib'
        refs.write_text("""@article{a, title = {A}, doi = {10.1/a}}
@article{b, title = {B}, doi = {10.1/b}}
""", encoding='utf-8')
        s = project_status('foo', root=self.root)
        self.assertEqual(s['n_papers'], 2)

    def test_status_with_labels(self):
        init_project('foo', root=self.root)
        db = self.root / 'foo' / 'judges.sqlite'
        conn = sqlite3.connect(str(db))
        conn.execute("INSERT INTO judgements (query, paper_key, relevance) VALUES (?, ?, ?)",
                     ('q1', 'a', 2))
        conn.execute("INSERT INTO judgements (query, paper_key, relevance) VALUES (?, ?, ?)",
                     ('q1', 'b', 1))
        conn.execute("INSERT INTO judgements (query, paper_key, relevance) VALUES (?, ?, ?)",
                     ('q2', 'a', 0))
        conn.commit()
        conn.close()
        s = project_status('foo', root=self.root)
        self.assertEqual(s['n_labels'], 3)

    def test_status_nonexistent_raises(self):
        with self.assertRaises(FileNotFoundError):
            project_status('nope', root=self.root)

    def test_status_includes_paths(self):
        init_project('foo', root=self.root)
        s = project_status('foo', root=self.root)
        self.assertIn('paths', s)
        self.assertIn('refs', s['paths'])
        self.assertIn('judges', s['paths'])
        self.assertIn('meta', s['paths'])


class TestRemoveProject(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.root = self.tmpdir / 'projects'

    def test_remove_existing(self):
        init_project('foo', root=self.root)
        result = remove_project('foo', root=self.root)
        self.assertTrue(result)
        self.assertFalse((self.root / 'foo').exists())

    def test_remove_nonexistent(self):
        result = remove_project('nope', root=self.root)
        self.assertFalse(result)

    def test_remove_refuses_without_meta(self):
        # Create dir without meta.json
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / 'no-meta').mkdir()
        with self.assertRaises(ValueError):
            remove_project('no-meta', root=self.root)

    def test_remove_force_overrides(self):
        # With --force, removes even without meta.json
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / 'no-meta').mkdir()
        result = remove_project('no-meta', root=self.root, force=True)
        self.assertTrue(result)
        self.assertFalse((self.root / 'no-meta').exists())


class TestCliSmoke(unittest.TestCase):
    """Smoke tests for the project CLI subcommands."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.root = self.tmpdir / 'projects'

    def test_init_via_cli(self):
        from pa_cli.cli import main
        from pa_cli.project import DEFAULT_ROOT
        # Patch DEFAULT_ROOT for the duration of this test
        import pa_cli.project as proj_mod
        orig = proj_mod.DEFAULT_ROOT
        proj_mod.DEFAULT_ROOT = self.root
        try:
            main(['project', 'init', 'cli_test', '--title', 'CLI Test', '--root', str(self.root)])
        except SystemExit as e:
            self.assertEqual(e.code, 0)
        finally:
            proj_mod.DEFAULT_ROOT = orig
        # Verify project was created
        meta = json.loads((self.root / 'cli_test' / 'meta.json').read_text(encoding='utf-8'))
        self.assertEqual(meta['slug'], 'cli_test')
        self.assertEqual(meta['title'], 'CLI Test')

    def test_list_via_cli(self):
        from pa_cli.cli import main
        import pa_cli.project as proj_mod
        orig = proj_mod.DEFAULT_ROOT
        proj_mod.DEFAULT_ROOT = self.root
        try:
            init_project('p1', root=self.root)
            init_project('p2', root=self.root)
            main(['project', 'list', '--root', str(self.root)])
        except SystemExit as e:
            self.assertEqual(e.code, 0)
        finally:
            proj_mod.DEFAULT_ROOT = orig

    def test_status_via_cli(self):
        from pa_cli.cli import main
        import pa_cli.project as proj_mod
        orig = proj_mod.DEFAULT_ROOT
        proj_mod.DEFAULT_ROOT = self.root
        try:
            init_project('p1', root=self.root)
            main(['project', 'status', 'p1', '--root', str(self.root)])
        except SystemExit as e:
            self.assertEqual(e.code, 0)
        finally:
            proj_mod.DEFAULT_ROOT = orig

    def test_corpus_via_cli(self):
        from pa_cli.cli import main
        import pa_cli.project as proj_mod
        orig = proj_mod.DEFAULT_ROOT
        proj_mod.DEFAULT_ROOT = self.root
        try:
            init_project('p1', root=self.root)
            main(['project', 'corpus', 'p1'])
        except SystemExit as e:
            self.assertEqual(e.code, 0)
        finally:
            proj_mod.DEFAULT_ROOT = orig


class TestPhase2CorpusSearch(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.root = self.tmpdir / 'projects'
        init_project('search_proj', title='Search Test', root=self.root)
        from pa_cli.project import project_files, corpus_search
        refs = project_files('search_proj', self.root)['refs']
        sample_bib = """
@article{paper1,
  title = {Digital Finance and Economic Resilience},
  author = {Zhang, Wei and Li, Ming},
  journal = {Journal of Financial Economics},
  year = {2023},
  doi = {10.1016/j.jfineco.2023.01.001}
}
@article{paper2,
  title = {Fertility Dynamics in Urban China},
  author = {Wang, Fang and Chen, Hua},
  journal = {Demography},
  year = {2022},
  doi = {10.1215/00703370-9876543}
}
"""
        refs.write_text(sample_bib, encoding='utf-8')

    def test_search_by_keyword(self):
        from pa_cli.project import corpus_search
        res = corpus_search('search_proj', 'digital finance', root=self.root)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]['key'], 'paper1')
        self.assertIn('title', res[0]['_matched_fields'])

    def test_search_by_author(self):
        from pa_cli.project import corpus_search
        res = corpus_search('search_proj', 'Chen', root=self.root)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]['key'], 'paper2')
        self.assertIn('author', res[0]['_matched_fields'])

    def test_search_not_found(self):
        from pa_cli.project import corpus_search
        res = corpus_search('search_proj', 'blockchain crypto', root=self.root)
        self.assertEqual(res, [])


class TestPhase2CorpusMerge(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.root = self.tmpdir / 'projects'
        init_project('target_proj', title='Target', root=self.root)
        from pa_cli.project import project_files
        refs = project_files('target_proj', self.root)['refs']
        refs.write_text("""
@article{exist1,
  title = {Existing Paper Title},
  author = {Smith, John},
  year = {2021},
  doi = {10.1000/existing.doi}
}
""", encoding='utf-8')

    def test_merge_external_bib_with_dedup(self):
        from pa_cli.project import corpus_merge, project_status
        ext_bib = self.tmpdir / 'ext.bib'
        ext_bib.write_text("""
@article{new1,
  title = {Brand New Paper},
  author = {Taylor, Alex},
  year = {2024},
  doi = {10.1000/new.doi}
}
@article{dup1,
  title = {Existing Paper Title},
  author = {Smith, John},
  year = {2021},
  doi = {10.1000/existing.doi}
}
""", encoding='utf-8')
        res = corpus_merge('target_proj', ext_bib, root=self.root)
        self.assertEqual(res['added'], 1)
        self.assertEqual(res['duplicates_skipped'], 1)
        self.assertEqual(res['total_after'], 2)
        st = project_status('target_proj', root=self.root)
        self.assertEqual(st['n_papers'], 2)

    def test_merge_between_projects(self):
        from pa_cli.project import corpus_merge, corpus_add
        init_project('source_proj', title='Source', root=self.root)
        corpus_add('source_proj', doi='10.1000/source.paper', title='Source Paper', root=self.root)
        res = corpus_merge('target_proj', 'source_proj', root=self.root)
        self.assertEqual(res['added'], 1)
        self.assertEqual(res['total_after'], 2)

    def test_merge_stub_preserves_cite_key_and_rich_fields(self):
        from pa_cli.project import corpus_merge, project_files
        refs = project_files('target_proj', self.root)['refs']
        refs.write_text("""
@article{keepme,
  title = {Paper 10.1234/test},
  author = {Smith, John},
  year = {2020},
  doi = {10.1234/test},
  volume = {42},
  pages = {100--110},
  abstract = {A very important abstract.},
  note = {Do not delete},
}
@article{other_doc,
  title = {Other Untouched Paper},
  author = {Doe, Jane},
  year = {2021},
  doi = {10.5678/other},
  volume = {10},
  pages = {1--5},
  note = {Untouched note},
}
""", encoding='utf-8')
        ext_bib = self.tmpdir / 'rich_source.bib'
        ext_bib.write_text("""
@article{source_ref,
  title = {Rich Full Title for Test},
  author = {Smith, John and Brown, Charlie},
  journal = {Journal of Testing},
  year = {2020},
  doi = {10.1234/test},
}
""", encoding='utf-8')
        res = corpus_merge('target_proj', ext_bib, root=self.root)
        self.assertEqual(res['updated'], 1)
        updated_text = refs.read_text(encoding='utf-8')
        # Check cite keys remain intact
        self.assertIn("@article{keepme,", updated_text)
        self.assertIn("@article{other_doc,", updated_text)
        # Check rich fields preserved
        self.assertIn("volume = {42}", updated_text)
        self.assertIn("pages = {100--110}", updated_text)
        self.assertIn("abstract = {A very important abstract.}", updated_text)
        self.assertIn("note = {Do not delete}", updated_text)
        self.assertIn("volume = {10}", updated_text)
        self.assertIn("note = {Untouched note}", updated_text)
        # Check enriched metadata
        self.assertIn("title = {Rich Full Title for Test}", updated_text)
        self.assertIn("journal = {Journal of Testing}", updated_text)
        self.assertIn("author = {Smith, John and Brown, Charlie}", updated_text)



class TestPhase2CorpusAdd(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.root = self.tmpdir / 'projects'
        init_project('add_proj', root=self.root)

    def test_add_paper_by_doi_and_skip_duplicate(self):
        from pa_cli.project import corpus_add
        res1 = corpus_add('add_proj', doi='10.1038/nature12345', title='Nature Paper', root=self.root)
        self.assertEqual(res1['status'], 'added')
        res2 = corpus_add('add_proj', doi='10.1038/nature12345', root=self.root)
        self.assertEqual(res2['status'], 'skipped')
        self.assertEqual(res2['reason'], 'doi_already_exists')


class TestPhase2CliCommands(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.root = self.tmpdir / 'projects'
        init_project('p_cli', root=self.root)

    def test_cli_corpus_search_and_add(self):
        from pa_cli.cli import main
        import pa_cli.project as proj_mod
        orig = proj_mod.DEFAULT_ROOT
        proj_mod.DEFAULT_ROOT = self.root
        try:
            # Test corpus-add via CLI
            try:
                main(['project', 'corpus-add', 'p_cli', '--doi', '10.1145/3377325.3377500', '--title', 'Test CLI Paper', '--root', str(self.root)])
            except SystemExit as e:
                self.assertEqual(e.code, 0)

            # Test corpus-search via CLI
            try:
                main(['project', 'corpus-search', 'p_cli', 'CLI Paper', '--root', str(self.root)])
            except SystemExit as e:
                self.assertEqual(e.code, 0)
        finally:
            proj_mod.DEFAULT_ROOT = orig


class TestScanAndImportDirectory(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.root = self.tmpdir / 'projects'
        self.docs_dir = self.tmpdir / 'docs'
        self.docs_dir.mkdir(parents=True)
        # Create sample files
        (self.docs_dir / 'paper_a.md').write_text("""
# Literature Review Draft
We refer to recent findings in 10.1038/nature99999 and also 10.1145/3377325.1111111.
""", encoding='utf-8')
        sub = self.docs_dir / 'subfolder'
        sub.mkdir()
        (sub / 'notes.txt').write_text("""
Check this paper: https://doi.org/10.1038/nature99999 for methodology details.
""", encoding='utf-8')

    def test_scan_directory_dois(self):
        from pa_cli.project import scan_directory_dois
        res = scan_directory_dois(self.docs_dir, recursive=True)
        self.assertEqual(res['files_scanned'], 2)
        self.assertEqual(res['total_occurrences'], 3)
        self.assertEqual(res['unique_dois_count'], 2)
        # 10.1038/nature99999 occurred in 2 files
        top = next(item for item in res['dois'] if item['doi'] == '10.1038/nature99999')
        self.assertEqual(top['occurrences'], 2)

    def test_import_directory_to_project(self):
        from pa_cli.project import import_directory_to_project, project_status
        res = import_directory_to_project('imported_proj', self.docs_dir, root=self.root)
        self.assertEqual(res['discovered_dois'], 2)
        self.assertEqual(res['added'], 2)
        st = project_status('imported_proj', root=self.root)
        self.assertEqual(st['n_papers'], 2)

        # Re-import should be idempotent (added == 0)
        res2 = import_directory_to_project('imported_proj', self.docs_dir, root=self.root)
        self.assertEqual(res2['added'], 0)
        self.assertEqual(res2['already_present'], 2)

    def test_cli_scan_and_import(self):
        from pa_cli.cli import main
        import pa_cli.project as proj_mod
        orig = proj_mod.DEFAULT_ROOT
        proj_mod.DEFAULT_ROOT = self.root
        try:
            try:
                main(['project', 'scan', str(self.docs_dir)])
            except SystemExit as e:
                self.assertEqual(e.code, 0)

            try:
                main(['project', 'import-dir', 'cli_imp', str(self.docs_dir), '--root', str(self.root)])
            except SystemExit as e:
                self.assertEqual(e.code, 0)
        finally:
            proj_mod.DEFAULT_ROOT = orig


class TestProjectFetch(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.root = self.tmpdir / 'projects'
        init_project('fetch_proj', title='Fetch Test', root=self.root)
        refs = self.root / 'fetch_proj' / 'refs.bib'
        refs.write_text("""@article{p1,
  title = {Paper One},
  author = {Alice},
  doi = {10.1000/1},
  year = {2021}
}
@article{p2,
  title = {Paper Two},
  author = {Bob},
  doi = {10.1000/2},
  year = {2022}
}
""", encoding='utf-8')

    def test_project_fetch_mocked(self):
        from pa_cli.project import project_fetch, project_status
        from pa_cli.fetch_batch import FetchSummary, FetchResult

        def fake_run_fetch_batch(bib_path, out_dir, **kwargs):
            (out_dir / 'p1.pdf').write_bytes(b"%PDF-1.4 dummy p1")
            (out_dir / 'p2.pdf').write_bytes(b"%PDF-1.4 dummy p2")
            return FetchSummary(
                n_total=2,
                n_success=2,
                n_failure=0,
                n_skipped=0,
                total_size_bytes=34,
                total_elapsed_sec=0.5,
                results=[
                    FetchResult(key='p1', doi='10.1000/1', title='Paper One', success=True, out_path=str(out_dir / 'p1.pdf'), size_bytes=17),
                    FetchResult(key='p2', doi='10.1000/2', title='Paper Two', success=True, out_path=str(out_dir / 'p2.pdf'), size_bytes=17),
                ]
            )

        with patch('pa_cli.fetch_batch.run_fetch_batch', side_effect=fake_run_fetch_batch):
            res = project_fetch('fetch_proj', root=self.root)
            self.assertEqual(res['n_total'], 2)
            self.assertEqual(res['n_success'], 2)
            self.assertEqual(res['n_pdfs_in_project'], 2)

            st = project_status('fetch_proj', root=self.root)
            self.assertEqual(st['n_pdfs'], 2)

    def test_cli_project_fetch(self):
        from pa_cli.cli import main
        from pa_cli.fetch_batch import FetchSummary, FetchResult
        import pa_cli.project as proj_mod

        def fake_run_fetch_batch(bib_path, out_dir, **kwargs):
            (out_dir / 'p1.pdf').write_bytes(b"%PDF-1.4 dummy p1")
            return FetchSummary(
                n_total=2,
                n_success=1,
                n_failure=1,
                n_skipped=0,
                total_size_bytes=17,
                total_elapsed_sec=0.2,
                results=[
                    FetchResult(key='p1', doi='10.1000/1', title='Paper One', success=True, out_path=str(out_dir / 'p1.pdf'), size_bytes=17),
                    FetchResult(key='p2', doi='10.1000/2', title='Paper Two', success=False, error='404'),
                ]
            )

        orig = proj_mod.DEFAULT_ROOT
        proj_mod.DEFAULT_ROOT = self.root
        try:
            with patch('pa_cli.fetch_batch.run_fetch_batch', side_effect=fake_run_fetch_batch):
                try:
                    main(['project', 'fetch', 'fetch_proj', '--root', str(self.root)])
                except SystemExit as e:
                    self.assertEqual(e.code, 0)
        finally:
            proj_mod.DEFAULT_ROOT = orig


class TestProjectPrismaAndReview(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.root = self.tmpdir / 'projects'
        init_project('lit_proj', title='Literature Review Test', description='Test Description', root=self.root)
        refs = self.root / 'lit_proj' / 'refs.bib'
        refs.write_text("""@article{key2020,
  title = {Deep Reinforcement Learning in Finance},
  author = {Smith, John and Doe, Jane},
  journal = {Journal of Financial Data Science},
  year = {2020},
  doi = {10.1016/j.jfds.2020.01.001},
  abstract = {An empirical investigation of reinforcement learning methods.}
}
@article{key2022,
  title = {Macroeconomic Nowcasting with Transformers},
  author = {Wang, Wei},
  journal = {Quantitative Economics},
  year = {2022},
  doi = {10.3982/QE1234}
}
""", encoding='utf-8')

    def test_project_prisma_markdown(self):
        from pa_cli.project import project_prisma
        diagram = project_prisma('lit_proj', root=self.root, output_format='markdown')
        self.assertIn('PRISMA 2020', diagram)
        self.assertIn('flowchart TD', diagram)
        # Verify saved file
        out_file = self.tmpdir / 'prisma.md'
        project_prisma('lit_proj', root=self.root, out_file=out_file)
        self.assertTrue(out_file.exists())
        self.assertIn('flowchart TD', out_file.read_text(encoding='utf-8'))

    def test_project_prisma_mermaid(self):
        from pa_cli.project import project_prisma
        mermaid = project_prisma('lit_proj', root=self.root, output_format='mermaid')
        self.assertTrue(mermaid.startswith('```mermaid'))
        self.assertIn('flowchart TD', mermaid)

    def test_project_review_refs_only(self):
        from pa_cli.project import project_review
        rev = project_review('lit_proj', root=self.root, with_prisma=True)
        self.assertIn('Literature Review: Literature Review Test', rev)
        self.assertIn('Deep Reinforcement Learning in Finance', rev)
        self.assertIn('Macroeconomic Nowcasting with Transformers', rev)
        self.assertIn('PRISMA 2020', rev)
        self.assertIn('Smith, John', rev)

    def test_project_review_without_prisma(self):
        from pa_cli.project import project_review
        rev = project_review('lit_proj', root=self.root, with_prisma=False)
        self.assertIn('Literature Review: Literature Review Test', rev)
        self.assertNotIn('PRISMA 2020 流程图', rev)

    def test_project_review_with_pdfs(self):
        from pa_cli.project import project_review, project_files
        pdf_dir = project_files('lit_proj', self.root)['pdfs']
        # Review synthesizer reads .txt / .md / .pdf
        (pdf_dir / 'paper1.txt').write_text("# Deep Learning Applications\n" + "Word " * 1200, encoding='utf-8')
        rev = project_review('lit_proj', root=self.root, with_prisma=True)
        self.assertIn('Deep Learning Applications', rev)
        self.assertIn('FULL TEXT', rev)

    def test_cli_prisma_and_review(self):
        from pa_cli.cli import main
        import pa_cli.project as proj_mod
        orig = proj_mod.DEFAULT_ROOT
        proj_mod.DEFAULT_ROOT = self.root
        try:
            # Test prisma command
            out_prisma = self.tmpdir / 'cli_prisma.md'
            try:
                main(['project', 'prisma', 'lit_proj', '-o', str(out_prisma), '--root', str(self.root)])
            except SystemExit as e:
                self.assertEqual(e.code, 0)
            self.assertTrue(out_prisma.exists())

            # Test review command
            out_review = self.tmpdir / 'cli_review.md'
            try:
                main(['project', 'review', 'lit_proj', '-o', str(out_review), '--root', str(self.root)])
            except SystemExit as e:
                self.assertEqual(e.code, 0)
            self.assertTrue(out_review.exists())
            self.assertIn('Literature Review', out_review.read_text(encoding='utf-8'))
        finally:
            proj_mod.DEFAULT_ROOT = orig


class TestProjectTopics(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.root = self.tmpdir / 'projects'
        init_project('topic_proj', title='Topic Clustering Test', root=self.root)
        refs = self.root / 'topic_proj' / 'refs.bib'
        refs.write_text("""@article{p1,
  title = {Deep Convolutional Neural Networks for Medical Tumor Imaging},
  author = {Smith, John},
  year = {2020},
  abstract = {Deep convolutional neural networks for tumor detection in medical imaging.}
}
@article{p2,
  title = {Deep Learning Computer Vision for Cancer Diagnostics},
  author = {Doe, Jane},
  year = {2021},
  abstract = {Medical diagnostics using deep learning and image classification.}
}
@article{p3,
  title = {Recurrent Neural Networks for Actuarial Risk and Insurance Claims},
  author = {Wang, Wei},
  year = {2022},
  abstract = {Insurance claims forecasting using recurrent neural networks and actuarial statistics.}
}
@article{p4,
  title = {Predictive Modeling in Life Insurance using LSTM Networks},
  author = {Zhang, Li},
  year = {2023},
  abstract = {LSTM deep learning architectures for insurance claims prediction.}
}
""", encoding='utf-8')

    def test_project_topics_from_bib(self):
        from pa_cli.project import project_topics, project_status
        with patch('pa_cli.topics._fetch_concepts_for_doi', return_value=None):
            res = project_topics('topic_proj', root=self.root, force_method='handroll')
            self.assertEqual(res['slug'], 'topic_proj')
            self.assertIn('topics', res)
            self.assertGreaterEqual(len(res['topics']), 1)

            st = project_status('topic_proj', root=self.root)
            self.assertGreaterEqual(st['n_topics'], 1)
            self.assertTrue((self.root / 'topic_proj' / 'topics.json').exists())

    def test_cli_project_topics(self):
        from pa_cli.cli import main
        import pa_cli.project as proj_mod
        orig = proj_mod.DEFAULT_ROOT
        proj_mod.DEFAULT_ROOT = self.root
        try:
            with patch('pa_cli.topics._fetch_concepts_for_doi', return_value=None):
                try:
                    main(['project', 'topics', 'topic_proj', '--method', 'handroll', '--root', str(self.root)])
                except SystemExit as e:
                    self.assertEqual(e.code, 0)
        finally:
            proj_mod.DEFAULT_ROOT = orig


class TestProjectStatsCiteCheckExport(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.root = self.tmpdir / 'projects'
        init_project('adv_proj', title='Advanced Project Tools Test', description='Test suite for stats, cite-check, and export', root=self.root)
        refs = self.root / 'adv_proj' / 'refs.bib'
        refs.write_text("""@article{smith2020,
  title = {Deep Convolutional Neural Networks for Medical Tumor Imaging},
  author = {Smith, John and Doe, Jane},
  journal = {Journal of Medical AI},
  year = {2020},
  doi = {10.1016/j.jmai.2020.01.001},
  abstract = {Deep convolutional neural networks for tumor detection in medical imaging.}
}
@inproceedings{wang2022,
  title = {Actuarial Risk Modeling with Deep Neural Networks},
  author = {Wang, Wei},
  booktitle = {Proceedings of FinTech 2022},
  year = {2022},
  doi = {10.1145/fintech.2022.04},
  abstract = {Insurance claims forecasting using neural network architectures.}
}
""", encoding='utf-8')

    def test_project_stats(self):
        from pa_cli.project import project_stats
        st = project_stats('adv_proj', root=self.root, top_n=5)
        self.assertEqual(st['slug'], 'adv_proj')
        self.assertEqual(st['n_papers'], 2)
        self.assertEqual(st['n_with_doi'], 2)
        self.assertEqual(st['n_without_doi'], 0)
        self.assertIn('article', st['by_type'])
        self.assertIn('inproceedings', st['by_type'])
        self.assertEqual(st['year_min'], 2020)
        self.assertEqual(st['year_max'], 2022)
        self.assertEqual(len(st['top_authors']), 3)  # Smith, Doe, Wang

    def test_project_cite_check(self):
        from pa_cli.project import project_cite_check
        doc = self.tmpdir / 'draft.md'
        doc.write_text("""# Research Draft
According to [@smith2020], deep learning achieves high accuracy in medical diagnostics.
However, [@unknown_ref] disagrees with this conclusion.
""", encoding='utf-8')
        summary, report = project_cite_check('adv_proj', doc, root=self.root)
        self.assertEqual(summary['slug'], 'adv_proj')
        self.assertEqual(summary['n_missing'], 1)
        self.assertEqual(summary['missing'][0]['key'], 'unknown_ref')
        self.assertEqual(summary['n_orphan'], 1)
        self.assertEqual(summary['orphan'][0]['key'], 'wang2022')
        self.assertFalse(summary['clean'])
        self.assertIn('unknown_ref', report)

    def test_project_export_markdown(self):
        from pa_cli.project import project_export
        out_file = self.tmpdir / 'digest.md'
        res = project_export('adv_proj', format='markdown', out_file=out_file, root=self.root)
        self.assertEqual(res['slug'], 'adv_proj')
        self.assertEqual(res['format'], 'markdown')
        self.assertEqual(res['n_papers'], 2)
        self.assertTrue(out_file.exists())
        content = out_file.read_text(encoding='utf-8')
        self.assertIn('# Literature Digest: Advanced Project Tools Test', content)
        self.assertIn('Deep Convolutional Neural Networks', content)
        self.assertIn('Actuarial Risk Modeling', content)
        self.assertIn('Smith, John and Doe, Jane', content)
        self.assertIn('10.1016/j.jmai.2020.01.001', content)

    def test_project_export_bibtex_and_json(self):
        from pa_cli.project import project_export
        # Bibtex export
        out_bib = self.tmpdir / 'exported.bib'
        res_bib = project_export('adv_proj', format='bibtex', out_file=out_bib, root=self.root)
        self.assertEqual(res_bib['format'], 'bibtex')
        self.assertTrue(out_bib.exists())
        self.assertIn('@article{smith2020', out_bib.read_text(encoding='utf-8'))

        # JSON export
        res_json = project_export('adv_proj', format='json', root=self.root)
        self.assertEqual(res_json['format'], 'json')
        parsed = json.loads(res_json['content'])
        self.assertEqual(parsed['n_papers'], 2)
        self.assertEqual(len(parsed['papers']), 2)

    def test_cli_stats_cite_check_export(self):
        from pa_cli.cli import main
        import pa_cli.project as proj_mod
        orig = proj_mod.DEFAULT_ROOT
        proj_mod.DEFAULT_ROOT = self.root
        try:
            # CLI stats
            try:
                main(['project', 'stats', 'adv_proj', '--json', '--root', str(self.root)])
            except SystemExit as e:
                self.assertEqual(e.code, 0)

            # CLI cite-check
            doc = self.tmpdir / 'draft_clean.md'
            doc.write_text("As discussed in [@smith2020] and [@wang2022].\n", encoding='utf-8')
            try:
                main(['project', 'cite-check', 'adv_proj', str(doc), '--strict', '--root', str(self.root)])
            except SystemExit as e:
                self.assertEqual(e.code, 0)

            # CLI export
            out_export = self.tmpdir / 'cli_export.md'
            try:
                main(['project', 'export', 'adv_proj', '-o', str(out_export), '--root', str(self.root)])
            except SystemExit as e:
                self.assertEqual(e.code, 0)
            self.assertTrue(out_export.exists())
        finally:
            proj_mod.DEFAULT_ROOT = orig


class TestProjectEnrich(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.root = self.tmpdir / 'projects'
        init_project('enrich_proj', title='Enrich Project Test', description='Test suite for project enrich', root=self.root)
        refs = self.root / 'enrich_proj' / 'refs.bib'
        refs.write_text("""@article{stub_paper_1,
  title = {Paper 10.1057/s41599-024-04296-4},
  doi = {10.1057/s41599-024-04296-4},
  url = {https://doi.org/10.1057/s41599-024-04296-4}
}
@article{complete_paper_2,
  title = {Existing Complete Paper Title},
  author = {Smith, Alice},
  journal = {Science},
  year = {2021},
  doi = {10.1126/science.1234567}
}
""", encoding='utf-8')

    def test_project_enrich_stubs_mocked(self):
        from pa_cli.project import project_enrich, load_meta
        mock_work = {
            "title": "Unraveling Complexity of Celebrity Worship",
            "publication_year": 2024,
            "primary_location": {"source": {"display_name": "Humanities and Social Sciences Communications"}},
            "authorships": [{"author": {"display_name": "San Zhang"}}, {"author": {"display_name": "Si Li"}}],
            "type": "article",
            "abstract_inverted_index": {"The": [0], "study": [1], "examines": [2], "social": [3], "dynamics": [4]},
        }

        with patch('pa_cli.citations.get_work_by_doi', return_value=mock_work):
            res = project_enrich('enrich_proj', root=self.root)
            self.assertEqual(res['slug'], 'enrich_proj')
            self.assertEqual(res['total'], 2)
            self.assertEqual(res['stubs'], 1)
            self.assertEqual(res['enriched'], 1)
            self.assertEqual(res['unchanged'], 1)
            self.assertEqual(res['failed'], 0)

            # Check refs.bib contents
            refs_text = (self.root / 'enrich_proj' / 'refs.bib').read_text(encoding='utf-8')
            self.assertIn("title = {Unraveling Complexity of Celebrity Worship}", refs_text)
            self.assertIn("author = {Zhang, San and Li, Si}", refs_text)
            self.assertIn("journal = {Humanities and Social Sciences Communications}", refs_text)
            self.assertIn("abstract = {The study examines social dynamics}", refs_text)
            self.assertIn("@article{stub_paper_1", refs_text)
            self.assertIn("@article{complete_paper_2", refs_text)

            # Check meta.json
            meta = load_meta('enrich_proj', root=self.root)
            self.assertIn('last_enrich_at', meta)

    def test_cli_project_enrich(self):
        from pa_cli.cli import main
        import pa_cli.project as proj_mod
        orig = proj_mod.DEFAULT_ROOT
        proj_mod.DEFAULT_ROOT = self.root
        mock_work = {
            "title": "Unraveling Complexity of Celebrity Worship",
            "publication_year": 2024,
            "authorships": [{"author": {"display_name": "San Zhang"}}],
            "type": "article",
        }
        try:
            with patch('pa_cli.citations.get_work_by_doi', return_value=mock_work):
                try:
                    main(['project', 'enrich', 'enrich_proj', '--json', '--root', str(self.root)])
                except SystemExit as e:
                    self.assertEqual(e.code, 0)
        finally:
            proj_mod.DEFAULT_ROOT = orig


if __name__ == '__main__':
    unittest.main(verbosity=2)

