"""Clean up aminer_channel.py: remove duplicate old search_aminer function."""
import re
from pathlib import Path

p = Path(r"G:\minimax - workspace\Paper agent\pa_cli\aminer_channel.py")
content = p.read_text(encoding="utf-8")
lines = content.split("\n")

# Find the first search_aminer function (the old one)
old_start = None
old_end = None
for i, line in enumerate(lines):
    if line.startswith("def search_aminer(query:"):
        if old_start is None:
            old_start = i
        else:
            old_end = i
            break

print(f"Old function starts at line {old_start + 1}")
# Find the end of the first function (next def at column 0)
for i in range(old_start + 1, len(lines)):
    if lines[i].startswith("def ") and not lines[i].startswith("def search_aminer(query:"):
        old_end = i
        break
    # Also check for "return" + next blank + next def
    if lines[i].startswith("return results[:limit]") and i > old_start + 10:
        # End is at next blank line + next def
        for j in range(i + 1, len(lines)):
            if lines[j].startswith("def "):
                old_end = j
                break
        break

print(f"Old function ends at line {old_end + 1}")
print(f"First few lines of old function: {lines[old_start]}")
print(f"Last few lines of old function: {lines[old_end - 1] if old_end > 0 else 'N/A'}")
print(f"First line of new function: {lines[old_end]}")

# Remove old function (and the blank line before it)
new_lines = lines[:old_start - 1] + lines[old_end:]
new_content = "\n".join(new_lines)
p.write_text(new_content, encoding="utf-8")
print(f"Removed {old_end - old_start} lines. New total: {len(new_lines)} lines.")
