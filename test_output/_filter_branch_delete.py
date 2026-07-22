"""Filter-branch: delete the filter-branch helper scripts from history.

Removes:
  - test_output/_filter_branch_redact.py
  - test_output/_filter_branch_sed.sh

These were intermediate scripts used to do the history rewrite. They
contain the key patterns as sed/replace arguments and are themselves
flagged as false positives by the secret scanner. Better to remove
them entirely from history now that the rewrite is done.
"""
import os

TO_DELETE = [
    "test_output/_filter_branch_redact.py",
    "test_output/_filter_branch_sed.sh",
]

for f in TO_DELETE:
    if os.path.isfile(f):
        os.remove(f)
