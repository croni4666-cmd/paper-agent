"""paper-agent CLI — academic paper fetch + lit review synthesis.

Latest stable: v3.9.10.7 ([P2-11] `pa fetch-batch` batch PDF download ships.
See CHANGELOG [3.9.10.7] for full release notes including:
  - v3.9.10: deprecate BGE/LTR from default, promote combined
  - v3.9.10.1: Phase 1.5 holdout validation (5-fold + single 30/20)
  - v3.9.10.2: Simpler rerank alternative (Ridge/LogReg beat LTR)
  - v3.9.10.3: [P2-7] pa cite-check pre-build validator
  - v3.9.10.4: [P2-8] pa export-screening Bibtex→CSV
  - v3.9.10.5: [P2-9] pa search-saved named presets
  - v3.9.10.6: [P2-10] pa dedup-strict fuzzy + arxiv dedup
  - v3.9.10.7: [P2-11] pa fetch-batch batch PDF download).
Implements paper-agent v4 design principle: after 5 minutes of Cloudflare
challenge failure, stop iterating and surface a "your turn" handoff to
user. Real human browser sessions remain the only reliable Cloudflare
bypass for academic PDF recovery.
"""

__version__ = "3.9.10.7"
__author__ = "Mavis (mavis)"
__license__ = "MIT"

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