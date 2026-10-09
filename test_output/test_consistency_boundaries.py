"""Offline regressions for snapshot, linguistic, and reservation fault boundaries."""
import ctypes
import errno
import hashlib
import json
import multiprocessing as mp
import os
import tempfile
import time
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pymupdf as fitz
import pa_cli.evidence_review as er
import pa_cli.gateway as g
from pa_cli.align_findings import align_empirical_finding, parse_user_finding
from pa_cli.project import init_project

TEXT = "Methods\nWe use two-way fixed effects to identify employment effects for workers."


def write_oa(path):
    path.write_bytes(b'<article xmlns:xlink="http://www.w3.org/1999/xlink"><front>'
                     b'<article-meta><article-id pub-id-type="doi">10.1234/test</article-id>'
                     b'<permissions><license xlink:href="https://creativecommons.org/licenses/by/4.0/"/>'
                     b'</permissions></article-meta></front><body><p>Public evidence.</p></body></article>')


def evaluate(root, passages, **extra):
    return g._evaluate_legacy_gateway_request(
        "shared", "offline", [g.PaperEvaluationCandidate(
            "paper", str(root / "public.xml"), "10.1234/test",
            source="pmc_xml_only", url="https://eutils.ncbi.nlm.nih.gov")],
        passages, True, True, max_cost_usd_limit="0.004",
        audit_file=root / "audit.jsonl", **extra)[0]


def pending_worker(root, ready, release, results):
    root = Path(root)
    original = g.record_gateway_audit_event

    def delayed_record(receipt, **kwargs):
        ready.set()
        if not release.wait(15):
            raise TimeoutError("test did not release pending reservation")
        return original(receipt, **kwargs)

    try:
        with patch.object(g, "record_gateway_audit_event", delayed_record):
            results.put(evaluate(root, ["A" * 240000]).gateway_decision)
    except Exception as exc:
        results.put(repr(exc))


class TestConsistencyBoundaries(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.audit = self.root / "audit.jsonl"
        self.ledger = g._get_resv_path(self.audit)
        g._ACTIVE_RESERVATIONS.clear()
        self.addCleanup(g._ACTIVE_RESERVATIONS.clear)
        write_oa(self.root / "public.xml")

    def peer(self, pid=None):
        data = {"shared": {"peer": {"tokens": 60000, "cost": "0.00252",
                "timestamp": 1000.0, "pid": os.getpid() if pid is None else pid}}}
        self.ledger.write_bytes((json.dumps(data, indent=2).replace("\n", "\r\n") + "\r\n").encode())
        return self.ledger.read_bytes()

    def test_blocked_empty_payload_is_not_provenance_verified(self):
        (self.root / "public.xml").write_bytes(b"<article/>")
        receipt = evaluate(self.root, [], verify_passage_provenance=True)
        self.assertEqual(receipt.gateway_decision, "REJECTED")
        self.assertFalse(receipt.provenance_verified)

    def test_pdf_parse_uses_captured_bytes_despite_path_mutation(self):
        path = self.root / "paper.pdf"
        with fitz.open() as doc:
            doc.new_page().insert_text((50, 72), TEXT)
            original = doc.tobytes()
        with fitz.open() as doc:
            doc.new_page().insert_text((50, 72), "Methods\nWe use instrumental variables for employment.")
            replacement = doc.tobytes()
        path.write_bytes(original)
        real_open = er.fitz.open

        def concurrent_writer(*args, **kwargs):
            path.write_bytes(replacement)
            return real_open(*args, **kwargs)

        with patch.object(er.fitz, "open", concurrent_writer):
            rows = [e for group in er.harvest_paper_evidence(path, {"key": "p"}).values() for e in group]
        self.assertTrue(rows)
        self.assertTrue(all(e.artifact_sha256 == hashlib.sha256(original).hexdigest() for e in rows))
        self.assertIn("two-way fixed effects", rows[0].excerpt)

    def test_read_failure_cannot_produce_file_bound_evidence(self):
        path = self.root / "paper.txt"
        path.write_text(TEXT, encoding="utf-8")
        with patch.object(Path, "read_bytes", side_effect=PermissionError("denied")):
            rows = [e for group in er.harvest_paper_evidence(path, {"key": "p"}).values() for e in group]
        self.assertFalse(any(e.page > 0 for e in rows))

    def test_text_hash_is_physical_bytes_and_spans_verify(self):
        root = self.root / "projects"
        init_project("case", root=root)
        path = root / "case" / "pdfs" / "paper.txt"
        (root / "case" / "refs.bib").write_text('@article{paper,title={Study}}', encoding="utf-8")
        for data in (TEXT.replace("\n", "\r\n").encode(), b"\xff" + TEXT.encode()):
            with self.subTest(data=data[:8]):
                path.write_bytes(data)
                _, report = er.generate_evidence_backed_review("case", root, with_prisma=False)
                self.assertGreater(report.total_claims, 0)
                self.assertTrue(all(c["evidence"]["artifact_sha256"] == hashlib.sha256(data).hexdigest()
                                    for c in report.manifest))
                self.assertEqual(report.binding_rate, 1.0)

    def test_ambiguous_percentages_do_not_contribute_benchmarks(self):
        finding = parse_user_finding(var_x="Corporate ESG Performance", var_y="Firm Financial Performance",
                                     direction="negative", coefficient=-0.06)
        tails = ("profits failed to decrease by {n}%.", "profits don't decrease by {n}%.",
                 "profits didn’t decrease by {n}%.", "profits did not appear to decrease by {n}%.",
                 "survey attrition rate declines by {n}%.", "survey retention rate lowered by {n}%.",
                 "side effects decrease by {n}%.", "profits might decrease by {n}%.",
                 "profits not only decrease by {n}%.", "profits backdrop by {n}%.",
                 "profits show a drop of {n}%.", "side-effects decrease by {n}%.")
        for tail in tails:
            with self.subTest(tail=tail):
                papers = [{"key": str(n), "title": f"Study {n}", "abstract":
                           "ESG disclosure negatively affects firm performance; " + tail.format(n=n)}
                          for n in (5, 8)]
                result = align_empirical_finding(finding, papers)
                self.assertIsNone(result.prior_distribution_benchmark["literature_typical_range"])

    def test_negation_in_previous_clause_does_not_hide_real_effect(self):
        finding = parse_user_finding(var_x="Corporate ESG Performance", var_y="Firm Financial Performance",
                                     direction="negative", coefficient=-0.06)
        papers = [{"key": str(n), "title": f"Study {n}", "abstract":
                   f"ESG disclosure negatively affects firm performance; profits did not change; profits decrease by {n}%."}
                  for n in (5, 8)]
        self.assertEqual(align_empirical_finding(finding, papers).prior_distribution_benchmark[
            "literature_typical_range"], [-0.08, -0.05])

    def test_posix_permission_error_retains_peer_budget(self):
        self.peer(pid=99999)
        with patch.object(g.sys, "platform", "linux"), patch.object(g.os, "kill", side_effect=PermissionError(errno.EPERM, "denied")), patch.object(g.time, "time", return_value=1301):
            receipt = evaluate(self.root, ["B" * 240000])
        self.assertEqual(receipt.gateway_decision, "REJECTED")
        self.assertIn("peer", json.loads(self.ledger.read_text())["shared"])

    @unittest.skipUnless(os.name == "nt", "Windows API fault")
    def test_windows_query_error_retains_peer_budget(self):
        self.peer(pid=99999)
        api = MagicMock()
        api.OpenProcess.return_value = 0
        with patch.object(ctypes, "WinDLL", return_value=api), patch.object(ctypes, "get_last_error", return_value=5), patch.object(g.time, "time", return_value=1301):
            receipt = evaluate(self.root, ["B" * 240000])
        self.assertEqual(receipt.gateway_decision, "REJECTED")

    @unittest.skipUnless(os.name == "nt", "Windows API fault")
    def test_windows_exit_code_query_failure_cannot_release_budget(self):
        self.peer(pid=99999)
        api = MagicMock()
        api.OpenProcess.return_value = 1234
        api.GetExitCodeProcess.return_value = 0
        with patch.object(ctypes, "WinDLL", return_value=api), patch.object(g.time, "time", return_value=1301):
            self.assertEqual(evaluate(self.root, ["B" * 240000]).gateway_decision, "REJECTED")

    def test_unknown_pid_result_is_not_expiration(self):
        self.peer(pid=99999)
        with patch.object(g, "_is_pid_alive", return_value=None), patch.object(g.time, "time", return_value=1301):
            self.assertIn("peer", g._load_all_reservations(self.audit).get("shared", {}))
            g._save_reservation(self.audit, "other", "new", 1, Decimal("0"))
            g._remove_reservation(self.audit, "other", "new")
        self.assertIn("peer", json.loads(self.ledger.read_text())["shared"])

    def test_legacy_pidless_reservation_is_not_silently_expired(self):
        self.peer()
        data = json.loads(self.ledger.read_text())
        del data["shared"]["peer"]["pid"]
        self.ledger.write_text(json.dumps(data))
        with patch.object(g.time, "time", return_value=1301):
            self.assertIn("peer", g._load_all_reservations(self.audit).get("shared", {}))

    def test_confirmed_dead_pid_allows_expiration(self):
        self.peer(pid=99999)
        with patch.object(g.sys, "platform", "linux"), patch.object(g.os, "kill", side_effect=ProcessLookupError(errno.ESRCH, "gone")), patch.object(g.time, "time", return_value=1301):
            self.assertNotIn("peer", g._load_all_reservations(self.audit).get("shared", {}))

    def test_replace_failure_preserves_exact_bytes_and_retry(self):
        original = self.peer()
        with patch.object(g.os, "replace", side_effect=OSError(errno.ENOSPC, "disk full")):
            with self.assertRaises(OSError):
                g._save_reservation(self.audit, "shared", "new", 10000, Decimal("0.00042"))
        self.assertEqual(self.ledger.read_bytes(), original)
        self.assertFalse(g._ACTIVE_RESERVATIONS)
        g._save_reservation(self.audit, "shared", "new", 10000, Decimal("0.00042"))
        self.assertIn("peer", json.loads(self.ledger.read_text())["shared"])

    def test_fsync_failure_preserves_peer_ledger(self):
        original = self.peer()
        with patch.object(g.os, "fsync", side_effect=OSError(errno.ENOSPC, "still full")):
            with self.assertRaises(OSError):
                g._save_reservation(self.audit, "shared", "new", 10000, Decimal("0.00042"))
        self.assertEqual(self.ledger.read_bytes(), original)
        self.assertFalse(g._ACTIVE_RESERVATIONS)

    def test_partial_temporary_write_preserves_peer_ledger(self):
        original = self.peer()
        real_fdopen = os.fdopen

        class FailingWriter:
            def __init__(self, file):
                self.file = file

            def __enter__(self):
                return self

            def __exit__(self, *args):
                self.file.close()

            def write(self, content):
                self.file.write(content[:12])
                self.file.flush()
                raise OSError(errno.ENOSPC, "partial temp write")

        with patch.object(g.os, "fdopen", side_effect=lambda *args, **kwargs: FailingWriter(real_fdopen(*args, **kwargs))):
            with self.assertRaises(OSError):
                g._save_reservation(self.audit, "shared", "new", 10000, Decimal("0.00042"))
        self.assertEqual(self.ledger.read_bytes(), original)
        self.assertFalse(g._ACTIVE_RESERVATIONS)

    def test_persistent_write_fault_does_not_poison_next_request(self):
        original = self.peer()
        with patch.object(g.os, "fsync", side_effect=OSError(errno.ENOSPC, "disk remains full")):
            self.assertEqual(evaluate(self.root, ["B" * 40000]).gateway_decision, "REJECTED")
        self.assertEqual(self.ledger.read_bytes(), original)
        self.assertEqual(evaluate(self.root, ["C" * 240000]).gateway_decision, "REJECTED")

    def test_remove_failure_does_not_destroy_peer_or_release_memory(self):
        self.peer()
        g._save_reservation(self.audit, "other", "new", 1, Decimal("0"))
        original = self.ledger.read_bytes()
        with patch.object(g.os, "replace", side_effect=OSError("replace failed")):
            with self.assertRaises(OSError):
                g._remove_reservation(self.audit, "other", "new")
        self.assertEqual(self.ledger.read_bytes(), original)
        self.assertIn("new", g._ACTIVE_RESERVATIONS["other"])

    def test_existing_empty_or_invalid_ledger_rejects_allocation(self):
        for raw in ("", "[]", '{"shared": null}', '{"shared": {"peer": "broken"}}'):
            with self.subTest(raw=raw):
                self.ledger.write_text(raw)
                self.assertEqual(evaluate(self.root, ["healthy request"]).gateway_decision, "REJECTED")

    def test_real_pending_process_stays_reserved_on_query_uncertainty(self):
        ctx = mp.get_context("spawn")
        ready, release, results = ctx.Event(), ctx.Event(), ctx.Queue()
        process = ctx.Process(target=pending_worker, args=(str(self.root), ready, release, results))
        process.start()
        try:
            self.assertTrue(ready.wait(10))
            self.assertTrue(process.is_alive())
            self.assertTrue(g._is_pid_alive(process.pid))
            with patch.object(g.time, "time", return_value=time.time() + 301), patch.object(g, "_is_pid_alive", return_value=None):
                receipt = evaluate(self.root, ["B" * 240000])
            self.assertEqual(receipt.gateway_decision, "REJECTED")
        finally:
            release.set()
            process.join(10)
            if process.is_alive():
                process.terminate()
                process.join()
        self.assertEqual(process.exitcode, 0)
        self.assertEqual(results.get(timeout=3), "AUTHORIZED")
        results.close()


if __name__ == "__main__":
    unittest.main()
