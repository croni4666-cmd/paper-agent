"""Regression tests for v4.1.5 fixes (AMiner auth/error propagation, reliable HTTP retry, PMC articleset provenance, engine cleanup)."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pa_cli import aminer_channel, provenance, search


class TestV415Fixes(unittest.TestCase):
    def test_aminer_auth_error_detection_and_propagation(self):
        self.assertTrue(aminer_channel._is_auth_error(500, {"code": 40308, "msg": "Invalid Token"}))
        self.assertTrue(aminer_channel._is_auth_error(401, {}))
        self.assertFalse(aminer_channel._is_auth_error(200, {"data": []}))

        merged = aminer_channel._merge_aminer_results(
            [{"error": aminer_channel.E_AUTH, "message": "expired"}],
            [{"error": aminer_channel.E_EMPTY, "message": "empty"}],
            10,
        )
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["error"], aminer_channel.E_AUTH)

    def test_reliable_get_json_retries_transient_stall(self):
        calls = {"n": 0}

        def fake_get(url, timeout=10):
            calls["n"] += 1
            return (0, {"error": "stall"}) if calls["n"] == 1 else (200, {"ok": True})

        with patch.object(search, "http_get_json", fake_get), patch.object(search.time, "sleep"):
            status, data = search._reliable_get_json("https://example.com", timeout=10, retries=2)
        self.assertEqual(status, 200)
        self.assertEqual(data, {"ok": True})
        self.assertEqual(calls["n"], 2)

    def test_provenance_pmc_articleset_single_ok_and_multi_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p_single = Path(tmp) / "single.xml"
            p_single.write_text(
                '<pmc-articleset><article xmlns:xlink="http://www.w3.org/1999/xlink">'
                '<front><article-meta>'
                '<article-id pub-id-type="doi">10.1234/pmc-single</article-id>'
                '<permissions><license xlink:href="https://creativecommons.org/licenses/by/4.0/"/></permissions>'
                '</article-meta></front></article></pmc-articleset>',
                encoding="utf-8",
            )
            res = provenance.inspect_artifact(
                p_single, "10.1234/pmc-single",
                source="pmc_xml_only", url="https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
                data_class="public",
            )
            self.assertEqual(res["identity"]["status"], "verified")
            self.assertEqual(res["rights"]["class"], "public_oa")
            self.assertTrue(res["external_evaluation_candidate"])

            p_multi = Path(tmp) / "multi.xml"
            p_multi.write_text(
                '<pmc-articleset>'
                '<article xmlns:xlink="http://www.w3.org/1999/xlink"><front><article-meta>'
                '<article-id pub-id-type="doi">10.1234/a</article-id>'
                '<permissions><license xlink:href="https://creativecommons.org/licenses/by/4.0/"/></permissions>'
                '</article-meta></front></article>'
                '<article><front><article-meta><article-id pub-id-type="doi">10.1234/b</article-id></article-meta></front></article>'
                '</pmc-articleset>',
                encoding="utf-8",
            )
            res_m = provenance.inspect_artifact(
                p_multi, "10.1234/a",
                source="pmc_xml_only", url="https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
                data_class="public",
            )
            self.assertEqual(res_m["identity"]["status"], "unverified")
            self.assertFalse(res_m["external_evaluation_candidate"])

    def test_default_all_excludes_removed_engines(self):
        called = []

        def fake_run(fn, *args):
            called.append(fn.__name__)
            return []

        with patch.object(search, "_run_search_engine", side_effect=fake_run), \
             patch("pa_cli.aminer_channel._aminer_token", return_value=""):
            res = search.run_search("fixture", engine="all")
        self.assertNotIn("search_semanticscholar", called)
        self.assertNotIn("search_cnki", called)
        self.assertNotIn("semanticscholar", res["engine_status"])
        self.assertNotIn("cnki", res["engine_status"])


if __name__ == "__main__":
    unittest.main()
