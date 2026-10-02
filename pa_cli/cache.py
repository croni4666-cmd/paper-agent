"""pa_cli.cache — Local PDF + sidecar-meta cache for `pa fetch`.

Avoids re-downloading the same DOI across `pa fetch` invocations.

Design (matches user's [P0-2] acceptance criteria):
  ~/.paper-agent/cache/{doi_slug}.pdf          ← actual PDF bytes
  ~/.paper-agent/cache/{doi_slug}.meta.json     ← {ts, sha256, channel, url, size}

Cache layout is **read-through**:
  - pa fetch checks cache first; on hit (PDF magic + sha256 match) returns path
  - cascade skips entirely on hit
  - after cascade success, sidecar is written so next call hits cache

Cache root configuration:
  - Default: ~/.paper-agent/cache/  (per original P0-2 spec)
  - Override: PA_CACHE_DIR env var
  - Dev fallback (HOME undefined): ./pa_cache/

TTL handling (admin-side, not enforced on read):
  - `pa cache stats` reports oldest/newest timestamps
  - `pa cache clean --older-than Nd` removes old entries
  - read-path ignores expired (treats as miss) — defensive against slow invalidation
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import time
import uuid
from pathlib import Path
from typing import Optional, Tuple


# Default cache root per [P0-2] acceptance criteria
DEFAULT_CACHE_ROOT = Path.home() / ".paper-agent" / "cache"


def get_cache_root() -> Path:
    """Resolve cache root. PA_CACHE_DIR env var > ~/.paper-agent/cache/."""
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
    """Remove supported DOI prefixes."""
    if doi.startswith("https://doi.org/"):
        doi = doi[len("https://doi.org/"):]
    elif doi.startswith("http://doi.org/"):
        doi = doi[len("http://doi.org/"):]
    elif doi.startswith("doi:"):
        doi = doi[len("doi:"):]
    return doi


def _doi_slug(doi: str) -> str:
    """DOI → filename slug. Strip URL prefixes, replace problematic chars."""
    bare = _bare_doi(doi)
    slug = bare.replace("/", "_").replace(".", "_")
    return re.sub(r'[^A-Za-z0-9_\-]', '_', slug)


def _generation_prefix(slug: str) -> str:
    return 'pa-' + hashlib.sha256(slug.encode('utf-8')).hexdigest()[:24] + '-'


def _generation_paths(root: Path, slug: str):
    return root.glob(_generation_prefix(slug) + '*.pdf')


def _paths(doi: str, root: Optional[Path] = None) -> Tuple[Path, Path]:
    """Return (pdf_path, meta_path) for a DOI's cache entries.

    If a metadata sidecar exists and specifies an immutable generation pdf_file,
    returns that active generation file; otherwise defaults to the standard slug path.
    """
    root = root or get_cache_root()
    slug = _doi_slug(doi)
    meta_path = root / f"{slug}.meta.json"
    if meta_path.exists():
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("pdf_file"):
                gen_path = root / data["pdf_file"]
                if gen_path.exists():
                    return gen_path, meta_path
        except (json.JSONDecodeError, OSError):
            pass
    return root / f"{slug}.pdf", meta_path


def _is_pdf(b: bytes) -> bool:
    """PDF magic check — same as fetch.is_pdf."""
    return b.startswith(b"%PDF") and len(b) > 50_000


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
      1. Both PDF and .meta.json exist
      2. PDF passes is_pdf() magic check
      3. .meta.json sha256 matches re-computed sha256 of PDF
      4. ts in meta is valid
    """
    root = root or get_cache_root()
    pdf_path, meta_path = _paths(doi, root)
    if not (pdf_path.exists() and meta_path.exists()):
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    if not isinstance(meta, dict) or not isinstance(meta.get("doi"), str):
        return None
    if _bare_doi(meta["doi"]).casefold() != _bare_doi(doi).casefold():
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
    if meta.get("sha256") and meta["sha256"] != actual_sha:
        # Sidecar out of sync — treat as miss.
        # NEVER unlink existing files on read-time observation:
        # this prevents losing valid files during concurrent writes or inspection.
        return None

    ts = meta.get("ts", 0)
    age_days = (time.time() - ts) / 86400 if ts else 0.0

    return {
        "doi": doi,
        "pdf_path": str(pdf_path),
        "meta_path": str(meta_path),
        "sha256": actual_sha,
        "ts": ts,
        "channel": meta.get("channel", ""),
        "url": meta.get("url", ""),
        "size": len(body),
        "age_days": age_days,
    }


def cache_put(doi: str, body: bytes, channel: str = "", url: str = "",
              root: Optional[Path] = None) -> dict:
    """Persist PDF + sidecar to cache. Returns the entry dict on success.

    Idempotent: writes new immutable generation PDF, then atomically switches
    the metadata pointer (newer ts + sha256). If write fails, the old valid cache
    entry remains completely intact.
    """
    if not _is_pdf(body):
        raise ValueError(
            f"cache_put: refusing to cache invalid PDF for {doi} "
            f"(magic prefix check failed or size < 50KB: actual size={len(body)})"
        )
    root = root or get_cache_root()
    root.mkdir(parents=True, exist_ok=True)
    slug = _doi_slug(doi)
    meta_path = root / f"{slug}.meta.json"
    gen_filename = f"{_generation_prefix(slug)}{uuid.uuid4().hex[:16]}.pdf"
    gen_pdf_path = root / gen_filename

    sha = hashlib.sha256(body).hexdigest()
    ts = time.time()
    meta_dict = {
        "doi": doi,
        "ts": ts,
        "sha256": sha,
        "channel": channel,
        "url": url,
        "size": len(body),
        "pdf_file": gen_filename,
    }
    meta_bytes = json.dumps(meta_dict, ensure_ascii=False, indent=2).encode("utf-8")

    staged = []
    published = False
    try:
        # 1. Stage PDF
        with tempfile.NamedTemporaryFile(dir=root, prefix=".pa-put-pdf-", delete=False) as f_pdf:
            staged.append((Path(f_pdf.name), gen_pdf_path))
            f_pdf.write(body)
            f_pdf.flush()
            os.fsync(f_pdf.fileno())

        # 2. Stage metadata
        with tempfile.NamedTemporaryFile(dir=root, prefix=".pa-put-meta-", delete=False) as f_meta:
            staged.append((Path(f_meta.name), meta_path))
            f_meta.write(meta_bytes)
            f_meta.flush()
            os.fsync(f_meta.fileno())

        # 3. Publish: first write immutable generation PDF, then atomically replace metadata pointer
        os.replace(staged[0][0], gen_pdf_path)
        os.replace(staged[1][0], meta_path)
        published = True
    finally:
        for tmp_file, _ in staged:
            if tmp_file.exists():
                try:
                    tmp_file.unlink()
                except OSError:
                    pass
        if not published and gen_pdf_path.exists():
            try:
                gen_pdf_path.unlink()
            except OSError:
                pass

    return {
        "doi": doi,
        "pdf_path": str(gen_pdf_path),
        "meta_path": str(meta_path),
        "sha256": sha,
        "ts": ts,
        "channel": channel,
        "url": url,
        "size": len(body),
        "age_days": 0,
    }


def cache_remove(doi: str, root: Optional[Path] = None) -> bool:
    """Remove cache entry for one DOI. Returns True if anything was removed."""
    root = root or get_cache_root()
    slug = _doi_slug(doi)
    meta_path = root / f"{slug}.meta.json"
    legacy_pdf = root / f"{slug}.pdf"
    removed = False

    targets = [meta_path, legacy_pdf]
    targets.extend(_generation_paths(root, slug))

    for p in targets:
        if p.exists():
            try:
                p.unlink()
                removed = True
            except OSError:
                pass
    return removed


def cache_stats(root: Optional[Path] = None) -> dict:
    """Aggregate stats over all cache entries.

    Returns:
        {
            "root": str,
            "total_files": int,           # .pdf + .meta.json
            "paper_count": int,           # unique valid DOI count
            "total_size_bytes": int,
            "oldest_ts": float | None,
            "newest_ts": float | None,
            "oldest_age_days": float | None,
            "newest_age_days": float | None,
        }
    """
    root = root or get_cache_root()
    pdfs = [p for p in root.glob("*.pdf") if not p.name.startswith(".")]
    metas = [m for m in root.glob("*.meta.json") if not m.name.startswith(".")]

    valid_papers = 0
    total_size = 0
    ts_list: list = []
    for m in metas:
        try:
            data = json.loads(m.read_text(encoding="utf-8"))
            slug = m.name[:-len('.meta.json')]
            pdf_filename = data.get("pdf_file") or f"{slug}.pdf"
            p_file = root / pdf_filename
            if p_file.exists():
                actual_sha = hashlib.sha256(p_file.read_bytes()).hexdigest()
                if data.get("sha256") == actual_sha:
                    valid_papers += 1
                    total_size += p_file.stat().st_size
                    ts_list.append(data.get("ts", 0))
        except (json.JSONDecodeError, OSError):
            pass

    return {
        "root": str(root),
        "total_files": len(pdfs) + len(metas),
        "paper_count": valid_papers,
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
    metas = [m for m in root.glob("*.meta.json") if not m.name.startswith(".")]
    for m in metas:
        try:
            data = json.loads(m.read_text(encoding="utf-8"))
            ts = data.get("ts", 0)
        except (json.JSONDecodeError, OSError):
            ts = 0
        if older_than_days is not None and (now - ts) < older_than_days * 86400:
            continue
        slug = m.name[:-len('.meta.json')]
        targets = [m, root / f'{slug}.pdf', *_generation_paths(root, slug)]
        for target in targets:
            if target.exists():
                try:
                    size = target.stat().st_size
                    target.unlink()
                    removed_files += 1
                    if target.suffix == '.pdf':
                        freed_bytes += size
                except OSError:
                    pass

    # Clean orphaned temporary files if cleaning all
    if older_than_days is None or older_than_days < 0:
        for target in root.glob('.pa-put-*'):
            try:
                target.unlink()
                removed_files += 1
            except OSError:
                pass

    pdfs = [p for p in root.glob("*.pdf") if not p.name.startswith(".")]
    remaining_metas = [m for m in root.glob("*.meta.json") if not m.name.startswith(".")]

    return {
        "removed_files": removed_files,
        "freed_bytes": freed_bytes,
        "remaining_files": len(pdfs) + len(remaining_metas),
        "remaining_papers": len(remaining_metas),
    }

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
