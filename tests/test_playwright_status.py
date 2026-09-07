import unittest
from unittest.mock import patch

from pa_cli.cnki_channel import status_report


class PlaywrightRuntimeStatusTests(unittest.TestCase):
    @patch("pa_cli.cnki_channel._playwright_runtime_status")
    @patch("pa_cli.cnki_channel.load_cookies", return_value=[])
    @patch("pa_cli.cnki_channel.cookie_age_hours", return_value=None)
    @patch("pa_cli.cnki_channel.cookies_exist", return_value=False)
    def test_status_reports_browser_runtime(
        self, _exists, _age, _cookies, runtime_status
    ):
        runtime_status.return_value = {
            "installed": True,
            "browser_ready": False,
            "executable_path": "C:/cache/chromium/chrome.exe",
            "message": "Chromium is not installed",
        }

        report = status_report()

        self.assertTrue(report["playwright_installed"])
        self.assertFalse(report["playwright_browser_ready"])
        self.assertEqual(
            report["playwright_executable_path"], "C:/cache/chromium/chrome.exe"
        )
        self.assertIn("Chromium", report["playwright_message"])


    @patch("pa_cli.cnki_channel._playwright_runtime_status")
    @patch("pa_cli.cnki_channel.load_cookies", return_value=[{"name": "session"}])
    @patch("pa_cli.cnki_channel.cookie_age_hours", return_value=1.0)
    @patch("pa_cli.cnki_channel.cookies_exist", return_value=True)
    def test_ready_requires_chromium(
        self, _exists, _age, _cookies, runtime_status
    ):
        runtime_status.return_value = {
            "installed": True,
            "browser_ready": False,
            "executable_path": "C:/cache/chromium/chrome.exe",
            "message": "Chromium is not installed",
        }

        report = status_report()

        self.assertTrue(report["cookies_fresh"])
        self.assertFalse(report["ready_for_search"])
if __name__ == "__main__":
    unittest.main()
