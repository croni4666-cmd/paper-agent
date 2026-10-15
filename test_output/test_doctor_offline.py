"""Offline inventory must stay read-only, private and failure-isolated."""
import json
import unittest
from unittest.mock import patch

from click.testing import CliRunner

from pa_cli import doctor
from pa_cli.cli import main


class DoctorTests(unittest.TestCase):
    def test_optional_missing_does_not_disable_cli(self):
        with patch.object(doctor.importlib.util, "find_spec", return_value=None), patch.object(
            doctor.shutil, "which", return_value=None
        ), patch.dict(doctor.os.environ, {}, clear=True):
            report = doctor.build_report()
        self.assertEqual(report["overall_status"], "attention")
        self.assertEqual(report["checks"]["pdf"]["status"], "unavailable")
        self.assertEqual(report["checks"]["pubmed"]["status"], "attention")

    def test_discovery_failure_does_not_hide_other_checks_or_expose_exception(self):
        def discovery(name):
            if name == "fitz":
                raise RuntimeError("private-path-and-token")
            return object()
        with patch.object(doctor.importlib.util, "find_spec", side_effect=discovery), patch.object(
            doctor.shutil, "which", side_effect=OSError("private-path-and-token")
        ):
            report = doctor.build_report()
        self.assertEqual(report["checks"]["pdf"]["status"], "unknown")
        self.assertEqual(report["checks"]["pandoc"]["status"], "unknown")
        self.assertEqual(report["checks"]["arxiv"]["status"], "ready")
        self.assertNotIn("private-path-and-token", json.dumps(report))

    def test_credential_values_never_appear(self):
        with patch.dict(doctor.os.environ, {
            "AMINER_API_KEY": "sensitive-a", "S2_API_KEY": "sensitive-b", "NCBI_API_KEY": "sensitive-c"
        }), patch.object(doctor.importlib.util, "find_spec", return_value=object()), patch.object(
            doctor.shutil, "which", return_value="private/executable/path"
        ):
            report = doctor.build_report()
        self.assertEqual(report["overall_status"], "ready")
        self.assertNotIn("sensitive-", json.dumps(report))
        self.assertNotIn("private/executable/path", json.dumps(report))

    def test_cli_json_no_files_network_or_subprocess(self):
        with patch("pa_cli.keys.load_env_into_environ", side_effect=AssertionError("dotenv read")), patch(
            "pa_cli.keys.cmd_remind", side_effect=AssertionError("registry read")
        ), patch("builtins.open", side_effect=AssertionError("private file read")), patch(
            "socket.socket.connect", side_effect=AssertionError("network")
        ), patch("subprocess.Popen", side_effect=AssertionError("subprocess")), patch.object(
            doctor.importlib.util, "find_spec", return_value=None
        ), patch.object(doctor.shutil, "which", return_value=None):
            result = CliRunner().invoke(main, ["doctor", "--json"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(json.loads(result.output)["mode"], "offline")

    def test_cli_human_output_and_help(self):
        with patch.object(doctor, "build_report", return_value={
            "overall_status": "attention", "scope": "local only", "checks": {
                "pdf": {"status": "unavailable", "summary": "Missing", "next_action": "Install dependency"}
            }
        }):
            result = CliRunner().invoke(main, ["doctor"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Install dependency", result.output)
        self.assertEqual(CliRunner().invoke(main, ["doctor", "--help"]).exit_code, 0)


if __name__ == "__main__":
    unittest.main()
