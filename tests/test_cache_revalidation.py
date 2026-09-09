from pathlib import Path
import tempfile
import unittest
from pa_cli import cache
from test_pdf_structure import make_pdf


class CacheRevalidationTests(unittest.TestCase):
    def test_legacy_marker_only_cache_is_miss_without_deletion(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            entry = cache.cache_put('10.1000/legacy', b'%PDF-1.7\nfake\n%%EOF', root=root)
            self.assertIsNone(cache.cache_get('10.1000/legacy', root=root))
            self.assertTrue(Path(entry['pdf_path']).exists())

    def test_valid_legacy_cache_remains_usable(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cache.cache_put('10.1000/legacy', make_pdf(), root=root)
            self.assertIsNotNone(cache.cache_get('10.1000/legacy', root=root))
