r"""
pa_cli.bibtex — convert paper-agent search results to BibTeX entries.

Designed for downstream academic workflows: Zotero, Mendeley, Overleaf,
LaTeX \cite{} references. Compatible with standard BibTeX parsers
(bibtexparser, JabRef, pybtex).

Output format: standard @article / @inproceedings / @misc entries with
DOI-based cite-keys (collision-handled with `_v2`, `_v3` suffix).

Author format: "Last, First Middle" joined with " and " — standard for
Zotero/Mendeley export.

Field mapping priority (when same data has multiple sources):
  title:    openalex > crossref
  author:   openalex (OpenAlex has best crossref-mapped author records)
  year:     openalex.publication_date > crossref.published-print
  journal:  openalex.primary_location.source.display_name >
            crossref.container-title
  doi:      openalex.doi (without https://doi.org/ prefix)
  url:      oa_url if open access, else doi.org
"""

import html
import re
from html.parser import HTMLParser
from .identifiers import split_identifiers, citation_url
from pathlib import Path
from typing import List, Dict, Optional, Any


# ---------- BibTeX entry type mapping ----------

_TYPE_MAP = {
    "article": "article",
    "journal-article": "article",
    "preprint": "article",  # arXiv preprints — bibtex sees them as articles
    "review": "article",
    "book": "book",
    "book-chapter": "incollection",
    "chapter": "incollection",
    "incollection": "incollection",
    "inproceedings": "inproceedings",
    "conference": "inproceedings",
    "proceedings": "proceedings",
    "proceedings-article": "inproceedings",
    "thesis": "phdthesis",
    "dissertation": "phdthesis",
    "phdthesis": "phdthesis",
    "mastersthesis": "mastersthesis",
    "report": "techreport",
    "techreport": "techreport",
    "dataset": "misc",
    "software": "misc",
    "other": "misc",
    "misc": "misc",
}


# ---------- Cite key generation ----------

def make_cite_key(paper: Dict, seen: set) -> str:
    """Generate unique BibTeX cite-key. Prefer DOI; fall back to author-year-title.

    `seen` is a mutable set of already-used keys; this function adds suffix
    `_v2`, `_v3` etc. on collision.
    """
    base = _base_key(paper)
    candidate = base
    n = 2
    while candidate in seen:
        candidate = f"{base}_v{n}"
        n += 1
    seen.add(candidate)
    return candidate


def _base_key(paper: Dict) -> str:
    if paper.get("key"):
        return str(paper["key"]).strip()
    doi, aid = split_identifiers(paper)
    if doi:
        # e.g. 10.1186/s41239-023-00411-8 -> 10_1186_s41239_023_00411_8
        # strip leading "10." since it's redundant
        return doi.replace("10.", "").replace("/", "_").replace(".", "_").replace("-", "_")
    if aid:
        return 'arxiv_' + re.sub(r'[^A-Za-z0-9]', '_', aid)
    # Fallback: first-author-lastname + year + first title word
    authors = paper.get("authors") or ["anon"]
    first_author = authors[0] or "anon"
    if isinstance(first_author, dict):
        first_author = first_author.get("family") or first_author.get("name") or "anon"
    first_author_str = str(first_author).strip()
    if "," in first_author_str:
        last = first_author_str.split(",")[0].strip().lower()
    else:
        last = first_author_str.split()[-1].lower() if first_author_str.split() else "anon"
    last = "".join(c for c in last if c.isalnum()) or "anon"
    year = paper.get("year") or "nd"
    title = (paper.get("title") or "").split()
    title_word = title[0].lower() if title else "untitled"
    title_word = "".join(c for c in title_word if c.isalnum()) or "untitled"
    return f"{last}_{year}_{title_word}"[:64]  # bibtex keys should be reasonable length


# ---------- Markup and LaTeX Text Cleaning ----------

class _MarkupText(HTMLParser):
    """Strip recognized markup only; unknown angle-bracket text stays literal."""
    tags = set('a b i em strong u s sub sup p br div span ul ol li h1 h2 h3 h4 h5 h6 '
               'table thead tbody tr td th blockquote italic bold underline sec title '
               'abstract article article-title label ext-link xref inline-formula '
               'disp-formula math mrow mi mn mo msup msub mfrac'.split())

    def __init__(self, source):
        super().__init__(convert_charrefs=False)
        self.source, self.parts = source, []
        self.starts = [0]
        self.starts.extend(m.end() for m in re.finditer('\n', source))

    def known(self, tag):
        return tag in self.tags or tag.startswith(('jats:', 'mml:'))

    def handle_starttag(self, tag, attrs):
        if not self.known(tag):
            self.parts.append(self.get_starttag_text())

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if not self.known(tag):
            line, col = self.getpos()
            start = self.starts[line - 1] + col
            self.parts.append(self.source[start:self.source.index('>', start) + 1])

    def handle_data(self, data):
        self.parts.append(data)

    def handle_entityref(self, name):
        self._entity('&' + name)

    def handle_charref(self, name):
        self._entity('&#' + name)

    def _entity(self, prefix):
        line, col = self.getpos()
        end = self.starts[line - 1] + col + len(prefix)
        self.parts.append(prefix + (';' if self.source[end:end + 1] == ';' else ''))

def unescape_bibtex(s: str) -> str:
    """Unescape common LaTeX escapes in BibTeX fields: \\& -> &, \\% -> %, etc.
    Also strips embedded XML/HTML tags and unescapes entities without collapsing spacing.
    """
    if not s:
        return ""
    s = str(s)
    s = re.sub(r'\\([&%$#_{}])', r'\1', s)
    s = s.replace(r'\\', r' ')
    parser = _MarkupText(s)
    parser.feed(s)
    parser.close()
    return html.unescape(''.join(parser.parts))


def clean_markup_text(s: str) -> str:
    """Clean HTML/XML tags (e.g. JATS tags like <jats:p>, <jats:sec>, <i>, <b>),
    HTML entities (&amp;, &lt;, &gt;, &quot;, &#39;), and normalize whitespace.
    """
    if not s:
        return ""
    text = unescape_bibtex(s)
    return " ".join(text.split()).strip()


# ---------- Author formatting ----------

def format_authors(authors: List[Any]) -> str:
    """Format author list into standard BibTeX 'Last, First and Last, First' format.

    Handles:
    - Already formatted: 'Brynjolfsson, Erik' -> 'Brynjolfsson, Erik'
    - First Last: 'Erik Brynjolfsson' -> 'Brynjolfsson, Erik'
    - First Middle Last: 'John F. Kennedy' -> 'Kennedy, John F.'
    - Trailing commas or dirty strings: 'Brynjolfsson, Erik,' -> 'Brynjolfsson, Erik'
    - Dicts: {'family': 'Brynjolfsson', 'given': 'Erik'} -> 'Brynjolfsson, Erik'
    - Single names: 'Plato' -> 'Plato'
    """
    formatted = []
    for a in authors:
        if not a:
            continue
        if isinstance(a, dict):
            fam = a.get("family") or a.get("lastName") or a.get("last") or ""
            giv = a.get("given") or a.get("firstName") or a.get("first") or ""
            if fam and giv:
                formatted.append(f"{str(fam).strip()}, {str(giv).strip()}")
                continue
            name_val = a.get("name") or fam or giv or ""
            a_str = str(name_val).strip()
        else:
            a_str = str(a).strip()

        # Clean leading/trailing commas or semicolons
        a_str = a_str.strip(",; ")
        if not a_str:
            continue

        if "," in a_str:
            # Already in "Last, First" or "Last, First Middle" format
            parts = [p.strip() for p in a_str.split(",") if p.strip()]
            if len(parts) >= 2:
                formatted.append(f"{parts[0]}, {', '.join(parts[1:])}")
            elif len(parts) == 1:
                formatted.append(parts[0])
        else:
            # "First Middle Last" format
            parts = a_str.split()
            if len(parts) >= 2:
                last = parts[-1]
                first_middle = " ".join(parts[:-1])
                formatted.append(f"{last}, {first_middle}")
            else:
                formatted.append(a_str)
    return " and ".join(formatted)


# ---------- BibTeX escape ----------

def escape_bibtex(s: str) -> str:
    """Escape characters that BibTeX treats specially: { } \\ and special LaTeX chars.

    Conservative escape: protects braces (used for case preservation),
    backslash, and percent. Doesn't try to be smart about Unicode — BibTeX
    handles UTF-8 natively in modern engines (biber + biblatex).
    """
    if not s:
        return ""
    s = str(s)
    s = s.replace("\\", "\\\\")
    s = s.replace("{", "\\{")
    s = s.replace("}", "\\}")
    s = s.replace("&", r"\&")
    s = s.replace("%", r"\%")
    s = s.replace("$", r"\$")
    s = s.replace("#", r"\#")
    s = s.replace("_", r"\_")
    return s


# ---------- Entry construction ----------

def to_bibtex(paper: Dict, seen: Optional[set] = None) -> str:
    """Convert one paper dict to a BibTeX entry string."""
    if seen is None:
        seen = set()
    cite_key = make_cite_key(paper, seen)
    entry_type = _TYPE_MAP.get((paper.get("type") or "article").lower(), "article")

    fields = []
    title = paper.get("title")
    if title:
        fields.append(("title", escape_bibtex(_clean_title(title))))
    authors = paper.get("authors") or []
    if authors:
        fields.append(("author", format_authors(authors)))
    venue = (paper.get("venue") or "").strip()
    if venue:
        fields.append(("journal", escape_bibtex(venue)))
    year = paper.get("year")
    if year:
        fields.append(("year", str(year)))
    doi, aid = split_identifiers(paper)
    if doi:
        fields.append(("doi", doi))
    if aid:
        fields.extend((("eprint", aid), ("archivePrefix", "arXiv")))
    url = citation_url(paper)
    if url:
        fields.append(("url", url))
    abstract = clean_markup_text(paper.get("abstract") or "")
    if abstract:
        fields.append(("abstract", escape_bibtex(abstract)))
    # Notes — useful for academic workflows
    notes = []
    if paper.get("is_oa"):
        notes.append("Open Access")
    if paper.get("cited_by_count") is not None:
        notes.append(f"cited by {paper['cited_by_count']}")
    if paper.get("oa_status"):
        notes.append(f"oa_status={paper['oa_status']}")
    if paper.get("source"):
        notes.append(f"source={paper['source']}")
    if notes:
        fields.append(("note", escape_bibtex("; ".join(notes))))

    field_str = ",\n  ".join(f"{k} = {{{v}}}" for k, v in fields)
    return f"@{entry_type}{{{cite_key},\n  {field_str}\n}}\n"


def format_bibtex_entry(entry: Dict) -> str:
    """Format an existing parsed BibTeX entry preserving original key and fields.

    Unlike to_bibtex() which constructs a new cite key and maps specific fields,
    format_bibtex_entry() preserves the original cite key, entry type, and any
    standard or custom fields (e.g. volume, pages, abstract, note, url) verbatim.
    Special entries (@string, @preamble, @comment) are returned verbatim.
    """
    if entry.get("_is_special") or entry.get("type") in ("string", "preamble", "comment"):
        raw = entry.get("_raw", "").strip()
        if raw:
            return raw + "\n\n"
        return ""

    key = str(entry.get("key", "")).strip() or "ref"
    raw_type = str(entry.get("type", "article")).strip().lower() or "article"
    etype = _TYPE_MAP.get(raw_type, raw_type)
    if "-" in etype:
        etype = _TYPE_MAP.get(etype.replace("-", ""), "misc")
    standard_order = [
        "title", "author", "journal", "booktitle", "year",
        "volume", "number", "pages", "month", "doi",
        "publisher", "address", "url", "abstract", "note"
    ]
    fields = []
    seen = {"key", "type", "_raw", "_was_updated", "_was_enriched", "_is_special", "macro", "_bare_fields", "_macros"}
    for f in standard_order:
        val = entry.get(f)
        if val is not None and str(val).strip():
            fields.append((f, str(val).strip()))
            seen.add(f)
    for f, val in entry.items():
        if f not in seen and not f.startswith("_") and val is not None and str(val).strip():
            fields.append((f, str(val).strip()))

    bare_fields = set(entry.get("_bare_fields") or ())
    if fields:
        field_lines = []
        for k, v in fields:
            if k in bare_fields:
                field_lines.append(f"{k} = {v}")
            else:
                field_lines.append(f"{k} = {{{v}}}")
        field_str = ",\n  ".join(field_lines)
        return f"@{etype}{{{key},\n  {field_str}\n}}\n"
    return f"@{etype}{{{key}\n}}\n"


def _clean_title(title: str) -> str:
    """Strip trailing period, normalize whitespace, clean markup and LaTeX escapes.
    BibTeX titles usually omit final period.
    """
    if not title:
        return ""
    title = unescape_bibtex(title)
    title = " ".join(title.split())
    if title.endswith("."):
        title = title[:-1].strip()
    return title



# ---------- File writer ----------

def write_bibtex(papers: List[Dict], output_path: str) -> str:
    """Write a list of paper dicts as a BibTeX file. Returns output_path."""
    seen = set()
    text = "% Generated by paper-agent CLI\n"
    text += "% https://github.com/croni4666-cmd/paper-agent\n"
    text += f"% {len(papers)} entries\n\n"
    for p in papers:
        text += to_bibtex(p, seen)
    fp = Path(output_path)
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(text, encoding="utf-8")
    return str(fp)
