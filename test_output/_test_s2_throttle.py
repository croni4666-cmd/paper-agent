"""Test [P1-20] S2 throttle — 1 RPS + 429 backoff/retry.

We mock `http_get_json` to avoid network. Tests:
  1. _s2_throttle_wait maintains 1 RPS (~1.1s gap between calls)
  2. _s2_request_with_retry returns 200 immediately on success
  3. _s2_request_with_retry backs off on 429, retries up to 3 times
  4. _s2_request_with_retry returns non-200 immediately on 400/404 (no retry)
  5. _s2_request_with_retry returns last status on exhausted retries
"""
import time
import unittest
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, '.')

import pa_cli.search as search_mod


class TestS2Throttle(unittest.TestCase):
    def setUp(self):
        # Reset module state between tests
        search_mod._S2_LAST_CALL = 0.0

    def test_throttle_maintains_1_rps(self):
        """Two back-to-back calls should sleep ~1.1s between them."""
        t0 = time.time()
        search_mod._s2_throttle_wait()
        search_mod._s2_throttle_wait()
        elapsed = time.time() - t0
        self.assertGreaterEqual(elapsed, 1.0, f"expected >= 1.0s, got {elapsed:.2f}s")
        self.assertLess(elapsed, 2.0, f"expected < 2.0s, got {elapsed:.2f}s")

    def test_throttle_no_wait_after_long_gap(self):
        """If >1.1s elapsed since last call, no sleep needed."""
        search_mod._S2_LAST_CALL = time.time() - 5.0  # 5s ago
        t0 = time.time()
        search_mod._s2_throttle_wait()
        elapsed = time.time() - t0
        self.assertLess(elapsed, 0.1, f"expected < 0.1s, got {elapsed:.2f}s")


class TestS2RequestWithRetry(unittest.TestCase):
    @patch('pa_cli.search.http_get_json')
    def test_returns_200_immediately(self, mock_http):
        mock_http.return_value = (200, {"data": []})
        s, data = search_mod._s2_request_with_retry("http://x", {})
        self.assertEqual(s, 200)
        self.assertEqual(data, {"data": []})
        self.assertEqual(mock_http.call_count, 1)

    @patch('pa_cli.search.http_get_json')
    def test_retries_on_429_then_succeeds(self, mock_http):
        # First 2 calls: 429, 3rd: 200
        mock_http.side_effect = [(429, {}), (429, {}), (200, {"data": ["ok"]})]
        t0 = time.time()
        s, data = search_mod._s2_request_with_retry("http://x", {})
        elapsed = time.time() - t0
        self.assertEqual(s, 200)
        self.assertEqual(data, {"data": ["ok"]})
        self.assertEqual(mock_http.call_count, 3)
        # 1s + 2s backoff before 3rd success = ~3s
        self.assertGreaterEqual(elapsed, 2.5, f"expected >= 2.5s, got {elapsed:.2f}s")

    @patch('pa_cli.search.http_get_json')
    def test_no_retry_on_400(self, mock_http):
        """400 bad request: don't retry, return immediately."""
        mock_http.return_value = (400, {})
        s, data = search_mod._s2_request_with_retry("http://x", {})
        self.assertEqual(s, 400)
        self.assertEqual(mock_http.call_count, 1)

    @patch('pa_cli.search.http_get_json')
    def test_no_retry_on_404(self, mock_http):
        """404 not found: don't retry, return immediately."""
        mock_http.return_value = (404, {})
        s, data = search_mod._s2_request_with_retry("http://x", {})
        self.assertEqual(s, 404)
        self.assertEqual(mock_http.call_count, 1)

    @patch('pa_cli.search.http_get_json')
    def test_exhausted_retries_returns_last_status(self, mock_http):
        """All retries 429: return last 429, no crash."""
        mock_http.return_value = (429, {})
        s, data = search_mod._s2_request_with_retry("http://x", {})
        self.assertEqual(s, 429)
        # 1 initial + 3 retries = 4 calls
        self.assertEqual(mock_http.call_count, 4)


class TestS2Integration(unittest.TestCase):
    """Verify search_semanticscholar() uses the retry helper."""

    @patch('pa_cli.search._s2_request_with_retry')
    def test_calls_throttle_helper(self, mock_retry):
        mock_retry.return_value = (200, {"data": []})
        result = search_mod.search_semanticscholar("test query", limit=10)
        self.assertEqual(result, [])
        self.assertEqual(mock_retry.call_count, 1)
        # Verify URL contains expected fields
        call_args = mock_retry.call_args
        url = call_args[0][0]
        self.assertIn("semanticscholar.org", url)
        self.assertIn("query=test", url.replace(" ", "%20"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
