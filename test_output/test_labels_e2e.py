"""End-to-end test for pa_cli.labels subpackage.

Tests the pluggable label generator interface and supporting utilities:
- LabelGenerator ABC + register_label_generator factory
- CustomLabelGenerator: user-supplied label override
- Domain stopwords: auto-extraction heuristics + file load/save roundtrip
- Integration: cluster_topics() with --label-method + --custom-labels +
  --domain-stopwords-file flowing end-to-end

These tests run on a synthetic mini-corpus (3-5 markdown files) to avoid
network/HF dependencies. Real-corpus verification is a separate manual step
(see _real_topics_*.py in the same dir for the 9-file ch1-econ-ppt run).
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

# Allow running directly: `python test_output/test_labels_e2e.py`
sys.path.insert(0, str(Path(__file__).parent.parent))

from pa_cli.labels import (
    CustomLabelGenerator,
    LabelGenerator,
    available_methods,
    extract_domain_stopwords,
    get_label_generator,
    load_domain_stopwords_file,
    register_label_generator,
    save_domain_stopwords,
)


class TestLabelGeneratorABC(unittest.TestCase):
    """LabelGenerator ABC and factory registration."""

    def test_abc_cannot_instantiate_directly(self):
        """Abstract base class should refuse direct instantiation."""
        with self.assertRaises(TypeError):
            LabelGenerator()  # type: ignore

    def test_available_methods_includes_builtins(self):
        """Built-in methods should be registered."""
        methods = available_methods()
        self.assertIn("ctfidf", methods)
        self.assertIn("handroll", methods)
        self.assertIn("custom", methods)

    def test_get_label_generator_dispatch(self):
        """Factory should return the right class per method name."""
        # CustomLabelGenerator requires custom_labels kwarg
        gen = get_label_generator("custom", custom_labels={1: "test"})
        self.assertIsInstance(gen, CustomLabelGenerator)
        self.assertEqual(gen.name(), "custom")

    def test_get_label_generator_auto_aliases_to_ctfidf(self):
        """`auto` should resolve to ctfidf."""
        gen = get_label_generator("auto")
        self.assertEqual(gen.name(), "ctfidf")

    def test_get_label_generator_unknown_method_raises(self):
        """Unknown method name should raise ValueError with helpful message."""
        with self.assertRaises(ValueError) as ctx:
            get_label_generator("nonexistent_xyz")
        self.assertIn("nonexistent_xyz", str(ctx.exception))
        self.assertIn("Available", str(ctx.exception))

    def test_register_custom_generator(self):
        """register_label_generator should add a new method to the registry."""
        class MyGen(LabelGenerator):
            def name(self) -> str:
                return "test_mygen"
            def generate(self, papers, clusters, **kwargs):
                return []

        register_label_generator("test_mygen", MyGen)
        self.assertIn("test_mygen", available_methods())
        gen = get_label_generator("test_mygen")
        self.assertIsInstance(gen, MyGen)

    def test_register_rejects_non_subclass(self):
        """register_label_generator should refuse non-LabelGenerator classes."""
        class NotAGenerator:
            pass

        with self.assertRaises(TypeError):
            register_label_generator("bogus", NotAGenerator)


class TestCustomLabelGenerator(unittest.TestCase):
    """CustomLabelGenerator overrides topic labels post-clustering."""

    def _make_topics(self):
        """Synthesize a topics list mimicking cluster_topics() output."""
        return [
            {
                "topic_id": 1,
                "label": "auto_label_1",
                "keywords": ["kw1", "kw2"],
                "paper_count": 5,
                "filenames": ["a.md", "b.md"],
            },
            {
                "topic_id": 2,
                "label": "auto_label_2",
                "keywords": ["kw3", "kw4"],
                "paper_count": 3,
                "filenames": ["c.md"],
            },
        ]

    def test_overrides_specified_topics(self):
        """custom_labels dict should override matching topic_ids' labels."""
        gen = CustomLabelGenerator(custom_labels={1: "Human-readable topic 1"})
        result = gen.generate(papers=[], clusters=[], topics=self._make_topics())
        self.assertEqual(result[0]["label"], "Human-readable topic 1")
        # Unspecified topic keeps auto label
        self.assertEqual(result[1]["label"], "auto_label_2")

    def test_overrides_multiple_topics(self):
        """Multiple topic_ids can be overridden at once."""
        gen = CustomLabelGenerator(custom_labels={
            1: "Topic A",
            2: "Topic B",
        })
        result = gen.generate(papers=[], clusters=[], topics=self._make_topics())
        self.assertEqual(result[0]["label"], "Topic A")
        self.assertEqual(result[1]["label"], "Topic B")

    def test_accepts_string_keys(self):
        """JSON-loaded dict may have string keys; should normalize to int."""
        gen = CustomLabelGenerator(custom_labels={"1": "From JSON"})  # type: ignore
        result = gen.generate(papers=[], clusters=[], topics=self._make_topics())
        self.assertEqual(result[0]["label"], "From JSON")

    def test_empty_custom_labels_raises(self):
        """Constructor should refuse empty custom_labels."""
        with self.assertRaises(ValueError):
            CustomLabelGenerator(custom_labels={})

    def test_generate_requires_topics_kwarg(self):
        """Standalone generate() should require `topics` kwarg."""
        gen = CustomLabelGenerator(custom_labels={1: "x"})
        with self.assertRaises(ValueError) as ctx:
            gen.generate(papers=[], clusters=[])
        self.assertIn("topics", str(ctx.exception))

    def test_does_not_mutate_input(self):
        """Should return new topic dicts, not mutate the input list."""
        original_topics = self._make_topics()
        snapshot = [dict(t) for t in original_topics]
        gen = CustomLabelGenerator(custom_labels={1: "Override"})
        gen.generate(papers=[], clusters=[], topics=original_topics)
        # Input should be unchanged
        for orig, snap in zip(original_topics, snapshot):
            self.assertEqual(orig, snap)


class TestDomainStopwords(unittest.TestCase):
    """extract_domain_stopwords + load/save roundtrip."""

    def _sample_corpus(self):
        return [
            {
                "filename": "design.md",
                "title": "PPT design",
                "text": "iPhone template using pptxgenjs gamma generates beautiful PPT",
            },
            {
                "filename": "content.md",
                "title": "Slide content",
                "text": "Western economics supply demand price elasticity",
            },
            {
                "filename": "export.md",
                "title": "PDF export",
                "text": "Export to jpg or png using default settings",
            },
        ]

    def test_extracts_tool_names_and_extensions(self):
        """Should pick out tool names (pptxgenjs) and file extensions (jpg)."""
        words = extract_domain_stopwords(self._sample_corpus(), top_n=20)
        # At least one of these should appear
        self.assertTrue(
            any(w in words for w in ["pptxgenjs", "jpg", "png", "iphone", "skill"]),
            f"Expected tool/ext names in {words}",
        )

    def test_keeps_real_english_words(self):
        """Real English content words (economics, supply, demand) should NOT be in stopwords."""
        words = extract_domain_stopwords(self._sample_corpus(), top_n=20)
        # These are content words, should be kept as topics
        for keep in ["economics", "supply", "demand", "price", "elasticity"]:
            self.assertNotIn(keep, words)

    def test_handles_empty_corpus(self):
        """Empty corpus should return empty list, not crash."""
        self.assertEqual(extract_domain_stopwords([], top_n=10), [])

    def test_handles_corpus_without_text(self):
        """Papers with empty text should be tolerated."""
        papers = [
            {"filename": "blank.md", "title": "", "text": ""},
            {"filename": "real.md", "title": "Real", "text": "actual content here"},
        ]
        words = extract_domain_stopwords(papers, top_n=10)
        # Should at least not crash
        self.assertIsInstance(words, list)

    def test_save_and_load_roundtrip(self):
        """save_domain_stopwords → load_domain_stopwords_file should preserve list."""
        words = ["pptxgenjs", "iphone", "skill", "jpg"]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "domain.txt"
            save_domain_stopwords(words, path)
            loaded = load_domain_stopwords_file(path)
        self.assertEqual(sorted(loaded), sorted(words))

    def test_load_skips_comments_and_blanks(self):
        """Lines starting with # should be skipped, blanks too."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "domain.txt"
            path.write_text(
                "# Comment line\n"
                "pptxgenjs\n"
                "\n"
                "  \n"
                "iphone\n"
                "# another comment\n",
                encoding="utf-8",
            )
            loaded = load_domain_stopwords_file(path)
        self.assertEqual(sorted(loaded), ["iphone", "pptxgenjs"])

    def test_load_returns_empty_for_missing_file(self):
        """Non-existent path should return empty list, not raise."""
        self.assertEqual(load_domain_stopwords_file(Path("/nonexistent/path")), [])


class TestEndToEndIntegration(unittest.TestCase):
    """Integration: cluster_topics() flows kwargs through to label generator."""

    def test_cluster_topics_with_handroll_and_custom_labels(self):
        """Full pipeline: handroll method + custom label override."""
        from pa_cli.topics import cluster_topics

        # Build a tiny synthetic corpus in temp dir (n=2, below auto-mine threshold)
        with tempfile.TemporaryDirectory() as tmp:
            corpus_dir = Path(tmp) / "corpus"
            corpus_dir.mkdir()
            (corpus_dir / "design.md").write_text(
                "# Design\niPhone template using pptxgenjs gamma to make beautiful slides",
                encoding="utf-8",
            )
            (corpus_dir / "content.md").write_text(
                "# Content\nWestern economics supply demand price elasticity theory",
                encoding="utf-8",
            )
            output_path = Path(tmp) / "topics.json"

            result = cluster_topics(
                corpus_dir=corpus_dir,
                output_path=output_path,
                label_method="handroll",
                custom_labels={1: "Design files", 2: "Content files"},
            )

        # Verify the custom labels were applied
        self.assertEqual(result["label_method"], "handroll")
        self.assertEqual(result["custom_labels"], {"1": "Design files", "2": "Content files"})
        # custom_labels_applied should appear (auto_mined_* may not for n<3)
        self.assertTrue(
            any("custom_labels_applied" in w for w in result["warnings"]),
            f"Expected custom_labels_applied warning in {result['warnings']}",
        )

        # Verify the topics list has the overridden labels
        labels = {t["topic_id"]: t["label"] for t in result["topics"]}
        # At least one of our custom labels should be present.
        # Note: with n=2, cluster_topics falls back to k=1, so only one
        # custom_label may be applied (whichever maps to the single topic_id).
        # On a real corpus (n>=5), all custom_labels get applied.
        self.assertTrue(
            any(v in labels.values() for v in ["Design files", "Content files"]),
            f"Expected at least one custom label in {labels.values()}",
        )

        # Verify topics.json schema has new fields
        self.assertIn("label_method", result)
        self.assertIn("domain_stopwords_count", result)
        self.assertIn("custom_labels", result)
        # domain_stopwords_count is 0+ (auto-mine may not extract from tiny n=2 corpus)

    def test_cluster_topics_auto_mine_runs_on_larger_corpus(self):
        """Verify auto-mine runs on n≥3 corpus and populates domain_stopwords_count."""
        from pa_cli.topics import cluster_topics

        with tempfile.TemporaryDirectory() as tmp:
            corpus_dir = Path(tmp) / "corpus"
            corpus_dir.mkdir()
            # n=5, with tool names that should trigger noise extraction
            for i, content in enumerate(
                [
                    "iPhone template pptxgenjs gamma beautiful slides",
                    "Western economics supply demand price elasticity",
                    "pptxgenjs gamma iPhone slide beautiful ppt",
                    "Western economics elasticity theory slide",
                    "iPhone gamma beautiful template pptxgenjs",
                ]
            ):
                (corpus_dir / f"doc{i}.md").write_text(content, encoding="utf-8")

            result = cluster_topics(
                corpus_dir=corpus_dir,
                output_path=Path(tmp) / "topics.json",
                label_method="handroll",
            )

        # At n=5, auto-mine should fire. pptxgenjs has camelCase pattern → should be picked.
        self.assertGreaterEqual(
            result["domain_stopwords_count"],
            1,
            f"Expected domain_stopwords_count >= 1, got {result['domain_stopwords_count']}. "
            f"warnings: {result['warnings']}",
        )

    def test_cluster_topics_writes_schema_fields(self):
        """topics.json on disk should include label_method + custom_labels."""
        from pa_cli.topics import cluster_topics

        with tempfile.TemporaryDirectory() as tmp:
            corpus_dir = Path(tmp) / "corpus"
            corpus_dir.mkdir()
            (corpus_dir / "a.md").write_text("apple banana cherry", encoding="utf-8")
            (corpus_dir / "b.md").write_text("dog elephant fox", encoding="utf-8")
            output_path = Path(tmp) / "topics.json"

            cluster_topics(
                corpus_dir=corpus_dir,
                output_path=output_path,
                label_method="handroll",
                custom_labels={1: "Custom-A", 2: "Custom-B"},
            )

            with open(output_path, "r", encoding="utf-8") as f:
                data = json.load(f)

        self.assertEqual(data["label_method"], "handroll")
        self.assertEqual(data["custom_labels"], {"1": "Custom-A", "2": "Custom-B"})
        self.assertIn("domain_stopwords_count", data)


if __name__ == "__main__":
    unittest.main()