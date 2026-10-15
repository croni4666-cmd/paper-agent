"""Generated offline contracts and failure isolation for local snapshot reports."""
import copy
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from click.testing import CliRunner

from pa_cli.cli import main
from pa_cli import run_report as rr


def search(ok=True):
    return dict(engine_status={"fixture": "ok" if ok else "error"},
                engine_errors={} if ok else {"fixture": "private-token"},
                by_engine={"fixture": 1 if ok else 0}, dedup_count=1 if ok else 0,
                results=[{"title": "private-token"}] if ok else [])


def batch(rows):
    skipped = sum(row.get("error") in ("skipped-existing", "global-timeout") for row in rows)
    success = sum(row["success"] and row.get("error") != "skipped-existing" for row in rows)
    return dict(n_total=len(rows), n_success=success, n_failure=len(rows)-skipped-success,
                n_skipped=skipped, results=rows)


class RunReportTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)

    def put(self, kind, data):
        path = self.root / (kind + ".json")
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def report(self, kind, data):
        return rr.build_report({kind: self.put(kind, data)})

    def test_search_success_and_exact_snapshot_hash(self):
        path = self.put("search", search())
        result = rr.build_report({"search": path})
        self.assertEqual(result["overall_status"], "success")
        self.assertEqual(result["stages"][0]["snapshot_sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(result["omitted_stages"], ["fetch", "review"])

    def test_search_failed_and_partial(self):
        self.assertEqual(self.report("search", search(False))["overall_status"], "failed")
        data = search()
        data["engine_status"]["other"] = "error"
        data["engine_errors"]["other"] = "private-token"
        data["by_engine"]["other"] = 0
        self.assertEqual(self.report("search", data)["overall_status"], "partial")

    def test_search_empty_is_not_failure(self):
        data = search()
        data.update(results=[], dedup_count=0, by_engine={"fixture": 0})
        self.assertEqual(self.report("search", data)["overall_status"], "success")

    def test_search_contradictions_unknown(self):
        mutations = [dict(dedup_count=True), dict(dedup_count=9), dict(by_engine={}),
                     dict(engine_status={"fixture": []}), dict(engine_errors={"fixture": "failure"}),
                     dict(results=[{"error": "failure"}]), dict(status="failed")]
        for changes in mutations:
            with self.subTest(changes=changes):
                data = search()
                data.update(changes)
                self.assertEqual(self.report("search", data)["overall_status"], "unknown")

    def test_skip_existing_and_timeout_are_distinct(self):
        data = batch([dict(success=True, error="skipped-existing"), dict(success=False, error="global-timeout")])
        result = self.report("fetch", data)
        self.assertEqual(result["overall_status"], "partial")
        counts = result["stages"][0]["counts"]
        self.assertEqual((counts["n_skipped"], counts["reported_available"], counts["timed_out"]), (2, 1, 1))

    def test_batch_all_outcomes(self):
        for rows, expected in [([], "unknown"), ([dict(success=True)], "success"),
                               ([dict(success=False, error="global-timeout")], "failed"),
                               ([dict(success=False, error="private-token")], "failed")]:
            with self.subTest(expected=expected):
                self.assertEqual(self.report("fetch", batch(rows))["overall_status"], expected)

    def test_current_batch_producer_contract(self):
        from pa_cli.fetch_batch import FetchResult, FetchSummary
        summary = FetchSummary(n_total=3, n_success=1, n_skipped=2, results=[
            FetchResult("a", "", "Fixture", True),
            FetchResult("b", "", "Fixture", True, error="skipped-existing"),
            FetchResult("c", "", "Fixture", False, error="global-timeout"),
        ])
        self.assertEqual(self.report("fetch", summary.to_dict())["overall_status"], "partial")

    def test_report_reads_only_selected_descriptor_without_dispatch(self):
        path = self.put("review", dict(status="completed", mode="clustering", corpus="do-not-open", output="do-not-open"))
        with patch.object(rr.os, "open", wraps=rr.os.open) as opened, \
             patch.object(Path, "open", side_effect=AssertionError("unselected file read")), \
             patch.object(socket.socket, "connect", side_effect=AssertionError("network")), \
             patch.object(subprocess, "Popen", side_effect=AssertionError("dispatch")):
            result = rr.build_report({"review": path})
        self.assertEqual(result["overall_status"], "success")
        self.assertEqual(opened.call_count, 1)
        self.assertEqual(opened.call_args.args[0], path)

    def test_batch_corrupt_counts_and_boolean_types(self):
        original = batch([dict(success=True)])
        for changes in [dict(n_success=True), dict(n_total=2), dict(n_skipped=-1),
                        dict(results=[dict(success="true")]), dict(results=[dict(success=True, error="bad")])]:
            data = copy.deepcopy(original)
            data.update(changes)
            self.assertEqual(self.report("fetch", data)["overall_status"], "unknown")

    def test_wrapper_batch_failure_downgrades_complete_rows(self):
        data = dict(summary=batch([dict(success=True)]), status="partial", exit_code=1, cli_exit_code=3)
        self.assertEqual(self.report("fetch", data)["overall_status"], "partial")
        data["status"] = "success"
        self.assertEqual(self.report("fetch", data)["overall_status"], "unknown")
        data.update(status="partial", cli_exit_code=-9)
        self.assertEqual(self.report("fetch", data)["overall_status"], "partial")

    def test_review_receipt_is_explicitly_unverified(self):
        data = dict(status="completed", corpus="private-token", output="https://private-token", mode="synthesis")
        with patch.object(rr, "_snapshot", wraps=rr._snapshot) as read:
            result = self.report("review", data)
        self.assertEqual(read.call_count, 1)
        self.assertFalse(result["stages"][0]["counts"]["artifact_verified"])
        self.assertEqual(result["overall_status"], "success")
        self.assertNotIn("private-token", json.dumps(result))
        data["error"] = "pa_review_failed"
        self.assertEqual(self.report("review", data)["overall_status"], "unknown")

    def test_review_failure_and_unknown_manifest(self):
        self.assertEqual(self.report("review", {"error": "review_timeout"})["overall_status"], "failed")
        self.assertEqual(self.report("review", {"error": "pa_review_failed", "exit_code": 0})["overall_status"], "unknown")
        self.assertEqual(self.report("review", {"binding_rate": 1.0})["overall_status"], "unknown")

    def test_unknown_isolated_from_healthy_stage(self):
        result = rr.build_report({"search": self.put("search", search()), "fetch": self.root / "private-token"})
        self.assertEqual([stage["status"] for stage in result["stages"]], ["success", "unknown"])
        self.assertEqual(result["overall_status"], "unknown")
        self.assertNotIn("private-token", json.dumps(result))

    def test_duplicate_keys_nonfinite_invalid_json_and_version_rejected(self):
        path = self.root / "input.json"
        for raw in [b'{"results":[],"results":[]}', b'{"x":NaN}', b'{"x":Infinity}', b'{"x":1e999}', b'[]', b'not JSON',
                    b'\xff', json.dumps(dict(search(), schema_version=999)).encode(),
                    ("["*1200 + "]"*1200).encode()]:
            path.write_bytes(raw)
            with self.subTest(raw=raw[:40]):
                result = rr.build_report({"search": path})
                self.assertEqual(result["overall_status"], "unknown")

    def test_digest_and_state_stay_with_captured_bytes_after_source_change(self):
        path = self.put("search", search())
        raw = path.read_bytes()
        snapshot = rr._snapshot
        def changing_snapshot(selected):
            captured = snapshot(selected)
            path.write_text(json.dumps(search(False)), encoding="utf-8")
            return captured
        with patch.object(rr, "_snapshot", side_effect=changing_snapshot):
            result = rr.build_report({"search": path})
        self.assertEqual(result["overall_status"], "success")
        self.assertEqual(result["stages"][0]["snapshot_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertNotEqual(path.read_bytes(), raw)

    def test_limits_and_directory(self):
        path = self.put("search", search())
        with patch.object(rr, "MAX_INPUT_BYTES", 8):
            self.assertEqual(rr.build_report({"search": path})["overall_status"], "unknown")
        self.assertEqual(rr.build_report({"search": self.root})["overall_status"], "unknown")

    @unittest.skipUnless(hasattr(os, "mkfifo"), "POSIX FIFO test")
    def test_fifo_does_not_block(self):
        path = self.root / "fifo"
        os.mkfifo(path)
        self.assertEqual(rr.build_report({"search": path})["overall_status"], "unknown")

    def test_no_inputs_or_unknown_kind(self):
        for inputs in ({}, {"other": "unused"}):
            with self.assertRaises(ValueError):
                rr.build_report(inputs)

    def test_markdown_all_rows_contiguous_and_no_raw_text(self):
        report = rr.build_report({"search": self.put("search", search()), "fetch": self.put("fetch", batch([]))})
        text = rr.render_markdown(report)
        self.assertNotIn("private-token", text)
        self.assertIn("| search | success |", text)
        self.assertIn("| fetch | unknown |", text)
        self.assertLess(text.index("| fetch |"), text.index("search counts:"))

    def test_cli_bypasses_private_config_and_strict_unknown(self):
        path = self.put("search", search())
        with patch("pa_cli.keys.load_env_into_environ", side_effect=AssertionError("private read")), \
             patch("pa_cli.keys.cmd_remind", side_effect=AssertionError("private read")):
            result = CliRunner().invoke(main, ["run-report", "--search", str(path), "--format", "json", "--strict"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(json.loads(result.output)["overall_status"], "success")
        missing = CliRunner().invoke(main, ["run-report", "--fetch", str(self.root / "missing"), "--strict", "--format", "json"])
        self.assertEqual(missing.exit_code, 1)
        self.assertEqual(json.loads(missing.output)["overall_status"], "unknown")
        self.assertEqual(CliRunner().invoke(main, ["run-report"]).exit_code, 2)

    def test_atomic_output_and_input_alias_protection(self):
        source = self.put("search", search())
        before = source.read_bytes()
        with self.assertRaises(ValueError):
            rr.write_report(source, "replace", [source])
        alias = self.root / "hardlink.json"
        os.link(source, alias)
        with self.assertRaises(ValueError):
            rr.write_report(alias, "replace", [source])
        self.assertEqual(source.read_bytes(), before)
        output = self.root / "report.json"
        rr.write_report(output, "complete", [source])
        self.assertEqual(output.read_text(), "complete")

    def test_publish_failures_preserve_existing_output_and_clean_temp(self):
        output = self.root / "report.json"
        output.write_text("previous")
        for target in ("fsync", "replace"):
            with patch.object(rr.os, target, side_effect=OSError("private-token")):
                with self.assertRaises(OSError):
                    rr.write_report(output, "new", [])
            self.assertEqual(output.read_text(), "previous")
            self.assertFalse(list(self.root.glob(".pa-run-report-*")))

    def test_cli_output_failure_is_sanitized(self):
        path = self.put("search", search())
        with patch.object(rr.os, "replace", side_effect=OSError("private-token")):
            result = CliRunner().invoke(main, ["run-report", "--search", str(path), "--output", str(self.root / "out")])
        self.assertEqual(result.exit_code, 1)
        self.assertNotIn("private-token", result.output)
        self.assertFalse((self.root / "out").exists())


if __name__ == "__main__":
    unittest.main()
