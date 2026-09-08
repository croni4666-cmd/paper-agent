"""pa_cli.cache — Local PDF + sidecar-meta cache for `pa fetch`.

Avoids re-downloading the same DOI across `pa fetch` invocations.

PDFs and JSON sidecars share the existing DOI-derived filename layout.
Reads verify DOI identity, PDF header, checksum, and a fixed 365-day lifetime.
Writes stage both files before replacing each destination. Pair publication is
not atomic: an interrupted replacement can leave a pair that reads as a miss.
PA_CACHE_DIR overrides the default ~/.paper-agent/cache/ directory.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
import time
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


def _is_pdf(b: bytes) -> bool:
    """Check the PDF header without validating the full document structure."""
    return b.startswith(b"%PDF") and len(b) > 4


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
      2. .pdf passes is_pdf() magic check
      3. .meta.json sha256 matches re-computed sha256 of .pdf
      4. DOI matches and ts is finite, positive, not future, and at most 365 days old
    """
    root = root or get_cache_root()
    pdf_path, meta_path = _paths(doi, root)
    if not (pdf_path.exists() and meta_path.exists()):
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
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

    # Validate PDF magic
    try:
        body = pdf_path.read_bytes()
    except OSError:
        return None
    if not _is_pdf(body):
        return None

    # Validate sha256 against sidecar
    actual_sha = hashlib.sha256(body).hexdigest()
    if meta.get("sha256") != actual_sha:
        # A reader may see the gap between the two published files. Treat it
        # as a miss, without deleting files another writer may be replacing.
        return None

    return {
        "doi": doi,
        "pdf_path": str(pdf_path),
        "meta_path": str(meta_path),
        "sha256": actual_sha,
        "ts": meta.get("ts", 0),
        "channel": meta.get("channel", ""),
        "url": meta.get("url", ""),
        "size": len(body),
        "age_days": age_days,
    }


def cache_put(doi: str, body: bytes, channel: str = "", url: str = "",
              root: Optional[Path] = None) -> dict:
    """Persist PDF + sidecar to cache. Returns the entry dict on success.

    Idempotent: overwrites existing entry if present (newer ts + sha256).
    Checks PDF headers before writing; does not parse or validate full PDF structure.
    """
    if not _is_pdf(body):
        raise ValueError(
            f"cache_put: refusing to cache invalid PDF for {doi} "
            f"(PDF header missing or incomplete: actual size={len(body)})"
        )
    root = root or get_cache_root()
    pdf_path, meta_path = _paths(doi, root)
    sha = hashlib.sha256(body).hexdigest()
    ts = time.time()
    metadata = json.dumps(
        {"doi": doi, "ts": ts, "sha256": sha, "channel": channel,
         "url": url, "size": len(body)},
        ensure_ascii=False, indent=2,
    ).encode("utf-8")
    root.mkdir(parents=True, exist_ok=True)
    staged = []
    try:
        for target, data in ((pdf_path, body), (meta_path, metadata)):
            with tempfile.NamedTemporaryFile(dir=root, prefix=".pa-cache-", delete=False) as stream:
                temporary = Path(stream.name)
                staged.append((temporary, target))
                stream.write(data)
            # Both files are fully staged before publishing either one.
        for temporary, target in staged:
            temporary.replace(target)
    finally:
        for temporary, _ in staged:
            temporary.unlink(missing_ok=True)
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
    for p in (pdf_path, meta_path):
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
    metas = {p.with_suffix(".meta.json") for p in pdfs}  # not strictly needed
    metas = [m for m in metas if m.exists()] if False else None  # placeholder
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

    paper_count = len(pdfs)  # .pdf count = unique papers (1 entry per DOI)

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
        # Remove paired .pdf and .meta.json
        slug = m.name.replace(".meta.json", "")
        pdf = root / f"{slug}.pdf"
        if pdf.exists():
            try:
                freed_bytes += pdf.stat().st_size
                pdf.unlink()
                removed_files += 1
            except OSError:
                pass
        try:
            m.unlink()
            removed_files += 1
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
        "remaining_papers": len(pdfs),
    }
