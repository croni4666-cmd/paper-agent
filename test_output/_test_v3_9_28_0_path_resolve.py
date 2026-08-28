"""v3.9.28.0 regression test: Skill wrapper resolves relative paths.

User reported: when the wrapper calls subprocess with cwd=pa_root,
any relative path (e.g., 'refs.bib') was interpreted against pa_root
(backend repo dir) instead of the user's invocation CWD. The fix is
to call Path(...).resolve() on the user-provided paths before
constructing the cmd list.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class TestPathResolution(unittest.TestCase):
    """v3.9.28.0: Skill wrapper should resolve user paths to absolute before subprocess."""

    def setUp(self):
        self.wrapper_path = ROOT / ".agents" / "skills" / "paper-agent" / "scripts" / "fetch_batch.py"
        self.content = self.wrapper_path.read_text(encoding="utf-8")

    def test_bibtex_path_resolved(self):
        """args.bibtex should be resolved to absolute via Path(...).resolve()."""
        # Should have: args.bibtex = str(Path(args.bibtex).resolve())
        self.assertRegex(
            self.content,
            r'args\.bibtex\s*=\s*str\(Path\(args\.bibtex\)\.resolve\(\)\)',
            "args.bibtex should be resolved to absolute before subprocess"
        )
        print("  [PASS] args.bibtex is resolved to absolute path")

    def test_output_dir_path_resolved(self):
        """args.output_dir should be resolved to absolute."""
        self.assertRegex(
            self.content,
            r'args\.output_dir\s*=\s*str\(Path\(args\.output_dir\)\.resolve\(\)\)',
            "args.output_dir should be resolved to absolute before subprocess"
        )
        print("  [PASS] args.output_dir is resolved to absolute path")

    def test_report_path_resolved(self):
        """args.report should be resolved if present."""
        self.assertRegex(
            self.content,
            r'args\.report\s*=\s*str\(Path\(args\.report\)\.resolve\(\)\)',
            "args.report should be resolved to absolute"
        )
        print("  [PASS] args.report is resolved to absolute path")

    def test_summary_json_path_resolved(self):
        """args.summary_json should be resolved if present."""
        self.assertRegex(
            self.content,
            r'args\.summary_json\s*=\s*str\(Path\(args\.summary_json\)\.resolve\(\)\)',
            "args.summary_json should be resolved to absolute"
        )
        print("  [PASS] args.summary_json is resolved to absolute path")

    def test_resolution_happens_before_subprocess(self):
        """Path resolution must happen BEFORE the subprocess.run call (with cwd=pa_root)."""
        # Find the position of the resolve calls and the subprocess.run
        resolve_pos = self.content.find("args.bibtex = str(Path(args.bibtex).resolve())")
        subprocess_pos = self.content.find("subprocess.run(")
        self.assertGreater(resolve_pos, 0, "Should have args.bibtex resolve")
        self.assertGreater(subprocess_pos, 0, "Should have subprocess.run call")
        self.assertLess(
            resolve_pos, subprocess_pos,
            "Path resolution must happen BEFORE subprocess.run (else cwd change breaks it)"
        )
        print("  [PASS] Path resolution happens before subprocess.run (line order correct)")

    def test_cwd_still_pa_root(self):
        """The subprocess.run should still use cwd=pa_root (so pa_cli imports work)."""
        self.assertIn("cwd=str(pa_root)", self.content,
                      "subprocess should still use cwd=pa_root (for pa_cli import)")
        print("  [PASS] subprocess.cwd is still pa_root (for pa_cli import)")


if __name__ == "__main__":
    import logging
    logging.disable(logging.CRITICAL)
    print("=" * 60)
    print("v3.9.28.0 regression test: relative path resolution")
    print("=" * 60)
    unittest.main(verbosity=2)
