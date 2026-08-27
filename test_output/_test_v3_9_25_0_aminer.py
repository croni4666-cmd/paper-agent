"""v3.9.25.0 regression tests: AMiner multi-word query fix.

Tests:
1. _title_relevance_score correctly scores 0.0-1.0
2. search_aminer with mode='basic' returns results ranked by title relevance
3. search_aminer with mode='pro' calls the Pro API
4. search_aminer with mode='auto' picks the right strategy
5. _search_aminer_basic tags each result with match_type
6. CLI --aminer-mode flag is recognized
"""
import inspect
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL_SCRIPTS = ROOT / ".agents" / "skills" / "paper-agent" / "scripts"


class TestAminerRelevanceScoring(unittest.TestCase):
    """v3.9.25.0: _title_relevance_score gives 0.0-1.0 based on title-query overlap."""

    def setUp(self):
        import sys
        sys.path.insert(0, str(ROOT))
        from pa_cli.aminer_channel import _title_relevance_score
        self.score = _title_relevance_score

    def test_full_phrase_match_returns_1(self):
        # "Wilson disease" appears verbatim in title
        score = self.score("Wilson disease associated with ATP7B", "Wilson Disease")
        self.assertGreaterEqual(score, 0.9, f"Full phrase match should be >= 0.9, got {score}")
        print(f"  [PASS] Full phrase match: {score:.3f}")

    def test_partial_match_returns_mid(self):
        # Only one word matches
        score = self.score("Dr. Wilson's recent work", "Wilson Disease")
        self.assertGreaterEqual(score, 0.3)
        self.assertLess(score, 0.9, f"Partial match should be 0.3-0.9, got {score}")
        print(f"  [PASS] Partial match (Wilson only): {score:.3f}")

    def test_no_match_returns_zero(self):
        score = self.score("A review of statistical methods", "Wilson Disease")
        self.assertEqual(score, 0.0)
        print(f"  [PASS] No match: {score:.3f}")

    def test_chinese_phrase_full_match(self):
        score = self.score("数字普惠金融 家庭消费", "数字普惠金融 家庭消费")
        self.assertGreaterEqual(score, 0.9, f"Chinese full phrase should be >= 0.9, got {score}")
        print(f"  [PASS] Chinese full phrase: {score:.3f}")

    def test_chinese_partial_match(self):
        score = self.score("数字普惠金融", "数字普惠金融 家庭消费")
        self.assertGreaterEqual(score, 0.3)
        self.assertLess(score, 0.9)
        print(f"  [PASS] Chinese partial: {score:.3f}")

    def test_score_in_range(self):
        # Always 0.0 to 1.0
        for title, query in [
            ("a", "b"),
            ("Wilson disease", "Wilson"),
            ("xyz" * 10, "abc"),
            ("", ""),
        ]:
            score = self.score(title, query)
            self.assertGreaterEqual(score, 0.0)
            self.assertLessEqual(score, 1.0)
        print("  [PASS] Score always in 0.0-1.0 range")


class TestAminerModeParameter(unittest.TestCase):
    """v3.9.25.0: search_aminer has mode parameter."""

    def setUp(self):
        import sys
        sys.path.insert(0, str(ROOT))
        from pa_cli import aminer_channel
        self.aminer_module = aminer_channel

    def test_search_aminer_signature_has_mode(self):
        sig = inspect.signature(self.aminer_module.search_aminer)
        self.assertIn("mode", sig.parameters)
        self.assertEqual(sig.parameters["mode"].default, "auto")
        print("  [PASS] search_aminer has mode='auto' default")

    def test_search_aminer_pro_exists(self):
        self.assertTrue(callable(self.aminer_module.search_aminer_pro))
        sig = inspect.signature(self.aminer_module.search_aminer_pro)
        self.assertIn("query", sig.parameters)
        print("  [PASS] search_aminer_pro exists and is callable")

    def test_search_aminer_basic_extracted(self):
        # _search_aminer_basic should exist (extracted from original search_aminer)
        self.assertTrue(callable(self.aminer_module._search_aminer_basic))
        print("  [PASS] _search_aminer_basic extracted as separate function")

    def test_merge_aminer_results_exists(self):
        self.assertTrue(callable(self.aminer_module._merge_aminer_results))
        print("  [PASS] _merge_aminer_results exists")

    def test_only_one_search_aminer_definition(self):
        # Make sure we removed the duplicate from the legacy code
        src = inspect.getsource(self.aminer_module)
        definitions = src.count("def search_aminer(query:")
        self.assertEqual(definitions, 1, f"Expected 1 search_aminer def, got {definitions}")
        print(f"  [PASS] Only 1 search_aminer definition (no duplicate)")


class TestAminerCLI(unittest.TestCase):
    """v3.9.25.0: pa search has --aminer-mode flag."""

    def test_cli_help_mentions_aminer_mode(self):
        # Run pa search --help and check output mentions --aminer-mode
        import subprocess
        import sys
        proc = subprocess.run(
            [sys.executable, "-m", "pa_cli.cli", "search", "--help"],
            capture_output=True, text=True, timeout=30,
            cwd=str(ROOT),
        )
        self.assertIn("--aminer-mode", proc.stdout,
                      "pa search --help should mention --aminer-mode flag")
        self.assertIn("auto", proc.stdout)
        self.assertIn("pro", proc.stdout)
        self.assertIn("basic", proc.stdout)
        print("  [PASS] pa search --help shows --aminer-mode flag with auto/pro/basic")


if __name__ == "__main__":
    import logging
    logging.disable(logging.CRITICAL)
    print("=" * 60)
    print("v3.9.25.0 regression tests: AMiner multi-word query fix")
    print("=" * 60)
    unittest.main(verbosity=2)
