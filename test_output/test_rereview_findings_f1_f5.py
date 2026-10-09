"""Unit tests for Re-Review Priority Findings F1-F5 (v3.10.0.25).

Covers:
- F1: Gateway budget reservation leakage / deletion of peer reservations during rejected requests.
- F2: Presumed Public-OA / fake CC BY 4.0 license approval for DOI strings lacking inspected artifact.
- F3: SE and p-values mixed into empirical effect size prior distributions.
- F4: None consistency rate causing TypeError in table and markdown formatters when no tests detected.
- F5: Evidence review harvesting citations from References, topic vs method, and artifact SHA-256 binding.
"""
from decimal import Decimal
import json
from pathlib import Path
import shutil
import tempfile
import threading
import unittest
from unittest.mock import patch

from click.testing import CliRunner

from pa_cli.align_findings import EmpiricalInput, align_empirical_finding
from pa_cli.cli import main
from pa_cli.evidence_review import BoundEvidence, harvest_paper_evidence
from pa_cli.gateway import (
    PaperEvaluationCandidate,
    _evaluate_legacy_gateway_request as evaluate_gateway_request,
    verify_paper_rights,
)
from pa_cli.stats_check import StatsCheckSummary, format_stats_report


class TestReReviewFindingsF1F5(unittest.TestCase):
    """Test suite directly validating fixes for F1 through F5."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="test_f1_f5_")
        self.root = Path(self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _create_mock_xml(self, filename: str = "mock.xml", doi: str = "10.48550/arXiv.2101.00001") -> Path:
        p = self.root / filename
        p.write_bytes(
            f'''<article xmlns:xlink="http://www.w3.org/1999/xlink">
            <front><article-meta>
              <article-id pub-id-type="doi">{doi}</article-id>
              <title-group><article-title>Valid OA Article</article-title></title-group>
              <permissions><license xlink:href="https://creativecommons.org/licenses/by/4.0/"/></permissions>
            </article-meta></front>
            <body><p>Study text</p></body></article>'''.encode("utf-8")
        )
        return p

    # -------------------------------------------------------------------------
    # F1: 3-request reservation ownership and rejection isolation
    # -------------------------------------------------------------------------
    def test_f1_three_request_reservation_ownership_safety(self):
        """F1: Rejected request B must not release in-flight reservation of request A."""
        xml_p = self._create_mock_xml("f1.xml")
        cand = PaperEvaluationCandidate(
            paper_id="cand_f1",
            artifact_path=str(xml_p),
            doi="10.48550/arXiv.2101.00001",
            source="arxiv",
            url="https://arxiv.org/abs/2101.00001",
            data_class="public",
        )
        audit_file = self.root / "audit_f1.jsonl"
        run_id = "run_f1_race"

        # Payload of 240,000 characters corresponds to ~60,000 tokens
        payload = ["A" * 240_000]

        a_paused = threading.Event()
        b_finished = threading.Event()
        receipt_a = None
        receipt_b = None
        receipt_c = None

        def run_request_a():
            nonlocal receipt_a
            # Hook into audit recording to pause A while its reservation is active
            orig_record = pa_cli.gateway.record_gateway_audit_event
            def pause_before_record(r, audit_file=None):
                a_paused.set()
                # Wait until request B has completed and been rejected
                b_finished.wait(timeout=5)
                return orig_record(r, audit_file=audit_file)

            with patch("pa_cli.gateway.record_gateway_audit_event", side_effect=pause_before_record):
                receipt_a, _ = evaluate_gateway_request(
                    run_id=run_id,
                    operator="op_a",
                    candidates=[cand],
                    passages=payload,
                    consent_public_oa=True,
                    consent_zero_retention=True,
                    audit_file=audit_file,
                )

        import pa_cli.gateway

        # Start Request A in background thread
        t_a = threading.Thread(target=run_request_a)
        t_a.start()

        # Wait until A has evaluated and acquired its reservation
        self.assertTrue(a_paused.wait(timeout=5))

        # Request B arrives while A is active: 60k + 60k = 120k > 100k ceiling -> REJECTED
        receipt_b, _ = evaluate_gateway_request(
            run_id=run_id,
            operator="op_b",
            candidates=[cand],
            passages=payload,
            consent_public_oa=True,
            consent_zero_retention=True,
            audit_file=audit_file,
        )
        self.assertEqual(receipt_b.gateway_decision, "REJECTED")
        self.assertFalse(receipt_b.ceiling_compliant)

        # Signal that B has finished
        b_finished.set()

        # Request C arrives before A releases its reservation: must ALSO be REJECTED!
        # Under the old bug, B's cleanup would have deleted A's reservation and C would pass.
        receipt_c, _ = evaluate_gateway_request(
            run_id=run_id,
            operator="op_c",
            candidates=[cand],
            passages=payload,
            consent_public_oa=True,
            consent_zero_retention=True,
            audit_file=audit_file,
        )
        self.assertEqual(receipt_c.gateway_decision, "REJECTED")
        self.assertFalse(receipt_c.ceiling_compliant)

        t_a.join(timeout=5)
        self.assertIsNotNone(receipt_a)
        self.assertEqual(receipt_a.gateway_decision, "AUTHORIZED")
        self.assertTrue(receipt_a.ceiling_compliant)

        # Decisions must strictly be AUTHORIZED, REJECTED, REJECTED
        # Cumulative authorized tokens = 60,000 <= 100,000 hard ceiling
        self.assertEqual(receipt_a.gateway_decision, "AUTHORIZED")
        self.assertEqual(receipt_b.gateway_decision, "REJECTED")
        self.assertEqual(receipt_c.gateway_decision, "REJECTED")

    # -------------------------------------------------------------------------
    # F2: No presumed OA or fake CC-BY grant without inspected artifact file
    # -------------------------------------------------------------------------
    def test_f2_no_artifact_presumed_oa_strictly_blocked(self):
        """F2: DOIs without inspected physical artifact are strictly blocked."""
        # 1. arXiv string heuristic without artifact file
        cand_arxiv = PaperEvaluationCandidate(
            paper_id="arxiv_str",
            artifact_path=None,
            doi="10.48550/arxiv.9999.99999",
            source="arxiv",
            data_class="public",
        )
        res_arxiv = verify_paper_rights(cand_arxiv)
        self.assertFalse(res_arxiv.is_public_oa)
        self.assertEqual(res_arxiv.status, "BLOCKED_NON_OA")
        self.assertEqual(res_arxiv.rights_class, "unverified_no_artifact")
        self.assertTrue(any("inspected artifact file" in r for r in res_arxiv.blocking_reasons))

        # 2. PMC source without artifact file
        cand_pmc = PaperEvaluationCandidate(
            paper_id="pmc_str",
            artifact_path=None,
            doi="10.1234/nonexistent",
            source="pmc",
            data_class="public",
        )
        res_pmc = verify_paper_rights(cand_pmc)
        self.assertFalse(res_pmc.is_public_oa)
        self.assertEqual(res_pmc.status, "BLOCKED_NON_OA")
        self.assertEqual(res_pmc.rights_class, "unverified_no_artifact")

        # 3. DOI containing arxiv substring without artifact file
        cand_sub = PaperEvaluationCandidate(
            paper_id="sub_str",
            artifact_path=None,
            doi="10.1234/containsarxiv",
            source="arxiv",
            data_class="public",
        )
        res_sub = verify_paper_rights(cand_sub)
        self.assertFalse(res_sub.is_public_oa)
        self.assertEqual(res_sub.status, "BLOCKED_NON_OA")
        self.assertEqual(res_sub.rights_class, "unverified_no_artifact")

    # -------------------------------------------------------------------------
    # F3: SE and p-values excluded from empirical effect size distribution
    # -------------------------------------------------------------------------
    def test_f3_se_and_pvalues_filtered_from_prior_benchmark(self):
        """F3: SE and p-values must not fabricate an empirical range for single paper."""
        # Single paper fixture: beta = 0.05, SE = 0.01, p = 0.003
        single_paper_corpus = [
            {
                "key": "study1",
                "title": "Corporate Investment Dynamics",
                "abstract": (
                    "Using panel fixed effects, we find that cash flow significantly promotes capital expenditure "
                    "with beta = 0.05 (SE = 0.01, p = 0.003)."
                ),
            }
        ]
        finding = EmpiricalInput(
            statement="Cash flow increases capital investment",
            var_x="Cash flow",
            var_y="Capital expenditure",
            direction="positive",
            coefficient=0.001,
            std_err=0.0005,
            p_value=0.04,
        )
        report = align_empirical_finding(finding, single_paper_corpus)
        bench = report.prior_distribution_benchmark
        # Must NOT construct a range from beta, SE, and p-value
        self.assertIsNone(bench["literature_typical_range"])
        self.assertIsNone(bench["is_outlier"])
        self.assertIn("Insufficient numerical estimates", bench["interpretation"])

        # Two distinct papers: Paper 1 (beta = 0.05), Paper 2 (beta = 0.08)
        two_paper_corpus = [
            {
                "key": "study1",
                "title": "Corporate Investment Dynamics",
                "abstract": "Cash flow significantly promotes capital expenditure with beta = 0.05 (SE = 0.01, p = 0.003).",
            },
            {
                "key": "study2",
                "title": "Investment Under Financing Constraints",
                "abstract": "Cash flow significantly increases capital expenditure with coef = 0.08, p < 0.01.",
            },
        ]
        report2 = align_empirical_finding(finding, two_paper_corpus)
        bench2 = report2.prior_distribution_benchmark
        self.assertEqual(bench2["literature_typical_range"], [0.05, 0.08])
        self.assertTrue(bench2["is_outlier"])

    # -------------------------------------------------------------------------
    # F4: Empty statistical check consistency rate formatting
    # -------------------------------------------------------------------------
    def test_f4_empty_stats_check_formatters_no_crash(self):
        """F4: None consistency_rate formats safely as N/A in table and markdown."""
        empty_summary = StatsCheckSummary(
            total_tests=0,
            consistent_count=0,
            inconsistent_count=0,
            decision_error_count=0,
            one_tailed_match_count=0,
            consistency_rate=None,
            items=[],
        )

        # 1. Table format does not raise TypeError and shows N/A
        tbl = format_stats_report(empty_summary, fmt="table")
        self.assertIn("N/A", tbl)
        self.assertIn("Total Tests: 0", tbl)

        # 2. Markdown format does not raise TypeError and shows N/A
        md = format_stats_report(empty_summary, fmt="markdown")
        self.assertIn("N/A", md)
        self.assertIn("**Total Tests Found**: 0", md)

        # 3. JSON format preserves null rate
        js = json.loads(format_stats_report(empty_summary, fmt="json"))
        self.assertIsNone(js["consistency_rate"])

    # -------------------------------------------------------------------------
    # F5: Evidence review references exclusion, method accuracy & SHA-256
    # -------------------------------------------------------------------------
    def test_f5_evidence_review_references_exclusion_and_sha256(self):
        """F5: References citations excluded from methods; artifact SHA-256 bound."""
        try:
            import fitz
        except ImportError:
            self.skipTest("PyMuPDF not installed")

        pdf_path = self.root / "software_paper.pdf"
        doc = fitz.open()

        # Page 1: Abstract & Methods
        p1 = doc.new_page()
        p1.insert_text(
            (50, 72),
            "Evaluating software engineering productivity with quasi-experiments.\n"
            "We implement a staggered difference-in-differences design across 20 teams.\n"
            "Empirical results indicate that code review tools significantly promote feature delivery by 15%."
        )

        # Page 2: References section
        p2 = doc.new_page()
        p2.insert_text(
            (50, 72),
            "References\n"
            "Rasmus, B. (2024). The programmer's assistant: large language models and software development. 2SLS estimation.\n"
            "Smith, J. (2023). Instrumental variables in developer studies. regression discontinuity."
        )

        doc.save(str(pdf_path))
        doc.close()

        entry = {"key": "soft2024", "year": "2024", "doi": "10.1145/12345"}
        buckets = harvest_paper_evidence(pdf_path, entry)

        # 1. Check artifact SHA-256 is attached
        for sec, ev_list in buckets.items():
            for ev in ev_list:
                self.assertTrue(ev.artifact_sha256)
                self.assertEqual(len(ev.artifact_sha256), 64)
                self.assertIn("software_paper.pdf", ev.filename)

        # 2. Methods must ONLY contain Staggered DiD from Page 1, NOT 2SLS from Page 2 references!
        methods = buckets.get("methods", [])
        self.assertTrue(any("staggered difference-in-differences" in m.excerpt.lower() for m in methods))
        self.assertFalse(any("2sls" in m.excerpt.lower() for m in methods))
        self.assertFalse(any("the programmer's assistant" in m.excerpt.lower() for m in methods))
        self.assertFalse(any("regression discontinuity" in m.excerpt.lower() for m in methods))


if __name__ == "__main__":
    unittest.main()
