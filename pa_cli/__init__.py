"""paper-agent CLI — academic paper fetch + lit review synthesis.

Latest stable: v3.9.10.11 ([P2-14] Quality filter + v3.9.10.10
honest re-eval finding). See CHANGELOG [3.9.10.11] for full notes:
  - v3.9.10.10: search.py http_get_json gzip/brotli encoding fix
  - v3.9.10.11: [P2-14] pa search --quality-mode {flag|filter|off} ships
                 + honest 3-tier finding that the fix's effect is mixed
                 (pool coverage -10%, NDCG@10 -0.66) when S2 is excluded
                 from rebuild. Added [P1-20] to ROADMAP for S2 throttling.
  - v3.9.10.10 (re-eval): S2 throttling needed to make fix actually help
Implements paper-agent v4 design principle: after 5 minutes of Cloudflare
challenge failure, stop iterating and surface a "your turn" handoff to
user. Real human browser sessions remain the only reliable Cloudflare
bypass for academic PDF recovery.
"""

__version__ = "3.9.10.11"
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