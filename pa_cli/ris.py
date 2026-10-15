"""Deterministic local RIS rendering; no provider, SDK or PDF dependency."""

import os
from pathlib import Path
import re
import tempfile

from .identifiers import citation_url, split_identifiers


TYPES = {
    "article": "JOUR", "journal-article": "JOUR", "journal_article": "JOUR",
    "book": "BOOK", "inbook": "CHAP", "incollection": "CHAP",
    "book-chapter": "CHAP", "inproceedings": "CPAPER", "conference": "CPAPER",
    "proceedings-article": "CPAPER", "proceedings": "CONF",
    "phdthesis": "THES", "mastersthesis": "THES", "thesis": "THES",
    "techreport": "RPRT", "report": "RPRT",
}


def _text(value):
    if value is None:
        return ""
    if not isinstance(value, (str, int, float)):
        raise ValueError("RIS bibliographic fields must be text or numbers")
    # No metadata value may create a new RIS tag or record (including CR and
    # Unicode line separators). Do not escape Unicode into ASCII sequences.
    value = " ".join(str(value).splitlines())
    return "".join(" " if ord(c) < 32 or ord(c) == 127 else c for c in value).strip()


def _authors(value):
    if not value:
        return []
    if isinstance(value, list):
        result = []
        for author in value:
            if isinstance(author, dict):
                author = author.get("name") or author.get("display_name") or " ".join(
                    str(author.get(part) or "") for part in ("given", "family")
                )
            name = _text(author)
            if name:
                result.append(name)
        return result
    text = _text(value)
    # BibTeX's top-level `and` separates people; braced organization names may
    # themselves contain `and`. Keep their spelling and grouping intact.
    names, start, depth, i = [], 0, 0, 0
    while i < len(text):
        if text[i] == "\\" and i + 1 < len(text):
            i += 2
            continue
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth = max(0, depth - 1)
        elif depth == 0:
            separator = re.match(r"\s+and\s+", text[i:])
            if separator:
                names.append(text[start:i].strip())
                i += separator.end()
                start = i
                continue
        i += 1
    names.append(text[start:].strip())
    return [name for name in names if name]


def ris_entries(data):
    if isinstance(data, dict):
        for key in ("papers", "entries", "results"):
            if key in data:
                data = data[key]
                break
        else:
            raise ValueError("RIS JSON requires papers, entries or results")
    if not isinstance(data, list) or not all(isinstance(e, dict) for e in data):
        raise ValueError("RIS input must be a list of bibliographic objects")
    return [e for e in data if not e.get("_is_special") and
            str(e.get("type", "")).lower() not in {"string", "preamble", "comment"}]


def render_ris(entries):
    """Render explicit bibliographic records, omitting unknown optional fields."""
    from .scaffold import resolve_bibtex_value

    entries = ris_entries(entries)
    records = []
    for entry in entries:
        entry = dict(entry)
        for name in entry.get("_bare_fields") or []:
            if name in entry:
                entry[name] = resolve_bibtex_value(entry[name], is_bare=True, macros=entry.get("_macros"))
        if entry.get("_is_special"):
            continue
        kind = _text(entry.get("type") or entry.get("ENTRYTYPE") or "misc").lower()
        lines = ["TY  - " + TYPES.get(kind, "GEN")]

        def field(tag, value):
            value = _text(value)
            if value:
                lines.append(f"{tag}  - {value}")

        field("ID", entry.get("key") or entry.get("ID") or entry.get("id"))
        field("TI", entry.get("title"))
        for author in _authors(entry.get("author") or entry.get("authors")):
            field("AU", author)
        year = _text(entry.get("year") or entry.get("publication_date"))
        if re.match(r"^\d{4}(?:\D|$)", year):
            field("PY", year[:4])
        field("T2", entry.get("journal") or entry.get("booktitle") or entry.get("venue"))
        for tag, name in (("VL", "volume"), ("IS", "number"), ("PB", "publisher"),
                          ("SN", "isbn"), ("AB", "abstract")):
            field(tag, entry.get(name))
        pages = _text(entry.get("pages"))
        if pages:
            bounds = re.split(r"\s*(?:--|[-–—])\s*", pages, maxsplit=1)
            field("SP", bounds[0])
            if len(bounds) == 2:
                field("EP", bounds[1])
        doi, aid = split_identifiers(entry)
        field("DO", doi)
        field("UR", citation_url(entry) or entry.get("url"))
        if aid:
            field("N1", f"arXiv:{aid}")
        lines.append("ER  - ")
        records.append("\n".join(lines) + "\n")
    return "\n".join(records)


def write_ris(path, content, *, protected_paths=()):
    """Publish a complete UTF-8 file atomically, preserving sources on failure."""
    path = Path(path)
    resolved = path.resolve()
    for source in protected_paths:
        source = Path(source)
        if resolved == source.resolve() or (path.exists() and source.exists() and os.path.samefile(path, source)):
            raise ValueError("RIS output must not overwrite an input/source file")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         dir=path.parent, prefix=".ris-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
