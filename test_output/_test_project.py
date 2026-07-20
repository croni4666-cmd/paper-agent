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
        for s in ['', 'has space', 'with/slash', '中文', 'my-课题', 'a*b', 'name?']:
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


if __name__ == '__main__':
    unittest.main(verbosity=2)
