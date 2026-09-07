"""Regression tests for real-environment search failures."""
import unittest
import threading
from unittest.mock import patch

from pa_cli import _http, search


class _Response:
    headers = {}

    def read(self):
        return b'{"results": []}'


class _Opener:
    def __init__(self):
        self.request = None

    def open(self, request, timeout):
        self.request = request
        return _Response()


class SearchRuntimeTests(unittest.TestCase):
    def test_http_get_does_not_advertise_unavailable_brotli(self):
        opener = _Opener()
        with patch.object(_http, "build_opener", return_value=opener):
            _http.http_get("https://example.test/api")
        self.assertNotIn("br", opener.request.get_header("Accept-encoding"))

    def test_invalid_json_is_returned_as_structured_error(self):
        with patch.object(_http, "http_get", return_value=b"<html>proxy error</html>"):
            status, payload = _http.http_get_json("https://example.test/api")
        self.assertEqual(status, 200)
        self.assertIsInstance(payload, dict)
        self.assertEqual(payload["error"], "invalid_json_response")

    def test_engine_exception_is_reported_without_fake_result_count(self):
        with patch.object(search, "search_openalex", side_effect=RuntimeError("network failed")):
            result = search.run_search("test", engine="openalex", limit=1)
        self.assertEqual(result["by_engine"], {"openalex": 0})
        self.assertEqual(result["engine_status"]["openalex"]["status"], "error")
        self.assertIn("network failed", result["engine_status"]["openalex"]["message"])

    def test_blocked_engine_times_out_without_blocking_search(self):
        release = threading.Event()

        def blocked(*_args, **_kwargs):
            release.wait(1)
            return []

        try:
            with patch.object(search, "search_openalex", side_effect=blocked):
                result = search.run_search(
                    "test", engine="openalex", limit=1, engine_timeout=0.01
                )
        finally:
            release.set()

        self.assertEqual(result["by_engine"], {"openalex": 0})
        self.assertEqual(result["engine_status"]["openalex"]["status"], "error")
        self.assertIn("timed out", result["engine_status"]["openalex"]["message"])

if __name__ == "__main__":
    unittest.main()
