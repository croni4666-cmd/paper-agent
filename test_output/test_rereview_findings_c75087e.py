"""test_output/test_rereview_findings_c75087e.py — Regression test suite for c75087e re-review findings (R1–R6).

Covers all 6 findings from the c75087e peer review report:
- R1: _save_reservation secondary read failure must propagate and never swallow with data = {},
      preserving peer reservations and preventing budget ceiling breaches (>100k tokens).
- R2: Failed reservation disk write rolls back in-memory _ACTIVE_RESERVATIONS, allowing clean healthy retries.
- R3: Candidate rights check and passage extraction bound to same artifact snapshot; mutated files fail closed.
- R4: Percentage extraction strips survey response/retention rates and parses decrease verbs as negative signs.
- R5: Evidence binding rate validates physical file SHA-256 against recorded artifact_sha256 (mismatch -> 0.0).
- R6: PyMuPDF evidence harvest binds artifact_sha256 to in-memory doc.stream bytes, resilient to ABA file swapping.
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
from pa_cli.align_findings import align_empirical_finding, parse_user_finding
from pa_cli.project import init_project


class TestReReviewFindingsC75087E(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.root = Path(self.tmpdir)
        self.audit_log = self.root / "audit.jsonl"

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_oa_xml(self, path: Path, text: str = "Public verified text.", doi: str = "10.1234/fixture") -> Path:
        path.write_text(
            f'<article xmlns:xlink="http://www.w3.org/1999/xlink"><front><article-meta>'
            f'<article-id pub-id-type="doi">{doi}</article-id>'
            f'<permissions><license xlink:href="https://creativecommons.org/licenses/by/4.0/"/></permissions>'
            f'</article-meta></front><body><p>{text}</p></body></article>',
            encoding="utf-8",
        )
        return path

    def _make_candidate(self, path: Path, doi: str = "10.1234/fixture") -> g.PaperEvaluationCandidate:
        return g.PaperEvaluationCandidate(
            "fixture", str(path), doi, source="pmc_xml_only", url="https://eutils.ncbi.nlm.nih.gov"
        )

    # -------------------------------------------------------------------------
    # R1: Secondary read fault in _save_reservation must propagate and prevent ceiling breaches
    # -------------------------------------------------------------------------
    def test_r1_second_save_read_fault_propagates_and_preserves_peer_ledger(self):
        """R1: _save_reservation read error must not be swallowed with data = {}, wiping existing reservations."""
        xml_path = self._write_oa_xml(self.root / "valid.xml")
        cand = self._make_candidate(xml_path)

        with patch.object(g, "DEFAULT_AUDIT_LOG_PATH", self.audit_log):
            # Authorize first request (60,000 tokens)
            first_receipt, _ = g.evaluate_gateway_request(
                "run-r1", "operator", [cand], ["A" * 240000], True, True
            )
            self.assertEqual(first_receipt.gateway_decision, "AUTHORIZED")
            self.assertEqual(first_receipt.estimated_tokens, 60000)

            # Direct check: _save_reservation propagates read errors rather than swallowing with data = {}
            orig_read = Path.read_text
            def deny_reservations_read(p, *args, **kwargs):
                if p.name.endswith(".reservations.json"):
                    raise PermissionError("controlled reservation read failure in save")
                return orig_read(p, *args, **kwargs)

            with patch.object(Path, "read_text", deny_reservations_read):
                with self.assertRaises(PermissionError):
                    g._save_reservation(self.audit_log, "run-r1", "resv-fault", 10000, Decimal("0.00042"))

            # End-to-end gateway check: Second request fails on reservation read during _save_reservation (the second read)
            counter = [0]
            def fail_second_read(p, *args, **kwargs):
                if p.name.endswith(".reservations.json"):
                    counter[0] += 1
                    if counter[0] == 2:
                        raise PermissionError("controlled second read in save")
                return orig_read(p, *args, **kwargs)

            with patch.object(Path, "read_text", fail_second_read):
                second_receipt, _ = g.evaluate_gateway_request(
                    "run-r1", "operator", [cand], ["B" * 240000], True, True
                )
                self.assertEqual(second_receipt.gateway_decision, "REJECTED")

            # Ensure that the peer ledger was NOT overwritten with an empty dict.
            # Active tokens on disk must still account for the first 60k tokens.
            # Another 60k request must be REJECTED because 60k + 60k = 120k > 100k ceiling.
            third_receipt, _ = g.evaluate_gateway_request(
                "run-r1", "operator", [cand], ["C" * 240000], True, True
            )
            self.assertEqual(third_receipt.gateway_decision, "REJECTED")
            self.assertIn("exceed hard ceiling", " ".join(third_receipt.rejection_reasons))

    # -------------------------------------------------------------------------
    # R2: Disk write failure cleans up in-memory reservations
    # -------------------------------------------------------------------------
    def test_r2_write_rollback_leaves_no_phantom_reservations(self):
        """R2: If disk write fails, in-memory _ACTIVE_RESERVATIONS is rolled back cleanly."""
        xml_path = self._write_oa_xml(self.root / "valid.xml")
        cand = self._make_candidate(xml_path)

        with patch.object(g, "DEFAULT_AUDIT_LOG_PATH", self.audit_log):
            with patch.object(g.os, "replace", side_effect=PermissionError("controlled reservation publish fault")):
                receipt, _ = g.evaluate_gateway_request(
                    "run-r2", "operator", [cand], ["D" * 240000], True, True
                )
                self.assertEqual(receipt.gateway_decision, "REJECTED")

            # Check that _ACTIVE_RESERVATIONS has 0 entries for run-r2
            self.assertEqual(len(g._ACTIVE_RESERVATIONS.get("run-r2", {})), 0)

            # A subsequent healthy retry succeeds without hitting phantom reservation ceilings
            retry_receipt, _ = g.evaluate_gateway_request(
                "run-r2", "operator", [cand], ["E" * 240000], True, True
            )
            self.assertEqual(retry_receipt.gateway_decision, "AUTHORIZED")

    # -------------------------------------------------------------------------
    # R3: Provenance hash continuity between rights check and passage extraction
    # -------------------------------------------------------------------------
    def test_r3_provenance_hash_continuity_rejects_mutated_artifact(self):
        """R3: If physical artifact is altered between rights check and provenance check, request is rejected."""
        xml_path = self._write_oa_xml(self.root / "valid.xml")
        cand = self._make_candidate(xml_path)

        orig_verify = g.verify_paper_rights
        secret = "MUTATED UNAUTHORIZED TEXT"
        def mutate_after_rights(c):
            res = orig_verify(c)
            xml_path.write_text(secret, encoding="utf-8")
            return res

        with patch.object(g, "DEFAULT_AUDIT_LOG_PATH", self.audit_log):
            with patch.object(g, "verify_paper_rights", side_effect=mutate_after_rights):
                receipt, _ = g.evaluate_gateway_request(
                    "run-r3", "operator", [cand], [secret], True, True, verify_passage_provenance=True
                )
                self.assertEqual(receipt.gateway_decision, "REJECTED")
                self.assertFalse(receipt.provenance_verified)
                self.assertTrue(any("hash mismatch" in r.lower() or "provenance" in r.lower() for r in receipt.rejection_reasons))

    # -------------------------------------------------------------------------
    # R4: Non-causal survey percentages filtered and decrease verbs parse signed coefficients
    # -------------------------------------------------------------------------
    def test_r4_survey_rates_filtered_and_decrease_verbs_signed(self):
        """R4: Survey response rates are filtered out, while decrease verbs yield negative coefficients."""
        base = "ESG disclosure affects firm financial performance; "
        pos_finding = parse_user_finding(
            var_x="Corporate ESG Performance", var_y="Firm Financial Performance", direction="positive", coefficient=0.001
        )
        papers_survey = [
            {"key": "a", "title": "Study A", "abstract": base + "survey response rate of 40% was recorded."},
            {"key": "b", "title": "Study B", "abstract": base + "survey participation rate of 50% was observed."},
        ]
        res_survey = align_empirical_finding(pos_finding, papers_survey)
        self.assertIsNone(res_survey.prior_distribution_benchmark["literature_typical_range"])
        self.assertIsNone(res_survey.prior_distribution_benchmark["is_outlier"])

        neg_finding = parse_user_finding(
            var_x="Corporate ESG Performance", var_y="Firm Financial Performance", direction="negative", coefficient=-0.06
        )
        papers_decrease = [
            {"key": "a", "title": "Study A", "abstract": "ESG disclosure negatively affects firm performance; profitability decreases by 5%."},
            {"key": "b", "title": "Study B", "abstract": "ESG disclosure negatively affects firm performance; profitability decreases by 8%."},
        ]
        res_decrease = align_empirical_finding(neg_finding, papers_decrease)
        benchmark = res_decrease.prior_distribution_benchmark
        self.assertEqual(benchmark["literature_typical_range"], [-0.08, -0.05])
        self.assertFalse(benchmark["is_outlier"])

    # -------------------------------------------------------------------------
    # R5: Evidence binding rate validates physical file SHA-256 against recorded artifact_sha256
    # -------------------------------------------------------------------------
    def test_r5_evidence_binding_validates_physical_file_sha256(self):
        """R5: If physical file on disk does not match recorded artifact_sha256, binding rate is 0.0."""
        projects = self.root / "projects"
        init_project("test-binding", title="Controlled Binding Test", root=projects)
        pdir = projects / "test-binding"
        pdfdir = pdir / "pdfs"
        pdfdir.mkdir(parents=True, exist_ok=True)
        doc_path = pdfdir / "paper.pdf"

        with pymupdf.open() as d:
            d.new_page().insert_text((50, 72), "Methods\nWe use two-way fixed effects to identify employment effects for workers.")
            d.save(doc_path)

        orig_bytes = doc_path.read_bytes()
        (pdir / "refs.bib").write_text("@article{paper,title={Controlled Evidence Paper}}", encoding="utf-8")

        # Create altered replacement with different metadata
        with pymupdf.open(stream=orig_bytes, filetype="pdf") as d:
            d.set_metadata({"title": "Altered Metadata Paper"})
            altered_bytes = d.tobytes()

        orig_harvest = er.harvest_paper_evidence
        def harvest_then_mutate_disk(*args, **kwargs):
            result = orig_harvest(*args, **kwargs)
            doc_path.write_bytes(altered_bytes)
            return result

        with patch.object(er, "harvest_paper_evidence", side_effect=harvest_then_mutate_disk):
            _, report = er.generate_evidence_backed_review("test-binding", projects, with_prisma=False)

        self.assertGreater(report.total_claims, 0)
        self.assertEqual(report.binding_rate, 0.0)
        self.assertFalse(all(c["evidence"]["artifact_sha256"] == hashlib.sha256(doc_path.read_bytes()).hexdigest() for c in report.manifest))

    # -------------------------------------------------------------------------
    # R6: PyMuPDF evidence harvest binds artifact_sha256 to parsed in-memory doc.stream
    # -------------------------------------------------------------------------
    def test_r6_aba_snapshot_binding_to_pymupdf_stream(self):
        """R6: PyMuPDF evidence extraction binds artifact_sha256 to in-memory doc.stream, resilient to ABA disk swaps."""
        old_pdf = self.root / "old.pdf"
        new_pdf = self.root / "new.pdf"
        with pymupdf.open() as d:
            d.new_page().insert_text((50, 72), "Methods\nWe use two-way fixed effects.")
            d.save(old_pdf)
        with pymupdf.open() as d:
            d.new_page().insert_text((50, 72), "Methods\nWe use instrumental variables.")
            d.save(new_pdf)

        old_bytes = old_pdf.read_bytes()
        new_bytes = new_pdf.read_bytes()

        real_read = Path.read_bytes
        def aba_read(path, *args, **kwargs):
            if path == old_pdf:
                old_pdf.write_bytes(new_bytes)
                snapshot = real_read(path, *args, **kwargs)
                old_pdf.write_bytes(old_bytes)
                return snapshot
            return real_read(path, *args, **kwargs)

        with patch.object(Path, "read_bytes", aba_read):
            ev_dict = er.harvest_paper_evidence(old_pdf, {"key": "aba"})

        rows = [e.to_dict() for items in ev_dict.values() for e in items]
        expected_parsed_hash = hashlib.sha256(new_bytes).hexdigest()
        self.assertTrue(len(rows) > 0)
        for r in rows:
            self.assertEqual(r["artifact_sha256"], expected_parsed_hash)


if __name__ == "__main__":
    unittest.main()
