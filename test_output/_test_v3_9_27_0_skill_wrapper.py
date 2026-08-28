"""v3.9.27.0 regression tests for Skill wrapper + size fallback.

Tests the 2 remaining user-reported issues from v3.9.26.0:

1. Skill `scripts/fetch_batch.py` was calling `python -m pa_cli.cli fetch-batch`
   which loaded the wrong (old) cli.py. User wanted `python -m pa_cli`
   (the documented package entry point). Now the wrapper uses the right entry.

2. PMC jats_pdf returns `size` (not `size_bytes`). v3.9.26.0 fix used
   `r.get('size_bytes', 0)` which returned 0. v3.9.27.0 fix uses fallback
   chain: `r.get("size_bytes") or r.get("size") or stat(file).st_size`.
"""
import inspect
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class TestSkillWrapperEntry(unittest.TestCase):
    """v3.9.27.0: Skill wrapper should use 'python -m pa_cli' not 'pa_cli.cli'."""

    def setUp(self):
        self.wrapper_path = ROOT / ".agents" / "skills" / "paper-agent" / "scripts" / "fetch_batch.py"
        self.content = self.wrapper_path.read_text(encoding="utf-8")

    def test_wrapper_uses_pa_cli_not_pa_cli_cli(self):
        """The subprocess cmd should use 'pa_cli' (package) not 'pa_cli.cli' (subpackage)."""
        # Find the cmd list construction
        self.assertIn('PYTHON, "-m", "pa_cli", "fetch-batch"', self.content,
                      "Wrapper should use 'pa_cli' (package) not 'pa_cli.cli' (subpackage)")
        # Should NOT have the old "pa_cli.cli" path
        self.assertNotIn('PYTHON, "-m", "pa_cli.cli", "fetch-batch"', self.content,
                         "Old 'pa_cli.cli' path should be removed")
        print("  [PASS] Skill wrapper uses 'python -m pa_cli' (correct entry point)")

    def test_wrapper_has_clean_xml_flag(self):
        """v3.9.27.0: wrapper should expose --clean-xml flag."""
        self.assertIn('--clean-xml', self.content,
                      "Wrapper should accept --clean-xml flag")
        # Should pass --clean-xml to pa fetch-batch
        self.assertIn('cmd.append("--clean-xml")', self.content,
                      "Wrapper should pass --clean-xml to pa fetch-batch when set")
        # Should have the action='store_true' argparse definition
        self.assertIn('"--clean-xml", action="store_true"', self.content,
                      "Wrapper should define --clean-xml as store_true action")
        print("  [PASS] Skill wrapper has --clean-xml flag (action=store_true)")

    def test_wrapper_documents_clean_xml_in_epilog(self):
        """v3.9.27.0: epilog should show clean-xml example."""
        self.assertIn('--clean-xml --report', self.content,
                      "Epilog should include --clean-xml example")
        print("  [PASS] Wrapper epilog shows --clean-xml usage example")


class TestSizeFallback(unittest.TestCase):
    """v3.9.27.0: fetch_batch.py should use size fallback chain."""

    def setUp(self):
        from pa_cli import fetch_batch as fb
        self.fb = fb
        self.src = inspect.getsource(fb._fetch_one_entry)

    def test_uses_fallback_chain(self):
        """The code should try 'size_bytes', then 'size', then stat the file."""
        # Should have the or-chain pattern
        self.assertIn('r.get("size_bytes")', self.src,
                      "Should try r.get('size_bytes') first")
        self.assertIn('r.get("size")', self.src,
                      "Should fallback to r.get('size')")
        self.assertIn('Path(', self.src,
                      "Should stat the file as final fallback")
        print("  [PASS] fetch_batch.py uses size fallback chain (size_bytes → size → stat)")

    def test_no_more_size_bytes_0_default(self):
        """The old 'r.get('size_bytes', 0)' pattern should be gone (it was wrong for PMC)."""
        self.assertNotIn("r.get('size_bytes', 0)", self.src,
                         "Old 'r.get('size_bytes', 0)' with 0 default is gone")
        print("  [PASS] Old 'r.get(size_bytes, 0)' with 0 default removed")

    def test_uses_stat_only_when_file_exists(self):
        """The stat fallback should only call stat if file exists (avoid FileNotFoundError)."""
        # Should have an existence check before .stat()
        self.assertIn('.exists()', self.src,
                      "Should check file exists before .stat() (avoid FileNotFoundError)")
        print("  [PASS] Stat fallback guarded by file existence check")


class TestFetchBatchFetchStillWorks(unittest.TestCase):
    """v3.9.27.0: confirm the size fallback doesn't break normal cases."""

    def test_skip_existing_still_uses_stat(self):
        """Skip-existing path should still use os.stat (was already correct)."""
        from pa_cli import fetch_batch as fb
        src = inspect.getsource(fb._fetch_one_entry)
        self.assertIn("out_path.stat().st_size", src)
        print("  [PASS] skip-existing path still uses file stat (no regression)")

    def test_size_key_renamed_in_skip_path(self):
        """Skip path should set size_bytes from stat (was already correct)."""
        from pa_cli import fetch_batch as fb
        src = inspect.getsource(fb._fetch_one_entry)
        # The skip-existing branch should have size_bytes from stat
        self.assertIn("result.size_bytes = out_path.stat().st_size", src)
        print("  [PASS] skip-existing sets result.size_bytes from stat")


if __name__ == "__main__":
    import logging
    logging.disable(logging.CRITICAL)
    print("=" * 60)
    print("v3.9.27.0 regression tests (Skill wrapper + size fallback)")
    print("=" * 60)
    unittest.main(verbosity=2)
