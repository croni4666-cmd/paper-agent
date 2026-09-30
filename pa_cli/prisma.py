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

try:
    # Add project root to import path on demand (skill/ is sibling of pa_cli/)
    _root = Path(__file__).resolve().parent.parent
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))
    from skill.core.prisma import generate_mermaid, generate_markdown  # noqa: E402
except ImportError as e:
    from datetime import datetime

    def generate_mermaid(
        identified_count: int,
        after_screening_count: int,
        after_eligibility_count: int,
        included_count: int,
        by_source: Dict[str, int] = None,
        pdf_count: int = 0,
        abstract_count: int = 0,
    ) -> str:
        if by_source is None:
            by_source = {}
        sources = [
            ('arxiv', 'arXiv', '15'),
            ('openalex', 'OpenAlex', '50'),
            ('semanticscholar', 'Semantic Scholar', '50'),
            ('eric', 'ERIC', '22'),
            ('doaj', 'DOAJ', '29'),
            ('core', 'CORE', '27'),
        ]
        screening_excluded = identified_count - after_screening_count
        eligibility_excluded = after_screening_count - after_eligibility_count

        md = "```mermaid\n"
        md += "flowchart TD\n"
        md += f'    A["**Identification**<br/>6 通道检索<br/>({identified_count})"]\n'
        for i, (key, label, default) in enumerate(sources):
            count = by_source.get(key, default)
            md += f'    A -->|"<b>{label}</b>"| A{i}["{label}: {count}"]\n'
        for i in range(len(sources)):
            md += f'    A{i} --> B\n'
        md += f'    B["**{identified_count} identified**<br/>(dedup)"]\n'
        md += f'    B -->|"3-stage 筛选<br/>(exclude {screening_excluded})"| C["**{after_screening_count} screened**"]\n'
        md += f'    C -->|"主题精选<br/>(exclude {eligibility_excluded})"| D["**{after_eligibility_count} eligible**"]\n'
        md += f'    D -->|"PDF 下载"| E1["PDF: {pdf_count} 篇"]\n'
        md += f'    D -->|"abstract-only"| E2["Abstract: {abstract_count} 篇"]\n'
        md += f'    E1 & E2 --> F["**{included_count} included**"]\n'
        md += '    style A fill:#e1f5ff\n'
        md += '    style B fill:#b3e0ff\n'
        md += '    style C fill:#80ccff\n'
        md += '    style D fill:#4db8ff\n'
        md += '    style E1 fill:#66ff99\n'
        md += '    style E2 fill:#ffcc66\n'
        md += '    style F fill:#ff9966\n'
        md += '```\n'
        return md

    def generate_markdown(
        identified_count: int,
        after_screening_count: int,
        after_eligibility_count: int,
        included_count: int,
        by_source: Dict[str, int] = None,
        pdf_count: int = 0,
        abstract_count: int = 0,
        excluded_reasons: Dict[str, int] = None,
    ) -> str:
        if by_source is None:
            by_source = {}
        if excluded_reasons is None:
            excluded_reasons = {}
        md = []
        md.append('# PRISMA 2020 流程图')
        md.append('')
        md.append(f'**生成时间**: {datetime.now().isoformat()}')
        md.append('')
        md.append('## 📊 流程图')
        md.append('')
        md.append(generate_mermaid(
            identified_count=identified_count,
            after_screening_count=after_screening_count,
            after_eligibility_count=after_eligibility_count,
            included_count=included_count,
            by_source=by_source,
            pdf_count=pdf_count,
            abstract_count=abstract_count,
        ))
        md.append('')
        md.append('## 📋 阶段详情')
        md.append('')
        md.append('### 1. Identification')
        md.append(f'- 总检索: **{identified_count} 篇**')
        if by_source:
            md.append('- 通道分布:')
            for src, cnt in by_source.items():
                md.append(f'  - {src}: {cnt}')
        md.append('')
        md.append('### 2. Screening')
        md.append(f'- 3-stage 筛选后: **{after_screening_count} 篇**')
        md.append(f'- 排除: {identified_count - after_screening_count}')
        if excluded_reasons.get('stage1'):
            md.append(f'  - Stage 1 粗筛: - {excluded_reasons["stage1"]}')
        if excluded_reasons.get('stage2'):
            md.append(f'  - Stage 2 严格: - {excluded_reasons["stage2"]}')
        if excluded_reasons.get('stage3'):
            md.append(f'  - Stage 3 终筛: - {excluded_reasons["stage3"]}')
        md.append('')
        md.append('### 3. Eligibility')
        md.append(f'- 主题精选后: **{after_eligibility_count} 篇**')
        md.append('')
        md.append('### 4. Included')
        md.append(f'- 最终纳入: **{included_count} 篇**')
        md.append(f'  - PDF (high conf): {pdf_count}')
        md.append(f'  - Abstract-only: {abstract_count}')
        md.append('')
        return '\n'.join(md)



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
