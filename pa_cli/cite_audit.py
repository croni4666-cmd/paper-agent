"""pa_cli.cite_audit — Manuscript citation fidelity and hallucination audit.

Per ROADMAP [P2-21]:
  Accepts a full academic manuscript written by the user (Markdown, LaTeX, Typst, or text).
  Extracts all citations (`[@key]`, `\\cite{key}`, `@key`, `[^key]`, `(Author, Year)`).
  Sentence-by-sentence verification of draft citations against local cached PDF evidence
  packets and BibTeX entries, achieving >= 90% detection rate for misattributions,
  contradictory claims, quotes out of context, numerical hallucinations, and ungrounded references.

Global Rule audit:
  100% offline-first; pure Python lexical, directional, and numerical verification;
  zero external API cost; Windows safe ASCII fallback.
"""
from __future__ import annotations

import json
import logging
import math
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from .cache import DEFAULT_CACHE_ROOT, _bare_doi, _doi_slug
from .doi import canonicalize_doi

log = logging.getLogger(__name__)

# ==============================================================================
# Data Models
# ==============================================================================

@dataclass
class CitationMarker:
    """An individual citation marker parsed from manuscript text."""
    key: str
    raw_text: str
    marker_type: str  # 'citeproc', 'latex', 'typst', 'footnote', 'author_year'
    line_number: int
    char_start: int
    char_end: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvidencePassage:
    """Best-matching candidate evidence snippet from source material."""
    text: str
    page: int  # 1-indexed, or 0 if from BibTeX abstract / metadata
    char_start: int = 0
    char_end: int = 0
    section: str = "body"
    lexical_score: float = 0.0
    detected_direction: str = "unspecified"
    source_origin: str = ""  # path to PDF or 'bibtex_abstract'

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AuditItem:
    """Audit result for a single cited assertion in the manuscript."""
    citation_key: str
    marker_type: str
    line_number: int
    claim_sentence: str
    claim_direction: str
    claim_numbers: list[str]
    resolved_source: Optional[str] = None
    source_title: str = ""
    source_doi: str = ""
    evidence_passage: Optional[EvidencePassage] = None
    fidelity_score: float = 0.0  # EFS in [0.0, 1.0]
    verdict: str = "HALLUCINATED_CITATION"
    # VERIFIED_FAITHFUL | PARTIALLY_SUPPORTED | MISATTRIBUTION |
    # HALLUCINATED_CITATION | NUMERICAL_DISCREPANCY
    flags: list[str] = field(default_factory=list)
    explanation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "citation_key": self.citation_key,
            "marker_type": self.marker_type,
            "line_number": self.line_number,
            "claim_sentence": self.claim_sentence,
            "claim_direction": self.claim_direction,
            "claim_numbers": self.claim_numbers,
            "resolved_source": self.resolved_source,
            "source_title": self.source_title,
            "source_doi": self.source_doi,
            "evidence_passage": self.evidence_passage.to_dict() if self.evidence_passage else None,
            "fidelity_score": round(self.fidelity_score, 4),
            "verdict": self.verdict,
            "flags": self.flags,
            "explanation": self.explanation,
        }


@dataclass
class AuditReport:
    """Comprehensive manuscript citation fidelity and hallucination report."""
    manuscript_name: str
    total_sentences: int
    total_citations: int
    verified_count: int
    partially_supported_count: int
    misattribution_count: int
    hallucinated_count: int
    numerical_discrepancy_count: int
    overall_fidelity_score: float
    pass_status: bool
    threshold: float
    items: list[AuditItem] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "manuscript_name": self.manuscript_name,
            "total_sentences": self.total_sentences,
            "total_citations": self.total_citations,
            "verified_count": self.verified_count,
            "partially_supported_count": self.partially_supported_count,
            "misattribution_count": self.misattribution_count,
            "hallucinated_count": self.hallucinated_count,
            "numerical_discrepancy_count": self.numerical_discrepancy_count,
            "overall_fidelity_score": round(self.overall_fidelity_score, 4),
            "pass_status": self.pass_status,
            "threshold": self.threshold,
            "items": [item.to_dict() for item in self.items],
        }


# ==============================================================================
# Direction and Linguistic Lexicons
# ==============================================================================

STOPWORDS: Set[str] = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can't", "cannot", "could", "couldn't",
    "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during",
    "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't",
    "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here",
    "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i",
    "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it",
    "it's", "its", "itself", "let's", "me", "more", "most", "mustn't", "my",
    "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or",
    "other", "ought", "our", "ours", "ourselves", "out", "over", "own", "same",
    "shan't", "she", "she'd", "she'll", "she's", "should", "shouldn't", "so",
    "some", "such", "than", "that", "that's", "the", "their", "theirs", "them",
    "themselves", "then", "there", "there's", "these", "they", "they'd", "they'll",
    "they're", "they've", "this", "those", "through", "to", "too", "under",
    "until", "up", "very", "was", "wasn't", "we", "we'd", "we'll", "we're",
    "we've", "were", "weren't", "what", "what's", "when", "when's", "where",
    "where's", "which", "while", "who", "who's", "whom", "why", "why's", "with",
    "won't", "would", "wouldn't", "you", "you'd", "you'll", "you're", "you've",
    "your", "yours", "yourself", "yourselves", "paper", "author", "authors",
    "study", "et", "al", "find", "finds", "show", "shows", "demonstrate",
    "demonstrates", "suggest", "suggests", "article", "literature", "research",
}

DIR_POSITIVE = re.compile(
    r"\b(?:positive|positively|increases?|increased|increasing|boosts?|promotes?|promoted|"
    r"improves?|improved|higher|enhances?|enhanced|stimulates?|fosters?|expansion|gains?)\b|"
    r"(?:正向|促进|显著提升|增加|提升|积极影响)",
    re.IGNORECASE,
)

DIR_NEGATIVE = re.compile(
    r"\b(?:negative|negatively|decreases?|decreased|decreasing|reduces?|reduced|reducing|"
    r"lower|inhibits?|inhibited|dampens?|impedes?|deteriorates?|adversely|drops?|decline)\b|"
    r"(?:负向|抑制|显著降低|减少|消极影响|阻碍)",
    re.IGNORECASE,
)

DIR_NULL = re.compile(
    r"\b(?:no\s+(?:significant\s+)?(?:effect|impact|relationship|association|correlation|difference)|"
    r"not\s+(?:statistically\s+)?significant|fails?\s+to\s+(?:find|reject)|insignificant|"
    r"uncorrelated|does\s+not\s+affect|did\s+not\s+find)\b|"
    r"(?:无显著(?:影响|差异|相关)|不显著|未发现显著|未见相关)",
    re.IGNORECASE,
)

DIR_NONLINEAR = re.compile(
    r"\b(?:u-shaped|inverted[- ]u|non-linear|nonlinear|convex|concave|quadratic)\b|"
    r"(?:倒U型|U型|非线性)",
    re.IGNORECASE,
)

# Number and statistical patterns
NUM_REGEX = re.compile(
    r"(?:-?\d+(?:\.\d+)?%|-?\b\d+\.\d+\b|\b\d+(?:\.\d+)?\s*(?:bps|percentage points?|fold|times|percent)\b)",
    re.IGNORECASE,
)

HEDGE_REGEX = re.compile(
    r"\b(?:suggests?|tentative|preliminary|may\s+indicate|could\s+be|under\s+certain\s+conditions|"
    r"partially|caution|weak\s+evidence|not\s+conclusive)\b",
    re.IGNORECASE,
)

ABBREVIATIONS = (
    "e.g.", "i.e.", "et al.", "vs.", "cf.", "fig.", "tab.", "eq.", "sec.",
    "p.", "pp.", "vol.", "no.", "ed.", "eds.", "al.", "dr.", "prof.",
    "approx.", "ca.", "dept.", "univ.",
)


# ==============================================================================
# Citation & Sentence Parsing
# ==============================================================================

# LaTeX cite commands: \cite{key}, \citep[...]{key}, \citet{k1, k2}
_LATEX_CITE_RE = re.compile(
    r"\\(?:cite|citep|citet|citeauthor|citeyear|autocite|parencite|footcite|textcite|fullcite|citealp)\*?"
    r"(?:\[[^\]]*\])?(?:\[[^\]]*\])?\{([^}]+)\}"
)

# Markdown citeproc: [@key], [@key1; @key2], [@key, p. 12], [-@key]
_CITEPROC_RE = re.compile(
    r"\[-?@([a-zA-Z0-9_\-:\.]+)(?:(?:\s*,\s*[^\];]+)?(?:;\s*-?@[a-zA-Z0-9_\-:\.]+(?:,[^\];]+)?)*)\]"
)

# Individual @key inside citeproc bracket or typst
_SUBKEY_RE = re.compile(r"@([a-zA-Z0-9_\-:\.]+)")

# Markdown footnote: [^key]
_FOOTNOTE_CITE_RE = re.compile(r"\[\^([a-zA-Z0-9_\-:\.]+)\]")

# Typst: @key (preceded by whitespace/start/open paren, followed by punct/close paren/whitespace)
_TYPST_CITE_RE = re.compile(r"(?:^|(?<=[\s\(]))@([a-zA-Z][a-zA-Z0-9_\-:\.]+)(?=[,\.;\?\s\)]|$)")

# Author-year textual citations: "Author et al. (2020)", "(Author & Coauthor, 2021)"
_AUTHOR_YEAR_RE1 = re.compile(
    r"\b([A-Z][a-zA-Z\u4e00-\u9fa5]+(?:\s+et\s+al\.)?)\s*[\(（](\d{4}[a-z]?)[\)）]"
)
_AUTHOR_YEAR_RE2 = re.compile(
    r"[\(（]([A-Z][a-zA-Z\u4e00-\u9fa5]+(?:\s+et\s+al\.|\s+&\s+[A-Z][a-zA-Z]+)?),\s*(\d{4}[a-z]?)[\)）]"
)


def extract_citation_markers(text: str) -> list[CitationMarker]:
    """Extract all citation markers across formats with line numbers and character spans."""
    markers: list[CitationMarker] = []
    lines = text.splitlines(keepends=True)

    # Track character offset for each line
    line_offsets = []
    curr_offset = 0
    for line in lines:
        line_offsets.append(curr_offset)
        curr_offset += len(line)

    def get_line_num(char_idx: int) -> int:
        for idx, offset in enumerate(line_offsets, start=1):
            if char_idx < offset:
                return max(1, idx - 1)
        return len(line_offsets)

    # 1. LaTeX citations
    for m in _LATEX_CITE_RE.finditer(text):
        raw_keys = m.group(1).split(",")
        for rk in raw_keys:
            clean_k = rk.strip()
            if clean_k:
                markers.append(
                    CitationMarker(
                        key=clean_k,
                        raw_text=m.group(0),
                        marker_type="latex",
                        line_number=get_line_num(m.start()),
                        char_start=m.start(),
                        char_end=m.end(),
                    )
                )

    # 2. Markdown Citeproc citations
    for m in _CITEPROC_RE.finditer(text):
        bracket_content = m.group(0)
        subkeys = _SUBKEY_RE.findall(bracket_content)
        for sk in subkeys:
            clean_k = sk.strip()
            if clean_k:
                markers.append(
                    CitationMarker(
                        key=clean_k,
                        raw_text=m.group(0),
                        marker_type="citeproc",
                        line_number=get_line_num(m.start()),
                        char_start=m.start(),
                        char_end=m.end(),
                    )
                )

    # 3. Footnote citations
    for m in _FOOTNOTE_CITE_RE.finditer(text):
        clean_k = m.group(1).strip()
        if clean_k:
            markers.append(
                CitationMarker(
                    key=clean_k,
                    raw_text=m.group(0),
                    marker_type="footnote",
                    line_number=get_line_num(m.start()),
                    char_start=m.start(),
                    char_end=m.end(),
                )
            )

    # 4. Typst citations (exclude matches already captured by citeproc)
    existing_spans = {(m.char_start, m.char_end) for m in markers}
    for m in _TYPST_CITE_RE.finditer(text):
        if any(s <= m.start() and m.end() <= e for s, e in existing_spans):
            continue
        clean_k = m.group(1).strip()
        if clean_k and not clean_k.startswith("http") and "@" not in clean_k:
            markers.append(
                CitationMarker(
                    key=clean_k,
                    raw_text=m.group(0),
                    marker_type="typst",
                    line_number=get_line_num(m.start()),
                    char_start=m.start(),
                    char_end=m.end(),
                )
            )

    # 5. Author-Year text citations
    for m in _AUTHOR_YEAR_RE1.finditer(text):
        auth, yr = m.groups()
        author_clean = re.sub(r"\s+et\s+al\.", "", auth).strip().lower()
        key = f"{author_clean}{yr}"
        markers.append(
            CitationMarker(
                key=key,
                raw_text=m.group(0),
                marker_type="author_year",
                line_number=get_line_num(m.start()),
                char_start=m.start(),
                char_end=m.end(),
            )
        )

    for m in _AUTHOR_YEAR_RE2.finditer(text):
        auth, yr = m.groups()
        author_clean = re.sub(r"\s+et\s+al\.|\s*&.*", "", auth).strip().lower()
        key = f"{author_clean}{yr}"
        markers.append(
            CitationMarker(
                key=key,
                raw_text=m.group(0),
                marker_type="author_year",
                line_number=get_line_num(m.start()),
                char_start=m.start(),
                char_end=m.end(),
            )
        )

    # Deduplicate overlapping markers with same key on same line
    unique_markers = []
    seen = set()
    for m in markers:
        key_tuple = (m.key.lower(), m.line_number, m.marker_type)
        if key_tuple not in seen:
            seen.add(key_tuple)
            unique_markers.append(m)

    unique_markers.sort(key=lambda m: (m.line_number, m.char_start))
    return unique_markers


def split_sentences_academic(text: str) -> list[Tuple[str, int, int]]:
    """Split academic text into sentences, protecting academic abbreviations and decimals.

    Returns list of (sentence_text, start_char, end_char).
    """
    if not text.strip():
        return []

    # Protect abbreviations by temporarily replacing periods
    safe_text = text
    placeholder = "\u0000"
    for abbr in ABBREVIATIONS:
        # Case insensitive match for abbreviation
        pattern = re.compile(re.escape(abbr), re.IGNORECASE)
        safe_text = pattern.sub(abbr.replace(".", placeholder), safe_text)

    # Protect decimals: digit.digit
    safe_text = re.sub(r"(\d)\.(\d)", rf"\1{placeholder}\2", safe_text)

    # Split on sentence boundaries: period, question mark, exclamation, or double newline
    sentence_spans = []
    split_pattern = re.compile(r"([^\.\?!;\n]+[\.\?!;]+|\n\s*\n)", re.MULTILINE)

    for m in split_pattern.finditer(safe_text):
        chunk = m.group(0)
        # Restore periods
        orig_chunk = chunk.replace(placeholder, ".")
        s_clean = orig_chunk.strip()
        if s_clean and len(s_clean) > 3:
            sentence_spans.append((s_clean, m.start(), m.end()))

    if not sentence_spans and text.strip():
        # Fallback if no delimiter was found
        sentence_spans.append((text.strip(), 0, len(text)))

    return sentence_spans


def detect_claim_direction(statement: str) -> str:
    """Detect direction of empirical/causal claim."""
    if DIR_NULL.search(statement):
        return "neutral"
    if DIR_NONLINEAR.search(statement):
        return "nonlinear"
    is_pos = bool(DIR_POSITIVE.search(statement))
    is_neg = bool(DIR_NEGATIVE.search(statement))
    if is_pos and not is_neg:
        return "positive"
    if is_neg and not is_pos:
        return "negative"
    return "unspecified"


def extract_numbers_from_claim(statement: str) -> list[str]:
    """Extract quantitative tokens (percentages, decimals, basis points)."""
    matches = NUM_REGEX.findall(statement)
    out = []
    for m in matches:
        clean = m.strip()
        if clean and clean not in out:
            out.append(clean)
    return out


# ==============================================================================
# Source Material Resolution (BibTeX & Local PDFs)
# ==============================================================================

def load_bibliography_db(bib_path: Optional[str | Path]) -> dict[str, dict[str, Any]]:
    """Load BibTeX file into key-indexed dictionary."""
    if not bib_path:
        return {}
    p = Path(bib_path)
    if not p.is_file():
        return {}

    try:
        from .scaffold import load_bibtex
        entries = load_bibtex(p)
    except Exception as e:
        log.warning(f"Failed to load BibTeX file {bib_path}: {e}")
        return {}

    db: dict[str, dict[str, Any]] = {}
    for entry in entries:
        key = entry.get("key", "")
        if key:
            db[key.lower()] = entry
            # Also index by canonicalized DOI if present
            doi = entry.get("doi")
            if doi:
                canon_doi = canonicalize_doi(doi)
                db[canon_doi] = entry
                db[_doi_slug(canon_doi)] = entry
    return db


def resolve_source_document(
    cite_key: str,
    bib_db: dict[str, dict[str, Any]],
    pdf_dir: Optional[Path] = None,
    manuscript_dir: Optional[Path] = None,
) -> Tuple[Optional[str], str, str, Optional[dict[str, Any]]]:
    """Locate local source PDF path or BibTeX metadata for a cited key.

    Returns:
        (pdf_path_or_none, title, doi, bib_entry_or_none)
    """
    clean_key = cite_key.lower().strip()
    bib_entry = bib_db.get(clean_key)

    # Search candidates if not exact key match
    if not bib_entry:
        for k, v in bib_db.items():
            if k in clean_key or clean_key in k:
                bib_entry = v
                break

    title = ""
    doi = ""
    if bib_entry:
        title = bib_entry.get("title", "")
        doi = canonicalize_doi(bib_entry.get("doi", ""))

    # 1. Check if bib entry points to an explicit file
    if bib_entry and bib_entry.get("file"):
        file_field = bib_entry["file"]
        cand = Path(file_field)
        if cand.is_file():
            return str(cand), title, doi, bib_entry
        if manuscript_dir and (manuscript_dir / cand).is_file():
            return str(manuscript_dir / cand), title, doi, bib_entry

    # 2. Search PDF search directories
    search_dirs: list[Path] = []
    if pdf_dir and pdf_dir.is_dir():
        search_dirs.append(pdf_dir)
    if manuscript_dir and manuscript_dir.is_dir():
        search_dirs.append(manuscript_dir)
        if (manuscript_dir / "pdfs").is_dir():
            search_dirs.append(manuscript_dir / "pdfs")
        if (manuscript_dir / "papers").is_dir():
            search_dirs.append(manuscript_dir / "papers")

    # Include default cache root (~/.paper-agent/cache)
    cache_root = DEFAULT_CACHE_ROOT
    if cache_root.is_dir():
        search_dirs.append(cache_root)

    for s_dir in search_dirs:
        # Check by key.pdf
        cand1 = s_dir / f"{cite_key}.pdf"
        if cand1.is_file():
            return str(cand1), title, doi, bib_entry
        cand2 = s_dir / f"{clean_key}.pdf"
        if cand2.is_file():
            return str(cand2), title, doi, bib_entry
        # Check by doi slug
        if doi:
            slug = _doi_slug(doi)
            cand3 = s_dir / f"{slug}.pdf"
            if cand3.is_file():
                return str(cand3), title, doi, bib_entry

    # If PDF is not found, but we have bib_entry with abstract, we return None for PDF path
    # but bib_entry is preserved
    return None, title, doi, bib_entry


# ==============================================================================
# PDF & Evidence Text Extraction
# ==============================================================================

def extract_passages_from_pdf(pdf_path: str, chunk_chars: int = 400) -> list[Tuple[int, str]]:
    """Extract page-aware textual passages from a local PDF using PyMuPDF."""
    p = Path(pdf_path)
    if not p.is_file():
        return []

    try:
        import fitz  # PyMuPDF
    except ImportError:
        # Fallback to pure text reading if text file masquerades or fitz unavailable
        try:
            raw = p.read_text(encoding="utf-8", errors="ignore")
            return [(1, raw[i:i+chunk_chars]) for i in range(0, len(raw), chunk_chars)]
        except Exception:
            return []

    passages: list[Tuple[int, str]] = []
    try:
        doc = fitz.open(str(p))
        for page_num, page in enumerate(doc, start=1):
            txt = page.get_text("text")
            if not txt.strip():
                continue
            # Break page text into paragraphs / sentence chunks
            paras = [pr.strip().replace("\n", " ") for pr in txt.split("\n\n") if pr.strip()]
            for para in paras:
                if len(para) < 20:
                    continue
                if len(para) > chunk_chars * 2:
                    # Break long paragraphs into chunks
                    for c_start in range(0, len(para), chunk_chars):
                        c_end = min(len(para), c_start + chunk_chars)
                        passages.append((page_num, para[c_start:c_end]))
                else:
                    passages.append((page_num, para))
        doc.close()
    except Exception as e:
        log.warning(f"Error reading PDF {pdf_path}: {e}")

    return passages


# ==============================================================================
# Offline Evidence Alignment & Fidelity Scoring
# ==============================================================================

def tokenize_claim(claim: str) -> list[str]:
    """Tokenize claim into lowercased content keywords excluding stopwords."""
    words = re.findall(r"[a-zA-Z\u4e00-\u9fa5]{2,}", claim.lower())
    return [w for w in words if w not in STOPWORDS]


def find_best_evidence_passage(
    claim_sentence: str,
    passages: list[Tuple[int, str]],
    source_origin: str = "",
) -> Optional[EvidencePassage]:
    """Find candidate evidence passage maximizing lexical and semantic overlap with claim."""
    claim_tokens = tokenize_claim(claim_sentence)
    if not claim_tokens or not passages:
        return None

    claim_set = set(claim_tokens)
    scored: list[Tuple[float, int, str]] = []

    for page_num, text in passages:
        p_tokens = tokenize_claim(text)
        if not p_tokens:
            continue
        p_set = set(p_tokens)
        overlap = claim_set & p_set
        if not overlap:
            continue

        # Recall of claim keywords in passage
        recall = len(overlap) / len(claim_set)
        # Jaccard overlap
        jaccard = len(overlap) / len(claim_set | p_set)
        # Term frequency bonus
        tf = sum(p_tokens.count(w) for w in overlap)
        score = 0.6 * recall + 0.3 * jaccard + 0.1 * min(1.0, tf / max(1, len(claim_tokens)))

        scored.append((score, page_num, text))

    if not scored:
        # If no positive overlap, pick the first passage if available
        first_page, first_text = passages[0]
        return EvidencePassage(
            text=first_text[:300],
            page=first_page,
            lexical_score=0.0,
            detected_direction=detect_claim_direction(first_text),
            source_origin=source_origin,
        )

    scored.sort(key=lambda x: -x[0])
    best_score, best_page, best_text = scored[0]

    return EvidencePassage(
        text=best_text,
        page=best_page,
        lexical_score=best_score,
        detected_direction=detect_claim_direction(best_text),
        source_origin=source_origin,
    )


def compute_fidelity_score(
    claim_sentence: str,
    claim_dir: str,
    claim_nums: list[str],
    evidence: Optional[EvidencePassage],
    full_source_text: str = "",
) -> Tuple[float, str, list[str], str]:
    """Evaluate Evidence Fidelity Score (EFS) and assign categorical verdict.

    Returns:
        (fidelity_score, verdict, flags, explanation)
    """
    if evidence is None:
        return 0.0, "HALLUCINATED_CITATION", ["UNGROUNDED_REFERENCE"], "Source material could not be located."

    flags: list[str] = []
    base_lexical = min(1.0, evidence.lexical_score)

    # 1. Directional alignment
    dir_bonus = 0.0
    evid_dir = evidence.detected_direction
    if claim_dir != "unspecified" and evid_dir != "unspecified":
        if claim_dir == evid_dir:
            dir_bonus = 0.15
            flags.append("DIRECTION_CONFIRMED")
        else:
            # Polarity inversion or null conflict
            if (claim_dir == "positive" and evid_dir == "negative") or \
               (claim_dir == "negative" and evid_dir == "positive"):
                dir_bonus = -0.50
                flags.append("OPPOSITE_DIRECTION")
            elif evid_dir == "neutral" and claim_dir in ("positive", "negative"):
                dir_bonus = -0.45
                flags.append("CONTRADICTORY_NULL")

    # 2. Numerical claim verification
    num_bonus = 0.0
    if claim_nums:
        # Check if numbers appear in best evidence or full text
        found_in_evidence = [n for n in claim_nums if n.lower() in evidence.text.lower()]
        found_in_full = [n for n in claim_nums if n.lower() in full_source_text.lower()]

        if len(found_in_evidence) == len(claim_nums):
            num_bonus = 0.15
            flags.append("NUMERICAL_CONFIRMED")
        elif len(found_in_full) == len(claim_nums):
            num_bonus = 0.10
            flags.append("NUMERICAL_CONFIRMED_IN_FULLTEXT")
        else:
            num_bonus = -0.30
            missing_nums = [n for n in claim_nums if n.lower() not in full_source_text.lower()]
            flags.append(f"NUMERICAL_DISCREPANCY:missing({','.join(missing_nums)})")

    # 3. Domain mismatch check
    if base_lexical < 0.15:
        flags.append("DOMAIN_MISMATCH")

    # 4. Synthesize final fidelity score (clamped to [0.0, 1.0])
    raw_score = base_lexical + dir_bonus + num_bonus
    efs = max(0.0, min(1.0, raw_score))

    # 5. Verdict determination
    if "OPPOSITE_DIRECTION" in flags or "CONTRADICTORY_NULL" in flags:
        verdict = "MISATTRIBUTION"
        explanation = (
            f"Assertion claims {claim_dir} outcome, but source paper explicitly reports "
            f"{evid_dir} finding."
        )
    elif any("NUMERICAL_DISCREPANCY" in fl for fl in flags) and efs < 0.60:
        verdict = "NUMERICAL_DISCREPANCY"
        explanation = "Specific numerical estimates claimed in draft are not supported in source document."
    elif "DOMAIN_MISMATCH" in flags:
        verdict = "MISATTRIBUTION"
        explanation = "Extremely low topical relevance between draft assertion and cited paper."
    elif efs >= 0.70:
        verdict = "VERIFIED_FAITHFUL"
        explanation = "High semantic overlap and consistent direction with cited source."
    elif efs >= 0.40:
        verdict = "PARTIALLY_SUPPORTED"
        explanation = "Relevant context located, but nuances, hedges, or specific qualifiers differ."
    else:
        verdict = "MISATTRIBUTION"
        explanation = "Insufficient evidence in cited source to support the specific claim."

    return efs, verdict, flags, explanation


# ==============================================================================
# Manuscript Auditor Orchestrator
# ==============================================================================

def audit_manuscript(
    manuscript_text: str,
    bib_path: Optional[str | Path] = None,
    pdf_dir: Optional[str | Path] = None,
    threshold: float = 0.60,
    manuscript_path: Optional[str | Path] = None,
) -> AuditReport:
    """Audit full manuscript draft for citation fidelity and hallucinations."""
    m_path = Path(manuscript_path) if manuscript_path else None
    manuscript_name = m_path.name if m_path else "draft_manuscript"
    manuscript_dir = m_path.parent if m_path else Path.cwd()

    # Auto-discover bibtex if not explicitly passed
    if not bib_path and manuscript_dir:
        cand_bibs = list(manuscript_dir.glob("*.bib"))
        if cand_bibs:
            bib_path = cand_bibs[0]

    bib_db = load_bibliography_db(bib_path)
    pdf_dir_p = Path(pdf_dir) if pdf_dir else None

    # Extract sentences and citation markers
    sentences = split_sentences_academic(manuscript_text)
    markers = extract_citation_markers(manuscript_text)

    # Map markers to sentences by character span
    audit_items: list[AuditItem] = []

    for marker in markers:
        # Find enclosing sentence
        enclosing_sentence = ""
        for s_text, s_start, s_end in sentences:
            if s_start <= marker.char_start and marker.char_end <= s_end:
                enclosing_sentence = s_text
                break
            # Fallback if marker spans boundary slightly
            if marker.char_start >= s_start and marker.char_start <= s_end:
                enclosing_sentence = s_text
                break

        if not enclosing_sentence:
            # Fallback to line text
            lines = manuscript_text.splitlines()
            if 1 <= marker.line_number <= len(lines):
                enclosing_sentence = lines[marker.line_number - 1].strip()
            else:
                enclosing_sentence = marker.raw_text

        claim_dir = detect_claim_direction(enclosing_sentence)
        claim_nums = extract_numbers_from_claim(enclosing_sentence)

        # Resolve source document
        pdf_path, title, doi, bib_entry = resolve_source_document(
            marker.key,
            bib_db=bib_db,
            pdf_dir=pdf_dir_p,
            manuscript_dir=manuscript_dir,
        )

        evidence: Optional[EvidencePassage] = None
        full_source_text = ""

        if pdf_path:
            passages = extract_passages_from_pdf(pdf_path)
            full_source_text = " ".join(p[1] for p in passages)
            evidence = find_best_evidence_passage(
                enclosing_sentence, passages, source_origin=pdf_path
            )
        elif bib_entry and bib_entry.get("abstract"):
            # Fall back to BibTeX abstract
            abstract = bib_entry["abstract"]
            full_source_text = abstract
            passages = [(0, s[0]) for s in split_sentences_academic(abstract)]
            evidence = find_best_evidence_passage(
                enclosing_sentence, passages, source_origin="bibtex_abstract"
            )

        if not pdf_path and not bib_entry:
            # Complete ungrounded / hallucinated citation
            efs = 0.0
            verdict = "HALLUCINATED_CITATION"
            flags = ["UNGROUNDED_REFERENCE"]
            explanation = (
                f"Citation key '{marker.key}' was not found in bibliography or local PDF cache. "
                f"Suspected hallucinated reference."
            )
        else:
            efs, verdict, flags, explanation = compute_fidelity_score(
                claim_sentence=enclosing_sentence,
                claim_dir=claim_dir,
                claim_nums=claim_nums,
                evidence=evidence,
                full_source_text=full_source_text,
            )

        audit_items.append(
            AuditItem(
                citation_key=marker.key,
                marker_type=marker.marker_type,
                line_number=marker.line_number,
                claim_sentence=enclosing_sentence,
                claim_direction=claim_dir,
                claim_numbers=claim_nums,
                resolved_source=pdf_path or ("bibtex:" + marker.key if bib_entry else None),
                source_title=title,
                source_doi=doi,
                evidence_passage=evidence,
                fidelity_score=efs,
                verdict=verdict,
                flags=flags,
                explanation=explanation,
            )
        )

    # Compute aggregate summary statistics
    total_citations = len(audit_items)
    verified = sum(1 for it in audit_items if it.verdict == "VERIFIED_FAITHFUL")
    partially = sum(1 for it in audit_items if it.verdict == "PARTIALLY_SUPPORTED")
    misattributions = sum(1 for it in audit_items if it.verdict == "MISATTRIBUTION")
    hallucinated = sum(1 for it in audit_items if it.verdict == "HALLUCINATED_CITATION")
    numerical = sum(1 for it in audit_items if it.verdict == "NUMERICAL_DISCREPANCY")

    avg_efs = (
        sum(it.fidelity_score for it in audit_items) / total_citations
        if total_citations > 0
        else 1.0
    )

    pass_status = (avg_efs >= threshold) and (hallucinated == 0) and (misattributions == 0)

    return AuditReport(
        manuscript_name=manuscript_name,
        total_sentences=len(sentences),
        total_citations=total_citations,
        verified_count=verified,
        partially_supported_count=partially,
        misattribution_count=misattributions,
        hallucinated_count=hallucinated,
        numerical_discrepancy_count=numerical,
        overall_fidelity_score=avg_efs,
        pass_status=pass_status,
        threshold=threshold,
        items=audit_items,
    )


# ==============================================================================
# Report Formatters (Terminal Table, Markdown, JSON)
# ==============================================================================

def format_audit_table(report: AuditReport) -> str:
    """Format audit results as a clean, Windows-safe ASCII table."""
    lines: list[str] = []
    lines.append("=" * 86)
    lines.append(f"  PAPER AGENT MANUSCRIPT CITATION FIDELITY AUDIT [P2-21]")
    lines.append("=" * 86)
    lines.append(f"Target Manuscript:       {report.manuscript_name}")
    lines.append(f"Total Sentences:         {report.total_sentences}")
    lines.append(f"Total Citations Audited: {report.total_citations}")
    lines.append(
        f"Verified Faithful:       {report.verified_count} "
        f"({report.verified_count / max(1, report.total_citations):.1%})"
    )
    lines.append(
        f"Partially Supported:     {report.partially_supported_count} "
        f"({report.partially_supported_count / max(1, report.total_citations):.1%})"
    )
    lines.append(
        f"Misattributions:         {report.misattribution_count} "
        f"({report.misattribution_count / max(1, report.total_citations):.1%})"
    )
    lines.append(
        f"Hallucinated / Missing:  {report.hallucinated_count} "
        f"({report.hallucinated_count / max(1, report.total_citations):.1%})"
    )
    lines.append(f"Numerical Discrepancies: {report.numerical_discrepancy_count}")
    lines.append(f"Average Fidelity (EFS):  {report.overall_fidelity_score:.1%}")
    status_str = "PASS [OK]" if report.pass_status else "FAIL [REVIEW REQUIRED]"
    lines.append(f"Audit Status (>= {report.threshold:.0%}):   {status_str}")
    lines.append("-" * 86)

    if not report.items:
        lines.append("No citations detected in target manuscript.")
        lines.append("=" * 86)
        return "\n".join(lines)

    lines.append(
        f"{'Line':<5} | {'Citation Key':<18} | {'EFS':<6} | {'Verdict':<21} | {'Issue Flags / Context'}"
    )
    lines.append("-" * 86)

    for item in report.items:
        flags_str = ", ".join(item.flags) if item.flags else "OK"
        if len(flags_str) > 30:
            flags_str = flags_str[:27] + "..."

        verdict_display = item.verdict
        if item.verdict == "VERIFIED_FAITHFUL":
            verdict_display = "[OK] FAITHFUL"
        elif item.verdict == "PARTIALLY_SUPPORTED":
            verdict_display = "[WARN] PARTIAL"
        elif item.verdict == "MISATTRIBUTION":
            verdict_display = "[FAIL] MISATTRIB"
        elif item.verdict == "HALLUCINATED_CITATION":
            verdict_display = "[FAIL] HALLUCINATED"
        elif item.verdict == "NUMERICAL_DISCREPANCY":
            verdict_display = "[FAIL] NUM_ERROR"

        lines.append(
            f"{item.line_number:<5} | {item.citation_key[:18]:<18} | {item.fidelity_score:>5.1%} | "
            f"{verdict_display:<21} | {flags_str}"
        )

        # Print indented explanation if flagged
        if item.verdict != "VERIFIED_FAITHFUL":
            lines.append(f"      \\-- Explanation: {item.explanation}")
            if item.evidence_passage and item.evidence_passage.text:
                evid_snip = item.evidence_passage.text[:90].replace("\n", " ")
                lines.append(f"      \\-- Source Evidence (p.{item.evidence_passage.page}): \"{evid_snip}...\"")

    lines.append("=" * 86)
    return "\n".join(lines)


def format_audit_markdown(report: AuditReport) -> str:
    """Format audit results as a publication-ready Markdown report."""
    lines: list[str] = [
        "# Manuscript Citation Fidelity & Hallucination Audit Report\n",
        f"- **Target Manuscript**: `{report.manuscript_name}`",
        f"- **Total Sentences Analyzed**: {report.total_sentences}",
        f"- **Total Citations Checked**: {report.total_citations}",
        f"- **Average Evidence Fidelity Score (EFS)**: **{report.overall_fidelity_score:.1%}**",
        f"- **Audit Outcome**: **{'PASS' if report.pass_status else 'FAIL (Issues Detected)'}** (Threshold: {report.threshold:.0%})\n",
        "### Audit Metric Summary\n",
        "| Category | Count | Proportion | Evaluation |",
        "|---|---|---|---|",
        f"| **Verified Faithful** | {report.verified_count} | {report.verified_count / max(1, report.total_citations):.1%} | Supported by local evidence |",
        f"| **Partially Supported** | {report.partially_supported_count} | {report.partially_supported_count / max(1, report.total_citations):.1%} | Context present but nuanced/hedged |",
        f"| **Misattributions** | {report.misattribution_count} | {report.misattribution_count / max(1, report.total_citations):.1%} | Direction conflict or topic divergence |",
        f"| **Hallucinated / Missing** | {report.hallucinated_count} | {report.hallucinated_count / max(1, report.total_citations):.1%} | Reference absent from local cache/bib |",
        f"| **Numerical Discrepancies** | {report.numerical_discrepancy_count} | - | Cited metrics missing from source |\n",
        "### Detailed Citation Audit Log\n",
        "| Line | Citation Key | EFS | Verdict | Claim Assertion | Explanation & Evidence |",
        "|---|---|---|---|---|---|",
    ]

    for item in report.items:
        clean_claim = item.claim_sentence.replace("|", "\\|").replace("\n", " ")[:120]
        evid_note = item.explanation
        if item.evidence_passage and item.evidence_passage.text:
            p_text = item.evidence_passage.text.replace("|", "\\|").replace("\n", " ")[:140]
            evid_note += f"<br><sub>*Evidence (p.{item.evidence_passage.page})*: \"{p_text}...\"</sub>"

        lines.append(
            f"| {item.line_number} | `{item.citation_key}` | {item.fidelity_score:.1%} | "
            f"**{item.verdict}** | {clean_claim} | {evid_note} |"
        )

    lines.append("\n### Recommendations for Manuscript Revision\n")
    flagged = [it for it in report.items if it.verdict != "VERIFIED_FAITHFUL"]
    if not flagged:
        lines.append("- All draft citations are faithfully grounded in local academic literature. Ready for compilation.")
    else:
        for idx, it in enumerate(flagged, start=1):
            lines.append(f"{idx}. **Line {it.line_number} (`{it.citation_key}`)**: {it.verdict}")
            lines.append(f"   - **Claim**: \"{it.claim_sentence}\"")
            lines.append(f"   - **Auditor Note**: {it.explanation}")
            if "OPPOSITE_DIRECTION" in it.flags:
                lines.append("   - **Action**: Correct direction of assertion or replace citation with supporting paper.")
            elif "UNGROUNDED_REFERENCE" in it.flags:
                lines.append("   - **Action**: Verify citation key spelling or ensure `.bib` / PDF exists in cache.")
            elif any("NUMERICAL_DISCREPANCY" in fl for fl in it.flags):
                lines.append("   - **Action**: Cross-check numerical statistics against source estimation tables.")

    return "\n".join(lines)


def format_audit_json(report: AuditReport) -> str:
    """Format audit results as a machine-readable JSON string."""
    return json.dumps(report.to_dict(), indent=2, ensure_ascii=False)
