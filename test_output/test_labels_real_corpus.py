"""End-to-end test against the user's REAL corpus (ch1-econ-ppt).

This is the integration test that v3.8.1 was missing. It validates
that `cluster_topics()` + `--custom-labels` + `--domain-stopwords`
actually flow through correctly on a real, non-synthetic corpus.

Gated by env var `PA_TEST_REAL_CORPUS=1` because:
- Requires the real corpus on disk (user-specific path)
- Runs against ~7,000-word corpus (slower than unit tests)
- CI may not have the corpus

Run manually with:
    PA_TEST_REAL_CORPUS=1 python test_output/test_labels_real_corpus.py
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

# Allow running directly: `python test_output/test_labels_real_corpus.py`
sys.path.insert(0, str(Path(__file__).parent.parent))

# Skip entire module unless explicitly opted in
SKIP_REASON = "set PA_TEST_REAL_CORPUS=1 to run (real corpus test)"

REAL_CORPUS = Path(r"G:\Minmax - workspace\课件\ch1-econ-ppt")


@unittest.skipUnless(os.environ.get("PA_TEST_REAL_CORPUS") == "1", SKIP_REASON)
class TestRealCorpusEndToEnd(unittest.TestCase):
    """Run cluster_topics() on the real 9-file ch1-econ-ppt corpus.

    Asserts the v3.8.1 polish actually works end-to-end on the corpus
    that surfaced the label-quality weakness in the first place.
    """

    def setUp(self):
        if not REAL_CORPUS.exists():
            self.skipTest(f"Real corpus not found: {REAL_CORPUS}")

    def test_custom_labels_override_on_real_corpus(self):
        """cluster_topics() applies user-supplied labels to real corpus."""
        from pa_cli.topics import cluster_topics

        result = cluster_topics(
            corpus_dir=REAL_CORPUS,
            output_path=REAL_CORPUS / "topics.json",
            label_method="handroll",
            custom_labels={1: "PPT 设计文档", 2: "PPT 内容来源"},
        )

        # Schema fields populated
        self.assertEqual(result["label_method"], "handroll")
        self.assertEqual(result["k"], 2)
        self.assertEqual(
            result["custom_labels"],
            {"1": "PPT 设计文档", "2": "PPT 内容来源"},
        )

        # Both custom labels applied to topic list
        labels = {t["topic_id"]: t["label"] for t in result["topics"]}
        self.assertEqual(labels[1], "PPT 设计文档")
        self.assertEqual(labels[2], "PPT 内容来源")

        # custom_labels_applied warning fired
        self.assertTrue(
            any("custom_labels_applied" in w for w in result["warnings"]),
            f"Expected custom_labels_applied warning in {result['warnings']}",
        )

    def test_domain_stopwords_auto_mines_real_corpus(self):
        """extract_domain_stopwords finds ≥3 noise terms in real corpus.

        Regression for v3.8.1 bug: heuristics were too strict, returned empty list.
        After v3.8.2 fix (common-English whitelist + length 4-12 lowercase path),
        should pick up iphone, skill, mermaid, chip, etc.
        """
        from pa_cli.labels.domain_stopwords import extract_domain_stopwords
        from pa_cli.review import build_corpus_index, extract_text

        papers = build_corpus_index(REAL_CORPUS, word_count_min=10)
        for p in papers:
            p["text"] = extract_text(Path(p["path"])).get("text", "") or ""

        words = extract_domain_stopwords(papers, top_n=20)

        # Before fix: returned 0 noise terms (empty list)
        # After fix: should return ≥3 terms including product/tool names
        self.assertGreaterEqual(
            len(words),
            3,
            f"Expected ≥3 noise terms from real corpus, got {len(words)}: {words}",
        )

        # Spot-check: at least one of these expected noise terms should appear
        expected_noise_signals = {"iphone", "skill", "pptxgenjs", "mermaid"}
        hits = expected_noise_signals & set(words)
        self.assertGreaterEqual(
            len(hits),
            1,
            f"Expected ≥1 of {expected_noise_signals} in extracted words, got {words}",
        )

    def test_domain_stopwords_via_cli_flag_flows_through(self):
        """`--custom-labels` + auto-mined domain stopwords both apply in cluster_topics()."""
        from pa_cli.topics import cluster_topics

        result = cluster_topics(
            corpus_dir=REAL_CORPUS,
            output_path=REAL_CORPUS / "topics.json",
            label_method="handroll",
            custom_labels={1: "Design", 2: "Source"},
            # domain_stopwords=None → triggers auto-mine
        )

        # auto_mined warning present (whether or not it found anything,
        # the auto-mine code path executed)
        self.assertTrue(
            any("auto_mined" in w or "n_papers=" in w for w in result["warnings"]),
            f"Expected auto-mined warning in {result['warnings']}",
        )

        # After v3.8.2 fix, domain_stopwords_count should be ≥ 3 on this corpus
        self.assertGreaterEqual(
            result["domain_stopwords_count"],
            3,
            f"Expected ≥3 auto-mined domain stopwords on real corpus, "
            f"got {result['domain_stopwords_count']}",
        )

    def test_topics_json_schema_on_disk(self):
        """topics.json written to disk has v3.8.1 schema fields."""
        from pa_cli.topics import cluster_topics

        output_path = REAL_CORPUS / "topics.json"
        cluster_topics(
            corpus_dir=REAL_CORPUS,
            output_path=output_path,
            label_method="handroll",
            custom_labels={1: "X", 2: "Y"},
        )

        import json as _json
        with open(output_path, "r", encoding="utf-8") as f:
            data = _json.load(f)

        # v3.8.1 added 3 schema fields
        self.assertIn("label_method", data)
        self.assertIn("custom_labels", data)
        self.assertIn("domain_stopwords_count", data)
        self.assertEqual(data["label_method"], "handroll")
        self.assertEqual(data["custom_labels"], {"1": "X", "2": "Y"})
        self.assertGreaterEqual(data["domain_stopwords_count"], 3)


if __name__ == "__main__":
    unittest.main()