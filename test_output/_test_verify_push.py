"""Verify the GitHub push worked. v1, 2026-07-23."""
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(r"G:\minimax - workspace\Paper agent")
GH = r"C:\Program Files\GitHub CLI\gh.exe"

# 1. Local HEAD
local = subprocess.run(
    ["git", "log", "-1", "--format=%H %s"],
    cwd=str(REPO), capture_output=True, text=True
).stdout.strip()
print(f"Local HEAD:  {local}")

# 2. Remote HEAD via API
r = subprocess.run(
    [GH, "api", "repos/croni4666-cmd/paper-agent/commits/main"],
    cwd=str(REPO), capture_output=True  # bytes mode
)
if r.returncode != 0:
    print(f"API error: {r.stderr.decode('utf-8', errors='ignore')}")
    sys.exit(1)
# Auto-detect encoding (BOM or fallback to utf-8)
raw = r.stdout
if raw.startswith(b'\xff\xfe') or raw.startswith(b'\xfe\xff'):
    text = raw.decode('utf-16')
elif raw.startswith(b'\xef\xbb\xbf'):
    text = raw.decode('utf-8-sig')
else:
    text = raw.decode('utf-8', errors='ignore')
d = json.loads(text)
remote_sha = d["sha"][:12]
remote_msg = d["commit"]["message"].split("\n")[0]
print(f"Remote HEAD: {remote_sha} {remote_msg}")

# 3. Match?
local_sha = local.split()[0][:12]
if local_sha == remote_sha:
    print(f"  -> MATCH (both at {local_sha})")
else:
    print(f"  -> MISMATCH (local {local_sha} vs remote {remote_sha})")

# 4. Repo info
r = subprocess.run(
    [GH, "api", "repos/croni4666-cmd/paper-agent"],
    cwd=str(REPO), capture_output=True
)
raw = r.stdout
if raw.startswith(b'\xff\xfe') or raw.startswith(b'\xfe\xff'):
    text = raw.decode('utf-16')
elif raw.startswith(b'\xef\xbb\xbf'):
    text = raw.decode('utf-8-sig')
else:
    text = raw.decode('utf-8', errors='ignore')
d = json.loads(text)
print()
print(f"Repo: {d['full_name']}")
print(f"URL:  {d['html_url']}")
print(f"Visibility: {d['visibility']}")
print(f"Description: {d['description']}")
print(f"Stars: {d['stargazers_count']} | Forks: {d['forks_count']} | Size: {d['size']}KB")
print(f"Default branch: {d['default_branch']}")

# 5. Top-level files
r = subprocess.run(
    [GH, "api", "repos/croni4666-cmd/paper-agent/contents"],
    cwd=str(REPO), capture_output=True
)
raw = r.stdout
if raw.startswith(b'\xff\xfe') or raw.startswith(b'\xfe\xff'):
    text = raw.decode('utf-16')
elif raw.startswith(b'\xef\xbb\xbf'):
    text = raw.decode('utf-8-sig')
else:
    text = raw.decode('utf-8', errors='ignore')
contents = json.loads(text)
print()
print(f"Top-level entries ({len(contents)}):")
for c in contents[:20]:
    icon = "DIR " if c["type"] == "dir" else "FILE"
    size = c.get("size", 0)
    print(f"  [{icon}] {c['name']:40} {size:>10} bytes")
if len(contents) > 20:
    print(f"  ... and {len(contents) - 20} more")
