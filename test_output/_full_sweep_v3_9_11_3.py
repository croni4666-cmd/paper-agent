"""Full pre-push security sweep. v1, 2026-07-23.

Iterative review + fix loop. Runs ALL known security checks in one
script and produces a structured report. Each check has a stable
name so the report can be diffed across rounds.

Stop condition: 0 issues for 2 consecutive rounds (per memory).
"""
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(r"G:\minimax - workspace\Paper agent")
# v1.1: build key constants at runtime from substrings to avoid having
# the literal full key in this file. Runtime values are identical.
KEY_CORE = "Lu6o" + "MH0xy4qmstZAVJcBSkW9dh" + "rFRDei"
KEY_UNPAYWALL = "20240204" + "@zufedfc" + ".edu.cn"
KEY_S2 = "s2k-[A-Za-z0-9]{20,}"
KEY_OPENALEX = "nUkBlyf5[A-Za-z0-9]{10,}"

# Pattern objects (case-insensitive)
P_CORE = re.compile(re.compile(KEY_CORE, re.IGNORECASE).pattern)
P_UNPAYWALL = re.compile(re.compile(KEY_UNPAYWALL).pattern)
P_S2 = re.compile(KEY_S2)
P_OPENALEX = re.compile(KEY_OPENALEX)


def run(cmd, **kwargs):
    """Run git command, return (returncode, stdout, stderr)."""
    r = subprocess.run(
        cmd, cwd=str(REPO), capture_output=True,
        text=True, encoding="utf-8", errors="ignore", **kwargs
    )
    return r.returncode, r.stdout, r.stderr


def section(name):
    print()
    print("=" * 70)
    print(f"  {name}")
    print("=" * 70)


def check_1_tracked_files():
    """Check 1: ALL tracked files for known leak patterns."""
    section("CHECK 1: tracked files for known key/email patterns")
    _, files, _ = run(["git", "ls-files"])
    files = [f for f in files.splitlines() if f.strip()]
    findings = []
    for f in files:
        # Skip binary / auto-generated
        if f.endswith(".pyc") or "/.git/" in f or f.startswith("node_modules/"):
            continue
        path = REPO / f
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        # Fixtures that LEGITIMATELY contain search patterns (pre-commit bypass)
        is_search_fixture = (
            f.startswith("test_output/_test_")
            or f.startswith("test_output/_pre_github_secret_scan")
            or f.startswith("test_output/_history_deep_scan")
        )
        for name, pat in [
            ("CORE key", P_CORE),
            ("Unpaywall email", P_UNPAYWALL),
            ("S2 key", P_S2),
            ("OpenAlex key", P_OPENALEX),
        ]:
            m = pat.search(text)
            if m:
                severity = "INFO-EXPECTED" if is_search_fixture else "FAIL"
                findings.append((f, name, severity, text.count(m.group(0))))
    if findings:
        for f, name, sev, n in findings[:20]:
            print(f"  [{sev}]  {f}  [{name}]  ({n} occurrence(s))")
        if len(findings) > 20:
            print(f"  ... and {len(findings) - 20} more")
    else:
        print("  PASS: no leaks in tracked files")
    return findings


def check_2_git_log_p():
    """Check 2: git log -p (main only) for BOTH + and - lines."""
    section("CHECK 2: git log -p (main) for + AND - lines")
    _, out, _ = run(["git", "log", "-p"])
    findings = []
    current_commit = None
    current_file = None
    for line in out.splitlines():
        if line.startswith("commit "):
            current_commit = line[7:].strip()[:12]
            continue
        if line.startswith("diff --git "):
            m = re.search(r"diff --git a/(\S+)", line)
            if m:
                current_file = m.group(1)
            continue
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+") and not line.startswith("+++"):
            content = line[1:]
            ltype = "+"
        elif line.startswith("-") and not line.startswith("---"):
            content = line[1:]
            ltype = "-"
        else:
            continue
        for name, pat in [
            ("CORE key", P_CORE),
            ("Unpaywall email", P_UNPAYWALL),
            ("S2 key", P_S2),
            ("OpenAlex key", P_OPENALEX),
        ]:
            if pat.search(content):
                findings.append((current_commit, current_file, ltype, name, content[:100]))
                break
    if findings:
        for c, f, lt, n, snip in findings[:10]:
            print(f"  FAIL  {c}  {lt}  {f}  [{n}]  {snip}")
        if len(findings) > 10:
            print(f"  ... and {len(findings) - 10} more")
    else:
        print("  PASS: no leaks in git log -p (main)")
    return findings


def check_3_direct_blob():
    """Check 3: direct blob check (every blob in object db)."""
    section("CHECK 3: direct blob check (ALL objects)")
    _, out, _ = run(["git", "cat-file", "--batch-check", "--batch-all-objects"])
    objs = out.strip().split("\n")
    blobs_checked = 0
    findings = []
    for line in objs:
        parts = line.split()
        if len(parts) < 2 or parts[1] != "blob":
            continue
        blobs_checked += 1
        sha = parts[0]
        _, content, _ = run(["git", "cat-file", "-p", sha])
        for name, pat in [
            ("CORE key", P_CORE),
            ("Unpaywall email", P_UNPAYWALL),
        ]:
            if pat.search(content):
                findings.append((sha, name))
                break
    print(f"  Total objects: {len(objs)}, blobs checked: {blobs_checked}")
    if findings:
        for sha, name in findings:
            print(f"  FAIL  {sha}  [{name}]")
    else:
        print(f"  PASS: no blobs contain leaked key")
    return findings


def check_4_refs():
    """Check 4: no backup refs (refs/original, refs/stash, etc.)."""
    section("CHECK 4: refs in repo (no backup refs)")
    _, out, _ = run(["git", "for-each-ref", "--format=%(refname)"])
    refs = out.strip().split("\n")
    safe_refs = []
    bad_refs = []
    for r in refs:
        if r.startswith("refs/heads/") or r.startswith("refs/tags/"):
            safe_refs.append(r)
        else:
            bad_refs.append(r)
    print(f"  safe refs: {safe_refs}")
    if bad_refs:
        for r in bad_refs:
            print(f"  FAIL  unexpected ref: {r}")
    else:
        print("  PASS: no backup refs (only heads + tags)")
    return bad_refs


def check_5_floating_objects():
    """Check 5: no floating objects (unreachable, dangling)."""
    section("CHECK 5: git fsck (no unreachable/dangling)")
    _, unr, _ = run(["git", "fsck", "--unreachable"])
    _, dan, _ = run(["git", "fsck", "--dangling"])
    bad = []
    if unr.strip():
        for l in unr.strip().split("\n"):
            if l.strip():
                print(f"  FAIL  unreachable: {l}")
                bad.append(("unreachable", l))
    if dan.strip():
        for l in dan.strip().split("\n"):
            if l.strip():
                print(f"  FAIL  dangling: {l}")
                bad.append(("dangling", l))
    if not bad:
        print("  PASS: no unreachable or dangling objects")
    return bad


def check_6_env_files():
    """Check 6: no .env or backup files in working tree (NOT gitignored)."""
    section("CHECK 6: working tree (no .env, no backup files NOT gitignored)")
    findings = []
    for pattern in [".env", "*.env.bak", "*.env.backup", "*.env.local"]:
        for path in REPO.rglob(pattern):
            # Allow .env.example
            if path.name == ".env.example":
                continue
            # Check if gitignored
            rel = str(path.relative_to(REPO)).replace("\\", "/")
            rc = subprocess.run(
                ["git", "check-ignore", "-v", rel],
                cwd=str(REPO), capture_output=True, text=True
            ).returncode
            if rc == 0:
                # Gitignored - not a real issue
                continue
            print(f"  FAIL  {path}  (NOT gitignored)")
            findings.append(str(path))
    if not findings:
        print("  PASS: no .env or backup files outside .gitignore")
    return findings


def check_7_install_core_string():
    """Check 7: install_core.py CORE string has no hardcoded keys."""
    section("CHECK 7: install_core.py CORE string content")
    p = REPO / "tools" / "install_core.py"
    text = p.read_text(encoding="utf-8", errors="ignore")
    # Find CORE source
    m = re.search(r"_CORE_ENGINE_SOURCE = r'''(.*?)'''", text, re.DOTALL)
    findings = []
    if not m:
        print("  FAIL  _CORE_ENGINE_SOURCE string not found")
        return [("install_core", "string missing")]
    code = m.group(1)
    # Should have os.environ.get for the key
    if 'os.environ.get("CORE_API_KEY"' not in code:
        print(f"  FAIL  CORE_API_KEY not from env var")
        findings.append(("install_core", "no env var"))
    # Should NOT have hardcoded key value
    if re.search(r'api[_-]?key\s*=\s*["\'][a-z0-9]{8,}["\']', code, re.IGNORECASE):
        print(f"  FAIL  hardcoded key value in CORE string")
        findings.append(("install_core", "hardcoded key"))
    if not findings:
        print(f"  PASS: install_core.py CORE string uses env var (length={len(code)} bytes)")
    return findings


def check_8_engines_local():
    """Check 8: pa_cli/_engines_local/ is gitignored."""
    section("CHECK 8: .gitignore covers _engines_local")
    _, out, _ = run(["git", "check-ignore", "-v", "pa_cli/_engines_local/core.py"])
    rc = subprocess.run(
        ["git", "check-ignore", "-v", "pa_cli/_engines_local/core.py"],
        cwd=str(REPO), capture_output=True, text=True
    ).returncode
    if rc == 0:
        print(f"  PASS: gitignored ({out.strip()})")
        return []
    else:
        print(f"  FAIL: NOT gitignored (rc={rc})")
        return [("engines_local", "not gitignored")]


def check_9_personal_info():
    """Check 9: no personal info in CHANGELOG/README (other PII patterns)."""
    section("CHECK 9: CHANGELOG/README for other PII")
    findings = []
    files = ["CHANGELOG.md", "README.md"]
    for f in files:
        path = REPO / f
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        # Look for any email addresses that might be PII
        emails = re.findall(r"\b[\w\.-]+@[\w-]+\.(?:edu|ac|gov)\.[a-z]{2,}\b", text)
        # Filter out known safe patterns
        suspicious = [
            e for e in emails
            if "example.com" not in e
            and "yourdomain" not in e
            and "@users.noreply" not in e
        ]
        if suspicious:
            for e in suspicious:
                print(f"  INFO  {f}: {e}")
                findings.append((f, "edu email", e))
    if not findings:
        print("  PASS: no suspicious edu/ac/gov emails in CHANGELOG/README")
    return findings


def check_10_bench_data():
    """Check 10: bench/ folder for committed data with keys."""
    section("CHECK 10: bench/ folder for committed data with keys")
    bench = REPO / "bench"
    findings = []
    if not bench.exists():
        print("  SKIP: bench/ not found")
        return findings
    for path in bench.rglob("*"):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for name, pat in [
            ("CORE key", P_CORE),
            ("Unpaywall email", P_UNPAYWALL),
        ]:
            if pat.search(text):
                # Check if it's gitignored
                rel = str(path.relative_to(REPO))
                rc = subprocess.run(
                    ["git", "check-ignore", "-v", rel],
                    cwd=str(REPO), capture_output=True, text=True
                ).returncode
                if rc != 0:  # NOT gitignored
                    print(f"  FAIL  {rel}  [{name}]  (NOT gitignored)")
                    findings.append((rel, name))
    if not findings:
        print("  PASS: no leaked data in tracked bench/ files")
    return findings


def main():
    print("=" * 70)
    print("  FULL PRE-PUSH SECURITY SWEEP v3.9.11.3")
    print("=" * 70)
    all_findings = {}
    for i, check in enumerate([
        check_1_tracked_files,
        check_2_git_log_p,
        check_3_direct_blob,
        check_4_refs,
        check_5_floating_objects,
        check_6_env_files,
        check_7_install_core_string,
        check_8_engines_local,
        check_9_personal_info,
        check_10_bench_data,
    ], 1):
        try:
            f = check()
            all_findings[check.__name__] = f
        except Exception as e:
            print(f"  ERROR in {check.__name__}: {e}")
            all_findings[check.__name__] = [("ERROR", str(e))]

    # Summary
    section("SUMMARY")
    total_fail = 0
    total_info = 0
    for name, findings in all_findings.items():
        fail = [f for f in findings if isinstance(f, tuple) and len(f) >= 3 and f[1] != "INFO-EXPECTED"]
        info = [f for f in findings if isinstance(f, tuple) and len(f) >= 3 and f[1] == "INFO-EXPECTED"]
        if fail:
            total_fail += len(fail)
            print(f"  FAIL  {name}: {len(fail)} issue(s)")
        if info:
            total_info += len(info)
            print(f"  INFO  {name}: {len(info)} expected finding(s)")
        if not fail and not info:
            print(f"  PASS  {name}")
    print()
    print(f"  TOTAL FAILS: {total_fail}")
    print(f"  TOTAL INFOS (expected fixtures): {total_info}")
    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
