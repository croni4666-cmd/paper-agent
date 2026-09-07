import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class CliModuleEntrypointTests(unittest.TestCase):
    def test_module_entrypoint_registers_sample_pool(self):
        result = subprocess.run(
            [sys.executable, "-m", "pa_cli.cli", "sample-pool", "--help"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Global Sample Pool", result.stdout)


if __name__ == "__main__":
    unittest.main()
