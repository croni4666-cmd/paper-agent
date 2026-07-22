"""Filter-branch: delete the filter-branch helper scripts from history.

Uses git rm to ensure the file deletion is staged properly.
"""
import subprocess

TO_DELETE = [
    "test_output/_filter_branch_redact.py",
    "test_output/_filter_branch_sed.sh",
]

for f in TO_DELETE:
    # Use git rm --cached + rm to delete from index and working tree
    try:
        subprocess.run(["git", "rm", "-f", "--cached", f],
                       capture_output=True, text=True)
    except Exception:
        pass
    import os
    if os.path.isfile(f):
        os.remove(f)
