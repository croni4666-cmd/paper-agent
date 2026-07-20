"""Unit + e2e tests for pa_cli.search_saved ([P2-9])."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, '.')

from pa_cli.search_saved import (
    load_all, save_all, add, update, delete, get, list_all, to_pa_args,
    validate_name, DEFAULT_PATH, _ensure_path,
)


class TestValidateName(unittest.TestCase):
    def test_valid_names(self):
        for n in ['my_search', 'ai-lit-2024', 'foo.bar', 'v1.2.3', 'X', 'a_b_c']:
            try:
                validate_name(n)
            except ValueError:
                self.fail(f"valid name rejected: {n!r}")

    def test_invalid_names(self):
        for n in ['', 'has space', 'with/slash', '中文', 'a*b', 'name?']:
            with self.assertRaises(ValueError, msg=f"invalid name accepted: {n!r}"):
                validate_name(n)


class TestAdd(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.path = self.tmpdir / 'saved.json'

    def test_add_simple(self):
        entry = add('my_search', 'AI literacy', self.path)
        self.assertEqual(entry['query'], 'AI literacy')
        self.assertIn('created_at', entry)
        self.assertIn('updated_at', entry)

    def test_add_with_flags(self):
        entry = add('ai2024', 'transformer', self.path,
                    year_min=2020, year_max=2024, engine='openalex,arxiv',
                    limit=20, sort_by='cite')
        self.assertEqual(entry['year_min'], 2020)
        self.assertEqual(entry['year_max'], 2024)
        self.assertEqual(entry['engine'], 'openalex,arxiv')
        self.assertEqual(entry['limit'], 20)
        self.assertEqual(entry['sort_by'], 'cite')

    def test_add_duplicate_raises(self):
        add('dup', 'q1', self.path)
        with self.assertRaises(FileExistsError):
            add('dup', 'q2', self.path)

    def test_add_invalid_name_raises(self):
        with self.assertRaises(ValueError):
            add('has space', 'q', self.path)

    def test_add_persists_to_disk(self):
        add('persisted', 'q1', self.path)
        data = load_all(self.path)
        self.assertIn('persisted', data['searches'])


class TestUpdate(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.path = self.tmpdir / 'saved.json'
        add('original', 'q1', self.path, year_min=2020)

    def test_update_existing_field(self):
        updated = update('original', self.path, year_min=2024)
        self.assertEqual(updated['year_min'], 2024)
        # query preserved
        self.assertEqual(updated['query'], 'q1')

    def test_update_bumps_updated_at(self):
        before = get('original', self.path)
        update('original', self.path, year_min=2024)
        after = get('original', self.path)
        self.assertGreaterEqual(after['updated_at'], before['updated_at'])

    def test_update_nonexistent_raises(self):
        with self.assertRaises(KeyError):
            update('nonexistent', self.path, year_min=2024)

    def test_update_only_specified_fields(self):
        """Flags not in update call should be preserved."""
        add('multi', 'q', self.path, year_min=2020, engine='openalex', limit=30)
        update('multi', self.path, year_min=2024)  # only change year_min
        e = get('multi', self.path)
        self.assertEqual(e['year_min'], 2024)
        self.assertEqual(e['engine'], 'openalex')  # preserved
        self.assertEqual(e['limit'], 30)  # preserved


class TestDelete(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.path = self.tmpdir / 'saved.json'
        add('to_del', 'q', self.path)

    def test_delete_existing(self):
        result = delete('to_del', self.path)
        self.assertTrue(result)
        self.assertIsNone(get('to_del', self.path))

    def test_delete_nonexistent(self):
        result = delete('nonexistent', self.path)
        self.assertFalse(result)


class TestList(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.path = self.tmpdir / 'saved.json'

    def test_list_empty(self):
        rows = list_all(self.path)
        self.assertEqual(rows, [])

    def test_list_sorted(self):
        add('zebra', 'q1', self.path)
        add('alpha', 'q2', self.path)
        add('mango', 'q3', self.path)
        rows = list_all(self.path)
        names = [r['name'] for r in rows]
        self.assertEqual(names, ['alpha', 'mango', 'zebra'])

    def test_list_n_flags_count(self):
        add('minimal', 'q', self.path)
        add('flagged', 'q', self.path, year_min=2020, engine='openalex', limit=20)
        rows = list_all(self.path)
        minimal = next(r for r in rows if r['name'] == 'minimal')
        flagged = next(r for r in rows if r['name'] == 'flagged')
        self.assertEqual(minimal['n_flags'], 0)
        self.assertEqual(flagged['n_flags'], 3)  # year_min, engine, limit


class TestToPaArgs(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.path = self.tmpdir / 'saved.json'
        add('foo', 'q1', self.path, year_min=2020, engine='openalex',
            limit=20, sort_by='cite', created_at='2026-01-01T00:00:00',
            updated_at='2026-01-01T00:00:00')

    def test_to_pa_args_excludes_timestamps(self):
        args = to_pa_args('foo', self.path)
        self.assertIn('query', args)
        self.assertIn('year_min', args)
        self.assertNotIn('created_at', args)
        self.assertNotIn('updated_at', args)

    def test_to_pa_args_preserves_values(self):
        args = to_pa_args('foo', self.path)
        self.assertEqual(args['query'], 'q1')
        self.assertEqual(args['year_min'], 2020)
        self.assertEqual(args['engine'], 'openalex')
        self.assertEqual(args['limit'], 20)
        self.assertEqual(args['sort_by'], 'cite')

    def test_to_pa_args_nonexistent_raises(self):
        with self.assertRaises(KeyError):
            to_pa_args('nonexistent', self.path)


class TestPersistence(unittest.TestCase):
    """Test that data survives save/load round-trip."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.path = self.tmpdir / 'saved.json'

    def test_save_load_round_trip(self):
        add('e2e_test', 'q1', self.path,
            year_min=2020, year_max=2024, engine='openalex,arxiv',
            limit=20, sort_by='cite', enrich_top=10)
        # Load fresh
        data = load_all(self.path)
        self.assertIn('e2e_test', data['searches'])
        e = data['searches']['e2e_test']
        self.assertEqual(e['query'], 'q1')
        self.assertEqual(e['year_min'], 2020)
        self.assertEqual(e['year_max'], 2024)
        self.assertEqual(e['engine'], 'openalex,arxiv')
        self.assertEqual(e['limit'], 20)
        self.assertEqual(e['sort_by'], 'cite')
        self.assertEqual(e['enrich_top'], 10)

    def test_concurrent_updates_no_corruption(self):
        """Multiple sequential add/update/delete should leave consistent state."""
        add('a', 'q1', self.path)
        add('b', 'q2', self.path)
        add('c', 'q3', self.path)
        update('b', self.path, year_min=2024)
        delete('a', self.path)
        data = load_all(self.path)
        self.assertIn('b', data['searches'])
        self.assertIn('c', data['searches'])
        self.assertNotIn('a', data['searches'])
        self.assertEqual(data['searches']['b']['year_min'], 2024)


class TestCliSmoke(unittest.TestCase):
    """CLI smoke tests (no actual search invocation)."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.path = self.tmpdir / 'saved.json'
        # Patch DEFAULT_PATH to use tmpdir
        import pa_cli.search_saved as ss
        self._orig = ss.DEFAULT_PATH
        ss.DEFAULT_PATH = self.path

    def tearDown(self):
        import pa_cli.search_saved as ss
        ss.DEFAULT_PATH = self._orig

    def test_list_via_cli(self):
        from pa_cli.cli import main
        add('test1', 'q1', self.path)
        add('test2', 'q2', self.path)
        try:
            main(['search-saved', 'list'])
        except SystemExit as e:
            self.assertEqual(e.code, 0)

    def test_list_json_via_cli(self):
        from pa_cli.cli import main
        add('test1', 'q1', self.path)
        try:
            main(['search-saved', 'list', '--json'])
        except SystemExit as e:
            self.assertEqual(e.code, 0)

    def test_add_via_cli(self):
        from pa_cli.cli import main
        try:
            main(['search-saved', 'add', 'cli_test', '--query', 'AI literacy',
                  '--year-min', '2020', '--engine', 'openalex'])
        except SystemExit as e:
            self.assertEqual(e.code, 0)
        e = get('cli_test', self.path)
        self.assertEqual(e['query'], 'AI literacy')
        self.assertEqual(e['year_min'], 2020)
        self.assertEqual(e['engine'], 'openalex')

    def test_del_via_cli(self):
        from pa_cli.cli import main
        add('to_del', 'q', self.path)
        try:
            main(['search-saved', 'del', 'to_del'])
        except SystemExit as e:
            self.assertEqual(e.code, 0)
        self.assertIsNone(get('to_del', self.path))

    def test_add_duplicate_via_cli_exits_1(self):
        from pa_cli.cli import main
        add('dup', 'q1', self.path)
        try:
            main(['search-saved', 'add', 'dup', '--query', 'q2'])
            self.fail("should have raised SystemExit")
        except SystemExit as e:
            self.assertEqual(e.code, 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
