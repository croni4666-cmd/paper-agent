"""Sequential BibTeX retrieval with cancellable workers and staged PDF output."""
from __future__ import annotations

import json
import math
import tempfile
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
    xml_path: str = ''         # XML published by this attempt, if any

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
            'xml_path': self.xml_path,
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

def _complete_pdf(path: Path) -> bool:
    """Check header and EOF marker, not the full PDF object structure."""
    try:
        with path.open('rb') as stream:
            if stream.read(5) != b'%PDF-':
                return False
            stream.seek(0, 2)
            size = stream.tell()
            stream.seek(max(0, size - 4096))
            return stream.read().rstrip().endswith(b'%%EOF')
    except OSError:
        return False


def _fetch_one_entry(entry: Dict, out_dir: Path, skip_existing: bool = False,
                     prefer: str = 'auto', max_total_sec: float = 300) -> FetchResult:
    """Stage one isolated worker's files; publish only a completed PDF.

    The caller owns the batch deadline. Failed/timed-out PDF files are discarded;
    a completed worker's XML-only result is retained for full-text recovery.
    """
    from .fetch_deadline import run_fetch
    started = time.monotonic()
    key = entry.get('key', 'unknown')
    result = FetchResult(key=key, doi=entry.get('doi') or '',
                         title=entry.get('title') or '', success=False)
    # A citation key must be a single portable filename, never a path.
    if (not isinstance(key, str) or not key or key in ('.', '..')
            or any(c in key for c in '/\\:<>"|?*')
            or any(ord(c) < 32 for c in key) or key.endswith((' ', '.'))
            or key.split('.')[0].upper() in
            {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)),
             *(f'LPT{i}' for i in range(1, 10))}):
        result.error = 'invalid-citation-key'
        return result
    target = out_dir / f'{key}.pdf'
    if skip_existing and _complete_pdf(target):
        result.success, result.error = True, 'skipped-existing'
        result.out_path, result.size_bytes = str(target), target.stat().st_size
        return result
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix='.pa-batch-', dir=out_dir) as temp:
            stage = Path(temp)
            remaining = max_total_sec - (time.monotonic() - started)
            if remaining <= 0:
                result.error = 'fetch_timeout'
                return result
            response = run_fetch({'_operation': 'batch_entry', 'entry': entry,
                                  'out_dir': str(stage), 'prefer': prefer}, remaining)
            pdf, xml = stage / f'{key}.pdf', stage / f'{key}.xml'
            if response.get('success') and _complete_pdf(pdf):
                pdf.replace(target)
                result.success = True
                result.out_path, result.size_bytes = str(target), target.stat().st_size
                result.source = response.get('source', '')
            else:
                result.error = response.get('error') or 'invalid-pdf-output'
            # Preserve XML only when the worker completed normally. A timeout
            # may have left a truncated intermediate, so discard that stage.
            if response.get('error') not in ('fetch_timeout', 'fetch_worker_failed') and xml.is_file():
                try:
                    from .fetch import _is_jats_article
                    if _is_jats_article(xml.read_bytes()):
                        xml.replace(target.with_suffix('.xml'))
                        result.xml_path = str(target.with_suffix('.xml'))
                except OSError:
                    if not result.success:
                        result.error = 'batch-output-error'
    except OSError:
        result.error = 'batch-output-error'
        result.success = False
        result.out_path = ''
    finally:
        result.elapsed_sec = time.monotonic() - started
    return result


def _fetch_one_entry_in_process(
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
                # v3.9.27.0: pa fetch returns "size" (not "size_bytes")
                # for some channels (e.g. PMC jats_pdf, fetch_batch result
                # has "size_bytes" but the raw fetch() returns "size").
                # Use fallback chain for robustness.
                result.size_bytes = (
                    r.get("size_bytes")
                    or r.get("size")
                    or (Path(r.get("path", str(out_path))).stat().st_size
                        if Path(r.get("path", str(out_path))).exists()
                        else 0)
                )
                return result
            result.error = r.get('error', 'fetch failed')
        # Try title fallback
        if title:
            r = fetch(title=title, out_path=str(out_path), prefer=prefer)
            if 'error' not in r:
                result.success = True
                result.source = r.get('source', '')
                result.out_path = r.get('path', str(out_path))
                # v3.9.27.0: same fallback chain as DOI path
                result.size_bytes = (
                    r.get("size_bytes")
                    or r.get("size")
                    or (Path(r.get("path", str(out_path))).stat().st_size
                        if Path(r.get("path", str(out_path))).exists()
                        else 0)
                )
                result.error = ''
                return result
            if not result.error:
                result.error = r.get('error', 'title fallback failed')
    except Exception:
        result.error = "fetch-entry-failed"
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
    clean_xml: bool = False,  # v3.9.26.0: delete .xml intermediate after successful PDF
) -> FetchSummary:
    """Run batch PDF download for all entries in a Bibtex.

    Walks each entry sequentially (parallel would hit rate limits). Stops
    when all entries processed or max_total_sec elapsed.

    v3.9.26.0: added `clean_xml` option. When True, deletes the .xml
    intermediate file (created by JATS-to-PDF rendering for PMC papers)
    after the PDF is successfully generated. Reduces clutter in out_dir
    when the .xml is no longer needed.

    Returns FetchSummary with all per-entry results.
    """
    try:
        valid = (not isinstance(max_total_sec, bool)
                 and isinstance(max_total_sec, (int, float))
                 and math.isfinite(max_total_sec) and max_total_sec > 0)
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError('max_total_sec must be a finite positive number')
    out_dir.mkdir(parents=True, exist_ok=True)
    entries = load_bibtex(bib_path)
    summary = FetchSummary(n_total=len(entries))
    t_start = time.monotonic()

    for i, entry in enumerate(entries):
        # Global timeout check
        elapsed = time.monotonic() - t_start
        if elapsed >= max_total_sec:
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

        result = _fetch_one_entry(entry, out_dir, skip_existing=skip_existing, prefer=prefer,
                                  max_total_sec=max_total_sec - elapsed)
        summary.results.append(result)
        # v3.9.26.0: check skipped first (skipped has success=True with
        # error='skipped-existing'); otherwise skip counts as success
        if result.error == 'skipped-existing':
            summary.n_skipped += 1
            summary.total_size_bytes += result.size_bytes
        elif result.success:
            summary.n_success += 1
            summary.total_size_bytes += result.size_bytes
        else:
            summary.n_failure += 1
        # v3.9.26.0: clean up .xml intermediate (e.g., from JATS-to-PDF)
        # after successful PDF generation, if --clean-xml was passed
        if clean_xml and result.success and result.xml_path:
            xml_path = Path(result.xml_path)
            try:
                if xml_path.exists() and xml_path != Path(result.out_path):
                    xml_path.unlink()
                    result.xml_path = ''
            except OSError:
                pass  # best-effort cleanup, don't fail the batch

        if progress_callback:
            progress_callback(i + 1, len(entries), result)

    summary.total_elapsed_sec = time.monotonic() - t_start
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
