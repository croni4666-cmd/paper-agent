"""test_output/test_rereview_findings_4a0cb65.py — Regression test suite for 4a0cb65 re-review findings.

Covers all 6 findings (A1–A3, B1–B3) from the 4a0cb65 peer review report:
- A1: File lock failure / timeout fails closed and rejects request without executing budget logic.
- A2: Reservation ledger read and write faults fail closed, preventing budget ceiling breaches.
- A3: S3 verify_passage_provenance parameter in evaluate_gateway_request and provenance_verified field in GatewayReceipt.
- B1: Percentage coefficient scaling (beta = 5% -> 0.05) and sample demographic proportions filtered from benchmark distribution.
- B2: Missing/unlinked physical PDF file yields 0.0% binding rate, never defaulting to counting as verified.
- B3: Artifact SHA-256 strictly reflects the parsed document snapshot, preventing mismatch on post-open file mutations.
"""

import hashlib
import inspect
import json
import os
import shutil
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pymupdf

import pa_cli.evidence_review as er
import pa_cli.gateway as g
from pa_cli.align_findings import EmpiricalInput, align_empirical_finding, parse_user_finding
from pa_cli.project import init_project


class TestReReviewFindings4a0cb65(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.root = Path(self.tmpdir)
        self.audit_log = self.root / "audit.jsonl"

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # A1: Lock failure fail-closed
    # -------------------------------------------------------------------------
    def test_a1_lock_fault_fails_closed(self):
        """A1: When lock acquisition raises PermissionError/TimeoutError, gateway rejects and does not authorize."""
        xml_path = self.root / "valid.xml"
        xml_path.write_text(
            '<article xmlns:xlink="http://www.w3.org/1999/xlink"><front><article-meta>'
            '<article-id pub-id-type="doi">10.1234/a1-test</article-id>'
            '<permissions><license xlink:href="https://creativecommons.org/licenses/by/4.0/"/></permissions>'
            '</article-meta></front><body><p>Public open text.</p></body></article>',
            encoding="utf-8",
        )
        cand = g.PaperEvaluationCandidate("cand_a1", str(xml_path), "10.1234/a1-test", source="pmc_xml_only", url="https://eutils.ncbi.nlm.nih.gov")

        with patch("pa_cli.gateway.DEFAULT_AUDIT_LOG_PATH", self.audit_log):
            # Simulate lock open permission failure
            with patch("pa_cli.gateway.os.open", side_effect=PermissionError("controlled lock-open fault")):
                receipt, _ = g._evaluate_legacy_gateway_request(
                    "run-a1", "operator", [cand], ["Public open text."], True, True
                )
                self.assertEqual(receipt.gateway_decision, "REJECTED")
                self.assertFalse(receipt.ceiling_compliant)
                self.assertTrue(any("lock" in r.lower() for r in receipt.rejection_reasons))

    # -------------------------------------------------------------------------
    # A2: Reservation ledger read and write faults fail closed
    # -------------------------------------------------------------------------
    def test_a2_reservation_read_and_write_fault_fail_closed(self):
        """A2: When reservation ledger read or write fails, gateway fails closed to prevent budget leaks."""
        xml_path = self.root / "valid.xml"
        xml_path.write_text(
            '<article xmlns:xlink="http://www.w3.org/1999/xlink"><front><article-meta>'
            '<article-id pub-id-type="doi">10.1234/a2-test</article-id>'
            '<permissions><license xlink:href="https://creativecommons.org/licenses/by/4.0/"/></permissions>'
            '</article-meta></front><body><p>Public open text.</p></body></article>',
            encoding="utf-8",
        )
        cand = g.PaperEvaluationCandidate("cand_a2", str(xml_path), "10.1234/a2-test", source="pmc_xml_only", url="https://eutils.ncbi.nlm.nih.gov")

        with patch("pa_cli.gateway.DEFAULT_AUDIT_LOG_PATH", self.audit_log):
            # 1. Read fault fails closed
            with patch("pa_cli.gateway._load_all_reservations", side_effect=PermissionError("controlled reservation read fault")):
                r_read, _ = g._evaluate_legacy_gateway_request("run-a2-read", "operator", [cand], ["Public text"], True, True)
                self.assertEqual(r_read.gateway_decision, "REJECTED")
                self.assertTrue(any("Reservation ledger read failure" in r for r in r_read.rejection_reasons))

            # 2. Write fault fails closed
            with patch("pa_cli.gateway._save_reservation", side_effect=PermissionError("controlled reservation write fault")):
                r_write, _ = g._evaluate_legacy_gateway_request("run-a2-write", "operator", [cand], ["Public text"], True, True)
                self.assertEqual(r_write.gateway_decision, "REJECTED")
                self.assertTrue(any("Reservation ledger write failure" in r for r in r_write.rejection_reasons))

    # -------------------------------------------------------------------------
    # A3: S3 passage provenance contract
    # -------------------------------------------------------------------------
    def test_a3_gateway_verify_passage_provenance_contract(self):
        """A3: verify_passage_provenance parameter in evaluate_gateway_request and provenance_verified in receipt."""
        sig = inspect.signature(g._evaluate_legacy_gateway_request)
        self.assertIn("verify_passage_provenance", sig.parameters)
        self.assertIn("provenance_verified", g.GatewayReceipt.__dataclass_fields__)

        xml_path = self.root / "valid.xml"
        xml_path.write_text(
            '<article xmlns:xlink="http://www.w3.org/1999/xlink"><front><article-meta>'
            '<article-id pub-id-type="doi">10.1234/a3-test</article-id>'
            '<permissions><license xlink:href="https://creativecommons.org/licenses/by/4.0/"/></permissions>'
            '</article-meta></front><body><p>Legitimate verified research passage.</p></body></article>',
            encoding="utf-8",
        )
        cand = g.PaperEvaluationCandidate("cand_a3", str(xml_path), "10.1234/a3-test", source="pmc_xml_only", url="https://eutils.ncbi.nlm.nih.gov")

        with patch("pa_cli.gateway.DEFAULT_AUDIT_LOG_PATH", self.audit_log):
            # Matching passage -> provenance_verified is True
            r_match, _ = g._evaluate_legacy_gateway_request(
                "run-a3-match", "operator", [cand], ["Legitimate verified research passage."], True, True,
                verify_passage_provenance=True,
            )
            self.assertTrue(r_match.provenance_verified)

            # Unrelated passage not in candidate -> provenance_verified is False
            r_unmatch, _ = g._evaluate_legacy_gateway_request(
                "run-a3-unmatch", "operator", [cand], ["Completely synthesized unpublished internal memo."], True, True,
                verify_passage_provenance=True,
            )
            self.assertFalse(r_unmatch.provenance_verified)

    # -------------------------------------------------------------------------
    # B1: Percentage coefficient scaling and sample proportion filtering
    # -------------------------------------------------------------------------
    def test_b1_percentage_beta_and_sample_proportion_filter(self):
        """B1: Explicit beta = 5% scales to 0.05, and sample composition (40% large firms) is not treated as effect size."""
        finding = parse_user_finding(
            var_x="Corporate ESG Performance",
            var_y="Firm Financial Performance",
            direction="positive",
            coefficient=0.001,
        )
        base = "ESG disclosure positively affects firm financial performance; "

        # 1. Sample proportions must NOT create empirical benchmark distribution
        papers_sample = [
            {"key": "a", "title": "Study A", "abstract": base + "our sample contains 40% large firms and 60% small firms."},
            {"key": "b", "title": "Study B", "abstract": base + "our sample contains 50% large firms and 50% small firms."},
        ]
        rep_sample = align_empirical_finding(finding, papers_sample)
        bench_sample = rep_sample.prior_distribution_benchmark
        self.assertIsNone(bench_sample["literature_typical_range"])
        self.assertIsNone(bench_sample["is_outlier"])
        self.assertIn("Insufficient", bench_sample["interpretation"])

        # 2. Explicit percentage beta (beta = 5%, beta = 8%) scales to [0.05, 0.08]
        papers_beta = [
            {"key": "a", "title": "Study A", "abstract": base + "beta = 5%."},
            {"key": "b", "title": "Study B", "abstract": base + "beta = 8%."},
        ]
        rep_beta = align_empirical_finding(finding, papers_beta)
        bench_beta = rep_beta.prior_distribution_benchmark
        self.assertEqual(bench_beta["literature_typical_range"], [0.05, 0.08])
        self.assertTrue(bench_beta["is_outlier"])
        self.assertIn("[0.05, 0.08]", bench_beta["interpretation"])

    # -------------------------------------------------------------------------
    # B2: Missing physical PDF binding rate is 0.0%
    # -------------------------------------------------------------------------
    def test_b2_missing_file_binding_rate_zero(self):
        """B2: When physical PDF file is missing, generate_evidence_backed_review reports 0.0% binding rate."""
        projects = self.root / "projects"
        init_project("missing-file", title="Controlled failed verification", root=projects)
        pdf_dir = projects / "missing-file" / "pdfs"
        pdf_dir.mkdir(parents=True, exist_ok=True)
        pdf_file = pdf_dir / "paper.pdf"

        with pymupdf.open() as d:
            d.new_page().insert_text((50, 72), "Methods\nWe use instrumental variables to identify effects on employment.")
            d.save(str(pdf_file))

        (projects / "missing-file" / "refs.bib").write_text("@article{paper,title={Controlled Study}}", encoding="utf-8")

        # Simulate file unlinking right after harvest
        orig_harvest = er.harvest_paper_evidence
        def vanish_after_harvest(*args, **kwargs):
            result = orig_harvest(*args, **kwargs)
            if pdf_file.exists():
                pdf_file.unlink()
            return result

        with patch.object(er, "harvest_paper_evidence", side_effect=vanish_after_harvest):
            md, report = er.generate_evidence_backed_review("missing-file", projects, with_prisma=False)

        self.assertFalse(pdf_file.exists())
        self.assertGreater(report.total_claims, 0)
        self.assertEqual(report.binding_rate, 0.0)
        self.assertIn("0.0%", md)

    # -------------------------------------------------------------------------
    # B3: Parser snapshot hash consistency
    # -------------------------------------------------------------------------
    def test_b3_parser_snapshot_hash_consistency(self):
        """B3: Evidence artifact_sha256 matches the parsed document snapshot, not a mutated post-open disk file."""
        old_pdf = self.root / "old.pdf"
        new_pdf = self.root / "new.pdf"

        with pymupdf.open() as d:
            d.new_page().insert_text((50, 72), "Methods\nWe use two-way fixed effects to identify employment effects for workers.")
            d.save(str(old_pdf))

        with pymupdf.open() as d:
            d.new_page().insert_text((50, 72), "Methods\nWe use instrumental variables to identify employment effects for workers.")
            d.save(str(new_pdf))

        old_bytes = old_pdf.read_bytes()
        new_bytes = new_pdf.read_bytes()
        expected_hash = hashlib.sha256(old_bytes).hexdigest()

        orig_open = pymupdf.open
        def opened_old_snapshot(*args, **kwargs):
            if args and str(args[0]) == str(old_pdf):
                doc = orig_open(stream=old_bytes, filetype="pdf")
                old_pdf.write_bytes(new_bytes)
                return doc
            return orig_open(*args, **kwargs)

        with patch.object(er.fitz, "open", side_effect=opened_old_snapshot):
            rows = [e.to_dict() for items in er.harvest_paper_evidence(old_pdf, {"key": "old"}).values() for e in items]

        self.assertTrue(len(rows) > 0)
        self.assertTrue(all(r["artifact_sha256"] == expected_hash for r in rows))


if __name__ == "__main__":
    unittest.main()
