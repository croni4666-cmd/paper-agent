import unittest


class EngineProbeTests(unittest.TestCase):
    def test_probe_reports_each_requested_engine_without_network(self):
        from pa_cli.engine_probe import probe_search_engines

        calls = []

        def runner(query, *, engine, limit, engine_timeout):
            calls.append((query, engine, limit, engine_timeout))
            return {
                "by_engine": {engine: 2},
                "engine_status": {engine: {"status": "ok", "count": 2}},
            }

        report = probe_search_engines(
            "test query", engines=["crossref", "openalex"], limit=1,
            engine_timeout=2, runner=runner,
        )

        self.assertEqual([row["engine"] for row in report["engines"]], ["crossref", "openalex"])
        self.assertEqual([row["result_count"] for row in report["engines"]], [2, 2])
        self.assertEqual(calls, [("test query", "crossref", 1, 2), ("test query", "openalex", 1, 2)])

    def test_probe_redacts_credentials_from_error_messages(self):
        from pa_cli.engine_probe import probe_search_engines

        def runner(*_args, **_kwargs):
            return {
                "by_engine": {"crossref": 0},
                "engine_status": {"crossref": {
                    "status": "error", "count": 0,
                    "message": "proxy http://user:secret@example.test failed",
                }},
            }

        report = probe_search_engines("test", engines=["crossref"], runner=runner)
        message = report["engines"][0]["message"]
        self.assertNotIn("secret", message)
        self.assertIn("[REDACTED]", message)

