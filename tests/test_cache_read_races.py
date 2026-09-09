import tempfile
import multiprocessing
import unittest
from pathlib import Path
from unittest.mock import patch
from pa_cli import cache, pdf_validation
from test_pdf_structure import make_pdf


def paused_writer(root, body, ready, release):
    original = Path.replace
    def replace(source, target):
        result = original(source, target)
        if str(target).endswith('.pdf'):
            ready.set()
            if not release.wait(15):
                raise TimeoutError('Test writer release was not signalled')
        return result
    with patch.object(Path, 'replace', replace):
        cache.cache_put('10.1000/race', body, root=Path(root))


class CacheReadRaceTests(unittest.TestCase):
    def test_replacement_during_validation_is_a_miss(self):
        for component in ('pdf', 'metadata', 'deleted'):
            with self.subTest(component=component), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                entry = cache.cache_put('10.1000/race', make_pdf(), root=root)
                pdf, meta = Path(entry['pdf_path']), Path(entry['meta_path'])
                validate = pdf_validation.validate_pdf
                def race(path):
                    result = validate(path)
                    if component == 'deleted':
                        pdf.unlink()
                    else:
                        target = pdf if component == 'pdf' else meta
                        replacement = root / 'replacement'
                        replacement.write_bytes(target.read_bytes())
                        replacement.replace(target)
                    return result
                with patch.object(pdf_validation, 'validate_pdf', side_effect=race):
                    self.assertIsNone(cache.cache_get('10.1000/race', root=root))
                if component != 'deleted':
                    self.assertIsNotNone(cache.cache_get('10.1000/race', root=root))

    def test_interleaved_process_writers_never_accept_a_mixed_pair(self):
        context = multiprocessing.get_context('spawn')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cache.cache_put('10.1000/race', make_pdf(), root=root)
            ready, release = context.Event(), context.Event()
            worker = context.Process(target=paused_writer,
                                     args=(temp, make_pdf(2), ready, release))
            worker.start()
            try:
                self.assertTrue(ready.wait(10), 'First writer did not publish its PDF')
                self.assertIsNone(cache.cache_get('10.1000/race', root=root))
                # Writer B completes before A publishes its metadata.
                cache.cache_put('10.1000/race', make_pdf(3), root=root)
                self.assertIsNotNone(cache.cache_get('10.1000/race', root=root))
                release.set()
                worker.join(10)
                self.assertEqual(worker.exitcode, 0)
                self.assertIsNone(cache.cache_get('10.1000/race', root=root))
                cache.cache_put('10.1000/race', make_pdf(3), root=root)
                self.assertIsNotNone(cache.cache_get('10.1000/race', root=root))
            finally:
                release.set()
                if worker.is_alive():
                    worker.terminate()
                worker.join(5)
