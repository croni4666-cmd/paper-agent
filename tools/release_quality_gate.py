"""Run the full offline suite; reject failures and undeclared skipped tests.

This gate does not certify online availability or replace exact-commit CI and
artifact inspection. Missing original data are recorded as unexecuted, not passed.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS_MODULE = "test_output.test_labels_real_corpus"
CORPUS_TESTS = {
    "TestRealCorpusEndToEnd.test_custom_labels_override_on_real_corpus",
    "TestRealCorpusEndToEnd.test_domain_stopwords_auto_mines_real_corpus",
    "TestRealCorpusEndToEnd.test_domain_stopwords_via_cli_flag_flows_through",
    "TestRealCorpusEndToEnd.test_topics_json_schema_on_disk",
    "TestRealCorpusCLI.test_cli_custom_labels_end_to_end",
    "TestRealCorpusCLI.test_cli_domain_stopwords_file_end_to_end",
    "TestRealCorpusCLI.test_cli_ctfidf_method_with_timeout_fallback",
}


def allowed_skips(platform: str) -> dict[str, str]:
    result = {f"{CORPUS_MODULE}.{test}": "real corpus" for test in CORPUS_TESTS}
    if platform == "win32":
        result["test_output.test_run_report.RunReportTests.test_fifo_does_not_block"] = "POSIX FIFO test"
    elif platform.startswith("linux"):
        for name in ("test_windows_query_error_retains_peer_budget",
                     "test_windows_exit_code_query_failure_cannot_release_budget"):
            result[f"test_output.test_consistency_boundaries.TestConsistencyBoundaries.{name}"] = "Windows API fault"
    else:
        raise ValueError("Release acceptance supports Windows and Linux only")
    return result


def inspect_junit(path: Path, platform: str) -> dict:
    cases = list(ET.parse(path).getroot().iter("testcase"))
    allow = allowed_skips(platform)
    seen = set()
    skipped, failures, unexpected = [], [], []
    passed = 0
    for case in cases:
        identity = f"{case.get('classname', '')}.{case.get('name', '')}"
        seen.add(identity)
        if case.find("failure") is not None or case.find("error") is not None:
            failures.append(identity)
        elif case.find("skipped") is not None:
            reason = case.find("skipped").get("message", "")
            skipped.append({"test": identity, "reason": reason})
            if identity not in allow or allow[identity] not in reason:
                unexpected.append(identity)
        else:
            passed += 1
    missing = sorted(set(allow) - seen)
    required = ("tests.test_local_claim_entrypoints.",
                "tests.test_v413_round2_repairs.", "tests.test_v413_round2_boundaries.")
    absent_regressions = [prefix for prefix in required if not any(s.startswith(prefix) for s in seen)]
    return dict(passed=bool(cases) and not (failures or unexpected or missing or absent_regressions),
                cases=len(cases), tests_passed=passed, failures=failures,
                skipped_unexecuted=skipped, unexpected_skips=unexpected,
                missing_required_tests=missing, absent_regression_modules=absent_regressions)


def check_versions(root: Path) -> str:
    # Avoid importing an installed package or depending on tomllib on Python 3.10.
    version = re.search(r'^version = "([^"]+)"', (root / "pyproject.toml").read_text(), re.M).group(1)
    package = (root / "pa_cli/__init__.py").read_text(encoding="utf-8")
    assert re.search(r'__version__\s*=\s*[\'"]' + re.escape(version) + r'[\'"]', package)
    skill = (root / ".agents/skills/paper-agent/SKILL.md").read_text(encoding="utf-8")
    for field in ("version", "pa_cli_version"):
        assert re.search(r"^  " + field + ": " + re.escape(version) + r"$", skill, re.M)
    assert f"**Current release: v{version}**" in (root / "README.md").read_text(encoding="utf-8")
    return version


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".release-gate"))
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    version = check_versions(ROOT)
    junit = output / "pytest.xml"
    junit.unlink(missing_ok=True)
    run = subprocess.run([sys.executable, "-m", "pytest", "-q", "-rs", f"--junitxml={junit}"], cwd=ROOT)
    result = inspect_junit(junit, sys.platform) if junit.exists() else {"passed": False, "error": "No JUnit report"}
    result.update(version=version, platform=sys.platform, pytest_exit=run.returncode,
                  scope="offline_only; online and artifact gates required separately")
    result["passed"] = result["passed"] and run.returncode == 0
    (output / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
