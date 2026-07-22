"""paper-agent CLI — academic paper fetch + lit review synthesis.

Latest stable: v3.9.11.0 (stable release marker; all P0/P1/P2 code shipped
+ honest 3-tier finding for LTR). See CHANGELOG [3.9.11.0] for stable-release notes.

Previous in v3.9.10.x:
  - v3.9.10.10: search.py http_get_json gzip/brotli encoding fix
  - v3.9.10.11: [P2-14] pa search --quality-mode ships + [P1-20] S2 throttle
  - v3.9.10.12: [P0-8] path A 12-feature LTR baseline (12-feat = 8-feat at n=25)
  - v3.9.10.13: _load_dotenv() auto-load .env (CORE_API_KEY, S2_API_KEY, etc.)

v3.9.11.0 is a STABLE series marker:
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

__version__ = "3.9.11.0"
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