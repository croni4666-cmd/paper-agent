"""Offline contract tests for evidence-traceable review artifacts."""
import tempfile
from pathlib import Path
import json
import unittest

from pa_cli.review import (
    build_evidence_manifest,
    synthesize,
    validate_review_evidence,
    write_review_artifacts,
)


class ReviewEvidenceTests(unittest.TestCase):
    def test_manifest_ids_are_stable_and_resolve_review_citations(self):
        with tempfile.TemporaryDirectory() as temporary:
            corpus = Path(temporary)
            (corpus / "10.1000%2Falpha.md").write_text(
                "# Alpha paper\n\n" + "evidence " * 1100,
                encoding="utf-8",
            )
            (corpus / "metadata-only.md").write_text("# Metadata paper\n\nshort note", encoding="utf-8")

            manifest = build_evidence_manifest(corpus)
            review = synthesize(corpus)
            report = validate_review_evidence(review, manifest)

            self.assertEqual(len(manifest["entries"]), 2)
            self.assertEqual(
                [entry["evidence_id"] for entry in manifest["entries"]],
                [entry["evidence_id"] for entry in build_evidence_manifest(corpus)["entries"]],
            )
            self.assertEqual({entry["evidence_basis"] for entry in manifest["entries"]},
                             {"full_text", "abstract"})
            self.assertTrue(report["valid"])
            self.assertEqual(report["unresolved_ids"], [])
            self.assertEqual(report["unused_input_ids"], [])

    def test_validation_rejects_an_unknown_evidence_id(self):
        manifest = {"entries": [{"evidence_id": "E-000000000001", "evidence_basis": "full_text"}]}
        report = validate_review_evidence("Claim [E-FFFFFFFFFFFF]", manifest)
        self.assertFalse(report["valid"])
        self.assertEqual(report["unresolved_ids"], ["E-FFFFFFFFFFFF"])

    def test_writes_manifest_and_validation_sidecars(self):
        with tempfile.TemporaryDirectory() as temporary:
            corpus = Path(temporary) / "corpus"
            corpus.mkdir()
            (corpus / "paper.md").write_text("# Paper\n\n" + "evidence " * 1100, encoding="utf-8")
            output = Path(temporary) / "review.md"
            manifest = Path(temporary) / "review.manifest.json"
            report = Path(temporary) / "review.validation.json"

            result = write_review_artifacts(corpus, output, manifest, report)

            self.assertTrue(result["valid"])
            self.assertTrue(manifest.is_file())
            self.assertTrue(json.loads(report.read_text(encoding="utf-8"))["valid"])


if __name__ == "__main__":
    unittest.main()
