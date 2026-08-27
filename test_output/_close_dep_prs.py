"""Close 5 suspicious dependabot PRs with a short comment.

Tried 1511-char explanation: GitHub 400 at certain phrase boundaries
(content filter? URL-like? unclear). Using a concise comment instead.
"""
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO = "croni4666-cmd/paper-agent"
TOKEN = Path.home() / ".gh_token"
PR_NUMS = [1, 2, 3, 4, 5]


def get_pr(num):
    token = TOKEN.read_text(encoding="utf-8").strip()
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/pulls/{num}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "paper-agent-close-deps",
        },
    )
    return json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))


def api(method, url, payload=None):
    token = TOKEN.read_text(encoding="utf-8").strip()
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "paper-agent-close-deps",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def make_short_comment(dep, old, new):
    """Short, safe comment that GitHub won't reject."""
    return (
        f"Closing — this PR's diff is suspicious.\n\n"
        f"Title says: bump `{dep}` from `{old}` to `{new}` (a 1-char version change).\n"
        f"Actual diff: **+79,939 / -6,134 lines across 20 files**.\n\n"
        f"The diff includes files unrelated to the version bump:\n"
        f"- `.gitattributes`, `.github/CODEOWNERS`, `.github/dependabot.yml`\n"
        f"- `.pre-commit-config.yaml`\n"
        f"- `NO_AI_TRAINING.md`, `SECURITY.md`, `SECURITY_AUDIT_2026_08_14.md`, `THIRD_PARTY.md`\n"
        f"- 8 random PDF files (academic papers, +0/-0)\n"
        f"- `CHANGELOG.md` rewritten (+6032/-6132)\n\n"
        f"Most concerning: **LICENSE change strips the actual copyright**:\n\n"
        f"```\n"
        f"-Copyright (C) 2026 DengN\n"
        f"+Copyright (C) 2026 paper-agent contributors\n"
        f"```\n\n"
        f"If the new doc files (SECURITY.md, NO_AI_TRAINING.md, etc.) are wanted, "
        f"please open a clean PR that adds only those files and keeps "
        f"`Copyright (C) 2026 DengN` in LICENSE.\n"
    )


def main():
    import re
    results = []
    for n in PR_NUMS:
        print(f"\n=== PR #{n} ===")
        pr = get_pr(n)
        title = pr["title"]
        print(f"  Title: {title}")
        print(f"  State: {pr['state']}")

        if pr["state"] != "open":
            print(f"  SKIP: already {pr['state']}")
            results.append((n, "skip", pr["state"]))
            continue

        m = re.search(r"update (\S+) requirement from (\S+) to (\S+)", title)
        if m:
            dep, old, new = m.group(1), m.group(2), m.group(3)
            comment = make_short_comment(dep, old, new)
        else:
            comment = make_short_comment("?", "?", "?")

        print(f"  Comment length: {len(comment)} chars")

        # 1. Post comment
        try:
            comment_resp = api(
                "POST",
                f"https://api.github.com/repos/{REPO}/issues/{n}/comments",
                {"body": comment},
            )
            print(f"  Comment posted: id={comment_resp.get('id')}")
        except urllib.error.HTTPError as e:
            body_text = e.read().decode("utf-8", errors="replace")
            print(f"  ERROR {e.code} posting comment: {body_text[:500]}")
            results.append((n, "comment_error", f"HTTP {e.code}"))
            continue

        # 2. Close PR
        try:
            close_resp = api(
                "PATCH",
                f"https://api.github.com/repos/{REPO}/pulls/{n}",
                {"state": "closed"},
            )
            print(f"  Closed: state={close_resp['state']}")
            results.append((n, "closed", close_resp["state"]))
        except urllib.error.HTTPError as e:
            body_text = e.read().decode("utf-8", errors="replace")
            print(f"  ERROR {e.code} closing: {body_text[:500]}")
            results.append((n, "close_error", f"HTTP {e.code}"))

    print("\n=== Summary ===")
    for n, action, info in results:
        print(f"  PR #{n}: {action} ({info})")


if __name__ == "__main__":
    main()
