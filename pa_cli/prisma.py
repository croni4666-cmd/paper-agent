"""pa_cli.prisma — Thin re-export wrapper for skill.core.prisma.

[ P1-3 ] (ROADMAP.md): PRISMA flow diagram generation for systematic
review journal submissions.

Why this module exists (instead of just importing from skill/):
  - Avoids cross-package import paths (skill/ is untracked; pa_cli is
    the tracked package boundary)
  - Single stable surface for `pa prisma` command + `pa review` integration
  - Lets us add pa_cli-specific helpers later (e.g. count derivation from
    corpus_dir) without touching skill/ logic

The actual PRISMA generation logic lives in skill/core/prisma.py
(generate_mermaid + generate_markdown). We re-export it here.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Dict, Optional


log = logging.getLogger(__name__)

# Re-export from skill.core.prisma
try:
    # Add project root to import path on demand (skill/ is sibling of pa_cli/)
    _root = Path(__file__).resolve().parent.parent
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))
    from skill.core.prisma import generate_mermaid, generate_markdown  # noqa: E402
except ImportError as e:
    log.warning(f"could not import skill.core.prisma: {e}")
    generate_mermaid = None
    generate_markdown = None


# ============== pa_cli-specific helpers ==============

def derive_counts_from_corpus(corpus_dir: Path, word_count_min: int) -> Dict[str, int]:
    """Derive PRISMA counts from a corpus directory of PDFs.

    Reuses pa_cli.review.build_corpus_index() which already classifies
    each PDF as full-text vs abstract-only by word count.

    Returns dict with keys:
      identified       — total PDFs found
      after_screening  — PDFs that passed word-count threshold
      after_eligibility = after_screening  (no manual eligibility step)
      included         = after_screening  (same)
      pdf_count        = after_screening  (alias)
      abstract_count   = identified - after_screening  (excluded by length)
    """
    from .review import build_corpus_index  # local import to avoid heavy dep at module load
    papers = build_corpus_index(corpus_dir, word_count_min)
    identified = len(papers)
    full_text = sum(1 for p in papers if p.get("is_full_text"))
    abstract = identified - full_text
    return {
        "identified": identified,
        "after_screening": full_text,
        "after_eligibility": full_text,
        "included": full_text,
        "pdf_count": full_text,
        "abstract_count": abstract,
    }


def render_prisma(
    identified: int,
    after_screening: int,
    after_eligibility: int,
    included: int,
    by_source: Optional[Dict[str, int]] = None,
    pdf_count: int = 0,
    abstract_count: int = 0,
    excluded_reasons: Optional[Dict[str, int]] = None,
    output_format: str = "markdown",
) -> str:
    """Top-level render entry. Output_format: 'markdown' (default, full report)
    or 'mermaid' (just the mermaid block, for embedding)."""
    if generate_mermaid is None or generate_markdown is None:
        raise RuntimeError(
            "skill.core.prisma not importable — pa prisma cannot generate diagrams. "
            "Check that skill/ directory exists at the project root."
        )
    if output_format == "mermaid":
        return generate_mermaid(
            identified_count=identified,
            after_screening_count=after_screening,
            after_eligibility_count=after_eligibility,
            included_count=included,
            by_source=by_source or {},
            pdf_count=pdf_count,
            abstract_count=abstract_count,
        )
    return generate_markdown(
        identified_count=identified,
        after_screening_count=after_screening,
        after_eligibility_count=after_eligibility,
        included_count=included,
        by_source=by_source or {},
        pdf_count=pdf_count,
        abstract_count=abstract_count,
        excluded_reasons=excluded_reasons or {},
    )


def parse_json_arg(s: str) -> Dict[str, int]:
    """Parse a JSON string into {str: int}. Used for --by-source and --excluded-reasons."""
    if not s:
        return {}
    try:
        data = json.loads(s)
        if not isinstance(data, dict):
            raise ValueError(f"expected JSON object, got {type(data).__name__}")
        return {str(k): int(v) for k, v in data.items()}
    except (json.JSONDecodeError, ValueError) as e:
        raise ValueError(f"invalid JSON for arg: {e}\ninput was: {s!r}")
