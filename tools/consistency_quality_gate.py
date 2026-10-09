"""Offline pre-push gate for evidence and gateway consistency fixes.

Run from any directory with the repository's [test] dependencies installed.
"""
from __future__ import annotations

import argparse
import compileall
import os
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
TEST_FILES = [
    "test_output/test_process_identity_v4.py",
    "test_output/test_gateway_store_v4.py",
    "test_output/test_gateway_v4.py",
    "test_output/test_consistency_boundaries.py",
    "test_output/test_security_audit_4bc4377.py",
    "test_output/test_rereview_findings_c75087e.py",
    "test_output/test_gateway_p3_34.py",
    "test_output/test_evidence_review_p2_20.py",
    "test_output/test_align_findings_p2_23.py",
    "test_output/test_rereview_findings_f1_f5.py",
    "test_output/test_rereview_findings_4a0cb65.py",
    "test_output/test_rereview_findings_6ce58eb.py",
]


def deny_connection(*args, **kwargs):
    raise OSError("Network access is disabled in the consistency quality gate")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stress-runs", type=int, default=3)
    args = parser.parse_args()
    if args.stress_runs < 1:
        parser.error("--stress-runs must be positive")

    subprocess.run(["git", "diff", "--check", "HEAD"], cwd=ROOT, check=True)
    if not compileall.compile_dir(ROOT / "pa_cli", quiet=1):
        return 1

    sys.path.insert(0, str(ROOT))
    import pytest
    import pa_cli.gateway as gateway

    scratch = ROOT / ".pytest_temp"
    scratch.mkdir(exist_ok=True)
    old_temp = tempfile.tempdir
    try:
        with tempfile.TemporaryDirectory(prefix="consistency-gate-", dir=scratch) as directory:
            run_dir = Path(directory)
            tempfile.tempdir = directory
            with patch.dict(os.environ, {"TEMP": directory, "TMP": directory}), \
                    patch.object(gateway, "DEFAULT_AUDIT_LOG_PATH", run_dir / "audit.jsonl"), \
                    patch.object(socket.socket, "connect", deny_connection), \
                    patch.object(socket, "create_connection", deny_connection):
                status = pytest.main([str(ROOT / path) for path in TEST_FILES]
                                     + ["-q", "--basetemp=" + str(run_dir / "pytest")])
                if status:
                    return int(status)
                for index in range(args.stress_runs):
                    print(f"Consistency boundary stress run {index + 1}/{args.stress_runs}", flush=True)
                    suite = unittest.defaultTestLoader.loadTestsFromName("test_output.test_consistency_boundaries")
                    if not unittest.TextTestRunner(verbosity=1).run(suite).wasSuccessful():
                        return 1
                    if pytest.main([str(ROOT / "test_output/test_gateway_store_v4.py"),
                                    str(ROOT / "test_output/test_gateway_v4.py"), "-q",
                                    "--basetemp=" + str(run_dir / f"v4-stress-{index}")]):
                        return 1
    finally:
        tempfile.tempdir = old_temp
    print("Consistency quality gate PASSED", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
