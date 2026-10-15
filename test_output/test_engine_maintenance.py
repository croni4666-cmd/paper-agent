"""Generated provider contracts and honest errors; no live services."""
import io
import json
import os
from pathlib import Path
from queue import Queue
import socket
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
from unittest.mock import MagicMock
import urllib.error

from pa_cli import search as search
from pa_cli import cnki_channel as cnki
from pa_cli import run_report
from tools import engine_health as health
from pa_cli import _http


def _bad_provider(*args, **kwargs):
    return {"unexpected": "object"}


class EngineContracts(unittest.TestCase):
    def test_non200_and_invalid_shapes_do_not_become_empty_success(self):
        providers = [search.search_crossref, search.search_openalex, search.search_pubmed,
                     search.search_clinicaltrials, search.search_semanticscholar]
        for provider in providers:
            for status, body in [(429, {}), (503, {}), (0, {}), (200, b"<html>"),
                                 (200, None), (200, []), (200, {}), (200, {"error": "private-token"})]:
                with self.subTest(provider=provider.__name__, status=status, body=body), \
                     patch.object(search, "http_get_json", return_value=(status, body)), \
                     patch.object(search, "_s2_request_with_retry", return_value=(status, body)), \
                     patch.object(search, "_pubmed_throttle"):
                    with self.assertRaises(search.EngineResponseError) as caught:
                        provider("fixture")
                    self.assertNotIn("private-token", str(caught.exception))

    def test_genuine_empty_results_are_successful(self):
        fixtures = [(search.search_crossref, {"message": {"items": []}}),
                    (search.search_openalex, {"results": []}),
                    (search.search_pubmed, {"esearchresult": {"idlist": []}}),
                    (search.search_clinicaltrials, {"studies": []}),
                    (search.search_semanticscholar, {"data": []})]
        for provider, body in fixtures:
            with self.subTest(provider=provider.__name__), \
                 patch.object(search, "http_get_json", return_value=(200, body)), \
                 patch.object(search, "_s2_request_with_retry", return_value=(200, body)), \
                 patch.object(search, "_pubmed_throttle"):
                self.assertEqual(provider("fixture"), [])

    def test_s2_exhaustion_does_not_sleep_after_last_attempt(self):
        with patch.object(search, "http_get_json", return_value=(429, {})) as request, \
             patch.object(search, "_s2_throttle_wait"), patch.object(search.time, "sleep") as sleep:
            status, _ = search._s2_request_with_retry("https://fixture.test", {})
        self.assertEqual(status, 429)
        self.assertEqual(request.call_count, search._S2_MAX_RETRIES + 1)
        self.assertEqual(sleep.call_count, search._S2_MAX_RETRIES)

    def test_malformed_optional_enrichment_preserves_primary_results(self):
        rows = [{"doi": "10.1234/fixture", "title": "Generated fixture title", "cited_by_count": 0}]
        with patch.object(search, "http_get_json", return_value=(200, b"not-json")), patch.object(search.time, "sleep"):
            result = search.enrich_top_n(rows, n=1, min_cites=0, max_age_years=0)
        self.assertEqual(result[0]["doi"], "10.1234/fixture")
        self.assertFalse(result[0]["_enrichment"])

    def test_worker_rejects_bad_rows_and_main_isolates_a_bad_engine(self):
        for invalid in ({}, ["bad"], [{"title": []}], [{"title": "x", "year": "2024"}],
                        [{"title": "x", "cited_by_count": True}], [{}]):
            queue = Queue()
            search._search_worker(queue, lambda: invalid, (), {})
            self.assertIn("error", queue.get()[0])
        def run(function, *args):
            return {} if function is search.search_arxiv else [{"title": "Healthy", "year": 2024}]
        with patch.object(search, "_run_search_engine", side_effect=run):
            result = search.run_search("fixture", engine="arxiv,openalex")
        self.assertEqual(result["engine_status"], {"arxiv": "error", "openalex": "ok"})
        self.assertEqual(result["dedup_count"], 1)

    def test_invalid_return_in_real_spawned_worker(self):
        rows = search._run_search_engine(_bad_provider, (), {}, 8)
        self.assertIn("error", rows[0])

    def test_unknown_and_duplicate_engines_are_explicit(self):
        with patch.object(search, "_run_search_engine", return_value=[]) as called:
            result = search.run_search("fixture", engine="openalex,openalex,unsupported")
        self.assertEqual(called.call_count, 1)
        self.assertEqual(result["engine_status"], {"openalex": "ok", "unsupported": "error"})

    def test_missing_optional_configuration_is_visible(self):
        with patch("pa_cli.aminer_channel._aminer_token", return_value=""), \
             patch.object(search, "_try_import_cnki", return_value=False):
            result = search.run_search("fixture", engine="aminer,cnki")
        self.assertEqual(result["skipped_engines"], {"aminer": "not_configured", "cnki": "not_configured"})
        self.assertEqual(result["engine_status"], {})

    def test_pubmed_failed_summary_is_visible_with_year_filter(self):
        with patch.object(search, "http_get_json", side_effect=[
                (200, {"esearchresult": {"idlist": ["1"]}}), (503, {})]), \
             patch.object(search, "_pubmed_throttle"):
            rows = search.search_pubmed("fixture", year_min=2020)
        self.assertEqual(rows[0]["error"], "partial_response")

    def test_pubmed_partial_chunk_preserves_healthy_records(self):
        summary = {"result": {"uids": ["1", "2"], "1": {"uid": "1", "title": "Fixture", "pubdate": "2024"},
                              "2": {"error": "unavailable"}}}
        with patch.object(search, "http_get_json", side_effect=[
                (200, {"esearchresult": {"idlist": ["1", "2"]}}), (200, summary)]), \
             patch.object(search, "_pubmed_throttle"):
            rows = search.search_pubmed("fixture", year_min=2020)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["title"], "Fixture")
        self.assertIn("error", rows[1])

    def test_arxiv_interrupted_iteration_is_not_complete(self):
        row = types.SimpleNamespace(doi=None, entry_id="https://arxiv.org/abs/2401.00001", title="Fixture", authors=[],
                                    published=types.SimpleNamespace(year=2024), pdf_url="https://example.test/fixture.pdf")
        def records(_request):
            yield row
            raise RuntimeError("interrupted")
        fake = types.SimpleNamespace(Client=lambda **kwargs: types.SimpleNamespace(results=records),
                                     Search=lambda **kwargs: kwargs, SortCriterion=types.SimpleNamespace(Relevance="relevance"))
        with patch.dict(sys.modules, {"arxiv": fake}):
            result = search.search_arxiv("fixture", year_min=2020)
        self.assertEqual(len(result), 2)
        self.assertIn("error", result[1])

    def test_partial_engine_rows_produce_partial_run_report(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "search.json"
            path.write_text(json.dumps(dict(engine_status={"pubmed": "error"}, engine_errors={"pubmed": "incomplete"},
                                           by_engine={"pubmed": 1}, results=[{"title": "Fixture"}], dedup_count=1)))
            self.assertEqual(run_report.build_report({"search": path})["overall_status"], "partial")

    def test_cnki_empty_malformed_and_valid_configuration(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(cnki, "CNKI_COOKIES_PATH", Path(directory) / "cookies.json"), \
             patch.dict(sys.modules, {"playwright": types.ModuleType("playwright")}):
            for payload, ready in [([], False), ([{}], False), (["bad"], False),
                                   ([{"name": "session", "value": "fixture", "domain": ".cnki.net", "path": "/"}], True)]:
                cnki.CNKI_COOKIES_PATH.write_text(json.dumps(payload))
                self.assertEqual(cnki.status_report()["ready_for_search"], ready)
            cnki.CNKI_COOKIES_PATH.write_bytes(b"\xff")
            self.assertFalse(cnki.status_report()["ready_for_search"])

    def test_cnki_future_timestamp_is_not_fresh(self):
        with patch.object(cnki, "cookies_exist", return_value=True), \
             patch.object(cnki.Path, "exists", return_value=True), \
             patch.object(cnki.Path, "stat", return_value=types.SimpleNamespace(st_mtime=100)), \
             patch.object(cnki.time, "time", return_value=50):
            self.assertIsNone(cnki.cookie_age_hours())
        with patch.object(cnki.Path, "exists", return_value=True), \
             patch.object(cnki.Path, "stat", return_value=types.SimpleNamespace(st_mtime=50.001)), \
             patch.object(cnki.time, "time", return_value=50):
            self.assertEqual(cnki.cookie_age_hours(), 0.0)


class HealthContracts(unittest.TestCase):
    def test_offline_inventory_never_dispatches(self):
        with patch.object(subprocess, "run", side_effect=AssertionError("dispatch")), \
             patch.object(socket.socket, "connect", side_effect=AssertionError("network")):
            result = health.collect()
        self.assertTrue(all(row["status"] == "not_checked" for row in result["checks"]))

    def test_public_schemas(self):
        fixtures = {"crossref": {"message": {"items": [{"DOI": "10.1234/fixture", "title": ["Fixture"]}]}},
                    "openalex": {"results": [{"id": "W1", "title": "Fixture"}]},
                    "semanticscholar": {"data": [{"paperId": "1", "title": "Fixture"}]},
                    "pubmed": {"esearchresult": {"idlist": ["1"]}},
                    "clinicaltrials": {"studies": [{"protocolSection": {"identificationModule": {"nctId": "NCT1", "briefTitle": "Fixture"}}}]}}
        for engine, data in fixtures.items():
            self.assertEqual(health.validate_body(engine, json.dumps(data).encode()), 1)
            with self.assertRaises((ValueError, KeyError, TypeError)):
                health.validate_body(engine, b"{}")
        self.assertEqual(health.validate_body("arxiv", b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>https://arxiv.org/abs/1</id><title>Fixture</title></entry></feed>'), 1)
        with self.assertRaises(ValueError):
            health.validate_body("arxiv", b'<!DOCTYPE feed><feed/>')
        self.assertEqual(health.validate_body("crossref", b'{"message":{"items":[{"DOI":"10.1234/fixture"}]}}'), 1)

    def test_scoped_probe_does_not_claim_other_engines_checked(self):
        result = health.collect(False, ["crossref", "crossref"])
        self.assertEqual(len(result["checks"]), 1)
        self.assertEqual(len(result["unselected_engines"]), 5)

    def test_http_failures_and_sensitive_text_are_not_relayed(self):
        for code, expected in [(429, "rate_limited"), (403, "access_denied"), (503, "unavailable")]:
            error = urllib.error.HTTPError("private-token", code, "private-token", {}, io.BytesIO(b"private-token"))
            with patch("urllib.request.build_opener") as opener:
                opener.return_value.open.side_effect = error
                result = health.probe("crossref")
            self.assertEqual(result["status"], expected)
            self.assertNotIn("private-token", json.dumps(result))

    def test_worker_timeout_isolated_and_raw_stderr_discarded(self):
        calls = [subprocess.TimeoutExpired("private-token", 15)] + [
            types.SimpleNamespace(returncode=0, stdout=json.dumps({"engine": engine, "status": "healthy", "secret": "private-token"}).encode(), stderr=b"private-token")
            for engine in list(health.ENDPOINTS)[1:]]
        with patch.object(subprocess, "run", side_effect=calls):
            result = health.collect(True)
        self.assertEqual(result["checks"][0]["status"], "timeout")
        self.assertTrue(all(row["status"] == "healthy" for row in result["checks"][1:]))
        self.assertNotIn("private-token", json.dumps(result))

    def test_http_response_is_closed_on_success_and_read_failure(self):
        for function in (_http.http_get, _http.http_post):
            for fails in (False, True):
                with self.subTest(function=function.__name__, fails=fails):
                    response = MagicMock()
                    response.__enter__.return_value = response
                    response.headers = {}
                    response.read.side_effect = OSError("fixture read failure") if fails else None
                    response.read.return_value = b"fixture"
                    with patch.object(_http, "build_opener") as opener:
                        opener.return_value.open.return_value = response
                        if fails:
                            with self.assertRaises(OSError):
                                function("https://fixture.test")
                        else:
                            self.assertEqual(function("https://fixture.test"), b"fixture")
                    response.__exit__.assert_called_once()

    def test_http_error_response_is_closed(self):
        stream = io.BytesIO(b'{"error":"fixture"}')
        error = urllib.error.HTTPError("https://fixture.test", 429, "rate limited", {}, stream)
        with patch.object(_http, "http_get", side_effect=error):
            status, _ = _http.http_get_json("https://fixture.test")
        self.assertEqual(status, 429)
        self.assertTrue(stream.closed)

    def test_probe_bounded_body_and_json_shape_failure(self):
        for raw, expected in [(b'xxxx', "response_too_large"), (b'{}', "schema_changed")]:
            response = MagicMock()
            response.__enter__.return_value = response
            response.status = 200
            response.read.return_value = raw
            with patch("urllib.request.build_opener") as opener, patch.object(health, "MAX_BYTES", 3):
                opener.return_value.open.return_value = response
                result = health.probe("crossref")
            self.assertEqual(result["status"], expected)
            response.read.assert_called_once_with(4)


if __name__ == "__main__":
    unittest.main()
