"""Repeat bounded, generated-only core capacity and engine fault checks offline."""
import argparse
import os
from pathlib import Path
import socket
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def deny_connection(*args, **kwargs):
    raise OSError("Network disabled in capability stress gate")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rounds", type=int, default=3)
    args = parser.parse_args()
    if not 1 <= args.rounds <= 20:
        parser.error("rounds must be between 1 and 20")
    sys.path.insert(0, str(ROOT))
    import pytest
    scratch = ROOT / ".pytest_temp"
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch, prefix="capability-") as directory:
        old_temp = tempfile.tempdir
        try:
            tempfile.tempdir = directory
            with patch.dict(os.environ, TEMP=directory, TMP=directory), \
                 patch.object(socket.socket, "connect", deny_connection), \
                 patch.object(socket, "create_connection", deny_connection):
                for index in range(args.rounds):
                    print(f"Offline capability round {index + 1}/{args.rounds}", flush=True)
                    result = pytest.main([str(ROOT / "test_output/test_capability_stress.py"),
                                          str(ROOT / "test_output/test_engine_maintenance.py"),
                                          str(ROOT / "test_output/test_live_workflow_repair.py"), "-q",
                                          "--basetemp=" + str(Path(directory) / str(index))])
                    if result:
                        return int(result)
        finally:
            tempfile.tempdir = old_temp
    print("Offline capability stress gate PASSED", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
