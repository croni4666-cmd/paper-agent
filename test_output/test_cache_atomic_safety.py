"""Regression test for cache atomic update safety and non-destructive reads (Issue 4)."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from pa_cli import cache

fake_pdf_1 = b"%PDF-1.4\n%version1\n" + b"%% padding to pass 50KB threshold\n" * 1500
fake_pdf_2 = b"%PDF-1.4\n%version2\n" + b"%% different padding for second version\n" * 1500


class TestCacheAtomicSafety(unittest.TestCase):
    def test_failed_update_preserves_old_cache(self):
        """When an update fails mid-way, the old valid entry remains readable."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            doi = "10.1234/atomic"

            # 1. Put initial version
            entry1 = cache.cache_put(doi, fake_pdf_1, channel="v1", root=root)
            self.assertEqual(entry1["sha256"], hashlib.sha256(fake_pdf_1).hexdigest())

            hit1 = cache.cache_get(doi, root=root)
            self.assertIsNotNone(hit1)
            self.assertEqual(hit1["channel"], "v1")
            self.assertEqual(hit1["sha256"], entry1["sha256"])

            # 2. Simulate failure during metadata replace (second replace)
            orig_replace = cache.os.replace

            def fail_meta_replace(src, dst):
                if str(dst).endswith(".meta.json"):
                    raise OSError("simulated interruption during metadata replacement")
                return orig_replace(src, dst)

            with patch("pa_cli.cache.os.replace", side_effect=fail_meta_replace):
                with self.assertRaises(OSError):
                    cache.cache_put(doi, fake_pdf_2, channel="v2", root=root)

            # 3. Verify old cache entry was NOT destroyed and remains valid
            hit_after = cache.cache_get(doi, root=root)
            self.assertIsNotNone(hit_after, "Old cache entry must survive failed update!")
            self.assertEqual(hit_after["channel"], "v1")
            self.assertEqual(hit_after["sha256"], entry1["sha256"])
            self.assertEqual(Path(hit_after["pdf_path"]).read_bytes(), fake_pdf_1)

    def test_cache_get_does_not_unlink_on_sha_mismatch(self):
        """Read-time hash mismatch treats entry as miss without deleting files on disk."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            doi = "10.1234/safe_read"

            entry = cache.cache_put(doi, fake_pdf_1, channel="v1", root=root)
            pdf_path = Path(entry["pdf_path"])
            meta_path = Path(entry["meta_path"])

            # Invalidate sha in metadata to simulate discrepancy
            meta_data = json.loads(meta_path.read_text(encoding="utf-8"))
            meta_data["sha256"] = "0000000000000000000000000000000000000000000000000000000000000000"
            meta_path.write_text(json.dumps(meta_data), encoding="utf-8")

            # cache_get should return None (miss)
            res = cache.cache_get(doi, root=root)
            self.assertIsNone(res)

            # BUT files must NOT be unlinked!
            self.assertTrue(pdf_path.exists(), "PDF must not be unlinked on read mismatch")
            self.assertTrue(meta_path.exists(), "Metadata sidecar must not be unlinked on read mismatch")


if __name__ == "__main__":
    unittest.main()
