"""Respectful route and rate-limit recovery, generated fixtures only."""
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
import io
import json
import urllib.error
import unittest
from unittest.mock import patch

from pa_cli import _http, search
from tools import engine_health as health


class RecoveryTests(unittest.TestCase):
    def test_configured_loopback_route_and_explicit_direct(self):
        with patch("urllib.request.getproxies", return_value={"https": "http://127.0.0.1:10809"}):
            self.assertEqual(health.proxy_handler("configured").proxies, {"https": "http://127.0.0.1:10809"})
            self.assertEqual(health.proxy_handler("direct").proxies, {})

    def test_credentials_and_remote_plaintext_routes_are_refused_without_request(self):
        for value in ("http://user:private-token@127.0.0.1:1", "http://remote.example:8080", "socks5://127.0.0.1:1080"):
            with self.subTest(value=value), patch("urllib.request.getproxies", return_value={"https": value}), \
                 patch("urllib.request.build_opener", side_effect=AssertionError("must not contact endpoint")):
                result = health.probe("arxiv")
            self.assertEqual(result["status"], "network_configuration_error")
            self.assertNotIn("private-token", json.dumps(result))

    def test_anonymous_429_is_not_amplified(self):
        with patch.object(search, "http_get_json", return_value=(429, {})) as request, \
             patch.object(search, "_s2_throttle_wait"), patch.object(search.time, "sleep") as sleep:
            status, _ = search._s2_request_with_retry("https://fixture.test", {})
        self.assertEqual(status, 429)
        self.assertEqual(request.call_count, 1)
        sleep.assert_not_called()

    def test_keyed_retry_honors_server_delay_and_can_recover(self):
        def request(_url, **kwargs):
            kwargs["response_headers"]["Retry-After"] = "3"
            return (429, {}) if request.calls == 0 else (200, {"data": []})
        request.calls = 0
        def counted(*args, **kwargs):
            result = request(*args, **kwargs)
            request.calls += 1
            return result
        with patch.object(search, "http_get_json", side_effect=counted) as called, \
             patch.object(search, "_s2_throttle_wait"), patch.object(search.time, "sleep") as sleep:
            status, _ = search._s2_request_with_retry("https://fixture.test", {"x-api-key": "fixture"})
        self.assertEqual(status, 200)
        self.assertEqual(called.call_count, 2)
        sleep.assert_called_once_with(3)

    def test_long_server_cooldown_does_not_trigger_early_retry_or_block_parent(self):
        def request(_url, **kwargs):
            kwargs["response_headers"]["Retry-After"] = "120"
            return 429, {}
        with patch.object(search, "http_get_json", side_effect=request) as called, \
             patch.object(search, "_s2_throttle_wait"), patch.object(search.time, "sleep") as sleep:
            status, _ = search._s2_request_with_retry("https://fixture.test", {"x-api-key": "fixture"})
        self.assertEqual(status, 429)
        self.assertEqual(called.call_count, 1)
        sleep.assert_not_called()

    def test_retry_after_parsing(self):
        self.assertEqual(search._retry_after_seconds("12"), 12)
        date = format_datetime(datetime.now(timezone.utc) + timedelta(seconds=60), usegmt=True)
        self.assertGreater(search._retry_after_seconds(date), 50)
        self.assertLessEqual(search._retry_after_seconds(date), 60)
        for value in (None, "NaN", "-1", "private-token", "9"*500):
            self.assertIsNone(search._retry_after_seconds(value))

    def test_http_error_metadata_preserves_two_tuple_and_closes_body(self):
        stream = io.BytesIO(b'{"error":"rate limit"}')
        error = urllib.error.HTTPError("https://fixture.test", 429, "limited", {"Retry-After": "30", "Set-Cookie": "private-token"}, stream)
        metadata = {}
        with patch.object(_http, "http_get", side_effect=error):
            result = _http.http_get_json("https://fixture.test", response_headers=metadata)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], 429)
        self.assertEqual(metadata, {"Retry-After": "30"})
        self.assertTrue(stream.closed)

    def test_arxiv_sdk_uses_three_second_spacing(self):
        import sys
        import types
        def client(**kwargs):
            self.assertGreaterEqual(kwargs["delay_seconds"], 3)
            self.assertEqual(kwargs["num_retries"], 1)
            return types.SimpleNamespace(results=lambda _request: iter([]))
        fake = types.SimpleNamespace(Client=client, Search=lambda **kwargs: kwargs,
                                     SortCriterion=types.SimpleNamespace(Relevance="relevance"))
        with patch.dict(sys.modules, {"arxiv": fake}):
            self.assertEqual(search.search_arxiv("fixture"), [])


if __name__ == "__main__":
    unittest.main()
