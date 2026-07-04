"""
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

from pathlib import Path
from typing import List, Dict, Optional


# ---------- BibTeX entry type mapping ----------

_TYPE_MAP = {
    "article": "article",
    "preprint": "article",  # arXiv preprints — bibtex sees them as articles
    "review": "article",
    "book": "book",
    "book-chapter": "incollection",
    "inproceedings": "inproceedings",
    "conference": "inproceedings",
    "proceedings": "proceedings",
    "thesis": "phdthesis",
    "report": "techreport",
    "dataset": "misc",
    "other": "misc",
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
    doi = (paper.get("doi") or "").replace("https://doi.org/", "").strip()
    if doi:
        # e.g. 10.1186/s41239-023-00411-8 -> 10_1186_s41239_023_00411_8
        # strip leading "10." since it's redundant
        return doi.replace("10.", "").replace("/", "_").replace(".", "_").replace("-", "_")
    # Fallback: first-author-lastname + year + first title word
    authors = paper.get("authors") or ["anon"]
    first_author = authors[0] or "anon"
    last = first_author.split()[-1].lower() if first_author.split() else "anon"
    last = "".join(c for c in last if c.isalnum()) or "anon"
    year = paper.get("year") or "nd"
    title = (paper.get("title") or "").split()
    title_word = title[0].lower() if title else "untitled"
    title_word = "".join(c for c in title_word if c.isalnum()) or "untitled"
    return f"{last}_{year}_{title_word}"[:64]  # bibtex keys should be reasonable length


# ---------- Author formatting ----------

def format_authors(authors: List[str]) -> str:
    """['First Last', 'First Middle Last'] -> ['Last, First Middle', ...] joined with ' and '."""
    formatted = []
    for a in authors:
        if not a:
            continue
        parts = a.strip().split()
        if len(parts) >= 2:
            last = parts[-1]
            first_middle = " ".join(parts[:-1])
            formatted.append(f"{last}, {first_middle}")
        else:
            formatted.append(a)
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
    doi = (paper.get("doi") or "").replace("https://doi.org/", "").strip()
    if doi:
        fields.append(("doi", doi))
    # URL priority: oa_url > doi.org URL
    url = paper.get("oa_url") or (f"https://doi.org/{doi}" if doi else "")
    if url:
        fields.append(("url", url))
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


def _clean_title(title: str) -> str:
    """Strip trailing period, normalize whitespace. BibTeX titles usually omit final period."""
    title = " ".join(title.split())
    if title.endswith("."):
        title = title[:-1]
    return title


# ---------- File writer ----------

def write_bibtex(papers: List[Dict], output_path: str) -> str:
    """Write a list of paper dicts as a BibTeX file. Returns output_path."""
    seen = set()
    text = "% Generated by paper-agent CLI v3.4.0\n"
    text += "% " + ("https://github.com/Mavis/mavis" if False else "G:\\minimax - workspace\\Paper agent") + "\n"
    text += f"% {len(papers)} entries\n\n"
    for p in papers:
        text += to_bibtex(p, seen)
    fp = Path(output_path)
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(text, encoding="utf-8")
    return str(fp)