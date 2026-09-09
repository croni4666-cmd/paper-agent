import tempfile
import json
import multiprocessing
from test_cache_read_races import paused_writer
import unittest
from pathlib import Path
from unittest.mock import patch
from pa_cli import cache
from test_pdf_structure import make_pdf

class AtomicCacheTests(unittest.TestCase):
    def test_failed_pointer_publish_preserves_old_hit(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            old = cache.cache_put('10.1000/atomic', make_pdf(), root=root)
            replace = Path.replace
            def fail_pointer(source, target):
                if str(target).endswith('.meta.json'):
                    raise OSError('interrupted index publication')
                return replace(source, target)
            with patch.object(Path, 'replace', fail_pointer):
                with self.assertRaises(OSError):
                    cache.cache_put('10.1000/atomic', make_pdf(2), root=root)
            hit = cache.cache_get('10.1000/atomic', root=root)
            self.assertIsNotNone(hit)
            self.assertEqual(hit['sha256'], old['sha256'])

    def test_returned_pdf_survives_update_and_explicit_remove_cleans_versions(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            old = cache.cache_put('10.1000/atomic', make_pdf(), root=root)
            new = cache.cache_put('10.1000/atomic', make_pdf(2), root=root)
            self.assertNotEqual(old['pdf_path'], new['pdf_path'])
            self.assertEqual(Path(old['pdf_path']).read_bytes(), make_pdf())
            self.assertEqual(cache.cache_get('10.1000/atomic', root=root)['sha256'], new['sha256'])
            self.assertEqual(cache.cache_stats(root)['paper_count'], 1)
            cache.cache_remove('10.1000/atomic', root)
            self.assertEqual(list(root.iterdir()), [])

    def test_legacy_layout_and_untrusted_pointer(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            entry = cache.cache_put('10.1000/atomic', make_pdf(), root=root)
            meta = Path(entry['meta_path'])
            data = json.loads(meta.read_text())
            data.pop('pdf_file')
            legacy = root / '10_1000_atomic.pdf'
            Path(entry['pdf_path']).replace(legacy)
            meta.write_text(json.dumps(data))
            self.assertEqual(cache.cache_get('10.1000/atomic', root=root)['pdf_path'], str(legacy))
            data['pdf_file'] = '../outside.pdf'
            meta.write_text(json.dumps(data))
            self.assertIsNone(cache.cache_get('10.1000/atomic', root=root))

    def test_clean_removes_all_retained_versions(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for pages in (1, 2, 3):
                cache.cache_put('10.1000/atomic', make_pdf(pages), root=root)
            result = cache.cache_clean(root=root)
            self.assertEqual(result['removed_files'], 4)
            self.assertEqual(result['remaining_papers'], 0)
            self.assertEqual(list(root.iterdir()), [])

    def test_killed_writer_preserves_published_cache(self):
        context = multiprocessing.get_context('spawn')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            old = cache.cache_put('10.1000/race', make_pdf(), root=root)
            ready, release = context.Event(), context.Event()
            writer = context.Process(target=paused_writer,
                                     args=(temp, make_pdf(2), ready, release))
            writer.start()
            try:
                self.assertTrue(ready.wait(10))
                writer.terminate()
                writer.join(5)
                self.assertFalse(writer.is_alive())
                self.assertEqual(cache.cache_get('10.1000/race', root=root)['sha256'], old['sha256'])
            finally:
                if writer.is_alive():
                    writer.terminate()
                writer.join(5)
