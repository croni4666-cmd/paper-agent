"""Deep scan: check BOTH + and - lines in git log -p. v1, 2026-07-23.

Finds what's hiding in deletion lines (the official scanner misses these).
"""
import re
import subprocess

REPO = r"G:\minimax - workspace\Paper agent"

# Known leak patterns
PATTERNS = [
    ("CORE key", re.compile(r"Lu6oMH0x[A-Za-z0-9]{10,}")),
    ("Unpaywall email", re.compile(r"20240204@zufedfc\.edu\.cn")),
    ("S2 key", re.compile(r"s2k-[A-Za-z0-9]{20,}")),
    ("OpenAlex key", re.compile(r"nUkBlyf5[A-Za-z0-9]{10,}")),
]

# Run git log -p
r = subprocess.run(
    ["git", "log", "--all", "-p"],
    cwd=REPO, capture_output=True, text=True, timeout=120, errors="ignore"
)

# Track findings
findings = {}  # pattern -> list of (commit, file, line_type, snippet)
current_commit = None
current_file = None

for line in r.stdout.splitlines():
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
    if line.startswith("+"):
        line_type = "+"
        content = line[1:]
    elif line.startswith("-"):
        line_type = "-"
        content = line[1:]
    else:
        continue

    for name, pat in PATTERNS:
        if pat.search(content):
            findings.setdefault(name, []).append(
                (current_commit, current_file, line_type, content[:100])
            )

print("=" * 70)
print("DEEP HISTORY SCAN (BOTH + AND - LINES)")
print("=" * 70)
print()
for name, hits in findings.items():
    print(f"[{name}]  {len(hits)} hits")
    for commit, fname, ltype, snip in hits[:5]:
        print(f"  {commit}  {ltype}  {fname}  {snip}")
    if len(hits) > 5:
        print(f"  ... and {len(hits) - 5} more")
    print()

if not findings:
    print("  NO LEAKS FOUND IN HISTORY. Clean.")
else:
    print(f"  TOTAL: {sum(len(h) for h in findings.values())} findings")
