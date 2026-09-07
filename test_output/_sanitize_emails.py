import pathlib
import subprocess
import sys

result = subprocess.run(['git', 'ls-files'], capture_output=True, text=True, encoding='utf-8')
files = result.stdout.splitlines()

# Email + handle replacements (2nd pass)
replacements = [
    # User-Agent headers (in CLI source + tests)
    ('mailto:redacted@example.invalid', 'mailto:paper-agent@users.noreply.github.com'),
    ('mailto:redacted@example.invalid', 'mailto:paper-agent@users.noreply.github.com'),
    ('mailto:sample-user@example.com', 'mailto:paper-agent@users.noreply.github.com'),
    ('mailto:redacted@example.invalid', 'mailto:paper-agent@users.noreply.github.com'),
    ('mailto:redacted@example.invalid', 'mailto:paper-agent@users.noreply.github.com'),
    ('mailto:redacted@example.invalid', 'mailto:paper-agent@users.noreply.github.com'),
    # Quoted email strings (test data)
    ('"redacted@example.invalid"', '"paper-agent@example.com"'),
    ('"redacted@example.invalid"', '"paper-agent@example.com"'),
    ('"sample-user@example.com"', '"paper-agent@example.com"'),
    ('"redacted@example.invalid"', '"paper-agent@example.com"'),
    ('"redacted@example.invalid"', '"paper-agent@example.com"'),
    ('"redacted@example.invalid"', '"paper-agent+research@example.com"'),
    ('"redacted@example.invalid"', '"paper-agent@mavis.local"'),
    # Unquoted (in log lines, comments)
    ('redacted@example.invalid', 'paper-agent@example.com'),
    ('redacted@example.invalid', 'paper-agent@example.com'),
    ('redacted@example.invalid', 'paper-agent@example.com'),
    ('redacted@example.invalid', 'paper-agent@example.com'),
    ('sample-user@example.com', 'paper-agent@example.com'),
    ('redacted@example.invalid', 'paper-agent@mavis.local'),
]

total_changes = 0
files_changed = []
for filepath in files:
    p = pathlib.Path(filepath)
    if not p.exists() or p.is_dir():
        continue
    if p.suffix in {'.pdf', '.png', '.jpg', '.jpeg', '.gif', '.zip', '.tar', '.gz', '.exe', '.dll', '.so', '.dylib'}:
        continue
    try:
        content = p.read_text(encoding='utf-8')
    except (UnicodeDecodeError, IsADirectoryError, PermissionError):
        continue
    original = content
    file_changes = 0
    for old, new in replacements:
        if old in content:
            count = content.count(old)
            content = content.replace(old, new)
            file_changes += count
    if content != original:
        p.write_text(content, encoding='utf-8')
        total_changes += file_changes
        files_changed.append((filepath, file_changes))

print(f'Total changes: {total_changes}')
print(f'Files changed: {len(files_changed)}')
for f, c in sorted(files_changed, key=lambda x: -x[1])[:15]:
    print(f'  {c:3d}  {f}')
