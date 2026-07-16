"""
pa_cli.scaffold — generate markdown outline skeleton from Bibtex (+ optional
topic clusters).

Per [P2-5] (ROADMAP "Writing pipeline"):
  The skeleton is NOT prose. It's a structured outline with:
    - section headings (H1/H2)
    - per-paper [cite: bibtex-key] placeholders
    - section-level transition prompts ("prompt: ..." blocks) that
      instruct Mavis (or the user) what kind of paragraph to write

  The user (or Mavis) then fills in the prose between headings. The
  final markdown + bibtex goes into `pa build` to produce a formatted
  manuscript.

Usage from CLI:
  pa scaffold refs.bib > skeleton.md             # 1 heading per paper, grouped by year
  pa scaffold refs.bib --group-by topic --topics topics.json > skeleton.md
  pa scaffold refs.bib --out skeleton.md
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ---------- Bibtex parsing (lightweight, no external deps) ----------

_BIB_ENTRY_RE = re.compile(
    r"@\w+\s*\{\s*([^,\s]+)\s*,", re.MULTILINE
)
_FIELD_RE = re.compile(
    r"(\w+)\s*=\s*(?:\{((?:[^{}]|\{[^{}]*\})*)\}|\"((?:[^\"]|\"[^\"]*\")*)\")",
    re.DOTALL,
)


def parse_bibtex(text: str) -> List[Dict[str, str]]:
    """Lightweight bibtex parser. Returns list of {key, type, title, author, year, ...}.

    Does NOT handle nested braces perfectly (one level deep is OK). Sufficient
    for `pa search --format bibtex` output.
    """
    entries = []
    # Split on @ entries
    chunks = re.split(r"(?=@\w+\s*\{)", text)
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk.startswith("@"):
            continue
        # Entry type and key
        m = re.match(r"@(\w+)\s*\{\s*([^,\s]+)\s*,", chunk)
        if not m:
            continue
        etype, key = m.group(1).lower(), m.group(2)
        # Strip balanced braces/quotes from field values
        body = chunk[m.end():]
        # Trim trailing closing brace
        # Find matching closing brace from the end
        depth = 0
        end = len(body) - 1
        for i in range(len(body) - 1, -1, -1):
            if body[i] == "}":
                depth += 1
            elif body[i] == "{":
                depth -= 1
            if depth == 0:
                end = i
                break
        body = body[:end]
        # Parse fields
        fields = {"key": key, "type": etype}
        for fm in _FIELD_RE.finditer(body):
            fname = fm.group(1).lower()
            fval = fm.group(2) if fm.group(2) is not None else fm.group(3)
            if fval is None:
                continue
            # Clean internal braces/quotes
            fval = re.sub(r"[{}]", "", fval)
            fval = fval.strip().replace("\n", " ").replace("\r", "")
            fval = re.sub(r"\s+", " ", fval)
            fields[fname] = fval
        entries.append(fields)
    return entries


def load_bibtex(path: Path) -> List[Dict[str, str]]:
    """Load + parse a .bib file."""
    return parse_bibtex(path.read_text(encoding="utf-8"))


# ---------- Topic clusters (from `pa review-topics`) ----------

def load_topics(path: Path) -> Optional[Dict]:
    """Load topics.json from `pa review-topics -o topics.json`. May be None if
    the file doesn't exist or is malformed — caller should fall back to
    year/author grouping.
    """
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


# ---------- Prompt templates (Chinese-friendly, English fallback) ----------

# Each section has a "prompt" line telling Mavis (or the user) what to write.
# Keep these short — they are breadcrumbs, not paragraphs.

INTRO_PROMPT = (
    "prompt: 用 1 段（80-150 字）介绍本综述的研究主题、研究问题、对应的文献范围；"
    "结尾点出本综述的组织结构（按 X 个主题 / 按时间 / 按方法）。"
)

CONCLUSION_PROMPT = (
    "prompt: 用 1 段（100-200 字）总结本综述的核心发现、研究空白、对未来研究的启示；"
    "可结合前述各主题的关键引用做收束。"
)

PAPER_PROMPT = (
    "prompt: 用 1-2 句总结该论文的核心方法 + 关键发现 + 与本节主题的关系，"
    "并在描述其贡献时引用 [@{key}]；可标注 {venue} {year} 等出处信息。"
)

THEME_HEADER_PROMPT = (
    "prompt: 用 1 段（60-120 字）引出本节主题，说明该主题在领域中的定位、"
    "为什么重要、与相邻主题的边界。"
)


# ---------- Grouping ----------

def _author_short(authors: str) -> str:
    """Take 'Smith, John; Doe, Jane' -> 'Smith & Doe' or 'Smith et al.'"""
    if not authors:
        return "Unknown"
    # Split on ' and ' or ';'
    parts = re.split(r"\s+and\s+|;\s*", authors)
    parts = [p.strip() for p in parts if p.strip()]
    if not parts:
        return "Unknown"
    # Last name = first part before comma (or whole string)
    def lastname(s: str) -> str:
        if "," in s:
            return s.split(",")[0].strip()
        return s.split()[-1] if s.split() else s
    if len(parts) == 1:
        return lastname(parts[0])
    if len(parts) == 2:
        return f"{lastname(parts[0])} & {lastname(parts[1])}"
    return f"{lastname(parts[0])} et al."


def _group_by_year(entries: List[Dict]) -> List[Tuple[str, List[Dict]]]:
    """Group entries by year (descending). Undated entries go to 'Undated'."""
    by_year: Dict[str, List[Dict]] = defaultdict(list)
    for e in entries:
        y = e.get("year", "").strip() or "Undated"
        by_year[y].append(e)
    years = sorted(by_year.keys(), key=lambda s: (s == "Undated", s), reverse=True)
    return [(y, by_year[y]) for y in years]


def _group_by_topic(
    entries: List[Dict], topics: Dict
) -> List[Tuple[str, List[Dict]]]:
    """Group entries by topic_id from topics.json. Falls back to all-in-one if
    topics.json shape is unrecognized.
    """
    # topics.json shape (per `pa review-topics`):
    #   { "alpha": ..., "topics": [{"id": 0, "label": "...", "papers": [paper_keys...]}], "outliers": [...] }
    topic_list = topics.get("topics") if isinstance(topics, dict) else None
    if not isinstance(topic_list, list) or not topic_list:
        return [("All Papers", entries)]
    key_to_entry = {e["key"]: e for e in entries}
    groups = []
    for t in topic_list:
        label = t.get("label") or f"Topic {t.get('id', '?')}"
        paper_keys = t.get("papers", [])
        papers = [key_to_entry[k] for k in paper_keys if k in key_to_entry]
        if papers:
            groups.append((label, papers))
    outliers = topics.get("outliers", [])
    if outliers:
        outlier_entries = [key_to_entry[k] for k in outliers if k in key_to_entry]
        if outlier_entries:
            groups.append(("Other / Unclustered", outlier_entries))
    return groups or [("All Papers", entries)]


def _group_by_author(entries: List[Dict]) -> List[Tuple[str, List[Dict]]]:
    """Group entries by first author last name (A-Z)."""
    by_author: Dict[str, List[Dict]] = defaultdict(list)
    for e in entries:
        a = _author_short(e.get("author", ""))
        by_author[a].append(e)
    return sorted(by_author.items())


# ---------- Render ----------

def render_skeleton(
    entries: List[Dict],
    group_by: str = "year",
    topics: Optional[Dict] = None,
    title: str = "文献综述",
    language: str = "zh",
) -> str:
    """Render a markdown skeleton.

    Args:
        entries: list of bibtex entries
        group_by: 'year' | 'topic' | 'author' | 'none'
        topics: required if group_by='topic'
        title: top-level title
        language: 'zh' | 'en' (currently only affects prompt templates)

    Returns:
        Markdown string.
    """
    if not entries:
        return (
            f"# {title}\n\n"
            "> [pa scaffold] Bibtex 解析成功但条目为空。检查 .bib 文件内容。\n"
        )

    # Sort entries within group: most recent first by year, then alpha by title
    def sort_key(e: Dict) -> Tuple[str, str]:
        y = e.get("year", "0000")
        return (y, e.get("title", "").lower())

    # Group
    if group_by == "topic":
        if topics is None:
            raise ValueError("group_by='topic' requires --topics topics.json")
        groups = _group_by_topic(entries, topics)
    elif group_by == "author":
        groups = _group_by_author(entries)
    elif group_by == "none":
        entries_sorted = sorted(entries, key=sort_key, reverse=True)
        groups = [("All Papers", entries_sorted)]
    else:  # default year
        groups = _group_by_year(entries)
        # Sort within year
        groups = [(y, sorted(es, key=sort_key, reverse=True)) for y, es in groups]

    # Render
    lines = [f"# {title}", ""]

    # Intro section
    lines += [
        "## 引言",
        "",
        f"> {INTRO_PROMPT}",
        "",
    ]

    # One section per group
    for group_label, group_entries in groups:
        lines.append(f"## {group_label}")
        lines.append("")
        if len(groups) > 1:
            lines += [f"> {THEME_HEADER_PROMPT}", ""]
        for e in group_entries:
            key = e["key"]
            title_short = (e.get("title") or "(untitled)").strip()
            # Truncate long titles
            if len(title_short) > 120:
                title_short = title_short[:117] + "..."
            venue = e.get("journal") or e.get("booktitle") or e.get("publisher") or ""
            year = e.get("year", "")
            author = _author_short(e.get("author", ""))
            # H3 sub-heading for the paper
            lines.append(f"### {title_short}")
            lines.append("")
            # Cite-key + minimal meta so Mavis can see context
            meta_bits = []
            if author and author != "Unknown":
                meta_bits.append(author)
            if year:
                meta_bits.append(year)
            if venue:
                meta_bits.append(venue)
            if meta_bits:
                lines.append(f"*{' · '.join(meta_bits)}*")
                lines.append("")
            # Per-paper prompt (includes the [@key] cite so Mavis can copy it
            # into the prose directly)
            lines.append(
                f"> {PAPER_PROMPT.format(key=key, venue=venue or '?', year=year or '?')}"
            )
            lines.append("")

    # Conclusion
    lines += [
        "## 结语",
        "",
        f"> {CONCLUSION_PROMPT}",
        "",
        "## 参考文献",
        "",
        "> pandoc 会在 build 时根据 refs.bib + csl 自动生成此节，无需手写。",
        "",
    ]
    return "\n".join(lines)


def scaffold(
    bibtex_path: Path,
    group_by: str = "year",
    topics_path: Optional[Path] = None,
    title: str = "文献综述",
    output_path: Optional[Path] = None,
) -> str:
    """End-to-end: read .bib, optionally read topics, render skeleton markdown.

    Returns the rendered markdown string. If output_path is given, also writes
    to that file.
    """
    entries = load_bibtex(bibtex_path)
    topics = load_topics(topics_path) if topics_path else None
    md = render_skeleton(entries, group_by=group_by, topics=topics, title=title)
    if output_path:
        Path(output_path).write_text(md, encoding="utf-8")
    return md
