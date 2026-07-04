"""paper-agent CLI — academic paper fetch + lit review synthesis.

Version 3.2.0 (post full-recovery). Implements paper-agent v4 design principle:
after 5 minutes of Cloudflare challenge failure, stop iterating and surface a
"your turn" handoff. Real human browser sessions remain the only reliable
Cloudflare bypass for academic PDF recovery.
"""

__version__ = "3.2.0"
__author__ = "Mavis (mavis)"
__license__ = "MIT"