"""pa_cli.fetch_batch — batch PDF download from a Bibtex file.

Per ROADMAP [P2-11] (added 2026-07-15, shipped 2026-07-20 in v3.9.10.7):
  Walks every Bibtex entry through the 8 fetch channels in priority order:
    1. CNKI (CN journal DOI heuristic, v3.9.8.3)
    2. Unpaywall (legal, stable)
    3. Sci-Hub (fallback)
    4. Anna's Archive
    5. CORE
    6. arXiv (for arXiv IDs)
    7. DOI redirect
    8. Playwright fallback
  Downloads to `pdfs/{key}.pdf`. Lists what failed and why.

  Reuses pa_cli/scaffold.py:load_bibtex for bib parsing, pa_cli/fetch.py:fetch
  for the actual download.

Usage from CLI:
  pa fetch-batch refs.bib --out-dir ./pdfs/
  pa fetch-batch refs.bib --out-dir ./pdfs/ --max-total-sec 1800
  pa fetch-batch refs.bib --out-dir ./pdfs/ --skip-existing
"""
from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional

from .scaffold import load_bibtex


# ──────────────────────────────────────────────────────────────────────
# Result types
# ──────────────────────────────────────────────────────────────────────

@dataclass
class FetchResult:
    """Per-entry fetch result."""
    key: str
    doi: str
    title: str
    success: bool
    source: str = ''           # 'unpaywall' / 'scihub' / etc.
    out_path: str = ''
    size_bytes: int = 0
    error: str = ''
    elapsed_sec: float = 0.0

    def to_dict(self) -> Dict:
        return {
            'key': self.key,
            'doi': self.doi,
            'title': self.title[:100] if self.title else '',
            'success': self.success,
            'source': self.source,
            'out_path': self.out_path,
            'size_bytes': self.size_bytes,
            'error': self.error,
            'elapsed_sec': round(self.elapsed_sec, 2),
        }


@dataclass
class FetchSummary:
    """Aggregate summary across all entries."""
    n_total: int = 0
    n_success: int = 0
    n_failure: int = 0
    n_skipped: int = 0
    total_size_bytes: int = 0
    total_elapsed_sec: float = 0.0
    results: List[FetchResult] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            'n_total': self.n_total,
            'n_success': self.n_success,
            'n_failure': self.n_failure,
            'n_skipped': self.n_skipped,
            'total_size_bytes': self.total_size_bytes,
            'total_elapsed_sec': round(self.total_elapsed_sec, 2),
            'results': [r.to_dict() for r in self.results],
        }


# ──────────────────────────────────────────────────────────────────────
# Per-entry fetch
# ──────────────────────────────────────────────────────────────────────

def _fetch_one_entry(
    entry: Dict,
    out_dir: Path,
    skip_existing: bool = False,
    prefer: str = 'auto',
) -> FetchResult:
    """Fetch a single bibtex entry via pa fetch.

    Returns FetchResult with success=True/False.
    """
    from .fetch import fetch  # lazy import to avoid heavy deps
    key = entry.get('key', 'unknown')
    doi = (entry.get('doi') or '').strip()
    title = entry.get('title', '')
    out_path = out_dir / f"{key}.pdf"
    result = FetchResult(key=key, doi=doi, title=title, success=False)

    if not doi and not title:
        result.error = 'no doi or title'
        return result

    if skip_existing and out_path.exists() and out_path.stat().st_size > 0:
        result.success = True
        result.out_path = str(out_path)
        result.size_bytes = out_path.stat().st_size
        result.error = 'skipped-existing'
        return result

    t0 = time.time()
    try:
        # Try DOI first if present
        if doi:
            r = fetch(doi=doi, out_path=str(out_path), prefer=prefer)
            if 'error' not in r:
                result.success = True
                result.source = r.get('source', '')
                result.out_path = r.get('path', str(out_path))
                result.size_bytes = r.get('size', 0)
                return result
            result.error = r.get('error', 'fetch failed')
        # Try title fallback
        if title:
            r = fetch(title=title, out_path=str(out_path), prefer=prefer)
            if 'error' not in r:
                result.success = True
                result.source = r.get('source', '')
                result.out_path = r.get('path', str(out_path))
                result.size_bytes = r.get('size', 0)
                result.error = ''
                return result
            if not result.error:
                result.error = r.get('error', 'title fallback failed')
    except Exception as e:
        result.error = f"exception: {e}"
    finally:
        result.elapsed_sec = time.time() - t0
    return result


# ──────────────────────────────────────────────────────────────────────
# Batch orchestrator
# ──────────────────────────────────────────────────────────────────────

def run_fetch_batch(
    bib_path: Path,
    out_dir: Path,
    max_total_sec: int = 1800,
    skip_existing: bool = False,
    prefer: str = 'auto',
    progress_callback: Optional[Callable[[int, int, FetchResult], None]] = None,
) -> FetchSummary:
    """Run batch PDF download for all entries in a Bibtex.

    Walks each entry sequentially (parallel would hit rate limits). Stops
    when all entries processed or max_total_sec elapsed.

    Returns FetchSummary with all per-entry results.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    entries = load_bibtex(bib_path)
    summary = FetchSummary(n_total=len(entries))
    t_start = time.time()

    for i, entry in enumerate(entries):
        # Global timeout check
        elapsed = time.time() - t_start
        if elapsed > max_total_sec:
            # Mark remaining as skipped
            for j, e in enumerate(entries[i:], start=i):
                r = FetchResult(
                    key=e.get('key', f'entry_{j}'),
                    doi=e.get('doi', ''),
                    title=e.get('title', ''),
                    success=False,
                    error='global-timeout',
                )
                summary.results.append(r)
                summary.n_skipped += 1
            break

        result = _fetch_one_entry(entry, out_dir, skip_existing=skip_existing, prefer=prefer)
        summary.results.append(result)
        if result.success:
            summary.n_success += 1
            summary.total_size_bytes += result.size_bytes
        else:
            summary.n_failure += 1
        summary.total_elapsed_sec += result.elapsed_sec

        if progress_callback:
            progress_callback(i + 1, len(entries), result)

    return summary


# ──────────────────────────────────────────────────────────────────────
# Failure report
# ──────────────────────────────────────────────────────────────────────

def write_failure_report(
    summary: FetchSummary,
    report_path: Path,
    bib_path: Path,
    out_dir: Path,
) -> int:
    """Write a markdown report of failed downloads.

    Returns number of failures written.
    """
    failures = [r for r in summary.results if not r.success]
    lines = []
    lines.append(f"# Fetch-batch failure report")
    lines.append(f"")
    lines.append(f"- Generated: {datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"- Bibtex: {bib_path}")
    lines.append(f"- Out dir: {out_dir}")
    lines.append(f"- Total entries: {summary.n_total}")
    lines.append(f"- Success: {summary.n_success}")
    lines.append(f"- Failure: {summary.n_failure}")
    lines.append(f"- Skipped (timeout): {summary.n_skipped}")
    lines.append(f"")
    if failures:
        lines.append(f"## Failures ({len(failures)})")
        lines.append(f"")
        lines.append(f"| # | Key | DOI | Error | Time (s) |")
        lines.append(f"|---:|---|---|---|---:|")
        for i, r in enumerate(failures, start=1):
            doi_short = (r.doi or '(no doi)')[:40]
            err = (r.error or 'unknown')[:60]
            lines.append(f"| {i} | `{r.key}` | {doi_short} | {err} | {r.elapsed_sec:.1f} |")
    else:
        lines.append("## All downloads succeeded!")
    lines.append(f"")
    report_path.write_text("\n".join(lines), encoding='utf-8')
    return len(failures)


# ──────────────────────────────────────────────────────────────────────
# JSON summary (for programmatic use)
# ──────────────────────────────────────────────────────────────────────

def write_summary_json(
    summary: FetchSummary,
    path: Path,
    bib_path: Path,
    out_dir: Path,
    max_total_sec: int,
) -> None:
    """Write JSON summary for programmatic consumption."""
    data = summary.to_dict()
    data['bib_path'] = str(bib_path)
    data['out_dir'] = str(out_dir)
    data['max_total_sec'] = max_total_sec
    data['timestamp'] = datetime.now().isoformat(timespec='seconds')
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
