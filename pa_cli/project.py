"""pa_cli.project — multi-corpus management for research topics.

Per ROADMAP [P2-12] (added 2026-07-15, Phase 1 shipped 2026-07-20 in v3.9.10.8):

  Phase 1 (this commit):
    - project layout spec: ~/.paper-agent/projects/<slug>/
    - pa project init <slug> [--title "..."]   - create project skeleton
    - pa project list                            - list all projects
    - pa project status [slug]                   - show n_papers, n_labels per project
    - pa project corpus [slug]                   - show path to refs.bib
    - pa project rm <slug>                       - remove a project

  Phase 2 (deferred; needs user input on corpus names):
    - pa project corpus-search <slug>            - re-execute saved search scoped
    - pa project corpus-merge <slug1> <slug2>   - cross-corpus dedup

Layout:
  ~/.paper-agent/projects/<slug>/
    meta.json         - project metadata (slug, title, created_at, description)
    refs.bib          - Bibtex file (per-project, user-managed or pa-search)
    judges.sqlite     - pa judge data (subset of global judgements, scoped)

Usage from CLI:
  pa project init finlit --title 'Digital Finance Review'
  pa project list
  pa project status finlit
  pa project corpus finlit       # prints /home/.../projects/finlit/refs.bib
  pa project rm finlit
"""
from __future__ import annotations

import json
import re
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Default project root
DEFAULT_ROOT = Path.home() / ".paper-agent" / "projects"

# Valid slug: ASCII alphanumeric, underscore, dash, dot. No spaces.
_SLUG_RE = re.compile(r"^[\w\-.]+$", re.ASCII)


# ──────────────────────────────────────────────────────────────────────
# Slug validation
# ──────────────────────────────────────────────────────────────────────

def validate_slug(slug: str) -> None:
    """Raise ValueError if slug is not a valid identifier."""
    if not slug:
        raise ValueError("slug cannot be empty")
    if not _SLUG_RE.match(slug):
        raise ValueError(
            f"invalid slug {slug!r}: must be ASCII alphanumeric + _-. (no spaces, no slashes)"
        )


# ──────────────────────────────────────────────────────────────────────
# Project paths
# ──────────────────────────────────────────────────────────────────────

def project_dir(slug: str, root: Path = DEFAULT_ROOT) -> Path:
    """Path to project directory: <root>/<slug>/"""
    return Path(root) / slug


def project_files(slug: str, root: Path = DEFAULT_ROOT) -> Dict[str, Path]:
    """Path to each file in the project."""
    pdir = project_dir(slug, root)
    return {
        'dir': pdir,
        'meta': pdir / 'meta.json',
        'refs': pdir / 'refs.bib',
        'judges': pdir / 'judges.sqlite',
    }


# ──────────────────────────────────────────────────────────────────────
# Meta I/O
# ──────────────────────────────────────────────────────────────────────

def load_meta(slug: str, root: Path = DEFAULT_ROOT) -> Dict:
    """Load meta.json. Returns empty dict if missing."""
    meta_path = project_files(slug, root)['meta']
    if not meta_path.exists():
        return {}
    return json.loads(meta_path.read_text(encoding='utf-8'))


def save_meta(slug: str, meta: Dict, root: Path = DEFAULT_ROOT) -> None:
    """Save meta.json (atomic via temp file)."""
    meta_path = project_files(slug, root)['meta']
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = meta_path.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding='utf-8')
    tmp.replace(meta_path)


# ──────────────────────────────────────────────────────────────────────
# Init
# ──────────────────────────────────────────────────────────────────────

def init_project(
    slug: str,
    title: str = '',
    description: str = '',
    root: Path = DEFAULT_ROOT,
) -> Dict:
    """Create a new project (skeleton: meta.json, empty refs.bib, empty judges.sqlite).

    Returns the saved meta dict.
    Raises FileExistsError if project already exists.
    """
    validate_slug(slug)
    pdir = project_dir(slug, root)
    if pdir.exists():
        raise FileExistsError(f"project {slug!r} already exists at {pdir}")
    pdir.mkdir(parents=True)

    meta = {
        'slug': slug,
        'title': title or slug,
        'description': description,
        'created_at': datetime.now().isoformat(timespec='seconds'),
        'updated_at': datetime.now().isoformat(timespec='seconds'),
    }
    save_meta(slug, meta, root)

    # Empty refs.bib (just a comment header)
    refs_path = project_files(slug, root)['refs']
    refs_path.write_text(
        f"% Bibtex for project {slug!r} ({meta['title']})\n"
        f"% Add entries via: pa search --format bibtex --out - | <append to this file>\n"
        f"% Or hand-craft entries below.\n\n",
        encoding='utf-8',
    )

    # Empty judges.sqlite
    judges_path = project_files(slug, root)['judges']
    conn = sqlite3.connect(str(judges_path))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS judgements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT NOT NULL,
            paper_key TEXT NOT NULL,
            paper_title TEXT,
            relevance INTEGER NOT NULL CHECK (relevance IN (0, 1, 2)),
            reason TEXT,
            source TEXT NOT NULL DEFAULT 'manual',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(query, paper_key)
        );
    """)
    conn.commit()
    conn.close()

    return meta


# ──────────────────────────────────────────────────────────────────────
# List
# ──────────────────────────────────────────────────────────────────────

def list_projects(root: Path = DEFAULT_ROOT) -> List[Dict]:
    """List all projects (sorted by slug). Returns list of meta dicts.

    Skips entries that are not valid project dirs (e.g. leftover files).
    """
    if not root.exists():
        return []
    out = []
    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        meta_path = entry / 'meta.json'
        if not meta_path.exists():
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding='utf-8'))
            meta['_path'] = str(entry)
            out.append(meta)
        except (json.JSONDecodeError, OSError):
            continue
    return out


# ──────────────────────────────────────────────────────────────────────
# Status
# ──────────────────────────────────────────────────────────────────────

def project_status(slug: str, root: Path = DEFAULT_ROOT) -> Dict:
    """Compute n_papers (count bib entries), n_labels (count judge rows)."""
    validate_slug(slug)
    files = project_files(slug, root)
    if not files['dir'].exists():
        raise FileNotFoundError(f"project {slug!r} not found at {files['dir']}")

    meta = load_meta(slug, root)
    n_papers = 0
    if files['refs'].exists():
        try:
            from .scaffold import load_bibtex
            n_papers = len(load_bibtex(files['refs']))
        except Exception:
            n_papers = 0

    n_labels = 0
    if files['judges'].exists():
        try:
            conn = sqlite3.connect(str(files['judges']))
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM judgements")
            n_labels = cur.fetchone()[0]
            conn.close()
        except Exception:
            n_labels = 0

    return {
        'slug': slug,
        'title': meta.get('title', slug),
        'description': meta.get('description', ''),
        'created_at': meta.get('created_at', ''),
        'updated_at': meta.get('updated_at', ''),
        'n_papers': n_papers,
        'n_labels': n_labels,
        'paths': {k: str(v) for k, v in files.items()},
    }


# ──────────────────────────────────────────────────────────────────────
# Remove
# ──────────────────────────────────────────────────────────────────────

def remove_project(slug: str, root: Path = DEFAULT_ROOT, force: bool = False) -> bool:
    """Remove a project directory.

    Returns True if removed, False if not found.
    Without force: refuses if meta.json is missing (to avoid nuking non-project dirs).
    """
    validate_slug(slug)
    pdir = project_dir(slug, root)
    if not pdir.exists():
        return False
    if not force and not (pdir / 'meta.json').exists():
        raise ValueError(
            f"refusing to remove {pdir}: no meta.json (use --force to override)"
        )
    shutil.rmtree(pdir)
    return True
