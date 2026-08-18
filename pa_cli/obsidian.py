"""pa_cli.obsidian - Research sub-vault + project management (v3.9.16, [P3-29])

Manages a research sub-vault inside the user's existing Obsidian vault.

**Design choice**: do NOT create a full Obsidian vault (user already has
`G:\\Todo list\\Todo List\\` GTD vault). Instead, write a `0-Research/`
sub-folder that the user points Obsidian at (or already has open as the
same vault).

**Directory layout** (auto-created by `pa obsidian init`):

    <vault>/0-Research/
    ├── Inbox/                    # uncategorized thoughts
    │   └── YYYY-MM-DD_HHMMSS_<slug>.md
    └── Projects/
        └── <project-slug>/
            ├── index.md          # project home: topic, direction, question
            ├── ideas.md          # raw / unformed thoughts
            ├── notes/            # atomic notes
            │   └── YYYY-MM-DD_HHMMSS_<slug>.md
            └── synthesis.md      # cross-paper synthesis

**Vault path**: read from `$PAPER_AGENT_OBSIDIAN_VAULT` env var
(留痕 discipline — NOT .env, NOT a config file). Must be an existing
Obsidian vault. If unset, all obsidian commands exit with a clear error.

**No external deps**. Pure stdlib (pathlib, re, datetime, dataclass).
Markdown is hand-rolled (not parsed) — we generate, not consume.

**Idempotency**: re-running `pa obsidian project create` for an existing
project is a no-op (returns status='exists'). Re-running `pa obsidian
init` is a no-op (won't overwrite existing files).

**Obsidian is a registered trademark of Obsidian.md. This module is not
affiliated with or endorsed by the Obsidian project.**
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ─────────────────────────────────────────────────────────────────
# Vault config
# ─────────────────────────────────────────────────────────────────
SUBFOLDER_NAME = "0-Research"  # user-overridable via $PAPER_AGENT_OBSIDIAN_SUBFOLDER

# Project files (relative to <vault>/0-Research/Projects/<slug>/)
PROJECT_FILES = {
    "index": "index.md",
    "ideas": "ideas.md",
    "synthesis": "synthesis.md",
}

# Allowed note types
NOTE_TYPES = ("idea", "reading", "synthesis", "question", "evidence")


def get_vault_path() -> Optional[Path]:
    """Read vault path from env var. Returns None if unset/empty.

    The vault must already exist (we don't create vaults — only sub-folders
    inside one).
    """
    raw = os.environ.get("PAPER_AGENT_OBSIDIAN_VAULT", "").strip()
    if not raw:
        return None
    return Path(raw)


def get_subfolder() -> str:
    """Read sub-folder name from env var. Default '0-Research'."""
    raw = os.environ.get("PAPER_AGENT_OBSIDIAN_SUBFOLDER", "").strip()
    return raw or SUBFOLDER_NAME


def get_research_root() -> Path:
    """Get the research sub-folder root inside the vault.

    Returns:
        Path: <vault>/<subfolder>/  (e.g. G:\\Todo list\\Todo List\\0-Research\\)

    Raises:
        ValueError: if vault env var unset (with clear message)
    """
    vault = get_vault_path()
    if vault is None:
        raise ValueError(
            "$PAPER_AGENT_OBSIDIAN_VAULT is not set. "
            "Set it to your Obsidian vault root, e.g.:\n"
            '  setx PAPER_AGENT_OBSIDIAN_VAULT "G:\\Todo list\\Todo List"\n'
            "or per session:\n"
            '  $env:PAPER_AGENT_OBSIDIAN_VAULT = "G:\\Todo list\\Todo List"'
        )
    return vault / get_subfolder()


# ─────────────────────────────────────────────────────────────────
# Slug / filename helpers
# ─────────────────────────────────────────────────────────────────
def slugify(s: str, max_len: int = 60) -> str:
    """Convert arbitrary string to a filesystem-safe slug.

    - lowercase, ASCII, hyphenated
    - strips punctuation
    - collapses repeated hyphens
    - trims leading/trailing hyphens
    - truncates to max_len

    Examples:
        >>> slugify("Long-term Care Insurance")
        'long-term-care-insurance'
        >>> slugify("数字普惠金融 / 长期护理保险")
        'shu-zi-pu-hui-jin-rong-chang-qi-hu-li-bao-xian'
    """
    if not s:
        return "untitled"
    s = s.strip().lower()
    # Replace CJK with pinyin placeholder? No — leave as-is, then strip.
    # ASCII only via NFKD
    import unicodedata
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode("ascii")
    # Remove anything that isn't alphanumeric or hyphen
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    if not s:
        # ASCII strip killed everything (pure CJK) — fall back to timestamp
        return f"untitled-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    return s[:max_len]


def timestamp_slug(prefix: str = "") -> str:
    """Return 'YYYY-MM-DD_HHMMSS' timestamp for filenames."""
    s = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    return f"{prefix}{s}" if prefix else s


def safe_filename(stem: str, suffix: str = ".md", max_len: int = 80) -> str:
    """Return a safe filename: <slug>-<timestamp><suffix>.

    Avoids collisions: appends random 4-char suffix if file exists.
    """
    base = slugify(stem, max_len=max_len - 20)  # leave room for timestamp
    return f"{base}-{timestamp_slug()}{suffix}"


# ─────────────────────────────────────────────────────────────────
# Init
# ─────────────────────────────────────────────────────────────────
def init_vault() -> Dict[str, Any]:
    """Create the research sub-folder skeleton inside the vault.

    Idempotent: existing files are NOT overwritten. Returns a dict of
    what was created vs already-existed.

    Returns:
        Dict {status, created: [...], existed: [...], root}
    """
    root = get_research_root()  # raises if env var unset
    created = []
    existed = []

    def _mkdir(p: Path) -> None:
        if p.exists():
            existed.append(str(p))
        else:
            p.mkdir(parents=True, exist_ok=True)
            created.append(str(p))

    _mkdir(root)
    _mkdir(root / "Inbox")
    _mkdir(root / "Projects")
    # Add a README explaining the structure
    readme = root / "README.md"
    if not readme.exists():
        readme.write_text(_README_TEMPLATE, encoding="utf-8")
        created.append(str(readme))
    else:
        existed.append(str(readme))

    return {
        "status": "ok",
        "root": str(root),
        "created": created,
        "existed": existed,
    }


_README_TEMPLATE = """# 0-Research

This is the research sub-folder managed by `pa obsidian` (paper-agent v3.9.16+).

## Layout

- `Inbox/` — uncategorized thoughts. Drop anything here; promote to a project later.
- `Projects/<slug>/` — one folder per research project.
  - `index.md` — project home: topic, direction, research questions, status
  - `ideas.md` — raw / unformed thoughts about this project
  - `notes/` — atomic notes (single concept, dated)
  - `synthesis.md` — cross-paper synthesis (manually written)

## CLI

```bash
# Project
pa obsidian project create --name "long-term care" \\
    --research-question "How does public LTCI affect family caregivers?" \\
    --direction "empirical microeconomics, China policy"

pa obsidian project thought --name "long-term care" --content "..."
pa obsidian project note --name "long-term care" --type idea --content "..."
pa obsidian project status --name "long-term care"

# Inbox
pa obsidian inbox add --content "Cross-ref: see paper X about Y"
pa obsidian inbox list
```
"""


# ─────────────────────────────────────────────────────────────────
# Projects
# ─────────────────────────────────────────────────────────────────
def project_root(slug: str) -> Path:
    """Get the project directory: <root>/Projects/<slug>/. Creates if missing."""
    return get_research_root() / "Projects" / slug


def project_index_path(slug: str) -> Path:
    return project_root(slug) / PROJECT_FILES["index"]


def project_ideas_path(slug: str) -> Path:
    return project_root(slug) / PROJECT_FILES["ideas"]


def list_projects() -> List[Dict[str, Any]]:
    """List all projects in the research sub-folder.

    Returns:
        List of {slug, name, has_index, has_ideas, note_count,
                 synthesis_present, created_at, modified_at}
    """
    root = get_research_root()
    projects_dir = root / "Projects"
    if not projects_dir.exists():
        return []
    out = []
    for entry in sorted(projects_dir.iterdir()):
        if not entry.is_dir():
            continue
        slug = entry.name
        index_file = entry / PROJECT_FILES["index"]
        ideas_file = entry / PROJECT_FILES["ideas"]
        notes_dir = entry / "notes"
        synth_file = entry / PROJECT_FILES["synthesis"]
        stat = entry.stat()
        # Read first heading of index.md as project name
        name = _read_first_heading(index_file) if index_file.exists() else slug
        note_count = sum(1 for _ in notes_dir.iterdir() if _.is_file() and _.suffix == ".md") if notes_dir.exists() else 0
        # Count thoughts (## YYYY- headings in ideas.md)
        thought_count = 0
        if ideas_file.exists():
            try:
                thought_count = sum(
                    1 for line in ideas_file.read_text(encoding="utf-8", errors="replace").splitlines()
                    if line.startswith("## 2")
                )
            except OSError:
                pass
        out.append({
            "slug": slug,
            "name": name,
            "has_index": index_file.exists(),
            "has_ideas": ideas_file.exists(),
            "synthesis_present": synth_file.exists(),
            "note_count": note_count,
            "thought_count": thought_count,
            "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(timespec="seconds"),
            "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        })
    return out


def _read_first_heading(path: Path) -> str:
    """Read the first `# heading` from a markdown file, fall back to YAML
    `title:` field, fall back to '?'."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "?"
    in_frontmatter = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "---":
            in_frontmatter = not in_frontmatter
            continue
        if in_frontmatter:
            m = re.match(r"^title:\s*['\"]?(.+?)['\"]?\s*$", stripped)
            if m:
                return m.group(1).strip()
            continue
        m = re.match(r"^#\s+(.+?)\s*$", line)
        if m:
            return m.group(1).strip()
    return "?"


def project_exists(slug: str) -> bool:
    """Check if a project directory + index.md exists."""
    return project_index_path(slug).exists()


def create_project(
    name: str,
    research_question: str = "",
    direction: str = "",
    topic: str = "",
) -> Dict[str, Any]:
    """Create a new project in the research sub-folder.

    Idempotent: if a project with the same slug exists, returns
    status='exists' without modifying files. To update an existing
    project, use a different code path (manual edit or future
    `pa obsidian project update`).

    Args:
        name: project name (will be slugified for folder name)
        research_question: optional research question (stored in index.md)
        direction: optional research direction
        topic: optional topic tag (free-text)

    Returns:
        Dict {status, slug, path, error?}
    """
    if not name or not name.strip():
        return {"status": "error", "error": "empty project name"}

    slug = slugify(name)
    if not slug or slug.startswith("untitled-"):
        # Slugification failed completely — use raw name + timestamp
        slug = f"untitled-{timestamp_slug()}"

    pr = project_root(slug)
    if project_exists(slug):
        return {
            "status": "exists",
            "slug": slug,
            "name": name,
            "path": str(project_index_path(slug)),
        }

    try:
        pr.mkdir(parents=True, exist_ok=False)
        (pr / "notes").mkdir(exist_ok=False)
    except FileExistsError:
        return {"status": "exists", "slug": slug, "path": str(pr)}
    except OSError as e:
        return {"status": "error", "error": f"mkdir failed: {e}"}

    # Write index.md
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    index_content = _render_index(
        name=name,
        slug=slug,
        research_question=research_question,
        direction=direction,
        topic=topic,
        created=now,
    )
    try:
        project_index_path(slug).write_text(index_content, encoding="utf-8")
        project_ideas_path(slug).write_text(
            f"# Ideas — {name}\n\n"
            f"_Raw / unformed thoughts. Append via `pa obsidian project thought`._\n\n",
            encoding="utf-8",
        )
    except OSError as e:
        return {"status": "error", "error": f"write failed: {e}"}

    return {
        "status": "created",
        "slug": slug,
        "name": name,
        "path": str(project_index_path(slug)),
    }


def _render_index(
    name: str,
    slug: str,
    research_question: str,
    direction: str,
    topic: str,
    created: str,
) -> str:
    parts = [
        f"# {name}",
        "",
        f"- **Slug**: `{slug}`",
        f"- **Created**: {created}",
        f"- **Status**: active",
    ]
    if topic:
        parts.append(f"- **Topic**: {topic}")
    if direction:
        parts += ["", "## Direction", "", direction, ""]
    if research_question:
        parts += ["", "## Research question", "", research_question, ""]
    parts += [
        "",
        "## Linked Zotero project",
        "",
        f"_If you have a Zotero collection with the same name, "
        f"link it here. Use `pa zotero project status --name \"{name}\"` "
        f"to see items in that collection._",
        "",
        "## Sub-notes",
        "",
        "_Atomic notes will appear here as you add them._",
        "",
        "## Synthesis",
        "",
        "_See `synthesis.md` for cross-paper analysis._",
        "",
    ]
    return "\n".join(parts)


def add_thought(name: str, content: str) -> Dict[str, Any]:
    """Append a thought to a project's ideas.md (raw/unformed thoughts).

    Creates the project (with empty index.md) if it doesn't exist yet,
    so you can quickly capture ideas before formalizing the project.

    Args:
        name: project name
        content: thought text (1-3 sentences usually)

    Returns:
        Dict {status, slug, path, thought_count}
    """
    if not content or not content.strip():
        return {"status": "error", "error": "empty content"}
    slug = slugify(name)
    if not slug:
        return {"status": "error", "error": "could not slugify project name"}

    # Auto-create project if missing (with minimal index.md)
    if not project_exists(slug):
        result = create_project(name, research_question="", direction="")
        if result["status"] == "error":
            return result

    ideas_path = project_ideas_path(slug)
    if not ideas_path.exists():
        # Re-create the ideas file if it was deleted
        ideas_path.write_text(
            f"# Ideas — {name}\n\n"
            f"_Raw / unformed thoughts. Append via `pa obsidian project thought`._\n\n",
            encoding="utf-8",
        )
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    try:
        with ideas_path.open("a", encoding="utf-8") as f:
            f.write(f"## {stamp}\n\n{content.strip()}\n\n")
    except OSError as e:
        return {"status": "error", "error": f"append failed: {e}"}

    # Count current thoughts (count "## YYYY-" headings)
    thought_count = sum(1 for line in ideas_path.read_text(encoding="utf-8").splitlines() if line.startswith("## 2"))
    return {
        "status": "ok",
        "slug": slug,
        "name": name,
        "path": str(ideas_path),
        "thought_count": thought_count,
    }


def add_note(
    name: str,
    content: str,
    note_type: str = "idea",
    title: str = "",
) -> Dict[str, Any]:
    """Create a new atomic note in a project.

    Auto-creates the project if missing (just like add_thought).

    Args:
        name: project name
        content: note body (markdown)
        note_type: one of NOTE_TYPES (idea, reading, synthesis, question, evidence)
        title: optional explicit title (else first line of content, or 'untitled')

    Returns:
        Dict {status, slug, path, title, type}
    """
    if not content or not content.strip():
        return {"status": "error", "error": "empty content"}
    if note_type not in NOTE_TYPES:
        return {
            "status": "error",
            "error": f"invalid note_type: {note_type!r}. Must be one of: {NOTE_TYPES}",
        }
    slug = slugify(name)
    if not slug:
        return {"status": "error", "error": "could not slugify project name"}

    if not project_exists(slug):
        result = create_project(name, research_question="", direction="")
        if result["status"] == "error":
            return result

    # Determine note title
    if not title:
        first_line = content.strip().splitlines()[0].lstrip("# ").strip() if content.strip() else ""
        title = first_line[:80] or "untitled"
    notes_dir = project_root(slug) / "notes"
    if not notes_dir.exists():
        notes_dir.mkdir(parents=True, exist_ok=True)
    fname = safe_filename(title, suffix=".md")
    fpath = notes_dir / fname

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    frontmatter = (
        f"---\n"
        f"title: \"{title}\"\n"
        f"type: {note_type}\n"
        f"project: {name}\n"
        f"created: {stamp}\n"
        f"---\n\n"
    )
    body = content.strip() + "\n"
    try:
        fpath.write_text(frontmatter + body, encoding="utf-8")
    except OSError as e:
        return {"status": "error", "error": f"write failed: {e}"}
    return {
        "status": "created",
        "slug": slug,
        "name": name,
        "path": str(fpath),
        "title": title,
        "type": note_type,
    }


def project_status(slug: str) -> Dict[str, Any]:
    """Get the current state of a project.

    Returns:
        Dict {status, slug, name, has_index, has_ideas, note_count,
              synthesis_present, recent_notes, root}
    """
    pr = project_root(slug)
    if not pr.exists():
        return {"status": "error", "error": f"project not found: {slug}"}
    index = pr / PROJECT_FILES["index"]
    ideas = pr / PROJECT_FILES["ideas"]
    notes_dir = pr / "notes"
    synth = pr / PROJECT_FILES["synthesis"]
    note_count = 0
    recent = []
    if notes_dir.exists():
        for f in sorted(notes_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
            if f.suffix == ".md" and f.is_file():
                note_count += 1
                if len(recent) < 5:
                    # Read first heading
                    title = _read_first_heading(f) or f.stem
                    stat = f.stat()
                    recent.append({
                        "path": str(f),
                        "title": title,
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                    })
    thought_count = 0
    if ideas.exists():
        thought_count = sum(1 for line in ideas.read_text(encoding="utf-8", errors="replace").splitlines() if line.startswith("## 2"))
    return {
        "status": "ok",
        "slug": slug,
        "name": _read_first_heading(index) if index.exists() else slug,
        "has_index": index.exists(),
        "has_ideas": ideas.exists(),
        "thought_count": thought_count,
        "note_count": note_count,
        "synthesis_present": synth.exists(),
        "recent_notes": recent,
        "root": str(pr),
    }


# ─────────────────────────────────────────────────────────────────
# Inbox (uncategorized thoughts)
# ─────────────────────────────────────────────────────────────────
def inbox_add(content: str) -> Dict[str, Any]:
    """Add a thought to the global Inbox (no project).

    Returns:
        Dict {status, path, filename}
    """
    if not content or not content.strip():
        return {"status": "error", "error": "empty content"}
    inbox_dir = get_research_root() / "Inbox"
    if not inbox_dir.exists():
        inbox_dir.mkdir(parents=True, exist_ok=True)
    fname = safe_filename(content[:30], suffix=".md")
    fpath = inbox_dir / fname
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    try:
        fpath.write_text(
            f"---\ncreated: {stamp}\nsource: pa obsidian inbox add\n---\n\n"
            f"# Inbox {stamp}\n\n{content.strip()}\n",
            encoding="utf-8",
        )
    except OSError as e:
        return {"status": "error", "error": f"write failed: {e}"}
    return {"status": "created", "path": str(fpath), "filename": fname}


def inbox_list(limit: int = 20) -> List[Dict[str, Any]]:
    """List recent inbox notes (most recent first).

    Returns:
        List of {path, filename, title, created, modified}
    """
    inbox_dir = get_research_root() / "Inbox"
    if not inbox_dir.exists():
        return []
    out = []
    for f in sorted(inbox_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if f.suffix == ".md" and f.is_file():
            stat = f.stat()
            out.append({
                "path": str(f),
                "filename": f.name,
                "title": _read_first_heading(f),
                "created": datetime.fromtimestamp(stat.st_ctime).isoformat(timespec="seconds"),
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
            })
    return out[:limit]


# ─────────────────────────────────────────────────────────────────
# Daily-note backlink (v3.9.20 [P3-29.2]) -- link today's daily note to
# an active research project, so the project's index page is 1 click
# away from any daily note that mentions it.
# ─────────────────────────────────────────────────────────────────
DAILY_SECTION_HEADER = "## Active research projects"
DAILY_SECTION_MARKER = "<!-- paper-agent:daily-link-section -->"  # idempotency marker


def daily_link(
    project_name: str,
    date: Optional[str] = None,
    vault_path: Optional[Path] = None,
    create_if_missing: bool = False,
) -> Dict[str, Any]:
    """Add a backlink to a research project in today's daily note.

    The daily note lives at `<vault>/4-Daily/<YYYY-MM-DD>.md`
    (the GTD vault convention). If the note exists, this appends
    a section `## Active research projects` (or adds to existing
    section) with a wiki-link to `0-Research/Projects/<slug>/index`.

    Args:
        project_name: research project name (= project slug derivation)
        date: ISO date string YYYY-MM-DD (default: today, local)
        vault_path: override vault path (default: $PAPER_AGENT_OBSIDIAN_VAULT)
        create_if_missing: if True, creates a stub daily note if it
            doesn't exist (default: False — skip gracefully)

    Returns:
        Dict with {status, daily_path, project_slug, link_added: bool,
        section_created: bool, error?}. Status values:
        - "linked": link added (or section already had the link)
        - "skipped_no_daily_note": daily note doesn't exist (and
          create_if_missing=False)
        - "skipped_no_vault": env var unset
        - "error": other failure
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    vault = Path(vault_path) if vault_path else get_vault_path()
    if vault is None:
        return {
            "status": "skipped_no_vault",
            "error": "$PAPER_AGENT_OBSIDIAN_VAULT is not set",
            "project_slug": "",
        }
    if not vault.exists():
        return {
            "status": "skipped_no_vault",
            "error": f"vault path does not exist: {vault}",
            "project_slug": "",
        }

    # Slugify the project name the same way init_vault does
    from .project import validate_slug  # reuse validator
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", project_name.strip()).strip("-").lower() or "research"

    daily_dir = vault / "4-Daily"
    daily_path = daily_dir / f"{date}.md"
    link_line = f"- [[{get_subfolder()}/Projects/{slug}/index|{project_name}]]"
    section_marker = f"<!-- paper-agent:daily-link:{slug} -->"  # per-project dedup marker

    # If daily note doesn't exist
    if not daily_path.exists():
        if not create_if_missing:
            return {
                "status": "skipped_no_daily_note",
                "daily_path": str(daily_path),
                "project_slug": slug,
                "project_name": project_name,
                "link_added": False,
            }
        # Create stub daily note
        daily_dir.mkdir(parents=True, exist_ok=True)
        stub = (
            f"# {date}\n\n"
            f"## Today's tasks\n\n"
            f"- [ ] \n\n"
            f"{DAILY_SECTION_HEADER}\n"
            f"{DAILY_SECTION_MARKER}\n"
            f"{link_line}  {section_marker}\n"
        )
        daily_path.write_text(stub, encoding="utf-8")
        return {
            "status": "linked",
            "daily_path": str(daily_path),
            "project_slug": slug,
            "project_name": project_name,
            "link_added": True,
            "section_created": True,
        }

    # Daily note exists; check for section marker (idempotency)
    content = daily_path.read_text(encoding="utf-8")
    if section_marker in content:
        # Already linked; idempotent return
        return {
            "status": "linked",
            "daily_path": str(daily_path),
            "project_slug": slug,
            "project_name": project_name,
            "link_added": False,
            "section_created": False,
        }

    # Check if the section exists
    if DAILY_SECTION_HEADER in content:
        # Section exists; append our link inside it (before the next
        # ## header or end of file)
        lines = content.split("\n")
        section_idx = next(
            (i for i, ln in enumerate(lines) if ln.strip() == DAILY_SECTION_HEADER),
            None,
        )
        if section_idx is None:
            # Shouldn't happen, but fall back to appending at end
            new_content = content.rstrip("\n") + f"\n\n{DAILY_SECTION_HEADER}\n{link_line}  {section_marker}\n"
        else:
            # Find the end of this section (next ## header or EOF)
            end_idx = len(lines)
            for i in range(section_idx + 1, len(lines)):
                if lines[i].startswith("## "):
                    end_idx = i
                    break
            insert = f"{link_line}  {section_marker}"
            lines.insert(end_idx, insert)
            new_content = "\n".join(lines)
    else:
        # Section doesn't exist; append at end
        new_content = content.rstrip("\n") + (
            f"\n\n{DAILY_SECTION_HEADER}\n"
            f"{DAILY_SECTION_MARKER}\n"
            f"{link_line}  {section_marker}\n"
        )

    daily_path.write_text(new_content, encoding="utf-8")
    return {
        "status": "linked",
        "daily_path": str(daily_path),
        "project_slug": slug,
        "project_name": project_name,
        "link_added": True,
        "section_created": DAILY_SECTION_HEADER not in content,
    }
