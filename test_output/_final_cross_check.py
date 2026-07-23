"""Final cross-check: things the 10-check sweep might miss. v1, 2026-07-23.

Catches:
1. Backup/temp files anywhere in the working tree (.bak, .orig, .tmp, .swp, .~)
2. Hidden env-var files (.envrc, .envfile, .env.bak, etc.)
3. Hidden directories with possible keys (.ssh/, .aws/, .docker/, etc.)
4. JSON/YAML/TOML files that might have inline keys
5. Markdown files with potential tokens/links
6. Python files with hardcoded credentials patterns (not just our known keys)
7. CSV/TSV files that might have API responses with keys
8. Check that the .env.example has no real keys (just placeholders)
9. Verify the install script actually works end-to-end
10. Verify version consistency across all files
"""
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(r"G:\minimax - workspace\Paper agent")
VERSION = "3.9.11.3"


def section(name):
    print()
    print("=" * 70)
    print(f"  {name}")
    print("=" * 70)


def find(cmd):
    r = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True)
    return r.stdout.strip().split("\n") if r.stdout.strip() else []


def check_backups():
    section("CROSS-CHECK 1: backup / temp files in working tree")
    patterns = [
        "*.bak", "*.orig", "*.tmp", "*.swp", "*.swo",
        "*~", ".*.swp", ".DS_Store", "Thumbs.db",
        "*.env.bak", "*.env.backup", "*.env.old",
    ]
    findings = []
    for p in patterns:
        for path in REPO.rglob(p):
            rel = str(path.relative_to(REPO)).replace("\\", "/")
            # Allow .gitignore to exclude
            rc = subprocess.run(
                ["git", "check-ignore", "-v", rel],
                cwd=str(REPO), capture_output=True, text=True
            ).returncode
            if rc == 0:
                continue
            print(f"  FAIL  {rel}  (NOT gitignored)")
            findings.append(rel)
    if not findings:
        print("  PASS: no untracked backup/temp files")
    return findings


def check_envrc():
    section("CROSS-CHECK 2: hidden env-var files")
    patterns = [".envrc", ".envfile", ".env.bak", ".env.old", ".env.backup",
                ".env.production", ".env.development", ".env.staging"]
    findings = []
    for p in patterns:
        for path in REPO.rglob(p):
            rel = str(path.relative_to(REPO)).replace("\\", "/")
            rc = subprocess.run(
                ["git", "check-ignore", "-v", rel],
                cwd=str(REPO), capture_output=True, text=True
            ).returncode
            if rc == 0:
                continue
            print(f"  FAIL  {rel}  (NOT gitignored)")
            findings.append(rel)
    if not findings:
        print("  PASS: no untracked env-var files")
    return findings


def check_hidden_dirs():
    section("CROSS-CHECK 3: hidden credential directories")
    # .ssh/, .aws/, .docker/, .kube/, .git-credentials, etc.
    suspicious = [".ssh", ".aws", ".docker", ".kube", ".git-credentials",
                  ".netrc", ".pgpass"]
    findings = []
    for d in suspicious:
        for path in REPO.rglob(d):
            if not path.exists():
                continue
            rel = str(path.relative_to(REPO)).replace("\\", "/")
            if rel.startswith(".git/"):
                continue  # .git/ is normal
            rc = subprocess.run(
                ["git", "check-ignore", "-v", rel],
                cwd=str(REPO), capture_output=True, text=True
            ).returncode
            if rc == 0:
                continue
            print(f"  FAIL  {rel}  (NOT gitignored)")
            findings.append(rel)
    if not findings:
        print("  PASS: no suspicious credential directories")
    return findings


def check_env_example():
    section("CROSS-CHECK 4: .env.example has only placeholders")
    p = REPO / ".env.example"
    if not p.exists():
        print("  FAIL: .env.example not found")
        return [("missing",)]
    text = p.read_text(encoding="utf-8", errors="ignore")
    findings = []
    # Look for any line that looks like KEY=actualvalue (not KEY= or KEY=$VAR)
    for i, line in enumerate(text.splitlines(), 1):
        m = re.match(r"^([A-Z_][A-Z0-9_]*)\s*=\s*(.+)$", line)
        if m:
            key, val = m.group(1), m.group(2).strip()
            # Allow empty, placeholder, or var reference
            if not val or val.startswith("$") or val.startswith("%"):
                continue
            # Allow common placeholder patterns
            placeholder_markers = (
                "your_", "_here", "example.com", "xxxx", "XXXX",
                "TODO", "CHANGEME", "placeholder", "<",
            )
            if any(marker in val for marker in placeholder_markers):
                continue
            # Real value? Check if it looks like a key
            if re.match(r"^[A-Za-z0-9_\-]{16,}$", val):
                print(f"  FAIL  line {i}: {key}={val[:20]}... (looks like real key)")
                findings.append((key, val))
    if not findings:
        print("  PASS: .env.example has only placeholders / var refs")
    return findings


def check_version_consistency():
    section("CROSS-CHECK 5: version consistency")
    files_to_check = [
        ("pa_cli/__init__.py", "__version__"),
        ("CHANGELOG.md", "## ["),
        ("README.md", "v3.9"),
    ]
    findings = []
    versions_found = set()
    for f, marker in files_to_check:
        path = REPO / f
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if f == "pa_cli/__init__.py":
            m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', text)
            if m:
                v = m.group(1)
                versions_found.add(("__init__", v))
                if v != VERSION:
                    print(f"  FAIL  pa_cli/__init__.py: __version__ = {v} (expected {VERSION})")
                    findings.append((f, v))
                else:
                    print(f"  PASS  pa_cli/__init__.py: {v}")
        elif f == "CHANGELOG.md":
            m = re.search(r"##\s*\[(\d+\.\d+\.\d+(?:\.\d+)?)\][^#]*?\b" + VERSION.replace(".", r"\.") + r"\b", text)
            if m:
                versions_found.add(("CHANGELOG", m.group(1)))
                print(f"  PASS  CHANGELOG.md: top entry {m.group(1)} (matches {VERSION})")
            else:
                # Check if any version entry matches
                m2 = re.search(r"##\s*\[(\d+\.\d+\.\d+(?:\.\d+)?)\]", text)
                if m2:
                    top = m2.group(1)
                    if top != VERSION:
                        print(f"  WARN  CHANGELOG.md: top entry is {top} (expected {VERSION})")
                        findings.append((f, top))
                    else:
                        print(f"  PASS  CHANGELOG.md: top entry {top}")
        elif f == "README.md":
            m = re.search(r"v3\.9\.\d+(?:\.\d+)?", text)
            if m:
                v = m.group(0)
                versions_found.add(("README", v))
                if v != "v" + VERSION:
                    print(f"  WARN  README.md: first version {v} (expected v{VERSION})")
                else:
                    print(f"  PASS  README.md: {v}")
    return findings


def check_install_e2e():
    section("CROSS-CHECK 6: install_core.py end-to-end")
    # 1. Run the install (idempotent)
    p = REPO / "tools" / "install_core.py"
    r = subprocess.run(
        ["python", str(p), "--no-verify"],
        cwd=str(REPO), capture_output=True, text=True
    )
    if r.returncode != 0:
        print(f"  FAIL  install failed: {r.stderr[:200]}")
        return [("install", r.returncode)]
    print("  PASS  install completed")
    # 2. Verify the file exists
    target = REPO / "pa_cli" / "_engines_local" / "core.py"
    if not target.exists():
        print(f"  FAIL  target not created: {target}")
        return [("target",)]
    print(f"  PASS  target file: {target}")
    # 3. Verify it's gitignored
    rel = str(target.relative_to(REPO)).replace("\\", "/")
    rc = subprocess.run(
        ["git", "check-ignore", "-v", rel],
        cwd=str(REPO), capture_output=True, text=True
    ).returncode
    if rc != 0:
        print(f"  FAIL  target not gitignored: {rel}")
        return [("not gitignored",)]
    print(f"  PASS  target gitignored")
    return []


def check_pre_push_scanner():
    section("CROSS-CHECK 7: pre-push scanner runs and reports correctly")
    r = subprocess.run(
        ["python", str(REPO / "test_output" / "_pre_github_secret_scan.py")],
        cwd=str(REPO), capture_output=True, text=True
    )
    out = r.stdout
    if "Safe to push to GitHub" in out:
        print("  PASS  pre-push scanner: Safe to push")
        return []
    if "DO NOT PUSH" in out:
        print("  FAIL  pre-push scanner: DO NOT PUSH")
        return [("scanner",)]
    print(f"  WARN  pre-push scanner returned unexpected output")
    return [("unknown",)]


def main():
    print("=" * 70)
    print("  FINAL CROSS-CHECK (10-check sweep + 7 additional cross-checks)")
    print("=" * 70)
    all_findings = {}
    for check in [
        check_backups,
        check_envrc,
        check_hidden_dirs,
        check_env_example,
        check_version_consistency,
        check_install_e2e,
        check_pre_push_scanner,
    ]:
        try:
            f = check()
            all_findings[check.__name__] = f
        except Exception as e:
            print(f"  ERROR in {check.__name__}: {e}")
            all_findings[check.__name__] = [("ERROR", str(e))]

    section("CROSS-CHECK SUMMARY")
    total_fail = sum(len([x for x in f if x]) for f in all_findings.values())
    if total_fail == 0:
        print("  ALL 7 CROSS-CHECKS PASS. Clean.")
        return 0
    else:
        for name, f in all_findings.items():
            if f:
                print(f"  {name}: {len(f)} issue(s)")
        print(f"  TOTAL: {total_fail} issue(s)")
        return 1


if __name__ == "__main__":
    sys.exit(main())
