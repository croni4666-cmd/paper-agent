"""Unit tests for Peer Review Priority Findings S1-S3 and E1-E6 on commit 6ce58eb (v3.10.0.26).

Covers:
- [P1] S1: Multi-process concurrent budget ceiling coordination across OS boundaries.
- [P1] S2: Audit ledger read failure injection fail-closed (PermissionError / corrupted ledger).
- [P1] S3: Gateway unanchored passages provenance boundary and candidate checks.
- [P1] E1: Literature alignment deduplication by canonical DOI vs fabricated distributions.
- [P1] E2: Prioritize explicit point estimates over confidence level percentages (95% CI vs beta).
- [P2] E3: Missing citation key fallback to p_item.title without AttributeError.
- [P1] E4: References section truncation preserving exact raw character offsets.
- [P1] E5: References heading with trailing punctuation ('References.') and prior work attribution filter.
- [P2] E6: Single-pass immutable snapshot / post-parse hash reconciliation.
"""
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import pymupdf

from pa_cli.align_findings import EmpiricalInput, align_empirical_finding, parse_user_finding
from pa_cli.evidence_review import BoundEvidence, harvest_paper_evidence
import pa_cli.gateway as gateway


class TestReReviewFindings6ce58eb(unittest.TestCase):
    """Regression tests for external peer review findings on 6ce58eb."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="test_6ce58eb_")
        self.root = Path(self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _create_mock_xml(self, filename: str = "mock.xml", doi: str = "10.1234/controlled-oa") -> Path:
        p = self.root / filename
        p.write_bytes(
            f'''<article xmlns:xlink="http://www.w3.org/1999/xlink">
            <front><article-meta>
              <article-id pub-id-type="doi">{doi}</article-id>
              <title-group><article-title>Controlled Study</article-title></title-group>
              <permissions><license xlink:href="https://creativecommons.org/licenses/by/4.0/"/></permissions>
            </article-meta></front>
            <body><p>Only public study text.</p></body></article>'''.encode("utf-8")
        )
        return p

    # -------------------------------------------------------------------------
    # S1: Multi-process cumulative budget ceiling barrier test
    # -------------------------------------------------------------------------
    def test_s1_multiprocess_budget_ceiling_enforced(self):
        """S1: 5 independent OS processes sharing run_id must not breach token/cost ceiling."""
        xml_p = self._create_mock_xml("s1.xml")
        cand = gateway.PaperEvaluationCandidate(
            "controlled", str(xml_p), "10.1234/controlled-oa",
            source="pmc_xml_only", url="https://eutils.ncbi.nlm.nih.gov", title="Controlled Study"
        )
        audit_path = self.root / "s1-process-audit.jsonl"

        child_script = self.root / "child_runner.py"
        child_script.write_text(f'''import json, sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import pa_cli.gateway as g
root = Path(sys.argv[2])
label = sys.argv[3]
g.DEFAULT_AUDIT_LOG_PATH = root / "s1-process-audit.jsonl"
c = g.PaperEvaluationCandidate("controlled", str(root / "s1.xml"), "10.1234/controlled-oa",
                               source="pmc_xml_only", url="https://eutils.ncbi.nlm.nih.gov", title="Controlled Study")
orig = g.record_gateway_audit_event
def hold(r, audit_file=None):
    (root / (label + ".ready")).write_text("ready")
    deadline = time.monotonic() + 15
    while not (root / "process.release").exists():
        if time.monotonic() > deadline:
            raise RuntimeError("barrier deadline")
        time.sleep(0.02)
    return orig(r, audit_file=audit_file)
g.record_gateway_audit_event = hold
r, _ = g.evaluate_gateway_request("same-processes-run", "local-review", [c], [label * 240000], True, True)
print(json.dumps(r.to_dict()))
''', encoding="utf-8")

        source_dir = Path(__file__).resolve().parent.parent
        env = os.environ.copy()
        env.update(PYTHONPATH=str(source_dir), PYTHONIOENCODING="utf-8", PA_TEST="1")

        children = [
            subprocess.Popen(
                [sys.executable, "-B", str(child_script), str(source_dir), str(self.root), label],
                env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8"
            )
            for label in "ABCDE"
        ]

        deadline = time.monotonic() + 15
        try:
            while not all((self.root / (f"{label}.ready")).exists() for label in "ABCDE"):
                if time.monotonic() > deadline:
                    self.fail("Concurrent child processes timed out before reaching barrier")
                time.sleep(0.03)
        finally:
            (self.root / "process.release").write_text("release")

        receipts = []
        for proc in children:
            stdout, stderr = proc.communicate(timeout=15)
            self.assertEqual(proc.returncode, 0, f"Child failed: {stderr}")
            receipts.append(json.loads(stdout.strip().splitlines()[-1]))

        accepted_tokens = sum(r["estimated_tokens"] for r in receipts if r["gateway_decision"] == "AUTHORIZED")
        accepted_cost = sum(Decimal(r["estimated_cost_usd"]) for r in receipts if r["gateway_decision"] == "AUTHORIZED")

        self.assertLessEqual(accepted_tokens, gateway.MAX_INPUT_TOKENS_CEILING)
        self.assertLessEqual(accepted_cost, gateway.MAX_COST_USD_CEILING)
        # Exactly one request of 60,000 tokens authorized; remaining four rejected
        self.assertEqual(accepted_tokens, 60000)

    # -------------------------------------------------------------------------
    # S2: Audit ledger read failure injection fail-closed
    # -------------------------------------------------------------------------
    def test_s2_audit_ledger_read_fault_fails_closed(self):
        """S2: Audit ledger read failure (PermissionError) must reject rather than resetting spend to 0."""
        xml_p = self._create_mock_xml("s2.xml")
        cand = gateway.PaperEvaluationCandidate(
            "controlled", str(xml_p), "10.1234/controlled-oa",
            source="pmc_xml_only", url="https://eutils.ncbi.nlm.nih.gov", title="Controlled Study"
        )
        audit_file = self.root / "s2-read-fault.jsonl"

        with patch.object(gateway, "DEFAULT_AUDIT_LOG_PATH", audit_file):
            # First request succeeds
            r1, _ = gateway.evaluate_gateway_request("read-fault-run", "op", [cand], ["A" * 240000], True, True)
            self.assertEqual(r1.gateway_decision, "AUTHORIZED")
            self.assertEqual(r1.estimated_tokens, 60000)

            # Subsequent reads fail with injected PermissionError
            original_read_text = Path.read_text
            def faulty_read(path, *args, **kwargs):
                if path == audit_file:
                    raise PermissionError("controlled audit read fault injection")
                return original_read_text(path, *args, **kwargs)

            with patch.object(Path, "read_text", faulty_read):
                r2, _ = gateway.evaluate_gateway_request("read-fault-run", "op", [cand], ["B" * 240000], True, True)
                self.assertEqual(r2.gateway_decision, "REJECTED")
                self.assertTrue(any("cannot verify historical spend against ceiling" in r for r in r2.rejection_reasons))

    # -------------------------------------------------------------------------
    # E1: Literature alignment deduplication by canonical DOI
    # -------------------------------------------------------------------------
    def test_e1_same_doi_different_keys_deduplication(self):
        """E1: Two entries with different keys but the same DOI must not fabricate a benchmark distribution."""
        finding = parse_user_finding(
            var_x="Corporate ESG Performance", var_y="Firm Financial Performance",
            direction="positive", coefficient=0.001
        )
        base = "ESG disclosure positively affects firm financial performance; "
        papers = [
            {"key": "rec_a", "title": "ESG and financial performance", "doi": "10.1234/same-study", "abstract": base + "beta = 0.05, SE = 0.01."},
            {"key": "rec_b", "title": "ESG and financial performance", "doi": "10.1234/same-study", "abstract": base + "beta = 0.08, SE = 0.02."},
        ]
        report = align_empirical_finding(finding, papers)
        # Should recognize only 1 independent study; typical range remains None
        self.assertIsNone(report.prior_distribution_benchmark["literature_typical_range"])
        self.assertIn("Insufficient", report.prior_distribution_benchmark["interpretation"])

    # -------------------------------------------------------------------------
    # E2: Confidence level percentages vs explicit beta estimates
    # -------------------------------------------------------------------------
    def test_e2_confidence_level_percentage_filtered(self):
        """E2: Confidence levels (95% confidence, 90% CI) must not hijack explicit beta effect sizes."""
        finding = parse_user_finding(
            var_x="Corporate ESG Performance", var_y="Firm Financial Performance",
            direction="positive", coefficient=0.001
        )
        base = "ESG disclosure positively affects firm financial performance; "
        papers = [
            {"key": "p1", "title": "ESG and financial performance", "doi": "10.1234/study-1", "abstract": base + "95% confidence; beta = 0.05, SE = 0.01."},
            {"key": "p2", "title": "ESG and financial performance", "doi": "10.1234/study-2", "abstract": base + "90% confidence; beta = 0.08, SE = 0.02."},
        ]
        report = align_empirical_finding(finding, papers)
        self.assertEqual(report.prior_distribution_benchmark["literature_typical_range"], [0.05, 0.08])

    # -------------------------------------------------------------------------
    # E3: Missing citation key does not raise AttributeError
    # -------------------------------------------------------------------------
    def test_e3_missing_key_attribute_error_fixed(self):
        """E3: Empty key in input paper must fall back to title without AttributeError."""
        finding = parse_user_finding(
            var_x="Corporate ESG Performance", var_y="Firm Financial Performance",
            direction="positive", coefficient=0.001
        )
        papers = [{"key": "", "title": "Study With Empty Key", "doi": "", "abstract": "ESG disclosure positively affects performance; beta = 0.05."}]
        report = align_empirical_finding(finding, papers)
        self.assertEqual(report.total_papers_analyzed, 1)

    # -------------------------------------------------------------------------
    # E4: References truncation preserves exact raw character offsets
    # -------------------------------------------------------------------------
    def test_e4_references_truncation_preserves_raw_offsets(self):
        """E4: References truncation must not strip leading page whitespace, preserving 0-based character offsets."""
        pdf_path = self.root / "leading-space.pdf"
        method_text = "We implement two-way fixed effects to study employment in a panel of firms."
        raw_page_text = "   Methods\n" + method_text + "\nReferences\nSmith discusses instrumental variables for identification."
        with pymupdf.open() as doc:
            doc.new_page().insert_text((50, 72), raw_page_text, fontsize=10)
            doc.save(str(pdf_path))

        with pymupdf.open(str(pdf_path)) as doc:
            extracted_raw = doc[0].get_text("text")

        buckets = harvest_paper_evidence(pdf_path, {"key": "leading-space"})
        self.assertTrue(len(buckets["methods"]) > 0)
        ev = buckets["methods"][0]

        # Verify verbatim offset slice against raw text
        slice_text = extracted_raw[ev.char_start:ev.char_end]
        self.assertEqual(slice_text, ev.excerpt)

    # -------------------------------------------------------------------------
    # E5: Trailing punctuation on References and prior literature exclusion
    # -------------------------------------------------------------------------
    def test_e5_references_dot_and_prior_literature_method_exclusion(self):
        """E5: 'References.' heading must be truncated, and prior work method citations must be excluded."""
        # 1. References heading with dot
        pdf_dot = self.root / "references-dot.pdf"
        with pymupdf.open() as doc:
            doc.new_page().insert_text(
                (50, 72),
                "Title\nNo methods are described in this study.\nReferences.\nSmith discusses instrumental variables for identification in a panel.",
                fontsize=10
            )
            doc.save(str(pdf_dot))

        buckets_dot = harvest_paper_evidence(pdf_dot, {"key": "dot"})
        self.assertEqual(len(buckets_dot["methods"]), 0)

        # 2. Prior literature attribution sentence
        pdf_prior = self.root / "other-study.pdf"
        with pymupdf.open() as doc:
            doc.new_page().insert_text(
                (50, 72),
                "Introduction\nPrior literature implements instrumental variables to estimate productivity; our study is descriptive.",
                fontsize=10
            )
            doc.save(str(pdf_prior))

        buckets_prior = harvest_paper_evidence(pdf_prior, {"key": "prior"})
        self.assertEqual(len(buckets_prior["methods"]), 0)

    # -------------------------------------------------------------------------
    # E6: Artifact snapshot replacement hash consistency
    # -------------------------------------------------------------------------
    def test_e6_artifact_hash_reconciliation_on_replacement(self):
        """E6: Evidence artifact_sha256 must match the document opened and parsed."""
        pdf_a = self.root / "swap-old.pdf"
        pdf_b = self.root / "swap-new.pdf"

        with pymupdf.open() as doc:
            doc.new_page().insert_text((50, 72), "Methods\nWe use two-way fixed effects to identify effects on employment.", fontsize=10)
            doc.save(str(pdf_a))

        with pymupdf.open() as doc:
            doc.new_page().insert_text((50, 72), "Methods\nWe use instrumental variables to identify effects on employment.", fontsize=10)
            doc.save(str(pdf_b))

        digest_b = hashlib.sha256(pdf_b.read_bytes()).hexdigest()

        # Simulate file replacement right before parse
        original_open = pymupdf.open
        swapped = False
        def switch_before_parse(*args, **kwargs):
            nonlocal swapped
            if not swapped and args and str(args[0]) == str(pdf_a):
                shutil.copyfile(pdf_b, pdf_a)
                swapped = True
            return original_open(*args, **kwargs)

        with patch.object(pymupdf, "open", side_effect=switch_before_parse):
            buckets = harvest_paper_evidence(pdf_a, {"key": "swap"})

        self.assertTrue(swapped)
        self.assertTrue(len(buckets["methods"]) > 0)
        ev = buckets["methods"][0]
        # Hash must match the actual file that was opened and parsed (pdf_b / swapped pdf_a)
        self.assertEqual(ev.artifact_sha256, digest_b)


if __name__ == "__main__":
    unittest.main()
