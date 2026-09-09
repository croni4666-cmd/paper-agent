import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pa_cli import cache

from test_pdf_structure import make_pdf
PDF = make_pdf()
DOI = '10.1000/a.b'


class CacheIntegrityTests(unittest.TestCase):
    def test_invalid_metadata_is_a_miss_without_deleting_files(self):
        for change in (None, [], {'sha256': ''}, {'sha256': 'wrong'},
                       {'ts': 'bad'}, {'ts': 10 ** 400}, {'ts': True}, {'ts': float('nan')}, {'ts': -1},
                       {'ts': 2000000001}, {'ts': 1900000000}, {'doi': '10.1000/a_b'}):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                with patch.object(cache.time, 'time', return_value=2000000000):
                    entry = cache.cache_put(DOI, PDF, root=root)
                    meta = Path(entry['meta_path'])
                    data = json.loads(meta.read_text())
                    if isinstance(change, dict):
                        data.update(change)
                    else:
                        data = change
                    meta.write_text(json.dumps(data))
                    self.assertIsNone(cache.cache_get(DOI, root=root))
                    self.assertTrue(meta.exists())
                    self.assertEqual(Path(entry['pdf_path']).read_bytes(), PDF)

    def test_expiry_boundary_and_doi_url_alias(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.object(cache.time, 'time', return_value=2000000000):
                cache.cache_put(DOI, PDF, root=root)
            with patch.object(cache.time, 'time', return_value=2000000000 + 365 * 86400):
                self.assertIsNotNone(cache.cache_get('https://doi.org/' + DOI, root=root))
            with patch.object(cache.time, 'time', return_value=2000000001 + 365 * 86400):
                self.assertIsNone(cache.cache_get(DOI, root=root))

    def test_metadata_stage_failure_preserves_previous_pair(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            entry = cache.cache_put(DOI, PDF, root=root)
            with patch.object(cache.json, 'dumps', side_effect=OSError('fixture failure')):
                with self.assertRaises(OSError):
                    cache.cache_put(DOI, b'%PDF new data', root=root)
            self.assertEqual(Path(entry['pdf_path']).read_bytes(), PDF)
            self.assertIsNotNone(cache.cache_get(DOI, root=root))
            self.assertEqual(len(list(root.iterdir())), 2)

    def test_interrupted_publish_leaves_no_temporary_files_or_false_hit(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cache.cache_put(DOI, PDF, root=root)
            original = Path.replace
            def replace(path, target):
                if str(target).endswith('.meta.json'):
                    raise OSError('fixture interrupted publication')
                return original(path, target)
            with patch.object(Path, 'replace', replace):
                with self.assertRaises(OSError):
                    cache.cache_put(DOI, b'%PDF new data', root=root)
            self.assertEqual(len(list(root.iterdir())), 2)
            self.assertIsNone(cache.cache_get(DOI, root=root))
