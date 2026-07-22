"""Quick ROADMAP audit. Read-only, no edits."""
import re
from pathlib import Path
from collections import Counter

content = Path("ROADMAP.md").read_text(encoding="utf-8-sig")
lines = content.splitlines()

section_re = re.compile(r"^### \[(P[0-3]-\d+(?:\.\d+[a-z]?)?)\] (.+?)\s*(\(.*\))?$")
section_close_re = re.compile(r"^###\s")  # any ### header closes the current section
status_re = re.compile(r"[\-\s]*\*\*Status\*\*:\s*(\S+)")

items = []
current = None
for i, line in enumerate(lines):
    m = section_re.match(line)
    if m:
        if current:
            items.append(current)
        current = {"id": m.group(1), "title": m.group(2).strip()[:60], "status": None, "line": i + 1}
    elif current and section_close_re.match(line):
        # Any other ### header closes the current P section
        items.append(current)
        current = None
    elif current and status_re.search(line):
        sm = status_re.search(line)
        current["status"] = sm.group(1).rstrip(".,;:").replace("[OK]", "done")
if current:
    items.append(current)

counts = Counter(it["status"] for it in items)
print("=== ROADMAP STATUS SUMMARY ===")
for s, c in counts.most_common():
    s_repr = (s if s is not None else "NULL").replace("\u2705", "DONE-emoji")
    print(f"  {s_repr:20s} {c:3d}")
print(f"  {'TOTAL':20s} {sum(counts.values()):3d}")
print()
print("=== ACTIVE ITEMS (proposed / in-progress / broken / modified / blocked) ===")
for it in items:
    if it["status"] in ("proposed", "in-progress", "broken", "modified", "blocked"):
        s = it["status"]
        i = it["id"]
        t = it["title"]
        l = it["line"]
        print(f"  [{s:>12s}] {i:>8s}  {t:<60s}  L{l}")
print()
print("=== DONE ITEMS ===")
for it in items:
    if it["status"] == "done":
        i = it["id"]
        t = it["title"]
        l = it["line"]
        print(f"  [done]  {i:>8s}  {t:<60s}  L{l}")
print()
print("=== ITEMS WITH NON-STANDARD STATUS (heuristic check) ===")
known_statuses = {"done", "in-progress", "proposed", "broken", "modified", "blocked", "deprecated"}
for it in items:
    if it["status"] not in known_statuses:
        s_repr = (it["status"] if it["status"] is not None else "NULL").replace("\u2705", "DONE-emoji")
        i = it["id"]
        t = it["title"]
        l = it["line"]
        print(f"  [{s_repr:>14s}] {i:>8s}  {t:<60s}  L{l}")

