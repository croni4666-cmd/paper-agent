from pathlib import Path
import tempfile
import unittest
import hashlib
import json
import time
from pa_cli import cache
from test_pdf_structure import make_pdf


class CacheRevalidationTests(unittest.TestCase):
    def test_legacy_marker_only_cache_is_miss_without_deletion(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            # Construct a legacy on-disk entry; new writes reject this body.
            body = b'%PDF-1.7\nfake\n%%EOF'
            pdf, meta = cache._paths('10.1000/legacy', root)
            pdf.write_bytes(body)
            meta.write_text(json.dumps({'doi':'10.1000/legacy', 'ts':time.time(),
                                        'sha256':hashlib.sha256(body).hexdigest()}))
            entry = {'pdf_path':str(pdf)}
            self.assertIsNone(cache.cache_get('10.1000/legacy', root=root))
            self.assertTrue(Path(entry['pdf_path']).exists())

    def test_valid_legacy_cache_remains_usable(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cache.cache_put('10.1000/legacy', make_pdf(), root=root)
            self.assertIsNotNone(cache.cache_get('10.1000/legacy', root=root))
