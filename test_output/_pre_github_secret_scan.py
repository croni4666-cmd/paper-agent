"""Pre-GitHub secret scan. Check ALL committed files (including git history)
for leaked API keys.

Scans for:
  - CORE API key prefix: Lu6oMH0x (or similar 32-char base58)
  - S2 API key prefix: s2k-
  - OpenAlex key (32-char base58)
  - Unpaywall email 20240204@zufedfc
  - Any string that looks like a key (long base58 in string literal)

Outputs a report by file + by commit.
"""
import re
import sys
import subprocess
from pathlib import Path

REPO = Path(".")

# Patterns
PATTERNS = {
    "CORE_API_KEY": re.compile(r"Lu6oMH0x[A-Za-z0-9]{10,}"),
    "S2_API_KEY": re.compile(r"s2k-[A-Za-z0-9]{20,}"),
    "OPENALEX_API_KEY": re.compile(r"nUkBlyf5[A-Za-z0-9]{10,}"),
    "UNPAYWALL_EMAIL": re.compile(r"20240204@zufedfc\.edu\.cn"),
    # Generic: any 32+ char string in KEY/TOKEN/SECRET literal
    "GENERIC_KEY": re.compile(r"""(?:KEY|TOKEN|SECRET|API_KEY|AUTHORIZATION)\s*=\s*['"]([A-Za-z0-9_\-]{20,})['"]"""),
}


def scan_file(path: Path) -> dict:
    """Scan one file for all patterns. Return {pattern: [matches]}."""
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except (UnicodeDecodeError, OSError):
        return {}
    found = {}
    for name, pat in PATTERNS.items():
        matches = pat.findall(content)
        if matches:
            found[name] = matches
    return found


def scan_tracked_files() -> dict:
    """Scan all git-tracked files for secrets."""
    print("=" * 70)
    print("SCAN 1: git-tracked files (will be pushed to GitHub)")
    print("=" * 70)
    result = subprocess.run(
        ["git", "ls-files"], capture_output=True, text=True, cwd=REPO
    )
    files = [f for f in result.stdout.splitlines() if f.strip()]
    leaks = {}
    for f in files:
        if f.endswith(".pyc") or "/.git/" in f:
            continue
        path = REPO / f
        if not path.is_file():
            continue
        found = scan_file(path)
        if found:
            leaks[f] = found
    return leaks


def scan_git_history() -> list:
    """Scan all commits for secret leaks via git log -p.

    v3.9.11.1 fix: BOTH + (added) and - (deleted) lines are checked.
    Previously only + lines were checked, which missed secrets in files
    that were added then deleted (e.g. filter-branch redaction scripts
    in commits b0afe15/f8cee28/4d7cdcf).
    """
    print()
    print("=" * 70)
    print("SCAN 2: git history (git log -p) for ALL commits")
    print("=" * 70)
    print("(this is slow but necessary -- secrets in history are still public after push)")
    result = subprocess.run(
        ["git", "log", "-p"],
        capture_output=True,
        text=True,
        cwd=REPO,
        errors="ignore",
    )
    findings = []
    current_commit = None
    current_file = None
    for line in result.stdout.splitlines():
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
        # v3.9.11.1: check BOTH + (added) and - (deleted) lines.
        # Previously only + lines were scanned, which missed secrets in
        # files that were added then removed (filter-branch redaction scripts).
        if line.startswith("+") and not line.startswith("+++"):
            content = line[1:]
        elif line.startswith("-") and not line.startswith("---"):
            content = line[1:]
        else:
            continue
        for name, pat in PATTERNS.items():
            if pat.search(content):
                findings.append((current_commit, current_file, name, content[:120]))
                break
    return findings


def main():
    print("PRE-GITHUB SECRET SCAN")
    print("=" * 70)

    leaks = scan_tracked_files()
    if leaks:
        print()
        print(f"FOUND {len(leaks)} tracked files with secrets:")
        for f, found in leaks.items():
            for name, matches in found.items():
                # Don't print full key, just first/last 4 chars
                for m in matches:
                    masked = m[:4] + "..." + m[-4:] if len(m) > 8 else m
                    print(f"  {f}  [{name}]  {masked}  ({len(matches)} total match(es))")
    else:
        print("  (no leaks in tracked files)")

    history = scan_git_history()
    if history:
        print()
        print(f"FOUND {len(history)} commits with secrets in git history:")
        for commit, fname, name, snippet in history[:50]:
            masked_snip = snippet[:80].replace(matches[0] if False else "", "XXX")
            print(f"  {commit}  {fname}  [{name}]  {snippet[:80]}")
    else:
        print("  (no leaks in git history)")

    print()
    print("=" * 70)
    print("VERDICT")
    print("=" * 70)
    if leaks or history:
        print("DO NOT PUSH TO GITHUB UNTIL LEAKS ARE FIXED")
        if history:
            print("  -- git history rewriting required (filter-repo or filter-branch)")
            print("  -- AND the leaked key MUST be rotated at the source")
        return 1
    else:
        print("Safe to push to GitHub")
        return 0


if __name__ == "__main__":
    sys.exit(main())
