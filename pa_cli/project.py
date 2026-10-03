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
import os
import re
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union

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
    if slug in ('.', '..') or '..' in slug or slug.startswith('.'):
        raise ValueError(f"invalid slug {slug!r}: cannot be '.' or contain '..'")
    if not _SLUG_RE.match(slug):
        raise ValueError(
            f"invalid slug {slug!r}: must be ASCII alphanumeric + _-. (no spaces, no slashes)"
        )


# ──────────────────────────────────────────────────────────────────────
# Project paths
# ──────────────────────────────────────────────────────────────────────

def project_dir(slug: str, root: Path = DEFAULT_ROOT) -> Path:
    """Path to project directory: <root>/<slug>/ with path-traversal prevention."""
    target = (Path(root) / slug).resolve()
    root_resolved = Path(root).resolve()
    try:
        target.relative_to(root_resolved)
    except ValueError:
        raise ValueError(f"Path traversal detected in slug {slug!r}")
    return target


def project_files(slug: str, root: Path = DEFAULT_ROOT) -> Dict[str, Path]:
    """Path to each file in the project."""
    pdir = project_dir(slug, root)
    return {
        'dir': pdir,
        'meta': pdir / 'meta.json',
        'refs': pdir / 'refs.bib',
        'judges': pdir / 'judges.sqlite',
        'pdfs': pdir / 'pdfs',
        'topics': pdir / 'topics.json',
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

    # Ensure pdfs directory exists
    pdfs_path = project_files(slug, root)['pdfs']
    pdfs_path.mkdir(parents=True, exist_ok=True)

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

    n_pdfs = 0
    if files['pdfs'].exists():
        try:
            n_pdfs = len(list(files['pdfs'].glob("*.pdf")))
        except Exception:
            n_pdfs = 0

    n_topics = meta.get('n_topics', 0)
    topics_file = files['dir'] / 'topics.json'
    if topics_file.exists() and not n_topics:
        try:
            t_data = json.loads(topics_file.read_text(encoding='utf-8'))
            n_topics = len(t_data.get('topics', []))
        except Exception:
            pass

    return {
        'slug': slug,
        'title': meta.get('title', slug),
        'description': meta.get('description', ''),
        'created_at': meta.get('created_at', ''),
        'updated_at': meta.get('updated_at', ''),
        'n_papers': n_papers,
        'n_labels': n_labels,
        'n_pdfs': n_pdfs,
        'n_topics': n_topics,
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


# ──────────────────────────────────────────────────────────────────────
# Phase 2: Corpus Search, Merge, and Zotero Check ([P2-12])
# ──────────────────────────────────────────────────────────────────────

def corpus_search(
    slug: str,
    query: str,
    root: Path = DEFAULT_ROOT,
) -> List[Dict]:
    """Search within the project's refs.bib by keyword/phrase in title, author, abstract, doi, or year."""
    validate_slug(slug)
    files = project_files(slug, root)
    if not files['refs'].exists():
        return []

    from .scaffold import load_bibtex
    entries = load_bibtex(files['refs'])
    if not entries:
        return []

    q_lower = query.strip().casefold()
    tokens = [t for t in q_lower.split() if t]

    matches = []
    for e in entries:
        title = e.get('title', '')
        author = e.get('author', '')
        abstract = e.get('abstract', '')
        doi = e.get('doi', '')
        year = e.get('year', '')
        journal = e.get('journal', '')
        key = e.get('key', '')

        search_blob = f"{title} {author} {abstract} {doi} {year} {journal} {key}".casefold()
        if all(token in search_blob for token in tokens):
            matched_fields = []
            for fname, fval in [('title', title), ('author', author), ('abstract', abstract),
                                ('doi', doi), ('year', year), ('journal', journal), ('key', key)]:
                if any(token in fval.casefold() for token in tokens):
                    matched_fields.append(fname)
            entry_copy = dict(e)
            entry_copy['_matched_fields'] = matched_fields
            matches.append(entry_copy)

    return matches


def corpus_merge(
    target_slug: str,
    source: Path | str,
    root: Path = DEFAULT_ROOT,
) -> Dict:
    """Merge an external BibTeX file or another project's refs.bib into target_slug.

    Deduplicates by DOI (normalized) and (normalized title, year) when DOI is missing.
    Appends only unique entries to target's refs.bib and updates meta.json.
    """
    validate_slug(target_slug)
    target_files = project_files(target_slug, root)
    if not target_files['dir'].exists():
        raise FileNotFoundError(f"target project {target_slug!r} not found at {target_files['dir']}")

    source_str = str(source).strip()
    source_p = Path(source_str).expanduser()
    if source_p.is_file():
        source_bib = source_p.resolve()
        source_desc = str(source_bib)
    else:
        # Check if source is a project slug
        try:
            validate_slug(source_str)
            source_pdir = project_dir(source_str, root)
            if source_pdir.is_dir() and (source_pdir / 'refs.bib').exists():
                source_bib = source_pdir / 'refs.bib'
                source_desc = f"project:{source_str}"
            else:
                source_bib = source_p.resolve()
                source_desc = str(source_bib)
        except ValueError:
            source_bib = source_p.resolve()
            source_desc = str(source_bib)

    if not source_bib.is_file():
        raise FileNotFoundError(f"source BibTeX file or project not found: {source}")

    from .scaffold import load_bibtex
    target_entries = load_bibtex(target_files['refs']) if target_files['refs'].exists() else []
    source_entries = load_bibtex(source_bib)

    def _entry_key(entry: Dict[str, str]) -> Tuple[str, str]:
        doi = entry.get('doi', '').strip().lower()
        if doi:
            doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi)
            return ("doi", doi)
        title = re.sub(r"\W+", "", entry.get('title', '').strip().lower())
        year = entry.get('year', '').strip()
        return ("title_year", f"{title}_{year}")

    existing_entries_by_key = {}
    target_entry_ids = {id(e) for e in target_entries}
    for e in target_entries:
        k = _entry_key(e)
        if k[1]:
            existing_entries_by_key[k] = e

    added = []
    updated = []
    skipped = []
    source_key_to_canonical: Dict[str, Dict] = {}

    for e in source_entries:
        if e.get("_is_special") or e.get("type") in ("string", "preamble", "comment"):
            target_special_raws = {t.get("_raw", "").strip() for t in target_entries if t.get("_is_special") or t.get("type") in ("string", "preamble", "comment")}
            if e.get("_raw", "").strip() not in target_special_raws:
                added.append(e)
            continue

        k = _entry_key(e)
        if k[1] and k in existing_entries_by_key:
            target_entry = existing_entries_by_key[k]
            t_title = target_entry.get("title", "")
            s_title = e.get("title", "")
            is_stub = t_title.startswith("Paper 10.") or not target_entry.get("author")
            has_rich = s_title and not s_title.startswith("Paper 10.") and (e.get("author") or e.get("journal"))
            if is_stub and has_rich:
                for field, val in e.items():
                    if field in ("key", "_raw", "_was_updated"):
                        continue
                    if val and (not target_entry.get(field) or field in ("title", "author", "journal", "booktitle", "year", "volume", "number", "pages", "type", "doi", "url", "abstract", "note", "publisher", "crossref")):
                        target_entry[field] = val
                        if field == "crossref":
                            target_entry["_crossref_from_source"] = True
                if id(target_entry) in target_entry_ids:
                    target_entry["_was_updated"] = True
                    updated.append(e)
                else:
                    skipped.append(e)
            else:
                skipped.append(e)
            canonical_entry = target_entry
        else:
            if k[1]:
                existing_entries_by_key[k] = e
            added.append(e)
            canonical_entry = e

        if e.get("key"):
            source_key_to_canonical[e["key"]] = canonical_entry

    from .bibtex import format_bibtex_entry
    import tempfile

    # Allocate non-colliding keys for added regular entries
    seen_keys = {item.get("key") for item in target_entries if item.get("key")}
    for item in added:
        if item.get("_is_special") or item.get("type") in ("string", "preamble", "comment"):
            continue
        orig_k = item.get("key") or "ref"
        candidate = orig_k
        suffix = 2
        while candidate in seen_keys:
            candidate = f"{orig_k}_v{suffix}"
            suffix += 1
        seen_keys.add(candidate)
        item["key"] = candidate

    # Build comprehensive source key mapping to canonical keys (for collisions, dedup, and aliases)
    source_key_map: Dict[str, str] = {}
    for src_k, canonical_ent in source_key_to_canonical.items():
        if canonical_ent.get("key"):
            source_key_map[src_k] = canonical_ent["key"]

    # Remap crossref references in added entries AND updated target entries using source_key_map
    entries_to_remap = [item for item in added if not item.get("_is_special") and item.get("type") not in ("string", "preamble", "comment")] + [item for item in target_entries if item.get("_was_updated") and item.get("_crossref_from_source")]
    for item in entries_to_remap:
        crossref = item.get("crossref")
        if crossref and crossref in source_key_map:
            item["crossref"] = source_key_map[crossref]

    if updated:
        # Re-write the full refs.bib with updated metadata, preserving raw text for untouched items
        meta = load_meta(target_slug, root)
        rebuilt_text = (
            f"% Bibtex for project {target_slug!r} ({meta.get('title', target_slug)})\n"
            f"% Updated with rich metadata on {datetime.now().isoformat(timespec='seconds')}\n\n"
        )
        for item in target_entries:
            if not item.get("_was_updated") and item.get("_raw"):
                rebuilt_text += item["_raw"].strip() + "\n\n"
            else:
                rebuilt_text += format_bibtex_entry(item) + "\n"
        if added:
            added_specials = [item for item in added if item.get("_is_special") or item.get("type") in ("string", "preamble", "comment")]
            added_regulars = [item for item in added if not item.get("_is_special") and item.get("type") not in ("string", "preamble", "comment")]
            if added_specials:
                for item in added_specials:
                    rebuilt_text += item.get("_raw", "").strip() + "\n\n"
            if added_regulars:
                rebuilt_text += f"\n% --- Merged from {source_desc} on {datetime.now().isoformat(timespec='seconds')} ---\n"
                for item in added_regulars:
                    rebuilt_text += format_bibtex_entry(item) + "\n"

        target_file = target_files['refs']
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=target_file.parent, delete=False, suffix='.tmp') as f_tmp:
            f_tmp.write(rebuilt_text)
            tmp_path = Path(f_tmp.name)
        os.replace(tmp_path, target_file)
        meta['updated_at'] = datetime.now().isoformat(timespec='seconds')
        save_meta(target_slug, meta, root)

    elif added:
        appended_text = ""
        added_specials = [item for item in added if item.get("_is_special") or item.get("type") in ("string", "preamble", "comment")]
        added_regulars = [item for item in added if not item.get("_is_special") and item.get("type") not in ("string", "preamble", "comment")]
        if added_specials:
            for item in added_specials:
                appended_text += "\n" + item.get("_raw", "").strip() + "\n"
        if added_regulars:
            appended_text += "\n% --- Merged from " + source_desc + " on " + datetime.now().isoformat(timespec='seconds') + " ---\n"
            for item in added_regulars:
                appended_text += format_bibtex_entry(item) + "\n"

        target_file = target_files['refs']
        existing_text = target_file.read_text(encoding='utf-8') if target_file.exists() else ""
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=target_file.parent, delete=False, suffix='.tmp') as f_tmp:
            f_tmp.write(existing_text + appended_text)
            tmp_path = Path(f_tmp.name)
        os.replace(tmp_path, target_file)

        meta = load_meta(target_slug, root)
        meta['updated_at'] = datetime.now().isoformat(timespec='seconds')
        save_meta(target_slug, meta, root)

    total_after = len(target_entries) + len(added)

    return {
        "target": target_slug,
        "source": source_desc,
        "total_source": len(source_entries),
        "added": len(added),
        "updated": len(updated),
        "duplicates_skipped": len(skipped),
        "total_after": total_after,
    }


def corpus_add(
    slug: str,
    doi: Optional[str] = None,
    bibtex_str: Optional[str] = None,
    title: Optional[str] = None,
    author: Optional[str] = None,
    year: Optional[str] = None,
    root: Path = DEFAULT_ROOT,
) -> Dict:
    """Add a single paper or bibtex snippet to project refs.bib."""
    validate_slug(slug)
    files = project_files(slug, root)
    if not files['dir'].exists():
        raise FileNotFoundError(f"project {slug!r} not found at {files['dir']}")

    from .scaffold import load_bibtex
    from .bibtex import to_bibtex
    target_entries = load_bibtex(files['refs']) if files['refs'].exists() else []

    if doi:
        clean_doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi.strip().lower())
        for e in target_entries:
            e_doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", e.get('doi', '').strip().lower())
            if e_doi and e_doi == clean_doi:
                return {"status": "skipped", "reason": "doi_already_exists", "doi": doi, "slug": slug}

    existing_cite_keys = {e.get('key') for e in target_entries if e.get('key')}
    if bibtex_str:
        snippet = f"\n{bibtex_str.strip()}\n"
    else:
        paper_dict = {
            "title": title or f"Paper {doi}",
            "authors": [a.strip() for a in author.split(" and ")] if author else [],
            "year": year or "",
            "doi": doi or "",
            "type": "article",
        }
        snippet = to_bibtex(paper_dict, existing_cite_keys)

    with files['refs'].open('a', encoding='utf-8') as f:
        f.write(snippet)

    meta = load_meta(slug, root)
    meta['updated_at'] = datetime.now().isoformat(timespec='seconds')
    save_meta(slug, meta, root)

    return {"status": "added", "slug": slug, "doi": doi, "total_after": len(target_entries) + 1}


def corpus_check_zotero(
    slug: str,
    root: Path = DEFAULT_ROOT,
    zotero_db: Optional[Path] = None,
) -> Dict:
    """Check all DOIs in the project's refs.bib against the user's local Zotero library."""
    validate_slug(slug)
    files = project_files(slug, root)
    if not files['refs'].exists():
        return {"error": "refs_bib_not_found", "slug": slug}

    from .zotero_local import find_zotero_db, get_library_dois, check_corpus, extract_dois_from_bibtex
    db_path = zotero_db or find_zotero_db()
    if not db_path:
        return {"error": "zotero_db_not_found", "slug": slug}

    dois = extract_dois_from_bibtex(files['refs'])
    lib_dois = get_library_dois(db_path)
    result = check_corpus(dois, lib_dois)
    result["slug"] = slug
    result["zotero_db"] = str(db_path)
    return result


def scan_directory_dois(
    dir_path: Path | str,
    recursive: bool = True,
    extensions: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Scan a directory for academic DOIs across markdown, text, latex, and bibtex files.

    Returns aggregated DOIs with file occurrences and counts.
    """
    p = Path(dir_path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"directory or file not found: {p}")

    exts = set(extensions or [".md", ".txt", ".tex", ".bib", ".html"])
    doi_re = re.compile(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+")

    if p.is_file():
        files = [p]
    else:
        files = [f for f in (p.rglob("*") if recursive else p.glob("*")) if f.is_file() and f.suffix.lower() in exts]

    occurrences: Dict[str, List[str]] = {}
    total_found = 0

    for f in sorted(files):
        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        for m in doi_re.finditer(content):
            raw_doi = m.group(0).rstrip(".,;)\"'>")
            clean_doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", raw_doi).strip()
            if not clean_doi:
                continue
            total_found += 1
            rel_file = str(f.relative_to(p)) if not p.is_file() else f.name
            if clean_doi not in occurrences:
                occurrences[clean_doi] = []
            if rel_file not in occurrences[clean_doi]:
                occurrences[clean_doi].append(rel_file)

    doi_list = [
        {
            "doi": doi,
            "occurrences": len(files_list),
            "files": files_list,
        }
        for doi, files_list in sorted(occurrences.items(), key=lambda x: -len(x[1]))
    ]

    return {
        "path": str(p),
        "files_scanned": len(files),
        "total_occurrences": total_found,
        "unique_dois_count": len(doi_list),
        "dois": doi_list,
    }


def import_directory_to_project(
    slug: str,
    dir_path: Path | str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    root: Path = DEFAULT_ROOT,
    recursive: bool = True,
) -> Dict[str, Any]:
    """Scan directory for DOIs and import them into project refs.bib.

    Auto-initializes the project if it doesn't exist yet.
    Deduplicates against already present papers.
    """
    validate_slug(slug)
    pdir = project_dir(slug, root)
    if not pdir.exists():
        init_project(slug, title=title or slug, description=description or f"Imported from {dir_path}", root=root)

    scan_res = scan_directory_dois(dir_path, recursive=recursive)
    discovered_dois = [item["doi"] for item in scan_res["dois"]]

    target_files = project_files(slug, root)
    from .scaffold import load_bibtex
    target_entries = load_bibtex(target_files['refs']) if target_files['refs'].exists() else []

    existing_dois = set()
    for e in target_entries:
        d = e.get("doi", "").strip().lower()
        if d:
            clean_d = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", d)
            existing_dois.add(clean_d)

    added = []
    skipped = []

    for d in discovered_dois:
        clean_d = d.strip().lower()
        if clean_d in existing_dois:
            skipped.append(d)
        else:
            existing_dois.add(clean_d)
            added.append(d)

    # Look for existing bibtex files in source directory to extract rich metadata if available
    bib_files = [f for f in (Path(dir_path).rglob("*.bib") if recursive else Path(dir_path).glob("*.bib")) if f.is_file()]
    bib_lookup = {}
    for bf in bib_files:
        try:
            for be in load_bibtex(bf):
                b_doi = be.get("doi", "").strip().lower()
                if b_doi:
                    clean_b_doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", b_doi)
                    bib_lookup[clean_b_doi] = be
        except Exception:
            pass

    if added:
        from .bibtex import to_bibtex
        existing_cite_keys = {e.get('key') for e in target_entries if e.get('key')}
        appended_text = f"\n% --- Scanned & imported from {dir_path} on {datetime.now().isoformat(timespec='seconds')} ---\n"
        for d in added:
            clean_d = d.strip().lower()
            if clean_d in bib_lookup:
                b_match = bib_lookup[clean_d]
                paper_dict = {
                    "title": b_match.get("title") or f"Paper {d}",
                    "authors": [a.strip() for a in b_match.get("author", "").split(" and ")] if b_match.get("author") else [],
                    "venue": b_match.get("journal") or b_match.get("booktitle") or "",
                    "year": b_match.get("year", ""),
                    "doi": d,
                    "type": b_match.get("type", "article"),
                }
            else:
                paper_dict = {
                    "title": f"Paper {d}",
                    "authors": [],
                    "doi": d,
                    "year": "",
                    "type": "article",
                }
            appended_text += to_bibtex(paper_dict, existing_cite_keys)

        with target_files['refs'].open('a', encoding='utf-8') as f:
            f.write(appended_text)

        meta = load_meta(slug, root)
        meta['updated_at'] = datetime.now().isoformat(timespec='seconds')
        save_meta(slug, meta, root)

    total_after = len(target_entries) + len(added)

    return {
        "slug": slug,
        "source_dir": str(Path(dir_path).expanduser().resolve()),
        "files_scanned": scan_res["files_scanned"],
        "discovered_dois": len(discovered_dois),
        "added": len(added),
        "already_present": len(skipped),
        "total_papers_after": total_after,
        "sample_added": added[:5],
    }


# ──────────────────────────────────────────────────────────────────────
# Project Operations: Fetch, PRISMA, and Literature Review
# ──────────────────────────────────────────────────────────────────────

def project_fetch(
    slug: str,
    root: Path = DEFAULT_ROOT,
    skip_existing: bool = True,
    max_total_sec: int = 1800,
    prefer: str = 'auto',
    clean_xml: bool = True,
) -> Dict[str, Any]:
    """Batch fetch PDFs for all papers in a project's refs.bib.

    Downloads PDFs into <root>/<slug>/pdfs/<key>.pdf.
    Updates project meta.json with last_fetch_at and n_pdfs.
    """
    validate_slug(slug)
    files = project_files(slug, root)
    if not files['dir'].exists():
        raise FileNotFoundError(f"project {slug!r} not found at {files['dir']}")

    pdf_dir = files['pdfs']
    pdf_dir.mkdir(parents=True, exist_ok=True)

    if not files['refs'].exists():
        return {
            "slug": slug,
            "refs_path": str(files['refs']),
            "pdf_dir": str(pdf_dir),
            "n_total": 0,
            "n_success": 0,
            "n_failure": 0,
            "n_skipped": 0,
            "total_size_bytes": 0,
            "total_elapsed_sec": 0.0,
            "n_pdfs_in_project": len(list(pdf_dir.glob("*.pdf"))),
            "results": [],
        }

    from .fetch_batch import run_fetch_batch
    summary = run_fetch_batch(
        bib_path=files['refs'],
        out_dir=pdf_dir,
        max_total_sec=max_total_sec,
        skip_existing=skip_existing,
        prefer=prefer,
        clean_xml=clean_xml,
    )

    n_pdfs = len(list(pdf_dir.glob("*.pdf")))
    meta = load_meta(slug, root)
    if meta:
        meta['last_fetch_at'] = datetime.now().isoformat(timespec='seconds')
        meta['n_pdfs'] = n_pdfs
        meta['updated_at'] = datetime.now().isoformat(timespec='seconds')
        save_meta(slug, meta, root)

    return {
        "slug": slug,
        "refs_path": str(files['refs']),
        "pdf_dir": str(pdf_dir),
        "n_total": summary.n_total,
        "n_success": summary.n_success,
        "n_failure": summary.n_failure,
        "n_skipped": summary.n_skipped,
        "total_size_bytes": summary.total_size_bytes,
        "total_elapsed_sec": summary.total_elapsed_sec,
        "n_pdfs_in_project": n_pdfs,
        "results": [r.to_dict() for r in summary.results],
    }


def project_prisma(
    slug: str,
    root: Path = DEFAULT_ROOT,
    word_count_min: int = 1000,
    output_format: str = "markdown",
    out_file: Optional[Path | str] = None,
) -> str:
    """Generate PRISMA 2020 flow diagram and stage counts for a project corpus.

    Computes:
      - identified: total papers in refs.bib (or found PDFs)
      - after_screening: papers surviving screening
      - after_eligibility / included: papers with full text
      - pdf_count / abstract_count: derived from downloaded PDFs
      - by_source: distribution across journals/sources/publishers in refs.bib

    Returns Markdown or Mermaid text, and optionally saves to out_file.
    """
    validate_slug(slug)
    files = project_files(slug, root)
    if not files['dir'].exists():
        raise FileNotFoundError(f"project {slug!r} not found at {files['dir']}")

    from .scaffold import load_bibtex
    entries = load_bibtex(files['refs']) if files['refs'].exists() else []
    n_papers = len(entries)

    by_source = {}
    for e in entries:
        src = e.get('journal') or e.get('booktitle') or e.get('publisher') or e.get('eprinttype') or e.get('type') or 'Other'
        src_clean = src.split(';')[0].strip()[:35]
        if src_clean:
            by_source[src_clean] = by_source.get(src_clean, 0) + 1

    pdf_dir = files['pdfs']
    corpus_files = [f for f in pdf_dir.iterdir() if f.is_file() and f.suffix.lower() in (".pdf", ".md", ".txt")] if pdf_dir.exists() else []

    if corpus_files:
        from .prisma import derive_counts_from_corpus
        counts = derive_counts_from_corpus(pdf_dir, word_count_min=word_count_min)
        identified = max(n_papers, counts["identified"])
        after_screening = n_papers if n_papers > 0 else counts["identified"]
        pdf_count = counts["pdf_count"]
        abstract_count = counts["abstract_count"]
        after_eligibility = pdf_count + abstract_count
        included = pdf_count
    else:
        identified = n_papers
        after_screening = n_papers
        after_eligibility = n_papers
        included = n_papers
        pdf_count = 0
        abstract_count = 0

    from .prisma import render_prisma
    top_sources = dict(sorted(by_source.items(), key=lambda x: -x[1])[:6]) if by_source else {}
    diagram = render_prisma(
        identified=identified,
        after_screening=after_screening,
        after_eligibility=after_eligibility,
        included=included,
        by_source=top_sources,
        pdf_count=pdf_count,
        abstract_count=abstract_count,
        output_format=output_format,
    )

    if out_file:
        out_p = Path(out_file)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(diagram, encoding='utf-8')

    meta = load_meta(slug, root)
    if meta:
        meta['last_prisma_at'] = datetime.now().isoformat(timespec='seconds')
        save_meta(slug, meta, root)

    return diagram


def project_review(
    slug: str,
    root: Path = DEFAULT_ROOT,
    template: str = "v32",
    word_count_min: int = 1000,
    with_prisma: bool = True,
    out_file: Optional[Path | str] = None,
) -> str:
    """Generate structured literature review document for a project topic corpus.

    If PDFs or documents are in <slug>/pdfs/, parses and synthesizes them.
    If only refs.bib exists, synthesizes a structured review catalogue from metadata.
    Includes PRISMA 2020 flow diagram if with_prisma is True.
    """
    validate_slug(slug)
    files = project_files(slug, root)
    if not files['dir'].exists():
        raise FileNotFoundError(f"project {slug!r} not found at {files['dir']}")

    meta = load_meta(slug, root)
    title = meta.get("title", slug)
    desc = meta.get("description", "")

    pdf_dir = files['pdfs']
    has_corpus_files = pdf_dir.exists() and any(
        f.suffix.lower() in (".pdf", ".md", ".txt") for f in pdf_dir.iterdir() if f.is_file()
    )

    if has_corpus_files:
        from .review import synthesize
        content = synthesize(pdf_dir, template=template, word_count_min=word_count_min)
    else:
        from .scaffold import load_bibtex
        entries = load_bibtex(files['refs']) if files['refs'].exists() else []
        date_str = datetime.now().strftime("%Y-%m-%d")
        lines = [
            f"# Literature Review: {title}\n",
            f"**Project Slug**: `{slug}` | **Date**: {date_str}\n",
        ]
        if desc:
            lines.append(f"**Topic Description**: {desc}\n")
        lines.append(f"**Total Papers in Corpus**: {len(entries)}\n")
        lines.append("\n---\n\n## Papers in Corpus\n\n")

        if not entries:
            lines.append("(No papers in project `refs.bib` yet. Add papers with `pa project corpus-add` or `pa project import-dir`.)\n")
        else:
            for i, e in enumerate(entries, 1):
                p_title = e.get("title", f"Paper {e.get('key', i)}")
                p_author = e.get("author", "Unknown Author")
                p_year = e.get("year", "n.d.")
                p_journal = e.get("journal") or e.get("booktitle") or e.get("publisher") or ""
                p_doi = e.get("doi", "")
                p_key = e.get("key", "")

                lines.append(f"### {i}. {p_title} ({p_year})\n\n")
                lines.append(f"- **Cite Key**: `{p_key}`\n")
                lines.append(f"- **Author(s)**: {p_author}\n")
                if p_journal:
                    lines.append(f"- **Venue**: {p_journal}\n")
                if p_doi:
                    lines.append(f"- **DOI**: [{p_doi}](https://doi.org/{p_doi})\n")
                if e.get("abstract"):
                    lines.append(f"\n> **Abstract**: {e.get('abstract')}\n")
                lines.append("\n")

            lines.append("\n---\n\n## Corpus Summary\n\n")
            years = [int(e.get("year")) for e in entries if e.get("year", "").isdigit()]
            if years:
                lines.append(f"- **Year Span**: {min(years)} – {max(years)}\n")
            lines.append(f"- **Papers with DOI**: {sum(1 for e in entries if e.get('doi'))}/{len(entries)}\n")
            lines.append(f"- **PDFs Downloaded**: 0 (run `pa project fetch {slug}` to retrieve full-text PDFs)\n")

        lines.append("\n---\n*Generated by paper-agent project review module.*\n")
        content = "".join(lines)

    if with_prisma:
        prisma_md = project_prisma(slug, root=root, word_count_min=word_count_min, output_format="markdown")
        content = f"{prisma_md}\n\n---\n\n{content}"

    if out_file:
        out_p = Path(out_file)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(content, encoding='utf-8')

    meta['last_review_at'] = datetime.now().isoformat(timespec='seconds')
    meta['updated_at'] = datetime.now().isoformat(timespec='seconds')
    save_meta(slug, meta, root)

    return content


def project_topics(
    slug: str,
    root: Path = DEFAULT_ROOT,
    alpha: float = 0.4,
    word_count_min: int = 1000,
    force_method: str = "auto",
    label_method: str = "auto",
    custom_labels: Optional[Dict[int, str]] = None,
    domain_stopwords: Optional[List[str]] = None,
    out_file: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """Cluster papers in a project topic into sub-topics.

    If project has downloaded PDFs or documents in <slug>/pdfs/, clusters them.
    If no PDFs exist yet, generates lightweight text representations from refs.bib
    (titles, authors, venue, year, abstract) into a temporary staging folder and clusters them.

    Auto-saves result to <slug>/topics.json and optionally to out_file.
    Updates project meta.json with last_topics_at and n_topics.
    """
    validate_slug(slug)
    files = project_files(slug, root)
    if not files['dir'].exists():
        raise FileNotFoundError(f"project {slug!r} not found at {files['dir']}")

    meta = load_meta(slug, root)
    pdf_dir = files['pdfs']
    corpus_files = [f for f in pdf_dir.iterdir() if f.is_file() and f.suffix.lower() in (".pdf", ".md", ".txt")] if pdf_dir.exists() else []

    temp_staging_dir: Optional[Path] = None
    try:
        if corpus_files:
            target_corpus_dir = pdf_dir
            effective_min_words = word_count_min
        else:
            from .scaffold import load_bibtex
            entries = load_bibtex(files['refs']) if files['refs'].exists() else []
            if not entries:
                return {
                    "slug": slug,
                    "topics": [],
                    "total_papers": 0,
                    "method": "none",
                    "warning": "empty_corpus",
                }
            temp_staging_dir = files['dir'] / ".topics_staging"
            temp_staging_dir.mkdir(parents=True, exist_ok=True)
            for i, e in enumerate(entries, 1):
                key = e.get("key") or f"ref_{i}"
                safe_key = re.sub(r"[^\w\-.]", "_", key)
                title = e.get("title", "")
                author = e.get("author", "")
                venue = e.get("journal") or e.get("booktitle") or e.get("publisher") or ""
                year = e.get("year", "")
                doi = e.get("doi", "")
                abstract = e.get("abstract", "")
                paper_text = (
                    f"# {title}\n\n"
                    f"Author: {author}\n"
                    f"Venue: {venue}\n"
                    f"Year: {year}\n"
                    f"DOI: {doi}\n\n"
                    f"Abstract:\n{abstract}\n"
                )
                (temp_staging_dir / f"{safe_key}.md").write_text(paper_text, encoding="utf-8")
            target_corpus_dir = temp_staging_dir
            effective_min_words = 10

        from .topics import cluster_topics
        result = cluster_topics(
            corpus_dir=target_corpus_dir,
            alpha=alpha,
            word_count_min=effective_min_words,
            force_method=force_method,
            label_method=label_method,
            custom_labels=custom_labels,
            domain_stopwords=domain_stopwords,
        )

        result["slug"] = slug
        result["project_title"] = meta.get("title", slug)

        # Default canonical save location: <slug>/topics.json
        canonical_topics_path = files['dir'] / "topics.json"
        canonical_topics_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        if out_file:
            out_p = Path(out_file)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            out_p.write_text(
                json.dumps(result, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        meta['last_topics_at'] = datetime.now().isoformat(timespec='seconds')
        meta['n_topics'] = len(result.get("topics", []))
        meta['updated_at'] = datetime.now().isoformat(timespec='seconds')
        save_meta(slug, meta, root)

        return result

    finally:
        if temp_staging_dir and temp_staging_dir.exists():
            shutil.rmtree(temp_staging_dir, ignore_errors=True)


def project_stats(slug: str, root: Path = DEFAULT_ROOT, top_n: int = 10) -> Dict[str, Any]:
    """[P2-19] Compute corpus bibliometric stats for a project.

    Returns dict with:
      - slug, title, description, created_at, updated_at
      - total_papers, with_doi, without_doi
      - by_type (e.g. article, book, inproceedings)
      - year_range, median_year, decade_histogram
      - top_authors, top_venues
      - n_pdfs, n_topics, n_labels
      - zotero sync information if linked
    """
    files = project_files(slug, root)
    if not files['dir'].exists():
        raise FileNotFoundError(f"Project {slug!r} does not exist at {root}")
    meta = load_meta(slug, root)

    from . import corpus_stats as cs
    raw_stats = cs.compute_corpus_stats(files['refs'], top_n=top_n)

    result = {
        "slug": slug,
        "title": meta.get("title", slug),
        "description": meta.get("description", ""),
        "created_at": meta.get("created_at"),
        "updated_at": meta.get("updated_at"),
        "n_pdfs": len(list(files['pdfs'].glob("*.pdf"))) if files['pdfs'].exists() else 0,
        "n_topics": meta.get("n_topics", 0),
        "n_labels": meta.get("n_labels", 0),
        **raw_stats,
    }
    if "zotero_collection_key" in meta:
        result["zotero_collection_key"] = meta["zotero_collection_key"]
        result["zotero_collection_version"] = meta.get("zotero_collection_version")
        result["zotero_last_sync_at"] = meta.get("zotero_last_sync_at")
    return result


def project_cite_check(
    slug: str,
    doc_path: Union[str, Path],
    root: Path = DEFAULT_ROOT,
) -> Tuple[Dict[str, Any], str]:
    """[P2-7] Validate `[@bibkey]` placeholders in markdown document against project's refs.bib.

    Returns: (result_dict, human_readable_report_text).
    Raises FileNotFoundError if project or doc_path does not exist.
    """
    files = project_files(slug, root)
    if not files['dir'].exists():
        raise FileNotFoundError(f"Project {slug!r} does not exist at {root}")
    doc_p = Path(doc_path)
    if not doc_p.exists():
        raise FileNotFoundError(f"Document {str(doc_path)!r} does not exist")

    from .cite_check import run_cite_check
    result, report = run_cite_check(files['refs'], doc_p, output_json=False)

    summary = {
        "slug": slug,
        "document": str(doc_p),
        "refs_bib": str(files['refs']),
        "missing": result['missing'],
        "typoed": result['typoed'],
        "orphan": result['orphan'],
        "n_missing": len(result['missing']),
        "n_typoed": len(result['typoed']),
        "n_orphan": len(result['orphan']),
        "clean": len(result['missing']) == 0 and len(result['typoed']) == 0,
    }
    return summary, report


def project_export(
    slug: str,
    format: str = "markdown",
    out_file: Optional[Union[str, Path]] = None,
    root: Path = DEFAULT_ROOT,
) -> Dict[str, Any]:
    """Export project corpus into structured distribution (markdown, bibtex, json).

    - markdown: Academic bibliography & literature digest, grouped by topics (if topics.json exists)
      or chronologically, with abstracts, DOIs, venue citations, and PDF availability.
    - bibtex: Curated, clean BibTeX file.
    - json: Full machine-readable export with meta, entries, and stats.
    """
    files = project_files(slug, root)
    if not files['dir'].exists():
        raise FileNotFoundError(f"Project {slug!r} does not exist at {root}")
    meta = load_meta(slug, root)

    from .scaffold import load_bibtex
    entries = load_bibtex(files['refs'])

    pdf_map = {}
    if files['pdfs'].exists():
        for pdf_path in files['pdfs'].glob("*.pdf"):
            pdf_map[pdf_path.stem] = str(pdf_path)

    topics_data = None
    topics_file = files['dir'] / "topics.json"
    if topics_file.exists():
        try:
            topics_data = json.loads(topics_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    format_lower = format.lower().strip()
    if format_lower == "bibtex":
        content = files['refs'].read_text(encoding="utf-8", errors="replace")
    elif format_lower == "json":
        export_dict = {
            "meta": meta,
            "n_papers": len(entries),
            "n_pdfs": len(pdf_map),
            "papers": entries,
            "topics": topics_data.get("topics", []) if topics_data else [],
        }
        content = json.dumps(export_dict, ensure_ascii=False, indent=2)
    elif format_lower == "markdown":
        lines = [
            f"# Literature Digest: {meta.get('title', slug)}",
            "",
            f"> **Project**: `{slug}`  ",
            f"> **Total Catalogued Papers**: {len(entries)}  ",
            f"> **Downloaded Full-Text PDFs**: {len(pdf_map)}  ",
            f"> **Exported At**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]
        if meta.get("description"):
            lines.extend(["## Overview", "", meta["description"], ""])

        if topics_data and topics_data.get("topics"):
            lines.append("## Sub-Topic Analysis\n")
            topic_list = topics_data["topics"]
            by_cite_key = {e.get('key'): e for e in entries}
            by_doi = {e.get('doi', '').lower(): e for e in entries if e.get('doi')}

            for t in topic_list:
                lines.append(f"### Topic {t.get('topic_id', '?')}: {t.get('label', 'Unnamed Topic')}")
                if t.get("keywords"):
                    lines.append(f"- **Keywords**: {', '.join(t['keywords'])}")
                if t.get("paper_count"):
                    lines.append(f"- **Papers in Cluster**: {t['paper_count']}")
                lines.append("")

                for fn in t.get("filenames", []):
                    stem = Path(fn).stem
                    matched_entry = by_cite_key.get(stem) or by_doi.get(stem.lower().replace("_", "/"))
                    if matched_entry:
                        title = matched_entry.get("title", "Untitled")
                        year = matched_entry.get("year", "n.d.")
                        authors = matched_entry.get("author", "Unknown")
                        doi = matched_entry.get("doi", "")
                        venue = matched_entry.get("journal") or matched_entry.get("booktitle") or matched_entry.get("publisher", "")
                        has_pdf = " [PDF Available]" if (stem in pdf_map) else ""
                        doi_link = f"https://doi.org/{doi}" if doi else ""
                        lines.append(f"#### [@{matched_entry.get('key')}]{has_pdf} {title} ({year})")
                        lines.append(f"- **Authors**: {authors}")
                        if venue:
                            lines.append(f"- **Venue**: {venue}")
                        if doi_link:
                            lines.append(f"- **DOI**: [{doi}]({doi_link})")
                        if matched_entry.get("abstract"):
                            lines.append(f"- **Abstract**: {matched_entry['abstract'][:500]}...")
                        lines.append("")

            lines.append("## Full Bibliography (Chronological)\n")
        else:
            lines.append("## Bibliography\n")

        sorted_entries = sorted(entries, key=lambda e: str(e.get("year", "0")), reverse=True)
        for i, e in enumerate(sorted_entries, 1):
            title = e.get("title", "Untitled")
            year = e.get("year", "n.d.")
            authors = e.get("author", "Unknown")
            doi = e.get("doi", "")
            venue = e.get("journal") or e.get("booktitle") or e.get("publisher", "")
            has_pdf = " [PDF Available]" if (e.get('key') in pdf_map) else ""
            doi_link = f"https://doi.org/{doi}" if doi else ""
            lines.append(f"### {i}. [@{e.get('key')}]{has_pdf} {title} ({year})")
            lines.append(f"- **Authors**: {authors}")
            if venue:
                lines.append(f"- **Venue**: {venue}")
            if doi_link:
                lines.append(f"- **DOI**: [{doi}]({doi_link})")
            if e.get("abstract"):
                lines.append(f"- **Abstract**: {e['abstract'][:400]}...")
            lines.append("")

        content = "\n".join(lines)
    else:
        raise ValueError(f"Unsupported export format {format!r}. Choose from 'markdown', 'bibtex', 'json'.")

    written_to = None
    if out_file:
        out_p = Path(out_file)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(content, encoding="utf-8")
        written_to = str(out_p)

    return {
        "slug": slug,
        "format": format_lower,
        "n_papers": len(entries),
        "n_pdfs": len(pdf_map),
        "out_file": written_to,
        "content_length": len(content),
        "content": content if not written_to else None,
    }


# ──────────────────────────────────────────────────────────────────────
# Enrich
# ──────────────────────────────────────────────────────────────────────

def project_enrich(
    slug: str,
    limit: int = 0,
    force: bool = False,
    root: Path = DEFAULT_ROOT,
) -> Dict[str, Any]:
    """Enrich stub bibliography entries in refs.bib with rich academic metadata from OpenAlex/S2.

    Resolves DOIs to full title, author list, publication year, venue/journal,
    abstract (reconstructed from inverted index), and publication type.
    Updates refs.bib and meta.json in place.

    Args:
        slug: project identifier
        limit: max number of stub papers to enrich (0 = all stubs)
        force: if True, re-enriches all papers with DOI even if not stubs
        root: projects root directory

    Returns:
        Dict with enrichment statistics (total, stubs, enriched, failed, unchanged).
    """
    validate_slug(slug)
    files = project_files(slug, root)
    if not files['dir'].exists():
        raise FileNotFoundError(f"project {slug!r} not found at {files['dir']}")
    if not files['refs'].exists():
        raise FileNotFoundError(f"project {slug!r} has no refs.bib at {files['refs']}")

    from .scaffold import parse_bibtex
    from .citations import get_work_by_doi
    from .bibtex import to_bibtex

    content = files['refs'].read_text(encoding='utf-8')
    entries = parse_bibtex(content)
    if not entries:
        return {
            "slug": slug,
            "total": 0,
            "stubs": 0,
            "enriched": 0,
            "failed": 0,
            "unchanged": 0,
        }

    def _is_stub(e: Dict[str, str]) -> bool:
        t = (e.get('title') or '').strip()
        a = (e.get('author') or '').strip()
        if not t or t.startswith('Paper 10.'):
            return True
        if not a or a.lower() in ('unknown', 'anon'):
            return True
        return False

    enriched_count = 0
    failed_count = 0
    unchanged_count = 0
    stubs_count = 0

    enriched_entries = []

    for entry in entries:
        if entry.get("_is_special") or entry.get("type") in ("string", "preamble", "comment"):
            continue
        doi = (entry.get('doi') or '').strip()
        if not doi and entry.get('url'):
            m = re.search(r'10\.\d{4,9}/[-._;()/:A-Za-z0-9]+', entry['url'])
            if m:
                doi = m.group(0)

        is_stub_entry = _is_stub(entry)
        if is_stub_entry:
            stubs_count += 1

        needs_enrichment = (is_stub_entry or force) and bool(doi)
        if needs_enrichment and (limit <= 0 or enriched_count < limit):
            norm_doi = re.sub(r'^https?://(?:dx\.)?doi\.org/', '', doi).strip()
            work = None
            try:
                work = get_work_by_doi(norm_doi)
            except Exception:
                work = None

            if not work:
                # Try S2 fallback
                try:
                    from .search import _s2_lookup_doi
                    work_s2 = _s2_lookup_doi(norm_doi)
                    if work_s2:
                        work = {
                            "title": work_s2.get("title"),
                            "publication_year": work_s2.get("year"),
                            "primary_location": {"source": {"display_name": work_s2.get("venue")}},
                            "authorships": [{"author": {"display_name": a}} for a in work_s2.get("authors", [])],
                            "type": work_s2.get("type", "article"),
                            "abstract_text": work_s2.get("abstract"),
                        }
                except Exception:
                    pass

            if work:
                # Extract fields
                title = work.get('title') or work.get('display_name')
                year = work.get('publication_year') or entry.get('year')
                authors = []
                for auth in work.get('authorships', []):
                    name = auth.get('author', {}).get('display_name')
                    if name:
                        authors.append(name)

                venue = ""
                pl = work.get('primary_location') or {}
                if isinstance(pl, dict):
                    src = pl.get('source') or {}
                    if isinstance(src, dict):
                        venue = src.get('display_name') or ""
                if not venue:
                    hv = work.get('host_venue') or {}
                    if isinstance(hv, dict):
                        venue = hv.get('name') or ""

                abstract = work.get('abstract_text') or ""
                if not abstract:
                    inv = work.get('abstract_inverted_index')
                    if inv and isinstance(inv, dict):
                        words = sorted([(pos, w) for w, poses in inv.items() for pos in poses if isinstance(poses, list)])
                        abstract = ' '.join(w for _, w in words)

                from .bibtex import format_authors
                if title:
                    entry['title'] = title
                if authors:
                    entry['author'] = format_authors(authors)
                if year:
                    entry['year'] = year
                if venue:
                    entry['journal'] = venue
                if norm_doi:
                    entry['doi'] = norm_doi
                from .bibtex import _TYPE_MAP
                raw_type = str(work.get('type') or entry.get('type', 'article')).strip().lower()
                entry_type = _TYPE_MAP.get(raw_type, raw_type)
                if "-" in entry_type:
                    entry_type = _TYPE_MAP.get(entry_type.replace("-", ""), "misc")
                entry['type'] = entry_type
                entry['_was_enriched'] = True
                if abstract:
                    entry['abstract'] = abstract
                enriched_count += 1
            else:
                failed_count += 1
        else:
            unchanged_count += 1

    if enriched_count > 0:
        from .bibtex import format_bibtex_entry
        import tempfile

        meta = load_meta(slug, root)
        rebuilt_text = (
            f"% Bibtex for project {slug!r} ({meta.get('title', slug)})\n"
            f"% Enriched with rich academic metadata on {datetime.now().isoformat(timespec='seconds')}\n\n"
        )
        for e in entries:
            if e.get("_is_special") or e.get("type") in ("string", "preamble", "comment"):
                rebuilt_text += e.get("_raw", "").strip() + "\n\n"
            elif not e.get("_was_enriched") and e.get("_raw"):
                rebuilt_text += e["_raw"].strip() + "\n\n"
            else:
                rebuilt_text += format_bibtex_entry(e) + "\n"

        target_file = files['refs']
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=target_file.parent, delete=False, suffix='.tmp') as f_tmp:
            f_tmp.write(rebuilt_text)
            tmp_path = Path(f_tmp.name)
        os.replace(tmp_path, target_file)
        meta['last_enrich_at'] = datetime.now().isoformat(timespec='seconds')
        meta['updated_at'] = datetime.now().isoformat(timespec='seconds')
        save_meta(slug, meta, root)

    return {
        "slug": slug,
        "total": len(entries),
        "stubs": stubs_count,
        "enriched": enriched_count,
        "failed": failed_count,
        "unchanged": unchanged_count,
    }




