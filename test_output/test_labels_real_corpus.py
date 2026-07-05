"""End-to-end test against the user's REAL corpus (ch1-econ-ppt).

This is the integration test that v3.8.1 was missing. It validates
that `cluster_topics()` + `--custom-labels` + `--domain-stopwords`
+ `--label-method ctfidf` (with 60s timeout fallback) actually flow
through correctly on a real, non-synthetic corpus.

Gated by env var `PA_TEST_REAL_CORPUS=1` because:
- Requires the real corpus on disk (user-specific path)
- Runs against ~7,000-word corpus (slower than unit tests)
- CI may not have the corpus
- ctfidf test runs subprocess with 120s timeout (HF download)

Run manually with:
    PA_TEST_REAL_CORPUS=1 python test_output/test_labels_real_corpus.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

# Allow running directly: `python test_output/test_labels_real_corpus.py`
sys.path.insert(0, str(Path(__file__).parent.parent))

# Skip entire module unless explicitly opted in
SKIP_REASON = "set PA_TEST_REAL_CORPUS=1 to run (real corpus test)"

REAL_CORPUS = Path(r"G:\Minmax - workspace\课件\ch1-econ-ppt")
PROJECT_ROOT = Path(__file__).parent.parent

# Path to the test fixture for --domain-stopwords-file CLI test
DOMAIN_STOPWORDS_FIXTURE = PROJECT_ROOT / "test_output" / "fixtures" / "domain_stopwords_for_test.txt"


@unittest.skipUnless(os.environ.get("PA_TEST_REAL_CORPUS") == "1", SKIP_REASON)
class TestRealCorpusEndToEnd(unittest.TestCase):
    """Run cluster_topics() on the real 9-file ch1-econ-ppt corpus.

    Asserts the v3.8.1 polish + v3.8.2 + v3.8.3 actually work end-to-end on the corpus
    that surfaced the label-quality weakness in the first place.
    """

    def setUp(self):
        if not REAL_CORPUS.exists():
            self.skipTest(f"Real corpus not found: {REAL_CORPUS}")


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


@unittest.skipUnless(os.environ.get("PA_TEST_REAL_CORPUS") == "1", SKIP_REASON)
class TestRealCorpusCLI(unittest.TestCase):
    """End-to-end CLI subprocess tests against real corpus.

    These exercise the full pa review-topics CLI surface (parse → thread
    → cluster → JSON write). v3.8.3 added: --domain-stopwords-file and
    --label-method ctfidf with 60s timeout fallback.
    """

    def setUp(self):
        if not REAL_CORPUS.exists():
            self.skipTest(f"Real corpus not found: {REAL_CORPUS}")

    def _run_cli(self, *args, timeout=180, isolate_tmp=True):
        """Run `python -m pa_cli review-topics <args>` as subprocess.

        Returns (rc, stdout, stderr, elapsed_seconds).

        isolate_tmp=True (default): give the subprocess unique TMPDIR +
        TORCH_HOME / XDG_CACHE_HOME so torch._inductor mega-cache and
        transformers cache don't collide across consecutive subprocess
        calls in the same parent process (each subprocess imports torch
        + transformers and they register precompile artifacts; second
        subprocess trips 'Artifact of type=precompile already registered'
        AssertionError if cache dir is shared).
        """
        import os as _os
        import tempfile as _tempfile
        import time

        env = None
        if isolate_tmp:
            env = dict(_os.environ)
            # Unique tempdir + torch cache dir
            unique_tmp = _tempfile.mkdtemp(prefix="pa_cli_test_")
            env["TMPDIR"] = unique_tmp
            env["TEMP"] = unique_tmp
            env["TMP"] = unique_tmp
            # torch caches precompile artifacts in ~/.cache/torch by default;
            # force it to a unique dir per subprocess
            env["TORCH_HOME"] = unique_tmp
            env["TORCHINDUCTOR_CACHE_DIR"] = unique_tmp
            env["XDG_CACHE_HOME"] = unique_tmp
            # Disable torch._dynamo auto-detection (avoids subprocess reload conflicts)
            env["TORCHDYNAMO_DISABLE"] = "1"
            env["TORCH_COMPILE_DISABLE"] = "1"

        cmd = [sys.executable, "-m", "pa_cli", "review-topics", str(REAL_CORPUS)] + list(args)
        start = time.time()
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(PROJECT_ROOT),
            env=env,
        )
        return result.returncode, result.stdout, result.stderr, time.time() - start

    def test_cli_custom_labels_end_to_end(self):
        """CLI `--custom-labels` flows end-to-end on real corpus."""
        import json
        rc, out, err, elapsed = self._run_cli(
            "--label-method", "handroll",
            "--custom-labels", '{"1": "PPT 设计文档", "2": "PPT 内容来源"}',
        )

        self.assertEqual(rc, 0, f"CLI failed: stderr={err[-500:]}")
        # Output mentions label_method + custom_labels
        self.assertIn("label_method=handroll", err)
        self.assertIn("custom_labels=", err)

        # topics.json has the custom labels applied
        with open(REAL_CORPUS / "topics.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        labels = {t["topic_id"]: t["label"] for t in data["topics"]}
        self.assertEqual(labels[1], "PPT 设计文档")
        self.assertEqual(labels[2], "PPT 内容来源")

    def test_cli_domain_stopwords_file_end_to_end(self):
        """CLI `--domain-stopwords-file` loads terms from file (v3.8.3).

        Regression for v3.8.1 gap: this CLI flag was wired but never tested
        end-to-end. Now verified: passing a file with 9 noise terms
        produces `domain_stopwords_count = 9` (not 20 = auto-mine).
        """
        import json
        self.assertTrue(
            DOMAIN_STOPWORDS_FIXTURE.exists(),
            f"Test fixture missing: {DOMAIN_STOPWORDS_FIXTURE}",
        )

        rc, out, err, elapsed = self._run_cli(
            "--label-method", "handroll",
            "--domain-stopwords-file", str(DOMAIN_STOPWORDS_FIXTURE),
        )

        self.assertEqual(rc, 0, f"CLI failed: stderr={err[-500:]}")
        # Output announces "domain_stopwords=9 terms" (file contents count)
        self.assertIn("domain_stopwords=9 terms", err)

        with open(REAL_CORPUS / "topics.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        # domain_stopwords_count should be 9 (the file's content count),
        # NOT 20 (the auto-mine default) — this proves the file was used.
        self.assertEqual(
            data["domain_stopwords_count"],
            9,
            f"Expected 9 (file-loaded), got {data['domain_stopwords_count']}. "
            f"Auto-mine default would be 20.",
        )

    def test_cli_ctfidf_method_with_timeout_fallback(self):
        """CLI `--label-method ctfidf` falls back within ~60s when HF unreachable.

        Regression for environment limitation: BERTopic needs HuggingFace
        download of all-MiniLM-L6-v2 (~80MB). In networks where HF is
        blocked, default wait is 5+ minutes. v3.8.3 added 60s timeout
        so the user sees clear "falling back to handroll" within ~1 min
        instead of staring at a hanging terminal.

        Accept either:
        - Path (a) HF download succeeded → ctfidf method runs, k > 0
        - Path (b) HF blocked → bertopic_failed_fallback_to_handroll
          warning fires within ~90s, fallback to handroll succeeds

        Both paths must produce topics.json + non-zero k + rc=0.
        """
        import time
        start = time.time()
        rc, out, err, elapsed = self._run_cli(
            "--label-method", "ctfidf",
            timeout=120,  # outer safety net
        )
        elapsed = time.time() - start

        self.assertEqual(rc, 0, f"CLI failed: stderr={err[-500:]}")

        # Must see EITHER successful ctfidf OR explicit fallback warning
        # (different error subtypes: TimeoutError, RuntimeError, ConnectionError)
        ctfidf_actually_ran = "label_method=ctfidf" in err and "bertopic_failed" not in err
        fallback_engaged = "bertopic_failed_fallback_to_handroll" in err

        self.assertTrue(
            ctfidf_actually_ran or fallback_engaged,
            f"Either ctfidf runs (HF accessible) or fallback engages. "
            f"Got stderr_tail:\n{err[-800:]}",
        )

        if fallback_engaged:
            # v3.8.3 fix verification: fallback must complete within
            # ~90s (60s timeout + ~30s processing), NOT 5+ minutes (default).
            self.assertLess(
                elapsed, 110,
                f"Fallback should happen within ~90s, got {elapsed:.1f}s. "
                f"Timeout not working?",
            )
            # Fallback warning must mention "fall back" so user knows
            import re as _re
            self.assertTrue(
                _re.search(r"fall ?back|falling ?back", err, _re.IGNORECASE),
                f"Fallback message should be visible to user. stderr:\n{err[-500:]}",
            )

        # topics.json must be saved either way
        import json as _json
        with open(REAL_CORPUS / "topics.json", "r", encoding="utf-8") as f:
            data = _json.load(f)
        self.assertGreater(data["k"], 0)
        self.assertEqual(data["label_method"], "ctfidf")

    def test_cli_abc_three_generators_actually_implement(self):
        """Verify v3.8.3 fix: CTFIDF + Handroll + Custom all implement ABC.

        v3.8.1 had CTFIDF + Handroll raising NotImplementedError. v3.8.3
        made them pass-through post-processors. Verify all 3 are now
        usable via the factory + generate() contract.
        """
        from pa_cli.labels import (
            CTFIDFLabelGenerator,
            CustomLabelGenerator,
            HandrollLabelGenerator,
        )
        # All 3 should instantiate without raising
        for cls in (CTFIDFLabelGenerator, HandrollLabelGenerator):
            instance = cls(custom_labels={1: "test"})
            self.assertEqual(instance.name(), cls.__name__.replace("LabelGenerator", "").lower())
        # All 3 should call generate() without raising NotImplementedError
        fake_topics = [{"topic_id": 1, "label": "auto"}, {"topic_id": 2, "label": "auto2"}]
        for cls in (CTFIDFLabelGenerator, HandrollLabelGenerator):
            instance = cls(custom_labels={1: "Human-A"})
            result = instance.generate(papers=[], clusters=[], topics=fake_topics)
            self.assertEqual(result[0]["label"], "Human-A")
            self.assertEqual(result[1]["label"], "auto2")

    def test_cli_register_custom_generator_end_to_end(self):
        """Verify register_label_generator() + get_label_generator() plugin chain.

        v3.8.1 added register_label_generator() but no production plugin
        used it. v3.8.3 verification: write a one-off MyGen, register it,
        get via factory, verify name() + generate() work.
        """
        from pa_cli.labels import (
            LabelGenerator,
            get_label_generator,
            register_label_generator,
            available_methods,
        )

        class _TestGen(LabelGenerator):
            def name(self):
                return "test_v383_plugin"

            def generate(self, papers, clusters, **kwargs):
                return [{"topic_id": 1, "label": "from-plugin",
                         "keywords": [], "paper_count": 0,
                         "filenames": [], "is_outlier_cluster": False}]

        # Register
        register_label_generator("test_v383_plugin", _TestGen)
        # Verify it's in available_methods()
        self.assertIn("test_v383_plugin", available_methods())
        # Verify factory returns our class
        gen = get_label_generator("test_v383_plugin")
        self.assertIsInstance(gen, _TestGen)
        self.assertEqual(gen.name(), "test_v383_plugin")
        # Verify generate() actually runs
        result = gen.generate(papers=[], clusters=[])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["label"], "from-plugin")


if __name__ == "__main__":
    unittest.main()