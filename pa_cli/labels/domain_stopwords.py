"""pa_cli.labels.domain_stopwords — Auto-extract corpus-specific noise terms.

When BERTopic / c-TF-IDF runs on a small or domain-specific corpus, certain
terms become high-IDF but low-information:
- Tool/library names (e.g. "pptxgenjs", "iphone")
- File extensions (e.g. "jpg", "png")
- Template names (e.g. "beautiful", "skill")
- URLs / paths

These terms dominate topic labels and obscure the actual content. The fix is
to add them to the stopwords list.

This module provides:
- `extract_domain_stopwords(papers, top_n=20, ...)` — auto-mine from corpus
- `save_domain_stopwords(words, path)` — write to disk for review
- `load_domain_stopwords_file(path)` — load user-edited list

The auto-extraction uses heuristics:
- Top-N highest-IDF terms from c-TF-IDF
- Filter: short (≤3 chars), all-caps, contains digits, paths
- Keep: tool-name-looking terms (camelCase, lowercase with hyphens)
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Set


# Heuristic patterns for "noise" terms we want to detect
_PATH_RE = re.compile(r"[\\/]")
_FILE_EXT_RE = re.compile(r"\.(jpg|jpeg|png|gif|pdf|docx?|xlsx?|pptx?|md|txt|json|csv|tsv|html?|xml)$", re.IGNORECASE)
_URL_RE = re.compile(r"^https?://|^www\.", re.IGNORECASE)
_VERSION_RE = re.compile(r"^v?\d+(\.\d+)*$")  # e.g. "v1.0", "1.2.3"
_DATE_RE = re.compile(r"^\d{4}([-_]\d{2}){0,2}$")  # e.g. "2025", "2025-07"
_CAMEL_CASE_RE = re.compile(r"^[a-z]+([A-Z][a-z]+)+$")  # e.g. "pptxGenJS"
_SNAKE_HYPHEN_RE = re.compile(r"^[a-z]+([_-][a-z0-9]+)+$")  # e.g. "pptxgenjs", "next-js"


def extract_domain_stopwords(
    papers: List[dict],
    top_n: int = 20,
    min_df: int = 1,
    custom_blacklist: Set[str] = None,
) -> List[str]:
    """Auto-extract corpus-specific noise terms.

    Strategy:
    1. Concatenate all paper text into a single corpus
    2. Run TF-IDF (or simple frequency) to find high-scoring terms
    3. Apply heuristics to keep "noise-looking" terms (tool names, etc.)

    Args:
        papers: List of {filename, title, text, ...} dicts.
        top_n: Return at most this many terms.
        min_df: Minimum document frequency (terms must appear in ≥min_df docs).
        custom_blacklist: User-supplied terms to always include.

    Returns:
        Sorted list of extracted domain stopwords.
    """
    custom_blacklist = custom_blacklist or set()

    # 1. Aggregate text from all papers
    all_texts = []
    for p in papers:
        title = (p.get("title") or "").strip()
        text = (p.get("text") or "").strip()
        combined = f"{title} {title} {text}".strip()  # title weighted 2x
        if combined:
            all_texts.append(combined)

    if not all_texts:
        return sorted(custom_blacklist)

    # 2. Compute TF-IDF
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer

        # Restrict token pattern to alphanumeric (no punctuation noise)
        vec = TfidfVectorizer(
            token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z0-9_-]+\b",
            lowercase=True,
            stop_words="english",
            min_df=min_df,
            max_df=0.95,
            ngram_range=(1, 1),
        )
        try:
            mat = vec.fit_transform(all_texts)
        except ValueError:
            return sorted(custom_blacklist)

        # Sum TF-IDF scores across documents for each term
        import numpy as np

        scores = np.asarray(mat.sum(axis=0)).flatten()
        terms = vec.get_feature_names_out()
        # Pair (term, score), sort by score desc
        term_scores = sorted(zip(terms, scores), key=lambda x: -x[1])
    except ImportError:
        # sklearn not available — fall back to plain word frequency
        term_scores = _fallback_frequency(all_texts, min_df=min_df)

    # 3. Apply heuristics to keep "noise-looking" terms
    candidates = []
    for term, _score in term_scores:
        if _looks_like_noise(term):
            candidates.append(term)
        if len(candidates) >= top_n:
            break

    # Always include custom blacklist
    result = sorted(set(candidates) | custom_blacklist)
    return result


def _looks_like_noise(term: str) -> bool:
    """Heuristic: does this term look like a noise term (tool name, template, etc.)?"""
    if not term or len(term) <= 2:
        return False

    # Skip if it's all-lowercase AND a real English word we want to keep.
    # Heuristic: keep if it ends in common English suffixes (heuristic, not exhaustive)
    english_suffixes = ("tion", "ment", "ness", "able", "ible", "ful", "less",
                       "ing", "ous", "ive", "ity", "ship", "hood", "ence", "ance")
    if term.islower() and any(term.endswith(s) for s in english_suffixes) and len(term) > 6:
        return False

    # Camel case (e.g. pptxGenJS, javaScript) — keep
    if _CAMEL_CASE_RE.match(term):
        return True

    # snake_case or kebab-case (e.g. pptxgenjs, next-js) — keep
    if _SNAKE_HYPHEN_RE.match(term):
        return True

    # Has digits (e.g. "v1.0", "2025", "ie11") — likely noise
    if any(c.isdigit() for c in term):
        return True

    # All uppercase or mostly uppercase (e.g. "JSON", "API", "JS")
    upper_ratio = sum(1 for c in term if c.isupper()) / len(term)
    if upper_ratio > 0.6 and len(term) <= 6:
        return True

    # Short tokens (3-4 chars) that aren't common words — likely noise
    if len(term) <= 3:
        return True

    # Looks like file extension (3-4 chars, all alpha)
    if _FILE_EXT_RE.match("." + term.lower()):
        return True

    # Looks like path / URL
    if _PATH_RE.search(term) or _URL_RE.match(term):
        return True

    # Looks like version
    if _VERSION_RE.match(term) or _DATE_RE.match(term):
        return True

    return False


def _fallback_frequency(all_texts: List[str], min_df: int = 1) -> List:
    """Simple word frequency fallback when sklearn not available."""
    from collections import Counter

    counter = Counter()
    for text in all_texts:
        words = set(re.findall(r"\b[a-zA-Z][a-zA-Z0-9_-]+\b", text.lower()))
        counter.update(words)

    # Return top by frequency (not by IDF, but close enough for fallback)
    return [(term, count) for term, count in counter.most_common(100) if count >= min_df]


def save_domain_stopwords(words: List[str], path: Path) -> Path:
    """Save domain stopwords list to a text file (one per line).

    The format is plain UTF-8 text — easy to review/edit by hand:
        # Lines starting with # are comments
        # Domain stopwords for ch1-econ-ppt corpus
        iphone
        pptxgenjs
        skill
        beautiful
        jpg
        ...
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        f.write("# Domain stopwords\n")
        f.write("# One term per line; lines starting with # are comments.\n")
        f.write("# Auto-extracted by pa_cli.labels.extract_domain_stopwords\n")
        f.write(f"# Total: {len(words)} terms\n\n")
        for w in words:
            if w and not w.startswith("#"):
                f.write(w + "\n")

    return path


def load_domain_stopwords_file(path: Path) -> List[str]:
    """Load domain stopwords from a text file.

    Skips empty lines and lines starting with #. Returns lowercase terms.
    """
    if not path or not Path(path).exists():
        return []

    words = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            words.append(line.lower())

    return words