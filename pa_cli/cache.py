"""pa_cli.cache — Local PDF + sidecar-meta cache for `pa fetch`.

Avoids re-downloading the same DOI across `pa fetch` invocations.

Metadata retains the DOI-derived filename; new PDFs use immutable generations.
Reads verify DOI identity, bounded PDF structure, checksum, and a fixed 365-day lifetime.
Writes publish a complete unique PDF, then atomically replace the metadata index.
Old PDFs remain until explicit cleaning; legacy PDF/sidecar pairs remain readable.
Concurrent destructive cleaning and power-loss durability are not guaranteed.
PA_CACHE_DIR overrides the default ~/.paper-agent/cache/ directory.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
import time
import uuid
import re
from pathlib import Path
from typing import Optional, Tuple


# Default cache root per [P0-2] acceptance criteria
DEFAULT_CACHE_ROOT = Path.home() / ".paper-agent" / "cache"


def get_cache_root() -> Path:
    """Resolve and create PA_CACHE_DIR, or the default user cache directory."""
    env = os.environ.get("PA_CACHE_DIR")
    if env:
        p = Path(env).expanduser()
        p.mkdir(parents=True, exist_ok=True)
        return p
    # Default: ~/.paper-agent/cache/
    p = DEFAULT_CACHE_ROOT
    p.mkdir(parents=True, exist_ok=True)
    return p


def _bare_doi(doi: str) -> str:
    """Remove supported DOI prefixes without collapsing identifier characters."""
    if doi.startswith("https://doi.org/"):
        doi = doi[len("https://doi.org/"):]
    elif doi.startswith("http://doi.org/"):
        doi = doi[len("http://doi.org/"):]
    elif doi.startswith("doi:"):
        doi = doi[len("doi:"):]
    return doi


def _doi_slug(doi: str) -> str:
    """Keep the existing cache filename format for compatibility."""
    return _bare_doi(doi).replace("/", "_").replace(".", "_")


def _paths(doi: str, root: Optional[Path] = None) -> Tuple[Path, Path]:
    """Return (pdf_path, meta_path) for a DOI's cache entries."""
    root = root or get_cache_root()
    slug = _doi_slug(doi)
    return root / f"{slug}.pdf", root / f"{slug}.meta.json"


def _generation_prefix(slug: str) -> str:
    return 'pa-' + hashlib.sha256(slug.encode('utf-8')).hexdigest() + '-'


def _generation_paths(root: Path, slug: str):
    return root.glob(_generation_prefix(slug) + '*.pdf')


def _is_pdf(b: bytes) -> bool:
    """Check the PDF header without validating the full document structure."""
    return b.startswith(b"%PDF") and len(b) > 4


def _file_identity(path: Path) -> tuple:
    """Observe replacement/in-place edits; this is not a lock or a durable lease."""
    stat = path.stat()
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


# ===== public API =====

def cache_get(doi: str, root: Optional[Path] = None) -> Optional[dict]:
    """Return cache entry dict if hit, else None.

    Dict shape (on hit):
        {
            "doi": str, "pdf_path": str, "meta_path": str,
            "sha256": str, "ts": float (epoch),
            "channel": str (last-fetch channel name),
            "url": str (originating URL),
            "size": int (bytes),
            "age_days": float,
        }

    Cache hit criteria (all must pass):
      1. Both .pdf and .meta.json exist
      2. .pdf passes resource-bounded structural validation
      3. .meta.json sha256 matches re-computed sha256 of .pdf
      4. DOI matches and ts is finite, positive, not future, and at most 365 days old
    """
    root = root or get_cache_root()
    pdf_path, meta_path = _paths(doi, root)
    try:
        meta_identity = _file_identity(meta_path)
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return None
    if isinstance(meta, dict) and 'pdf_file' in meta:
        filename = meta['pdf_file']
        pattern = re.escape(_generation_prefix(_doi_slug(doi))) + r'[0-9a-f]{32}\.pdf'
        if not isinstance(filename, str) or re.fullmatch(pattern, filename) is None:
            return None
        pdf_path = root / filename
    try:
        before = (_file_identity(pdf_path), meta_identity)
    except OSError:
        return None

    if not isinstance(meta, dict) or not isinstance(meta.get("doi"), str):
        return None
    if _bare_doi(meta["doi"]).casefold() != _bare_doi(doi).casefold():
        return None
    ts = meta.get("ts")
    if isinstance(ts, bool) or not isinstance(ts, (int, float)):
        return None
    try:
        if not math.isfinite(ts):
            return None
    except OverflowError:
        return None
    age_days = (time.time() - ts) / 86400
    if ts <= 0 or not 0 <= age_days <= 365:
        return None

    from .pdf_validation import validate_pdf
    checked = validate_pdf(pdf_path)
    if not checked.get('valid'):
        return None
    actual_sha = checked['sha256']
    if meta.get('sha256') != actual_sha:
        return None
    try:
        if before != (_file_identity(pdf_path), _file_identity(meta_path)):
            return None
    except OSError:
        return None

    return {
        "doi": doi,
        "pdf_path": str(pdf_path),
        "meta_path": str(meta_path),
        "sha256": actual_sha,
        "ts": meta.get("ts", 0),
        "channel": meta.get("channel", ""),
        "url": meta.get("url", ""),
        "size": checked["size"],
        "validation_policy": checked["validation_policy"],
        "age_days": age_days,
    }


def cache_put(doi: str, body: bytes, channel: str = "", url: str = "",
              root: Optional[Path] = None) -> dict:
    """Persist PDF + sidecar to cache. Returns the entry dict on success.

    Publishes a new generation and atomically switches the index (newer ts + sha256).
    Checks PDF headers before writing; does not parse or validate full PDF structure.
    """
    if not _is_pdf(body):
        raise ValueError(
            f"cache_put: refusing to cache invalid PDF for {doi} "
            f"(PDF header missing or incomplete: actual size={len(body)})"
        )
    root = root or get_cache_root()
    pdf_path, meta_path = _paths(doi, root)
    pdf_path = root / (_generation_prefix(_doi_slug(doi)) + uuid.uuid4().hex + '.pdf')
    sha = hashlib.sha256(body).hexdigest()
    ts = time.time()
    metadata = json.dumps(
        {"doi": doi, "ts": ts, "sha256": sha, "channel": channel,
         "url": url, "size": len(body), "pdf_file": pdf_path.name},
        ensure_ascii=False, indent=2,
    ).encode("utf-8")
    root.mkdir(parents=True, exist_ok=True)
    staged = []
    published = False
    try:
        for target, data in ((pdf_path, body), (meta_path, metadata)):
            with tempfile.NamedTemporaryFile(dir=root, prefix=".pa-cache-", delete=False) as stream:
                temporary = Path(stream.name)
                staged.append((temporary, target))
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            # Both files are fully staged before publishing either one.
        for temporary, target in staged:
            temporary.replace(target)
        published = True
    finally:
        for temporary, _ in staged:
            temporary.unlink(missing_ok=True)
        if not published:
            pdf_path.unlink(missing_ok=True)
    return {
        "doi": doi, "pdf_path": str(pdf_path), "meta_path": str(meta_path),
        "sha256": sha, "ts": ts, "channel": channel, "url": url,
        "size": len(body), "age_days": 0,
    }


def cache_remove(doi: str, root: Optional[Path] = None) -> bool:
    """Remove cache entry for one DOI. Returns True if anything was removed."""
    root = root or get_cache_root()
    pdf_path, meta_path = _paths(doi, root)
    removed = False
    for p in (meta_path, pdf_path, *_generation_paths(root, _doi_slug(doi))):
        if p.exists():
            p.unlink()
            removed = True
    return removed


def cache_stats(root: Optional[Path] = None) -> dict:
    """Aggregate stats over all cache entries.

    Returns:
        {
            "root": str,
            "total_files": int,           # .pdf + .meta.json
            "paper_count": int,           # unique DOI count
            "total_size_bytes": int,
            "oldest_ts": float | None,
            "newest_ts": float | None,
            "oldest_age_days": float | None,
            "newest_age_days": float | None,
        }
    """
    root = root or get_cache_root()
    pdfs = list(root.glob("*.pdf"))
    metas = list(root.glob("*.meta.json"))

    total_size = 0
    ts_list: list = []
    for p in pdfs:
        try:
            total_size += p.stat().st_size
        except OSError:
            pass
    for m in metas:
        try:
            data = json.loads(m.read_text(encoding="utf-8"))
            ts_list.append(data.get("ts", 0))
        except (json.JSONDecodeError, OSError):
            pass

    paper_count = len(metas)  # Index slots, independent of retained PDF versions.

    return {
        "root": str(root),
        "total_files": len(pdfs) + len(metas),
        "paper_count": paper_count,
        "total_size_bytes": total_size,
        "oldest_ts": min(ts_list) if ts_list else None,
        "newest_ts": max(ts_list) if ts_list else None,
        "oldest_age_days": (time.time() - min(ts_list)) / 86400 if ts_list else None,
        "newest_age_days": (time.time() - max(ts_list)) / 86400 if ts_list else None,
    }


def cache_clean(older_than_days: Optional[int] = None, root: Optional[Path] = None) -> dict:
    """Remove cache entries older than N days. Returns summary.

    Args:
        older_than_days: only remove entries with age > N days.
                          None means remove ALL (cache_clear semantics).
        root: cache root override; defaults to get_cache_root()

    Returns:
        {
            "removed_files": int,
            "freed_bytes": int,
            "remaining_files": int,
            "remaining_papers": int,
        }
    """
    root = root or get_cache_root()
    removed_files = 0
    freed_bytes = 0
    now = time.time()

    # Walk all .meta.json sidecars; check ts; remove pdf + meta together
    metas = list(root.glob("*.meta.json"))
    for m in metas:
        try:
            data = json.loads(m.read_text(encoding="utf-8"))
            ts = data.get("ts", 0)
        except (json.JSONDecodeError, OSError):
            ts = 0
        if older_than_days is not None and (now - ts) < older_than_days * 86400:
            continue
        # Explicit cleaning removes the index and all its retained generations.
        slug = m.name[:-len('.meta.json')]
        for target in (m, root / f'{slug}.pdf', *_generation_paths(root, slug)):
            try:
                size = target.stat().st_size
                target.unlink()
                removed_files += 1
                if target.suffix == '.pdf':
                    freed_bytes += size
            except OSError:
                pass
    if older_than_days is None:
        # A killed first writer may leave an unreferenced generation.
        for target in root.glob('pa-*.pdf'):
            if re.fullmatch(r'pa-[0-9a-f]{64}-[0-9a-f]{32}\.pdf', target.name):
                try:
                    size = target.stat().st_size
                    target.unlink()
                    removed_files += 1
                    freed_bytes += size
                except OSError:
                    pass

    # Recompute remaining stats
    pdfs = list(root.glob("*.pdf"))
    remaining_size = 0
    for p in pdfs:
        try:
            remaining_size += p.stat().st_size
        except OSError:
            pass

    return {
        "removed_files": removed_files,
        "freed_bytes": freed_bytes,
        "remaining_files": len(pdfs) + len(list(root.glob("*.meta.json"))),
        "remaining_papers": len(list(root.glob("*.meta.json"))),
    }
