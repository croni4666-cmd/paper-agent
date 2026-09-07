import unittest
from unittest.mock import patch

from click.testing import CliRunner

from pa_cli import search
from pa_cli.cli import main


class RetiredEngineTests(unittest.TestCase):
    def test_all_search_does_not_schedule_retired_engines(self):
        with patch.object(search, "_run_engine_with_timeout", return_value=[]):
            result = search.run_search("machine learning", engine="all", limit=1)

        self.assertNotIn("cnki", result["by_engine"])
        self.assertNotIn("semanticscholar", result["by_engine"])

    def test_cli_rejects_retired_search_engines(self):
        for engine in ("cnki", "semanticscholar"):
            result = CliRunner().invoke(main, ["search", "test", "--engine", engine])
            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("Invalid value", result.output)


if __name__ == "__main__":
    unittest.main()

