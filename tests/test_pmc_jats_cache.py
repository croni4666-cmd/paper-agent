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
class PmcJatsValidationTests(unittest.TestCase):
    def test_cold_cache_returns_readable_path(self):
        with tempfile.TemporaryDirectory() as temp, \
             patch.object(fetch, 'JATS_CACHE_DIR', Path(temp)), \
             patch.object(fetch.time, 'sleep'), \
             patch.object(fetch, '_http_get_bytes', return_value=(200, b'<article/>')):
            result = fetch._pmc_efetch_xml('PMC456')
            self.assertIsNotNone(result['path'])
            self.assertEqual(Path(result['path']).read_bytes(), b'<article/>')

    def test_invalid_payload_is_not_cached_or_written(self):
        for body in (b'<html>error</html>', b'<article>', b'<error>unavailable</error>'):
            with self.subTest(body=body), tempfile.TemporaryDirectory() as temp, \
                 patch.object(fetch, 'JATS_CACHE_DIR', Path(temp) / 'cache'), \
                 patch.object(fetch.time, 'sleep'), \
                 patch.object(fetch, '_http_get_bytes', return_value=(200, body)):
                result = fetch._pmc_efetch_xml('PMC123', str(Path(temp) / 'paper.pdf'))
                self.assertIn('error', result)
                self.assertFalse((Path(temp) / 'paper.xml').exists())
                self.assertFalse((Path(temp) / 'cache' / 'PMC123.xml').exists())

    def test_bad_cache_is_refetched(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'PMC123.xml').write_bytes(b'<html>error</html>')
            with patch.object(fetch, 'JATS_CACHE_DIR', root), \
                 patch.object(fetch.time, 'sleep'), \
                 patch.object(fetch, '_http_get_bytes', return_value=(200, b'<article/>')) as network:
                result = fetch._pmc_efetch_xml('PMC123')
            network.assert_called_once()
            self.assertFalse(result['cache_hit'])
            self.assertEqual((root / 'PMC123.xml').read_bytes(), b'<article/>')

    def test_invalid_id_never_reaches_network(self):
        for pmcid in ('../outside', 'PMC1/../../outside', '', 'PMC1?x=2'):
            with self.subTest(pmcid=pmcid), patch.object(fetch, '_http_get_bytes') as network:
                result = fetch._pmc_efetch_xml(pmcid)
                self.assertEqual(result.get('error'), 'pmc_invalid_id')
                network.assert_not_called()

    def test_article_set_and_namespace_are_accepted(self):
        for body in (b'<article-set><article/></article-set>',
                     b'<article xmlns="urn:jats"/>'):
            with self.subTest(body=body):
                self.assertTrue(fetch._is_jats_article(body))

    def test_network_failures_do_not_create_cache(self):
        for response in ((0, b''), (503, b'<article/>'), (200, b'')):
            with self.subTest(response=response), tempfile.TemporaryDirectory() as temp, \
                 patch.object(fetch, 'JATS_CACHE_DIR', Path(temp)), \
                 patch.object(fetch.time, 'sleep'), \
                 patch.object(fetch, '_http_get_bytes', return_value=response):
                self.assertIn('error', fetch._pmc_efetch_xml('PMC123'))
                self.assertFalse((Path(temp) / 'PMC123.xml').exists())

    def test_unwritable_cache_requires_output_or_returns_error(self):
        with tempfile.TemporaryDirectory() as temp:
            blocked = Path(temp) / 'file'
            blocked.write_text('occupied')
            with patch.object(fetch, 'JATS_CACHE_DIR', blocked), \
                 patch.object(fetch.time, 'sleep'), \
                 patch.object(fetch, '_http_get_bytes', return_value=(200, b'<article/>')):
                self.assertEqual(fetch._pmc_efetch_xml('PMC123')['error'], 'pmc_xml_save_error')
                result = fetch._pmc_efetch_xml('PMC123', str(Path(temp) / 'paper.pdf'))
                self.assertEqual(Path(result['path']).read_bytes(), b'<article/>')


if __name__ == "__main__":
    unittest.main()
