import json
import unittest
from unittest.mock import patch

from click.testing import CliRunner


class DoctorTests(unittest.TestCase):
    def test_missing_chromium_is_unavailable_and_tokens_are_not_reported(self):
        from pa_cli import doctor

        with patch.object(doctor, "_dependency_status", return_value={
            "playwright_package": True,
            "chromium_installed": False,
            "arxiv": True,
        }), patch.object(doctor, "_aminer_status", return_value={
            "token_set": True,
            "token_prefix": "secret-token...",
        }), patch.object(doctor, "_cnki_status", return_value={
            "ready_for_search": False,
            "n_cookies": 0,
        }):
            report = doctor.build_report()

        encoded = json.dumps(report)
        self.assertEqual(report["overall_status"], "unavailable")
        self.assertEqual(report["checks"]["playwright"]["status"], "unavailable")
        self.assertNotIn("secret-token", encoded)
        self.assertNotIn("token_prefix", encoded)

    def test_empty_cnki_cookie_list_is_not_ready(self):
        from pa_cli import doctor

        with patch.object(doctor, "_dependency_status", return_value={
            "playwright_package": True,
            "chromium_installed": True,
            "arxiv": True,
        }), patch.object(doctor, "_aminer_status", return_value={"token_set": True}),              patch.object(doctor, "_cnki_status", return_value={
                 "ready_for_search": True,
                 "n_cookies": 0,
             }):
            report = doctor.build_report()

        self.assertEqual(report["checks"]["cnki"]["status"], "attention")

    def test_cli_json_outputs_offline_report(self):
        from pa_cli.cli import main

        result = CliRunner().invoke(main, ["doctor", "--json"])

        self.assertEqual(result.exit_code, 0, result.output)
        report = json.loads(result.stdout)
        self.assertIn(report["overall_status"], {"ready", "attention", "unavailable"})
        self.assertIn("cnki", report["checks"])
        self.assertIn("playwright", report["checks"])


if __name__ == "__main__":
    unittest.main()
