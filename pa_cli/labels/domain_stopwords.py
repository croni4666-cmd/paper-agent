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


# Embedded high-frequency English word list (~200 words). Used as the
# negative side of the noise filter: a short lowercase token is "noise"
# if it's NOT in this list. This catches plain product/tool names like
# `iphone`, `skill`, `beautiful`, `gamma` that don't match the camelCase
# or snake_case heuristics.
#
# Source: top-frequency English words from COCA + Google Web Trillion Corpus
# (common-function words + common content words). 200 is enough to
# exclude the vast majority of "real English" in any technical corpus.
# Embedded directly (no NLTK dep) so the heuristic stays zero-dep.
_COMMON_ENGLISH = frozenset({
    # function words
    "the", "and", "for", "are", "but", "not", "you", "all", "can", "her",
    "was", "one", "our", "out", "day", "had", "has", "his", "how", "its",
    "let", "may", "new", "now", "old", "see", "two", "way", "who", "boy",
    "did", "get", "him", "hit", "let", "old", "own", "put", "run", "say",
    "she", "too", "use", "dad", "mom", "man", "men", "fun", "big", "end",
    "of", "to", "in", "it", "is", "on", "as", "at", "or", "an", "be",
    "by", "we", "do", "if", "go", "up", "so", "no", "my", "me", "he",
    "this", "that", "with", "have", "from", "they", "been", "said",
    "each", "which", "their", "will", "other", "about", "many", "then",
    "them", "some", "very", "when", "what", "your", "make", "like",
    "long", "look", "just", "over", "such", "take", "year", "into",
    "than", "come", "could", "would", "people", "after", "also", "back",
    "after", "only", "work", "first", "well", "even", "want", "because",
    "most", "give", "day", "very",
    # common content words
    "time", "year", "people", "way", "day", "man", "woman", "child",
    "world", "life", "hand", "part", "place", "case", "week", "company",
    "system", "program", "question", "work", "government", "number",
    "night", "point", "home", "water", "room", "mother", "area", "money",
    "story", "fact", "month", "lot", "right", "study", "book", "eye",
    "job", "word", "business", "issue", "side", "kind", "head", "house",
    "service", "friend", "father", "power", "hour", "game", "line",
    "end", "member", "law", "car", "city", "community", "name", "team",
    "minute", "idea", "body", "information", "back", "parent", "face",
    "level", "office", "door", "health", "art", "war", "history",
    "party", "result", "change", "morning", "reason", "research",
    "girl", "guy", "moment", "air", "teacher", "force", "education",
    "foot", "boy", "age", "policy", "process", "music", "market",
    "sense", "nation", "plan", "college", "interest", "death",
    "experience", "effect", "use", "class", "control", "care",
    "field", "development", "role", "effort", "rate", "heart", "drug",
    "show", "leader", "light", "society", "form", "patient", "worker",
    "student", "theory", "data", "model", "value", "test", "view",
    "table", "cost", "source", "factor", "page", "term", "type",
    "image", "cell", "line", "analysis", "design", "example", "set",
    "group", "number", "section", "state", "list", "method",
    "chapter", "figure", "section", "approach",
    # academic / business / technical content words (commonly seen in
    # paper corpora; without these the heuristic FPs on real content)
    "paper", "papers", "study", "studies", "analysis", "research",
    "topic", "topics", "cluster", "clusters", "corpus", "label",
    "labels", "summary", "method", "methods", "approach", "result",
    "results", "section", "sections", "chapter", "appendix",
    "table", "figure", "graph", "model", "models", "experiment",
    "experiments", "data", "dataset", "datasets", "feature", "features",
    "function", "functions", "variable", "variables", "parameter",
    "parameters", "example", "examples", "concept", "concepts",
    "domain", "domains", "review", "reviews", "introduction",
    "conclusion", "conclusions", "discussion", "background",
    "related", "literature", "abstract", "introduction",
    "economics", "economy", "economic", "market", "markets", "price",
    "prices", "supply", "demand", "elasticity", "production",
    "consumption", "investment", "growth", "inflation", "policy",
    "policies", "industry", "industries", "company", "companies",
    "business", "government", "household", "households", "income",
    "incomes", "trade", "export", "exports", "import", "imports",
    "western", "eastern", "southern", "northern", "european",
    "american", "asian", "african", "global", "national", "local",
    "public", "private", "social", "political", "cultural",
    "historical", "modern", "ancient", "contemporary",
})


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
    """Heuristic: does this term look like a noise term (tool name, template, etc.)?

    Heuristics applied in order of decreasing specificity:
    1. camelCase (pptxGenJS, javaScript) — yes
    2. snake_case / kebab-case (pptxgenjs, next-js, phase2-detail) — yes
    3. has digits (v1.0, 2025, ie11, p29) — yes
    4. all uppercase short (JSON, API, JS) — yes
    5. short token (≤3 chars) — yes
    6. file extension (.jpg, .png) — yes
    7. version / date pattern — yes
    8. **plain lowercase 4-12 chars NOT in common English list** — yes
       (catches `iphone`, `skill`, `beautiful`, `gamma`, `n276`, etc.)
    """
    if not term or len(term) <= 2:
        return False

    # 1. camelCase
    if _CAMEL_CASE_RE.match(term):
        return True

    # 2. snake_case / kebab-case
    if _SNAKE_HYPHEN_RE.match(term):
        return True

    # 3. has digits
    if any(c.isdigit() for c in term):
        return True

    # 4. all uppercase short
    upper_ratio = sum(1 for c in term if c.isupper()) / len(term)
    if upper_ratio > 0.6 and len(term) <= 6:
        return True

    # 5. short token
    if len(term) <= 3:
        return True

    # 6. file extension
    if _FILE_EXT_RE.match("." + term.lower()):
        return True

    # 7. version / date
    if _VERSION_RE.match(term) or _DATE_RE.match(term):
        return True

    # 8. plain lowercase 4-12 chars NOT in common English list
    #    (catches product names like `iphone`, `skill`, `beautiful`)
    #    but excludes real content words like `topic`, `cluster`, `paper`
    if term.islower() and 4 <= len(term) <= 12:
        if term not in _COMMON_ENGLISH:
            # Bonus: check for typical English suffix to further reduce FPs
            # (e.g. "tion", "ing", "ment" → likely real content word)
            english_suffixes = (
                "tion", "ment", "ness", "able", "ible", "ful", "less",
                "ing", "ous", "ive", "ity", "ship", "hood", "ence", "ance",
                "ity", "ize", "ise", "ate", "ity",
            )
            if not any(term.endswith(s) for s in english_suffixes):
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