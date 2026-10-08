"""test_output/test_security_audit_4bc4377.py — Regression test suite for 4bc4377 security audit findings (F1–F5).

Covers all 5 confirmed security audit findings:
- [P1] F1: verify_paper_rights & passage extraction use in-memory frozen bytes; ABA swaps rejected.
- [P1] F2: PyMuPDF & text harvesting bind SHA-256 to parsed content; ABA swaps yield binding_rate 0.0.
- [P1] F3: Econometric percentage extraction covers base verb forms (decrease, reduce, drop, etc.),
          filters out negations (does not decrease), and ignores non-causal metrics (side effects).
- [P1] F4: Reservation liveness validates holding process PID (_is_pid_alive); prevents logical clock double spend.
- [P2] F5: Atomic rollback on partial reservation write failure preserves peer ledger integrity.
"""

import hashlib
import json
import os
import shutil
import tempfile
import time
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pymupdf as fitz

import pa_cli.evidence_review as er
import pa_cli.gateway as g
import pa_cli.provenance as prov
from pa_cli.align_findings import align_empirical_finding, parse_user_finding
from pa_cli.project import init_project


class TestSecurityAudit4BC4377(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.root = Path(self.tmpdir)
        self.audit_log = self.root / "audit.jsonl"
        g._ACTIVE_RESERVATIONS.clear()

    def tearDown(self):
        g._ACTIVE_RESERVATIONS.clear()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_oa_xml(self, path: Path, text: str = "Public evidence.", oa: bool = True, doi: str = "10.1234/test") -> Path:
        lic = '<permissions><license xlink:href="https://creativecommons.org/licenses/by/4.0/"/></permissions>' if oa else ''
        content = (
            f'<article xmlns:xlink="http://www.w3.org/1999/xlink"><front><article-meta>'
            f'<article-id pub-id-type="doi">{doi}</article-id>{lic}'
            f'</article-meta></front><body><p>{text}</p></body></article>'
        )
        path.write_bytes(content.encode("utf-8"))
        return path

    def _make_candidate(self, path: Path, doi: str = "10.1234/test") -> g.PaperEvaluationCandidate:
        return g.PaperEvaluationCandidate(
            "cand-p", str(path), doi, source="pmc_xml_only", url="https://eutils.ncbi.nlm.nih.gov"
        )

    def _make_pdf(self, text: str, title: str = "A") -> bytes:
        with fitz.open() as doc:
            doc.new_page().insert_text((50, 72), text)
            doc.set_metadata({"title": title})
            return doc.tobytes()

    # -------------------------------------------------------------------------
    # F1 (R3): Immutable in-memory byte snapshot prevents ABA swaps
    # -------------------------------------------------------------------------
    def test_f1_r3_rights_aba_swap_rejected(self):
        """F1: Non-OA paper swapped with OA during inspect_artifact is rejected and provenance unverified."""
        p = self.root / "p.xml"
        a = self.root / "non_oa.xml"
        self._write_oa_xml(p, text="Non OA confidential passage.", oa=False)
        self._write_oa_xml(a, text="Public evidence.", oa=True)
        b_bytes = a.read_bytes()
        a_bytes = p.read_bytes()

        cand = self._make_candidate(p)
        orig_inspect = g.inspect_artifact

        def swap_inspect(*args, **kwargs):
            p.write_bytes(b_bytes)
            try:
                return orig_inspect(*args, **kwargs)
            finally:
                p.write_bytes(a_bytes)

        with patch.object(g, "inspect_artifact", swap_inspect):
            receipt, _ = g.evaluate_gateway_request(
                "run-f1", "offline-auditor", [cand], ["Non OA confidential passage."],
                True, True, audit_file=self.audit_log, verify_passage_provenance=True,
            )

        self.assertEqual(receipt.gateway_decision, "REJECTED")
        self.assertFalse(receipt.provenance_verified)

    def test_f1_r3_parse_swap_rejected(self):
        """F1: Swapping paper text during text extraction fails provenance verification."""
        p = self.root / "p.xml"
        self._write_oa_xml(p, text="Public evidence.", oa=True)
        cand = self._make_candidate(p)

        orig_read = Path.read_text

        def swap_read(path_obj, *args, **kwargs):
            if path_obj == p:
                self._write_oa_xml(p, text="Secret replacement passage.", oa=False)
                try:
                    return orig_read(path_obj, *args, **kwargs)
                finally:
                    self._write_oa_xml(p, text="Public evidence.", oa=True)
            return orig_read(path_obj, *args, **kwargs)

        with patch.object(Path, "read_text", swap_read):
            receipt, _ = g.evaluate_gateway_request(
                "run-f1-parse", "offline-auditor", [cand], ["Secret replacement passage."],
                True, True, audit_file=self.audit_log, verify_passage_provenance=True,
            )

        self.assertEqual(receipt.gateway_decision, "REJECTED")
        self.assertFalse(receipt.provenance_verified)

    # -------------------------------------------------------------------------
    # F2 (R5/R6): PyMuPDF & text evidence harvesting and review binding
    # -------------------------------------------------------------------------
    def test_f2_r6_real_path_aba_binds_parsed_hash(self):
        """F2: Harvesting from real path binds SHA-256 to active document content."""
        text_a = "Methods\nWe use two-way fixed effects to identify employment effects for workers."
        text_b = "Methods\nWe use instrumental variables to identify employment effects for workers."
        a_pdf = self._make_pdf(text_a, "A")
        b_pdf = self._make_pdf(text_b, "B")
        b_sha = hashlib.sha256(b_pdf).hexdigest()

        p = self.root / "paper.pdf"
        p.write_bytes(a_pdf)

        orig_open = fitz.open

        class ClosingRestore:
            def __init__(self, doc, path, content):
                self.doc = doc
                self.path = path
                self.content = content

            def __getattr__(self, k):
                return getattr(self.doc, k)

            def __iter__(self):
                return iter(self.doc)

            def close(self):
                self.doc.close()
                self.path.write_bytes(self.content)

        def swap_open(*args, **kwargs):
            if args and str(args[0]) == str(p):
                p.write_bytes(b_pdf)
                doc = orig_open(*args, **kwargs)
                return ClosingRestore(doc, p, a_pdf)
            return orig_open(*args, **kwargs)

        with patch.object(er.fitz, "open", swap_open):
            buckets = er.harvest_paper_evidence(p, {"key": "paper"})

        rows = [ev.to_dict() for group in buckets.values() for ev in group]
        self.assertTrue(bool(rows))
        self.assertTrue(all(r["artifact_sha256"] == b_sha for r in rows))

    def test_f2_r5_parse_swap_yields_zero_binding_rate(self):
        """F2: Post-harvest file mutation detected during review verification yields binding_rate == 0.0."""
        text = "Methods\nWe use two-way fixed effects to identify employment effects for workers."
        a_pdf = self._make_pdf(text, "A")
        b_pdf = self._make_pdf(text, "changed")

        proj_root = self.root / "projects"
        init_project("case", root=proj_root)
        p = proj_root / "case" / "pdfs" / "paper.pdf"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(a_pdf)
        (proj_root / "case" / "refs.bib").write_text("@article{paper,title={Evidence test}}", encoding="utf-8")

        orig_harvest = er.harvest_paper_evidence
        real_read = Path.read_bytes
        harvest_done = False

        def wrapped_harvest(*args, **kwargs):
            nonlocal harvest_done
            res = orig_harvest(*args, **kwargs)
            harvest_done = True
            return res

        def swap_read(path_obj, *args, **kwargs):
            res = real_read(path_obj, *args, **kwargs)
            if path_obj == p and harvest_done:
                p.write_bytes(b_pdf)
            return res

        with patch.object(er, "harvest_paper_evidence", wrapped_harvest), patch.object(Path, "read_bytes", swap_read):
            _, review = er.generate_evidence_backed_review("case", proj_root, with_prisma=False)

        self.assertGreater(review.total_claims, 0)
        self.assertEqual(review.binding_rate, 0.0)

    # -------------------------------------------------------------------------
    # F3 (R4): Directional verb normalization, negation & non-causal filtering
    # -------------------------------------------------------------------------
    def test_f3_r4_base_verbs_and_negations(self):
        """F3: Base decrease verbs map to negative range; negations & side effects return None."""
        finding = parse_user_finding(
            var_x="Corporate ESG Performance",
            var_y="Firm Financial Performance",
            direction="negative",
            coefficient=-0.06,
        )

        # Base and conjugated negative verbs must produce [-0.08, -0.05]
        neg_cases = [
            "profitability decreases by {n}%.",
            "profits decrease by {n}%.",
            "profitability reduces by {n}%.",
            "profits reduce by {n}%.",
            "profitability drops by {n}%.",
            "profits drop by {n}%.",
            "profits decline by {n}%.",
        ]
        for sentence_tpl in neg_cases:
            papers = [
                {
                    "key": str(i),
                    "title": f"Study {i}",
                    "abstract": "ESG disclosure negatively affects firm performance; " + sentence_tpl.format(n=n),
                }
                for i, n in enumerate([5, 8])
            ]
            rep = align_empirical_finding(finding, papers)
            b = rep.prior_distribution_benchmark
            self.assertEqual(b.get("literature_typical_range"), [-0.08, -0.05], f"Failed for {sentence_tpl}")
            self.assertFalse(b.get("is_outlier"), f"Outlier mismatch for {sentence_tpl}")

        # Negations and non-causal metrics must be excluded (range None)
        filtered_cases = [
            "survey response rate of {n}% was recorded.",
            "survey response rate increases by {n}%.",
            "profitability does not increase by {n}%.",
            "profitability does not decrease by {n}%.",
            "side effects of {n}% were reported.",
        ]
        for sentence_tpl in filtered_cases:
            papers = [
                {
                    "key": str(i),
                    "title": f"Study {i}",
                    "abstract": "ESG disclosure negatively affects firm performance; " + sentence_tpl.format(n=n),
                }
                for i, n in enumerate([5, 8])
            ]
            rep = align_empirical_finding(finding, papers)
            b = rep.prior_distribution_benchmark
            self.assertIsNone(b.get("literature_typical_range"), f"Should be filtered: {sentence_tpl}")

    # -------------------------------------------------------------------------
    # F4: PID liveness prevents premature lease expiration of active processes
    # -------------------------------------------------------------------------
    def test_f4_live_process_reservation_retained_past_300s(self):
        """F4: Uncommitted reservations from live PIDs are retained even if logical age > 300s."""
        resv_path = g._get_resv_path(self.audit_log)
        self.root.mkdir(parents=True, exist_ok=True)

        my_pid = os.getpid()
        ledger = {
            "run-live": {
                "resv-1": {
                    "tokens": 60000,
                    "cost": "0.00252",
                    "timestamp": 1000.0,
                    "pid": my_pid,
                }
            }
        }
        resv_path.write_text(json.dumps(ledger), encoding="utf-8")

        # Simulate logical clock advance to 1301s (age = 301s > 300s)
        with patch.object(g.time, "time", return_value=1301.0):
            loaded = g._load_all_reservations(self.audit_log)

        self.assertIn("run-live", loaded)
        self.assertIn("resv-1", loaded["run-live"])
        self.assertEqual(loaded["run-live"]["resv-1"][0], 60000)

    # -------------------------------------------------------------------------
    # F5 (R2): Atomic rollback on partial reservation write preserves ledger
    # -------------------------------------------------------------------------
    def test_f5_r2_partial_write_atomic_rollback(self):
        """F5: Disk failure during ledger save restores original peer reservations."""
        resv_path = g._get_resv_path(self.audit_log)
        self.root.mkdir(parents=True, exist_ok=True)

        peer_ledger = {
            "run-shared": {
                "peer-resv": {
                    "tokens": 60000,
                    "cost": "0.00252",
                    "timestamp": time.time(),
                    "pid": os.getpid(),
                }
            }
        }
        orig_content = json.dumps(peer_ledger, ensure_ascii=False)
        resv_path.write_text(orig_content, encoding="utf-8")

        orig_write = Path.write_text

        def failing_write(path_obj, text, *args, **kwargs):
            if path_obj == resv_path:
                orig_write(path_obj, text[:12], *args, **kwargs)
                raise OSError("simulated disk full midway through write")
            return orig_write(path_obj, text, *args, **kwargs)

        with patch.object(Path, "write_text", failing_write):
            with self.assertRaises(OSError):
                g._save_reservation(self.audit_log, "run-shared", "my-resv", 30000, Decimal("0.00126"))

        # Original uncorrupted peer reservation must be preserved exactly
        restored = resv_path.read_text(encoding="utf-8")
        self.assertEqual(restored, orig_content)
        data = json.loads(restored)
        self.assertIn("peer-resv", data["run-shared"])


if __name__ == "__main__":
    unittest.main()
