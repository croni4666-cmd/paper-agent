import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pa_cli import fetch


class PmcJatsCacheTests(unittest.TestCase):
    def test_cache_hit_avoids_network_and_writes_requested_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "jats-cache"
            root.mkdir()
            (root / "PMC123.xml").write_bytes(b"<article/>")
            out = Path(temp) / "paper.pdf"
            with patch.object(fetch, "JATS_CACHE_DIR", root), \
                 patch.object(fetch, "_http_get_bytes") as get_bytes:
                result = fetch._pmc_efetch_xml("PMC123", out_path=str(out))

            get_bytes.assert_not_called()
            self.assertTrue(result["cache_hit"])
            self.assertEqual(Path(result["path"]).read_bytes(), b"<article/>")

    def test_network_result_populates_cache(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "jats-cache"
            with patch.object(fetch, "JATS_CACHE_DIR", root), \
                 patch.object(fetch, "_http_get_bytes", return_value=(200, b"<article/>")):
                result = fetch._pmc_efetch_xml("PMC456")

            self.assertFalse(result["cache_hit"])
            self.assertEqual((root / "PMC456.xml").read_bytes(), b"<article/>")


if __name__ == "__main__":
    unittest.main()