"""Unit and regression tests for audit findings R1-R7 (review of commit 1ae4c36).

Covers:
- R1: Numerical discrepancy strictly overrides verdict to NUMERICAL_DISCREPANCY and blocks pass_status
- R2: Exact verbatim raw text slicing in character offsets without stripping/offset distortion
- R3: Rejecting non-DOI (10.foo) and unverified DOI combinations from bypassing public OA gate
- R4: Concurrency-safe budget reservation, corrupt log line tolerance, fail-closed audit write, cumulative ceiling compliance
- R5: Filtering out sample sizes, years, and non-effect numbers from prior distribution benchmarks
- R6: Untested hypotheses produce Insufficient Evidence and untested dominant direction; future/conditional testing sentences remain untested
- R7: Exact threshold evaluation for <= and >= without adding rounding margin; None rate for empty test sets
- Extractor heading version: headings-v3
"""

import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pymupdf

from pa_cli.align_findings import parse_user_finding, align_empirical_finding
from pa_cli.cite_audit import audit_manuscript, compute_fidelity_score, EvidencePassage
from pa_cli.consensus import extract_hypotheses_from_text, build_consensus_matrix
from pa_cli.evidence import build_index, _validate
from pa_cli.evidence_review import harvest_paper_evidence
from pa_cli.gateway import (
    PaperEvaluationCandidate,
    verify_paper_rights,
    evaluate_gateway_request,
    record_gateway_audit_event,
)
from pa_cli.stats_check import check_p_consistency, summarize_findings


class TestReviewFixes1ae4c36(unittest.TestCase):
    def test_r1_numerical_conflict_blocks_verified(self):
        """R1: Known numerical discrepancy blocks VERIFIED_FAITHFUL and pass_status."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            pdf_dir = Path(tmp_dir) / "pdf_cache"
            pdf_dir.mkdir(parents=True)
            pdf_file = pdf_dir / "p.pdf"

            doc = pymupdf.open()
            page = doc.new_page()
            page.insert_text((72, 72), "Productivity increases by 14%.")
            doc.save(str(pdf_file))
            doc.close()

            bib_file = pdf_dir / "refs.bib"
            bib_file.write_text('@article{p,title={Productivity study},year={2024}}\n', encoding="utf-8")

            # Draft claims 4%, cited paper reports 14%
            report = audit_manuscript("Productivity increases by 4% [@p].", bib_file, pdf_dir)
            self.assertEqual(len(report.items), 1)
            item = report.items[0]

            self.assertEqual(item.verdict, "NUMERICAL_DISCREPANCY")
            self.assertIn("NUMERICAL_DISCREPANCY:missing(4%)", item.flags)
            self.assertFalse(report.pass_status)
            self.assertEqual(report.numerical_discrepancy_count, 1)
            self.assertEqual(report.verified_count, 0)
            self.assertLessEqual(item.fidelity_score, 0.50)

    def test_r2_verbatim_offsets_and_no_fake_results(self):
        """R2: Exact character offsets match raw text slices verbatim."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            pdf_file = Path(tmp_dir) / "sample.pdf"
            doc = pymupdf.open()
            page = doc.new_page()
            page.insert_text(
                (72, 72),
                "Methodology.\n"
                "In our empirical baseline regression estimation, we specify a two-way fixed effects model.\n"
                "Empirical results indicate that corporate green innovation increases by 12% across firms.\n"
            )
            doc.save(str(pdf_file))
            doc.close()

            buckets = harvest_paper_evidence(pdf_file, {"key": "sample", "doi": ""})
            doc_verify = pymupdf.open(str(pdf_file))
            raw_page_text = doc_verify[0].get_text()
            doc_verify.close()

            for sec, ev_list in buckets.items():
                for ev in ev_list:
                    # Raw slice must match excerpt verbatim
                    raw_slice = raw_page_text[ev.char_start:ev.char_end]
                    self.assertEqual(raw_slice, ev.excerpt)

    def test_r3_gateway_unverified_doi_blocked(self):
        """R3: 10.foo and 10.1234/unverified without artifact are blocked."""
        c_foo = PaperEvaluationCandidate("unverified", None, "10.foo", source="arxiv")
        res_foo = verify_paper_rights(c_foo)
        self.assertFalse(res_foo.is_public_oa)
        self.assertEqual(res_foo.status, "BLOCKED_NON_OA")

        c_unver = PaperEvaluationCandidate("unverified", None, "10.1234/unverified", source="arxiv")
        res_unver = verify_paper_rights(c_unver)
        self.assertFalse(res_unver.is_public_oa)
        self.assertEqual(res_unver.status, "BLOCKED_NON_OA")

        # Canonical arXiv DOI is verified
        c_valid = PaperEvaluationCandidate("arxiv_01", None, "10.48550/arXiv.2101.00001", source="arxiv", data_class="public")
        res_valid = verify_paper_rights(c_valid)
        self.assertTrue(res_valid.is_public_oa)
        self.assertEqual(res_valid.status, "VERIFIED_PUBLIC_OA")

    def test_r4_gateway_cumulative_budget_and_write_failure(self):
        """R4: Cumulative ceilings, corrupted log resilience, write failure fail-closed, and race prevention."""
        with tempfile.TemporaryDirectory() as td:
            log_path = Path(td) / "audit.jsonl"
            cand = PaperEvaluationCandidate("cand_01", None, "10.48550/arXiv.2101.00001", source="arxiv", data_class="public")

            # 1. Sequential calls: second exceeds 100k cumulative limit
            with patch("pa_cli.gateway.DEFAULT_AUDIT_LOG_PATH", log_path):
                r1, _ = evaluate_gateway_request("same-run", "operator", [cand], ["x" * 240000], True, True)
                r2, _ = evaluate_gateway_request("same-run", "operator", [cand], ["x" * 240000], True, True)
                self.assertEqual(r1.gateway_decision, "AUTHORIZED")
                self.assertTrue(r1.ceiling_compliant)
                self.assertEqual(r2.gateway_decision, "REJECTED")
                self.assertFalse(r2.ceiling_compliant)

            # 2. Corrupt log line recovery
            corrupt_path = Path(td) / "corrupt.jsonl"
            corrupt_path.write_text("invalid-json-line\n" + json.dumps(r1.to_dict()) + "\n", encoding="utf-8")
            with patch("pa_cli.gateway.DEFAULT_AUDIT_LOG_PATH", corrupt_path):
                r_corrupt, _ = evaluate_gateway_request("same-run", "operator", [cand], ["x" * 240000], True, True)
                self.assertEqual(r_corrupt.gateway_decision, "REJECTED")

            # 3. Fail-closed on audit write failure
            block_file = Path(td) / "parent_file"
            block_file.write_text("file_not_dir", encoding="utf-8")
            with patch("pa_cli.gateway.DEFAULT_AUDIT_LOG_PATH", block_file / "audit.jsonl"):
                r_fail, _ = evaluate_gateway_request("fail-run", "operator", [cand], ["passage text"], True, True)
                self.assertEqual(r_fail.gateway_decision, "REJECTED")
                self.assertTrue(any("Audit log write failure" in r for r in r_fail.rejection_reasons))

            # 4. Concurrency race prevention
            barrier = threading.Barrier(2)
            def delayed_record(receipt):
                barrier.wait(timeout=5)
                record_gateway_audit_event(receipt)

            race_log = Path(td) / "race.jsonl"
            with patch("pa_cli.gateway.DEFAULT_AUDIT_LOG_PATH", race_log), patch("pa_cli.gateway.record_gateway_audit_event", side_effect=delayed_record):
                with ThreadPoolExecutor(2) as pool:
                    futures = [
                        pool.submit(evaluate_gateway_request, "race-run", "operator", [cand], ["x" * 240000], True, True)
                        for _ in range(2)
                    ]
                    results = [f.result()[0] for f in futures]
                    decisions = sorted([r.gateway_decision for r in results])
                    self.assertEqual(decisions, ["AUTHORIZED", "REJECTED"])

    def test_r5_prior_distribution_benchmark_filters_years_and_samples(self):
        """R5: Filter out sample sizes and publication years from empirical effect benchmark."""
        paper = {
            "key": "fixture",
            "title": "ESG and corporate financial performance",
            "abstract": "We find that ESG disclosure positively affects firm financial performance by 5% among 1000 firms during 2020.",
        }
        finding = parse_user_finding(
            var_x="Corporate ESG Performance",
            var_y="Firm Financial Performance",
            direction="positive",
            coefficient=2.0,
        )
        report = align_empirical_finding(finding, [paper])
        bench = report.prior_distribution_benchmark

        self.assertIsNone(bench["literature_typical_range"])
        self.assertIsNone(bench["is_outlier"])
        self.assertIn("Insufficient numerical estimates", bench["interpretation"])

    def test_r6_consensus_untested_matrix_and_future_hypotheses(self):
        """R6: Untested hypotheses result in Insufficient Evidence; planned future tests are untested."""
        # 1. Untested hypothesis matrix
        h = extract_hypotheses_from_text("H1: ESG disclosure positively affects firm financial performance.\n", "fixture")
        matrix = build_consensus_matrix(h)
        self.assertEqual(len(matrix.relationships), 1)
        rel = matrix.relationships[0]
        self.assertEqual(rel.dominant_direction, "untested")
        self.assertEqual(rel.debate_level, "Insufficient Evidence")
        self.assertEqual(rel.consensus_score, 0.0)

        # 2. Future study test
        future_text = (
            "H1: ESG disclosure positively affects firm financial performance.\n"
            "We plan to test whether H1 is supported in a future study."
        )
        hyps_future = extract_hypotheses_from_text(future_text, "fixture")
        self.assertEqual(len(hyps_future), 1)
        self.assertEqual(hyps_future[0].outcome, "untested")
        self.assertEqual(hyps_future[0].effective_finding, "untested")

    def test_r7_stats_inequality_threshold_and_empty_rate(self):
        """R7: Non-strict inequality p <= .05 does not add rounding tolerance to alpha; empty rate is None."""
        # p <= 0.05 reported, computed p = 0.054 -> inconsistent & decision error
        cons_two, dec_err, cons_one, expl = check_p_consistency("0.05", "<=", 0.054, 0.027)
        self.assertFalse(cons_two)
        self.assertTrue(dec_err)
        self.assertIn("DECISION ERROR", expl)

        # Zero findings return consistency_rate = None
        summary = summarize_findings([])
        self.assertIsNone(summary.consistency_rate)
        self.assertIsNone(summary.to_dict()["consistency_rate"])

    def test_extractor_headings_v3(self):
        """Verify heading extractor version identifier in index."""
        with tempfile.TemporaryDirectory() as td:
            pdf_path = Path(td) / "heading_test.pdf"
            doc = pymupdf.open()
            page = doc.new_page()
            page.insert_text((72, 72), "Abstract. Testing heading.\n1. Methods\nAlgorithm details.\n2. Results\nFindings.")
            doc.save(str(pdf_path))
            doc.close()

            idx = build_index(pdf_path)
            _validate(idx)
            self.assertIn("headings-v3", idx["extractor"])


if __name__ == "__main__":
    unittest.main()
