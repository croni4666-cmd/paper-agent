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
    r"@([\w-]+)\s*\{\s*([^,\s]+)\s*,", re.MULTILINE
)


def _find_entry_end(body: str, close_delim: str) -> int:
    """Find index of the matching closing delimiter ('}' or ')') for an entry body."""
    i = 0
    n = len(body)
    brace_depth = 0
    in_quotes = False
    quote_brace_depth = 0
    while i < n:
        c = body[i]
        # Ignore comments outside strings/braces
        if not in_quotes and brace_depth == 0 and c == '%':
            while i < n and body[i] != '\n':
                i += 1
            continue
        if in_quotes:
            if c == '\\' and i + 1 < n:
                i += 2
                continue
            if c == '{':
                quote_brace_depth += 1
            elif c == '}':
                if quote_brace_depth > 0:
                    quote_brace_depth -= 1
            elif c == '"' and quote_brace_depth == 0:
                in_quotes = False
            i += 1
            continue
        if c == '"':
            in_quotes = True
            quote_brace_depth = 0
            i += 1
            continue
        if c == '{':
            brace_depth += 1
            i += 1
            continue
        if c == '}':
            if brace_depth > 0:
                brace_depth -= 1
                i += 1
                continue
            elif close_delim == '}':
                return i
        if c == ')' and brace_depth == 0 and close_delim == ')':
            return i
        i += 1
    return n


def resolve_bibtex_value(val: str, is_bare: bool = False, macros: Optional[Dict[str, str]] = None) -> str:
    """Resolve a BibTeX field value, expanding macros only when is_bare is True.

    If is_bare is False, the value was quoted or braced and represents a literal string.
    If is_bare is True, bare tokens (macro identifiers) are resolved against macros.
    Handles single tokens as well as '#' concatenated expressions (even with empty macros).
    """
    if not val:
        return ""
    if not is_bare:
        return val

    macro_dict = macros or {}

    if "#" in val:
        tokens = []
        i = 0
        n = len(val)
        while i < n:
            while i < n and val[i].isspace():
                i += 1
            if i >= n:
                break
            if val[i] == '{':
                i += 1
                depth = 1
                start = i
                while i < n and depth > 0:
                    if val[i] == '\\' and i + 1 < n:
                        i += 2
                        continue
                    if val[i] == '{':
                        depth += 1
                    elif val[i] == '}':
                        depth -= 1
                    i += 1
                end = i - 1 if depth == 0 else i
                tokens.append(val[start:end])
            elif val[i] == '"':
                i += 1
                depth = 0
                start = i
                while i < n:
                    if val[i] == '\\' and i + 1 < n:
                        i += 2
                        continue
                    if val[i] == '{':
                        depth += 1
                    elif val[i] == '}':
                        if depth > 0:
                            depth -= 1
                    elif val[i] == '"' and depth == 0:
                        break
                    i += 1
                end = i
                if i < n and val[i] == '"':
                    i += 1
                tokens.append(val[start:end])
            else:
                start = i
                while i < n and not val[i].isspace() and val[i] != '#':
                    i += 1
                token_text = val[start:i].strip()
                if token_text.lower() in macro_dict:
                    tokens.append(macro_dict[token_text.lower()])
                else:
                    tokens.append(token_text)

            while i < n and val[i].isspace():
                i += 1
            if i < n and val[i] == '#':
                i += 1

        return "".join(tokens)

    v_clean = val.strip()
    if v_clean.lower() in macro_dict:
        return macro_dict[v_clean.lower()]
    return val


def _parse_bibtex_fields(body: str) -> Dict[str, Any]:
    """Parse fields from a BibTeX entry body with full brace nesting, macro, concatenation, and bare number support."""
    fields = {}
    bare_fields = set()
    i = 0
    n = len(body)
    while i < n:
        while i < n and (body[i].isspace() or body[i] == ','):
            i += 1
        if i >= n:
            break
        if body[i] == '%':
            while i < n and body[i] != '\n':
                i += 1
            continue
        m_name = re.match(r'([A-Za-z0-9_:-]+)\s*=', body[i:])
        if not m_name:
            while i < n and body[i] not in (',', '\n'):
                i += 1
            if i < n and body[i] in (',', '\n'):
                i += 1
            continue
        fname = m_name.group(1).lower()
        i += m_name.end()

        # Parse field value tokens joined by '#'
        tokens = []
        has_hash = False

        while i < n:
            while i < n and body[i].isspace():
                i += 1
            if i >= n or body[i] in (',', '}', ')'):
                break

            if body[i] == '{':
                i += 1
                depth = 1
                val_start = i
                while i < n and depth > 0:
                    if body[i] == '\\' and i + 1 < n:
                        i += 2
                        continue
                    if body[i] == '{':
                        depth += 1
                    elif body[i] == '}':
                        depth -= 1
                    i += 1
                val_end = i - 1 if depth == 0 else i
                tokens.append(('braced', body[val_start:val_end], body[val_start-1:i]))
            elif body[i] == '"':
                i += 1
                val_start = i
                depth = 0
                while i < n:
                    if body[i] == '\\' and i + 1 < n:
                        i += 2
                        continue
                    if body[i] == '{':
                        depth += 1
                    elif body[i] == '}':
                        if depth > 0:
                            depth -= 1
                    elif body[i] == '"' and depth == 0:
                        break
                    i += 1
                val_end = i
                if i < n and body[i] == '"':
                    i += 1
                tokens.append(('quoted', body[val_start:val_end], body[val_start-1:i]))
            else:
                val_start = i
                while i < n and not body[i].isspace() and body[i] not in ('#', ',', '}', ')'):
                    i += 1
                raw_token = body[val_start:i]
                if not raw_token:
                    break
                tokens.append(('bare', raw_token, raw_token))

            while i < n and body[i].isspace():
                i += 1

            if i < n and body[i] == '#':
                has_hash = True
                i += 1
                while i < n and body[i].isspace():
                    i += 1
            else:
                break

        if i < n and body[i] == ',':
            i += 1

        if not tokens:
            fields[fname] = ""
            continue

        if not has_hash and len(tokens) == 1:
            ttype, inner, raw = tokens[0]
            val = inner.strip().replace("\r", "")
            val = re.sub(r"[ \t]+", " ", val)
            fields[fname] = val
            if ttype == 'bare':
                bare_fields.add(fname)
        else:
            parts = []
            for ttype, inner, raw in tokens:
                p = raw.strip().replace("\r", "")
                p = re.sub(r"[ \t]+", " ", p)
                parts.append(p)
            fields[fname] = " # ".join(parts)
            bare_fields.add(fname)

    if bare_fields:
        fields["_bare_fields"] = list(sorted(bare_fields))
    return fields


def parse_bibtex(text: str, include_special: bool = False) -> List[Dict[str, Any]]:
    """Robust bibtex parser preserving nested braces, bare numbers, macros, and entry types.

    Args:
        text: BibTeX formatted string.
        include_special: If False (default), filters out @string, @preamble, and @comment
                         so downstream literature consumers receive only ordinary paper entries.
                         If True, preserves special records for bibliography rewriting.
    """
    entries = []
    chunks = re.split(r"(?=@[\w-]+\s*[\{\(])", text)
    macro_defs: Dict[str, str] = {}
    for chunk in chunks:
        chunk_clean = chunk.strip()
        if not chunk_clean.startswith("@"):
            continue
        m_head = re.match(r"@([\w-]+)\s*([\{\(])", chunk_clean)
        if not m_head:
            continue
        raw_type = m_head.group(1).lower()
        open_delim = m_head.group(2)
        close_delim = "}" if open_delim == "{" else ")"

        # Preserve special BibTeX entries: @string, @preamble, @comment
        if raw_type in ("string", "preamble", "comment"):
            macro_name = f"_{raw_type}"
            macro_val = ""
            if raw_type == "string":
                m_str = re.match(r"@string\s*[\{\(]\s*([A-Za-z0-9_:-]+)\s*=", chunk_clean, re.IGNORECASE)
                if m_str:
                    macro_name = m_str.group(1)

            sp_body = chunk_clean[m_head.end():]
            sp_end = _find_entry_end(sp_body, close_delim)
            raw_special = chunk_clean[:m_head.end() + sp_end + 1]

            if raw_type == "string":
                parsed_fields = _parse_bibtex_fields(sp_body[:sp_end])
                for k, v in parsed_fields.items():
                    if k.startswith("_"):
                        continue
                    macro_name = k
                    is_bare = k in (parsed_fields.get("_bare_fields") or ())
                    macro_val = resolve_bibtex_value(v, is_bare=is_bare, macros=macro_defs)
                    macro_defs[macro_name.lower()] = macro_val
                    break
                if not macro_val:
                    m_v = re.search(r'=\s*(?:\{([^}]*)\}|"([^"]*)"|([^,\s}]+))', sp_body[:sp_end])
                    if m_v:
                        macro_val = m_v.group(1) or m_v.group(2) or m_v.group(3) or ""
                        macro_defs[macro_name.lower()] = macro_val

            entries.append({
                "type": raw_type,
                "key": macro_name,
                "macro": macro_name,
                "value": macro_val,
                "_raw": raw_special,
                "_is_special": True,
            })
            continue

        m = re.match(r"@([\w-]+)\s*[\{\(]\s*([^,\s]+)\s*,", chunk_clean)
        if not m:
            continue

        raw_type, key = m.group(1).lower(), m.group(2)
        from .bibtex import _TYPE_MAP
        etype = _TYPE_MAP.get(raw_type, raw_type)
        if "-" in etype:
            etype = _TYPE_MAP.get(etype.replace("-", ""), "misc")

        body = chunk_clean[m.end():]
        end = _find_entry_end(body, close_delim)
        raw_entry = chunk_clean[:m.end() + end + 1]
        fields = _parse_bibtex_fields(body[:end])
        fields["key"] = key
        fields["type"] = etype
        fields["_raw"] = raw_entry
        if macro_defs:
            fields["_macros"] = dict(macro_defs)
        entries.append(fields)

    if not include_special:
        return [e for e in entries if not e.get("_is_special") and e.get("type") not in ("string", "preamble", "comment")]
    return entries


def load_bibtex(path: Path, include_special: bool = False) -> List[Dict[str, Any]]:
    """Load + parse a .bib file.
    
    If include_special is False (default), filters out non-paper records (@string, @preamble, @comment)
    so consumers only receive ordinary literature entries.
    """
    return parse_bibtex(path.read_text(encoding="utf-8"), include_special=include_special)


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
    entries = [e for e in entries if not e.get('_is_special') and e.get('type') not in ('string', 'preamble', 'comment')]
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
