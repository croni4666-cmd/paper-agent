"""pa_cli.search_saved — named search presets with parameter snapshots.

Per ROADMAP [P2-9] (added 2026-07-15, shipped 2026-07-20 in v3.9.10.5):
  Stores named search presets in ~/.paper-agent/saved_searches.json.
  Each preset is a dict of all `pa search` flags. Re-run without retyping:
    pa search-saved run <name>

Workaround for now: shell alias. Effort: 1h.

Usage from CLI:
  pa search-saved add <name> --query "AI literacy" --year-min 2020 --engine openalex,arxiv
  pa search-saved list
  pa search-saved run <name> [-o out.json]
  pa search-saved del <name>
  pa search-saved edit <name>  [--query Q] [--year-min Y] ...
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Path
DEFAULT_PATH = Path.home() / ".paper-agent" / "saved_searches.json"

# Schema: stored as
# {
#   "version": "1",
#   "searches": {
#     "<name>": {
#       "query": "...",
#       "year_min": 2020,
#       "year_max": null,
#       "engine": "all",
#       "limit": 50,
#       "format": "json",
#       "concepts": "...",
#       "concept": "...",
#       "concept_mode": "or",
#       "enrich_top": 0,
#       "enrich_top_min_cites": 1,
#       "enrich_max_age_years": 10,
#       "sort_by": "cite",
#       "source": null,
#       "created_at": "2026-07-20T...",
#       "updated_at": "2026-07-20T..."
#     },
#     ...
#   }
# }

# Valid name pattern: ASCII alphanumeric, underscore, dash, dot. No spaces.
# Use re.ASCII flag so \w is ASCII-only (not Unicode).
_NAME_RE = re.compile(r"^[\w\-.]+$", re.ASCII)


def _ensure_path(path: Path) -> None:
    """Ensure ~/.paper-agent/ exists; create empty file if missing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(json.dumps({"version": "1", "searches": {}}, indent=2),
                         encoding='utf-8')


def load_all(path: Path = DEFAULT_PATH) -> Dict:
    """Load all saved searches from disk. Returns the full dict."""
    _ensure_path(path)
    return json.loads(path.read_text(encoding='utf-8'))


def save_all(data: Dict, path: Path = DEFAULT_PATH) -> None:
    """Save the full dict back to disk (atomic via temp file)."""
    _ensure_path(path)
    tmp = path.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    tmp.replace(path)


def validate_name(name: str) -> None:
    """Raise ValueError if name is not a valid identifier."""
    if not name:
        raise ValueError("name cannot be empty")
    if not _NAME_RE.match(name):
        raise ValueError(
            f"invalid name {name!r}: must be ASCII alphanumeric + _-."
        )


def add(
    name: str,
    query: str,
    path: Path = DEFAULT_PATH,
    **flags,
) -> Dict:
    """Add or update a saved search.

    Returns the saved-search dict (with created_at / updated_at).
    Raises ValueError on bad name; FileExistsError if name is taken
    (use `update` to overwrite).
    """
    validate_name(name)
    data = load_all(path)
    if name in data['searches']:
        raise FileExistsError(
            f"saved search {name!r} already exists; use `pa search-saved edit` to modify"
        )
    now = datetime.now().isoformat(timespec='seconds')
    entry = {
        'query': query,
        'created_at': now,
        'updated_at': now,
    }
    # Apply flags (only known flags)
    for k, v in flags.items():
        if v is not None:
            entry[k] = v
    data['searches'][name] = entry
    save_all(data, path)
    return entry


def update(
    name: str,
    path: Path = DEFAULT_PATH,
    **flags,
) -> Dict:
    """Update an existing saved search in place. Returns the updated entry."""
    validate_name(name)
    data = load_all(path)
    if name not in data['searches']:
        raise KeyError(f"saved search {name!r} not found; use `add` to create")
    entry = data['searches'][name]
    for k, v in flags.items():
        if v is not None:
            entry[k] = v
    entry['updated_at'] = datetime.now().isoformat(timespec='seconds')
    save_all(data, path)
    return entry


def delete(name: str, path: Path = DEFAULT_PATH) -> bool:
    """Delete a saved search. Returns True if deleted, False if not found."""
    validate_name(name)
    data = load_all(path)
    if name not in data['searches']:
        return False
    del data['searches'][name]
    save_all(data, path)
    return True


def get(name: str, path: Path = DEFAULT_PATH) -> Optional[Dict]:
    """Get a saved search by name. Returns None if not found."""
    validate_name(name)
    data = load_all(path)
    return data['searches'].get(name)


def list_all(path: Path = DEFAULT_PATH) -> List[Dict]:
    """List all saved searches (sorted by name).

    Returns list of {name, query, created_at, updated_at, n_flags}.
    """
    data = load_all(path)
    out = []
    for name in sorted(data['searches'].keys()):
        entry = data['searches'][name]
        n_flags = sum(1 for k, v in entry.items()
                      if k not in ('query', 'created_at', 'updated_at') and v is not None)
        out.append({
            'name': name,
            'query': entry.get('query', ''),
            'created_at': entry.get('created_at', ''),
            'updated_at': entry.get('updated_at', ''),
            'n_flags': n_flags,
        })
    return out


def to_pa_args(name: str, path: Path = DEFAULT_PATH) -> Dict:
    """Convert saved search name to the kwargs dict for `pa search`.

    Returns {query, year_min, year_max, engine, limit, ...} that can be
    unpacked into the search() function (or passed to pa search via CLI).
    Raises KeyError if name not found.
    """
    entry = get(name, path)
    if entry is None:
        raise KeyError(f"saved search {name!r} not found")
    # Copy all stored fields except timestamps
    out = {k: v for k, v in entry.items()
           if k not in ('created_at', 'updated_at')}
    return out
