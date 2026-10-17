import importlib.util
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

SPEC = importlib.util.spec_from_file_location("release_gate", Path(__file__).resolve().parents[1] / "tools/release_quality_gate.py")
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


def report(tmp_path, platform="win32", extra=None, omit=None):
    root = ET.Element("testsuite")
    for identity, reason in gate.allowed_skips(platform).items():
        if identity == omit:
            continue
        cls, name = identity.rsplit(".", 1)
        case = ET.SubElement(root, "testcase", classname=cls, name=name)
        ET.SubElement(case, "skipped", message=reason)
    for module in ("test_local_claim_entrypoints", "test_v413_round2_repairs", "test_v413_round2_boundaries"):
        ET.SubElement(root, "testcase", classname=f"tests.{module}.Checks", name="test_contract")
    if extra:
        extra(root)
    path = tmp_path / "report.xml"
    ET.ElementTree(root).write(path)
    return gate.inspect_junit(path, platform)


@pytest.mark.parametrize("platform,count", [("win32", 8), ("linux", 9)])
def test_missing_data_remain_explicitly_unexecuted(tmp_path, platform, count):
    result = report(tmp_path, platform)
    assert result["passed"]
    assert result["tests_passed"] == 3
    assert len(result["skipped_unexecuted"]) == count


def test_unexpected_skip_blocks_release(tmp_path):
    def extra(root):
        case = ET.SubElement(root, "testcase", classname="tests.other", name="test_new")
        ET.SubElement(case, "skipped", message="optional dependency absent")
    assert not report(tmp_path, extra=extra)["passed"]


def test_failure_blocks_release(tmp_path):
    def extra(root):
        case = ET.SubElement(root, "testcase", classname="tests.other", name="test_new")
        ET.SubElement(case, "failure", message="bad")
    assert not report(tmp_path, extra=extra)["passed"]


def test_removed_missing_test_cannot_disappear_from_denominator(tmp_path):
    identity = next(iter(gate.allowed_skips("win32")))
    result = report(tmp_path, omit=identity)
    assert not result["passed"] and result["missing_required_tests"] == [identity]


def test_wrong_skip_reason_not_whitelisted(tmp_path):
    result = report(tmp_path)
    path = tmp_path / "report.xml"
    tree = ET.parse(path)
    next(tree.getroot().iter("skipped")).set("message", "network failed")
    tree.write(path)
    assert not gate.inspect_junit(path, "win32")["passed"]
