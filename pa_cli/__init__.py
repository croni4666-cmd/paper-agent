"""paper-agent CLI -- academic paper fetch + lit review synthesis.

Latest stable: v3.9.12.0 (ClinicalTrials.gov engine + 2026-08-10 hotfix chain).
See CHANGELOG [3.9.12.0] for the new engine.

v3.9.11.9 (2026-08-10): Hotfix for v3.9.11.8 PubMed year filter ?see
CHANGELOG [3.9.11.9]. esearch `pdat` filter post-filter on `year` field.

v3.9.12.0 (2026-08-10): NEW ENGINE ?ClinicalTrials.gov (NCBI sister
site). 500K+ registered clinical trial records, free public API, no
auth. Returns trial registry records (not papers ?different content
type from PubMed/PEDro). Use case: "is anyone running a trial for
this intervention?"

Previous in v3.9.10.x and v3.9.11.0..v3.9.11.5:
  - pa_cli/sample_pool.py: 13 cmd_* functions (read / propose / write)
  - pa_cli/cli.py: `pa sample-pool` group with 13 subcommands
  - 3 iron rules enforced at API + CLI level (user-write / Mavis-readonly / training-isolated)
  - ~/.paper-agent/sample_pool/ (cross-platform, user home): SQLite + README + schema + example
  - 5 sample libraries (P1-6/8/9/21) DEPRECATED, replaced by [P3-26]
  - 4 new gated tickets (P3-22/23/24/25) for future SoTA rerank methods
  - Phased plan: data-gated (n=30 / 100 / 200 / 500), not method-gated
  - Honest 3-tier audit: v01 numbers are in-sample, do not generalize
  - Schema v1 -> v2 migration: relevance_labels.label made nullable

v3.9.11.3 (2026-07-23): Dangling blob cleanup + direct-blob fixture.
  - Found 1 dangling blob with leaked key (my own _self_check_v3_9_11_1.py
    content, which contained the key as a search pattern string literal)
  - Blob was NOT reachable from main (not pushed), but was sloppy local state
  - Added test_output/_test_verify_blob_clean.py fixture
  - git gc --prune=now removed the dangling blob
  - 1322 blobs checked, 0 with key (post-cleanup)

v3.9.11.2 (2026-07-23): Pre-push scanner bug fix + filter-branch backup cleanup.
  - _pre_github_secret_scan.py: scan_git_history() now checks both + AND - lines
    (previously only + lines, missed secrets in deleted content)
  - refs/original/refs/heads/main deleted (filter-branch backup that contained
    redaction scripts with the key)
  - git reflog expire + gc prune to remove unreachable objects
  - 0 leaks confirmed by 3 independent scans (pre-push + deep history + blob)

v3.9.11.1 (2026-07-23): CORE engine code moved to pa_cli/_engines_local/core.py
(local-only, gitignored). Public `pa search --engine core` raises "not installed"
error; user runs `python tools/install_core.py` once after clone to enable.
Trade-off: CORE code IS in public repo as a string in install_core.py; it's NOT
in functional form. See tools/install_core.py docstring for the rationale.

v3.9.11.0 was a STABLE series marker:
  - All 21 P0/P1/P2 priority items shipped (or honestly partial)
  - 5 sample libraries (P1-6/8/9/10/21) waiting on user data
  - 2 blocked items (P1-13/19) chained to sample accumulation
  - 2 modified items (P0-8/P1-12) -- fulltext cross_encoder deferred to n>=100
  - Code-level work at natural ceiling per memory discipline (n<100 = noise)

Implements paper-agent v4 design principle: after 5 minutes of Cloudflare
challenge failure, stop iterating and surface a "your turn" handoff to
user. Real human browser sessions remain the only reliable Cloudflare
bypass for academic PDF recovery.
"""

__version__ = "3.9.18.0"
__author__ = "Mavis (mavis)"
__license__ = "AGPL-3.0-only WITH No-AI-Training-1.0 restriction"

# Public API surface (programmatic use)
from .keys import (
    load_registry,
    save_registry,
    cmd_list,
    cmd_check,
    cmd_add,
    cmd_audit,
    cmd_remind,
    write_alerts_to_state,
    DEFAULT_REGISTRY,
)
