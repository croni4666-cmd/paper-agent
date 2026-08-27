"""v3.9.26.0 fetch_batch regression tests.

Tests 4 user-reported bugs from Wilson disease end-to-end test:
1. Skill `scripts/fetch_batch.py` couldn't find `--out-dir` option
   Root cause: TWO `fetch-batch` click commands (old `fetch_batch()` CNKI
   guide + new `fetch-batch` PDF downloader) collided; OLD won registration
   race. Fix: renamed old function to `cnki-guide`.
2. First download size = 0 (Bug 2): `r.get('size', 0)` instead of
   `r.get('size_bytes', 0)`. Fix: changed key name.
3. --skip-existing counter wrong (Bug 3): skipped entries counted as
   `n_success` (not `n_skipped`). Fix: check `error == 'skipped-existing'`
   before incrementing `n_success`.
4. .xml intermediate not cleaned up. Fix: added `--clean-xml` flag.
"""
import importlib.util
import inspect
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


class TestClickCommandNames(unittest.TestCase):
    """Bug 1: Two `fetch-batch` click commands collided. Old renamed to cnki-guide."""

    def test_cnki_guide_command_exists(self):
        """The OLD function is now reachable as `pa cnki-guide`."""
        from click.testing import CliRunner
        from pa_cli.cli import main as cli_main
        runner = CliRunner()
        result = runner.invoke(cli_main, ['cnki-guide', '--help'])
        self.assertEqual(result.exit_code, 0,
                         f"cnki-guide --help failed: {result.output[:200]}")
        self.assertIn('cnki-guide', result.output.lower())
        self.assertIn('CNKI', result.output)
        print("  [PASS] cnki-guide command works (renamed from fetch_batch)")

    def test_fetch_batch_command_works(self):
        """The NEW fetch-batch (PDF downloader) is the default `pa fetch-batch`."""
        from click.testing import CliRunner
        from pa_cli.cli import main as cli_main
        runner = CliRunner()
        result = runner.invoke(cli_main, ['fetch-batch', '--help'])
        self.assertEqual(result.exit_code, 0,
                         f"fetch-batch --help failed: {result.output[:200]}")
        self.assertIn('fetch-batch', result.output)
        # Verify it shows the new PDF downloader help, not the old CNKI guide
        self.assertIn('out-dir', result.output, "fetch-batch should have --out-dir option")
        self.assertIn('skip-existing', result.output, "fetch-batch should have --skip-existing option")
        print("  [PASS] fetch-batch shows PDF downloader (has --out-dir, --skip-existing)")

    def test_fetch_batch_has_clean_xml_flag(self):
        """Bug 4: --clean-xml option should be present."""
        from click.testing import CliRunner
        from pa_cli.cli import main as cli_main
        runner = CliRunner()
        result = runner.invoke(cli_main, ['fetch-batch', '--help'])
        self.assertIn('--clean-xml', result.output,
                      "--clean-xml flag should be visible in fetch-batch --help")
        print("  [PASS] --clean-xml flag visible in fetch-batch --help")

    def test_old_fetch_batch_underscore_gone(self):
        """The old `pa fetch_batch` (underscore) should not exist anymore."""
        from click.testing import CliRunner
        from pa_cli.cli import main as cli_main
        runner = CliRunner()
        result = runner.invoke(cli_main, ['fetch_batch', '--help'])
        # Should fail with "No such command"
        self.assertNotEqual(result.exit_code, 0,
                           "fetch_batch (underscore) should not exist anymore")
        self.assertIn('No such command', result.output)
        print("  [PASS] old `fetch_batch` (underscore) command is gone")


class TestSizeKeyFix(unittest.TestCase):
    """Bug 2: size_bytes was 0 because code looked for 'size' not 'size_bytes'."""

    def setUp(self):
        from pa_cli import fetch_batch as fb
        self.fb = fb

    def test_size_key_is_size_bytes(self):
        """_fetch_one_entry should call r.get('size_bytes', 0), NOT r.get('size', 0)."""
        src = inspect.getsource(self.fb._fetch_one_entry)
        # Should be 0 instances of the old key
        self.assertNotIn("r.get('size', 0)", src,
                         "Old size key 'size' should be removed (was wrong)")
        # Should be 2 instances of the new key (DOI path + title path)
        count = src.count("r.get('size_bytes', 0)")
        self.assertEqual(count, 2,
                         f"Expected 2 'size_bytes' reads (DOI + title fallback), got {count}")
        print(f"  [PASS] size key is 'size_bytes' ({count} occurrences)")

    def test_skip_existing_uses_file_stat(self):
        """Skip-existing path should read file size from disk (already correct)."""
        src = inspect.getsource(self.fb._fetch_one_entry)
        self.assertIn("out_path.stat().st_size", src,
                      "Skip-existing should use os.stat to get file size")
        print("  [PASS] skip-existing reads file size from disk")


class TestSkipCounterFix(unittest.TestCase):
    """Bug 3: --skip-existing counted as n_success, not n_skipped."""

    def setUp(self):
        from pa_cli import fetch_batch as fb
        self.fb = fb

    def test_skip_existing_checked_before_n_success(self):
        """The run_fetch_batch loop should check 'skipped-existing' BEFORE incrementing n_success."""
        src = inspect.getsource(self.fb.run_fetch_batch)
        # Find the order: 'skipped-existing' check should come before n_success
        skip_check_idx = src.find("result.error == 'skipped-existing'")
        n_success_idx = src.find("summary.n_success += 1")
        n_skipped_idx = src.find("summary.n_skipped += 1")
        self.assertGreater(skip_check_idx, 0, "Should check skipped-existing")
        self.assertGreater(n_success_idx, 0, "Should increment n_success")
        self.assertGreater(n_skipped_idx, 0, "Should increment n_skipped")
        # Order: skip_check should be before n_success
        self.assertLess(skip_check_idx, n_success_idx,
                       "skipped-existing check must come BEFORE n_success")
        print(f"  [PASS] skip counter checked before n_success (idx {skip_check_idx} < {n_success_idx})")

    def test_summary_has_n_skipped_field(self):
        """FetchSummary should have a n_skipped field initialized to 0."""
        summary = self.fb.FetchSummary()
        self.assertEqual(summary.n_skipped, 0)
        self.assertIn('n_skipped', summary.to_dict())
        print("  [PASS] FetchSummary.n_skipped exists and defaults to 0")


class TestCleanXmlOption(unittest.TestCase):
    """Bug 4: --clean-xml should remove .xml after successful PDF generation."""

    def setUp(self):
        from pa_cli import fetch_batch as fb
        self.fb = fb

    def test_run_fetch_batch_has_clean_xml_param(self):
        sig = inspect.signature(self.fb.run_fetch_batch)
        self.assertIn('clean_xml', sig.parameters)
        self.assertEqual(sig.parameters['clean_xml'].default, False,
                         "clean_xml should default to False (backward compat)")
        print("  [PASS] run_fetch_batch has clean_xml=False parameter")

    def test_xml_cleanup_logic_present(self):
        """The run_fetch_batch loop should have XML cleanup logic when clean_xml=True."""
        src = inspect.getsource(self.fb.run_fetch_batch)
        self.assertIn("xml_path.unlink()", src,
                      "Should have xml_path.unlink() cleanup call")
        # Should be guarded by clean_xml check
        self.assertIn("if clean_xml", src,
                      "Cleanup should be guarded by 'if clean_xml'")
        print("  [PASS] XML cleanup logic present (xml_path.unlink() guarded by 'if clean_xml')")

    def test_cli_fetch_batch_passes_clean_xml(self):
        """The CLI handler should pass clean_xml to run_fetch_batch."""
        from pa_cli import cli
        src = inspect.getsource(cli.fetch_batch)
        # Should pass clean_xml=clean_xml
        self.assertIn("clean_xml=clean_xml", src,
                      "fetch_batch CLI should pass clean_xml to run_fetch_batch")
        print("  [PASS] CLI fetch_batch passes clean_xml to run_fetch_batch")


if __name__ == "__main__":
    import logging
    logging.disable(logging.CRITICAL)
    print("=" * 60)
    print("v3.9.26.0 fetch_batch regression tests (4 bug fixes)")
    print("=" * 60)
    unittest.main(verbosity=2)
