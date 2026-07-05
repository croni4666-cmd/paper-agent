"""pa_cli.topics — Cross-paper topic clustering for lit-review synthesis.

[ P1-4 ] (ROADMAP.md): pa review-topics <corpus_dir>

Strategy: BERTopic (sentence-transformers embeddings + UMAP + HDBSCAN +
c-TF-IDF) as primary, with the hand-rolled TF-IDF + Jaccard + Agglomerative
fallback if BERTopic is not installed or fails on the corpus (e.g. text too
short, hdbscan min_samples > n_papers).

Output: topics.json — clusters of papers with auto-generated labels
(top TF-IDF keywords + top OpenAlex concepts).

Design notes (2026-07-04):
  - This module does NOT call any LLM. Mavis session (user) reads the
    topics.json + relations.json + per-paper facts and writes the
    narrative synthesis themselves. Keeps paper-agent zero-LLM.
  - Wraps the bertopic library (verified installed 0.17.4 via clash proxy
    2026-07-04; 5 deps: bertopic + hdbscan + umap-learn + sentence-
    transformers + torch, ~880MB total). Falls back to my hand-roll
    (sklearn only) if any import fails.
  - For small corpora (n<5), BERTopic's default hdbscan min_samples=5
    is invalid; we set min_cluster_size=2 + min_samples=1.

Edge cases handled:
  - n=0 corpus → empty topics.json with warning
  - n=1 paper → single topic, label = paper title
  - n<5 papers → fall back to hand-roll (BERTopic degenerate on tiny)
  - All papers lack DOIs → still works via abstract text alone
  - sentence-transformers first run downloads ~80MB model; cached after
  - BERTopic fails (OOM / numerical issue) → fall back to hand-roll
"""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from .review import build_corpus_index, extract_text

log = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Optional BERTopic import (lazy — actual import only on first use, NOT on
# pa_cli.topics import, to keep pa_cli module load fast ~1s instead of ~30s
# due to torch + transformers initialization).
# -----------------------------------------------------------------------------

_BERTOPIC_AVAILABLE = None  # None = not yet probed
_BERTOPIC_IMPORT_ERROR: Optional[str] = None


def _ensure_bertopic():
    """Lazy-load BERTopic + dependencies. Idempotent."""
    global _BERTOPIC_AVAILABLE, _BERTOPIC_IMPORT_ERROR
    if _BERTOPIC_AVAILABLE is not None:
        return _BERTOPIC_AVAILABLE
    try:
        global BERTopic, HDBSCAN, UMAP, SentenceTransformer
        from bertopic import BERTopic as _B
        from hdbscan import HDBSCAN as _H
        from umap import UMAP as _U
        from sentence_transformers import SentenceTransformer as _S
        BERTopic, HDBSCAN, UMAP, SentenceTransformer = _B, _H, _U, _S
        _BERTOPIC_AVAILABLE = True
    except ImportError as e:
        _BERTOPIC_IMPORT_ERROR = str(e)
        _BERTOPIC_AVAILABLE = False
        log.info(f"BERTopic not available, will use hand-rolled fallback: {e}")
    return _BERTOPIC_AVAILABLE


# -----------------------------------------------------------------------------
# Stage 1: Per-paper concept vectors (OpenAlex) — same as hand-roll
# -----------------------------------------------------------------------------

def _extract_doi(text: str, filename: str) -> str:
    """Best-effort DOI extraction."""
    m = re.search(r'10\.\d{4,9}/[^\s"]+', filename)
    if m:
        return m.group(0).rstrip("._-")
    if text:
        m2 = re.search(r'(10\.\d{4,9}/[^\s,;]+)', text[:5000])
        if m2:
            return m2.group(1).rstrip(".,;)")
    return ""


def _fetch_concepts_for_doi(doi: str) -> Optional[Dict]:
    """Fetch OpenAlex work by DOI; return {doi, title, concepts: [{id,name}]} or None."""
    if not doi:
        return None
    try:
        from .citations import get_work_by_doi
        from .search import _normalize_openalex
    except ImportError:
        return None
    raw = get_work_by_doi(doi)
    if not raw:
        return None
    norm = _normalize_openalex(raw)
    concepts_raw = raw.get("concepts") or []
    concepts = []
    for c in concepts_raw:
        cid_full = c.get("id", "")
        cid = cid_full.replace("https://openalex.org/", "") if cid_full else ""
        score = c.get("score", 0) or 0
        concepts.append({
            "concept_id": cid,
            "name": c.get("display_name", ""),
            "score": float(score),
        })
    concepts.sort(key=lambda x: x["score"], reverse=True)
    concepts = concepts[:20]
    return {
        "doi": norm.get("doi", doi),
        "title": norm.get("title", ""),
        "year": norm.get("year"),
        "venue": norm.get("venue", ""),
        "cited_by_count": norm.get("cited_by_count", 0),
        "concepts": concepts,
        "openalex_url": raw.get("id", ""),
    }


def _build_concept_index(papers: List[Dict]) -> Tuple[Dict[str, Dict], List[str]]:
    """Per-paper OpenAlex concept fetch."""
    concept_data: Dict[str, Dict] = {}
    failed: List[str] = []
    for p in papers:
        filename = p["filename"]
        doi = p.get("doi") or _extract_doi(p.get("text", ""), filename)
        if not doi:
            failed.append(filename)
            continue
        data = _fetch_concepts_for_doi(doi)
        if not data:
            failed.append(filename)
            continue
        concept_data[filename] = data
    return concept_data, failed


# -----------------------------------------------------------------------------
# Stage 2: Build per-paper text docs (title + abstract + intro)
# -----------------------------------------------------------------------------

_ABSTRACT_PATTERNS = [
    re.compile(r'(?is)\babstract\s*[:.]\s*(.{100,3000}?)(?:\n\s*\n|introduction|1\.\s|keywords)'),
    re.compile(r'(?is)\babSTRACT\s+(.{100,3000}?)(?:\n\s*\n|INTRODUCTION|1\.\s|KEYWORDS)'),
]


def _extract_abstract(text: str, max_chars: int = 2500) -> str:
    if not text:
        return ""
    for pat in _ABSTRACT_PATTERNS:
        m = pat.search(text)
        if m:
            return m.group(1).strip()[:max_chars]
    return text[:1500].strip()


# -----------------------------------------------------------------------------
# Stage 2b: Chinese tokenization + stopwords (added 2026-07-05 per user feedback)
# -----------------------------------------------------------------------------

_CN_STOPWORDS: Optional[set] = None
_JIEBA_AVAILABLE = None  # None = not yet probed


def _load_cn_stopwords() -> set:
    """Lazy-load combined Chinese stopwords from pa_cli/data/cn_stopwords.txt.

    Source: gitee.com/yinzm/ChineseStopWords — 4-table union
    (哈工大 + 百度 + 四川大学机器智能实验室 + 中文常用). 1470 lines.
    """
    global _CN_STOPWORDS
    if _CN_STOPWORDS is not None:
        return _CN_STOPWORDS
    _CN_STOPWORDS = set()
    stopwords_path = Path(__file__).parent / "data" / "cn_stopwords.txt"
    if not stopwords_path.exists():
        log.warning(f"CN stopwords file not found: {stopwords_path}")
        return _CN_STOPWORDS
    try:
        text = stopwords_path.read_text(encoding="utf-8", errors="ignore")
        for line in text.splitlines():
            w = line.strip()
            if w and not w.startswith("#"):
                _CN_STOPWORDS.add(w)
    except Exception as e:
        log.warning(f"Failed to load CN stopwords: {e}")
    return _CN_STOPWORDS


def _ensure_jieba():
    """Lazy-import jieba. Returns True if available."""
    global _JIEBA_AVAILABLE
    if _JIEBA_AVAILABLE is None:
        try:
            global jieba
            import jieba as _j
            jieba = _j
            _JIEBA_AVAILABLE = True
        except ImportError:
            _JIEBA_AVAILABLE = False
    return _JIEBA_AVAILABLE


def _is_chinese_heavy(text: str, threshold: float = 0.3) -> bool:
    """Heuristic: if >threshold of characters are CJK, treat as Chinese-heavy."""
    if not text:
        return False
    cjk_count = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    return (cjk_count / max(len(text), 1)) > threshold


def _tokenize_chinese(text: str) -> str:
    """Tokenize Chinese text with jieba + filter Chinese stopwords.

    Falls back to identity (return text as-is) if jieba not installed.
    Returns a space-separated string of tokens (compatible with sklearn
    TfidfVectorizer's default word_tokenize, and with BERTopic's default
    CountVectorizer).
    """
    if not _ensure_jieba():
        return text
    stopwords = _load_cn_stopwords()
    try:
        tokens = []
        for tok in jieba.cut(text):
            tok = tok.strip()
            if not tok or tok in stopwords:
                continue
            # Filter pure punctuation
            if all(not c.isalnum() and not ('\u4e00' <= c <= '\u9fff') for c in tok):
                continue
            tokens.append(tok)
        return " ".join(tokens)
    except Exception:
        return text


def _build_docs(papers: List[Dict]) -> Tuple[List[str], List[str], List[Dict]]:
    """Build (docs, filenames, papers_with_text) for BERTopic/hand-roll input.

    Each doc = title (2x weighted) + abstract. Falls back to filename if text
    is empty (rare; only when PyMuPDF is missing or PDF is image-only).

    For Chinese-heavy corpora, applies jieba tokenization + Chinese stopwords
    filtering to improve label/keyword quality.  Falls back to plain text for
    English-only docs.
    """
    docs: List[str] = []
    filenames: List[str] = []
    papers_with_text: List[Dict] = []
    for p in papers:
        text = p.get("text", "") or ""
        title = p.get("title", "") or ""
        abstract = _extract_abstract(text)
        # Title weighted 2x for stronger signal in TF-IDF
        combined = f"{title} {title} {abstract}".strip()
        if not combined:
            combined = p.get("filename", "")
        # Apply Chinese tokenization for Chinese-heavy corpora
        if _is_chinese_heavy(combined):
            combined = _tokenize_chinese(combined)
        docs.append(combined)
        filenames.append(p["filename"])
        papers_with_text.append(p)
    return docs, filenames, papers_with_text


# -----------------------------------------------------------------------------
# Stage 3a: BERTopic (primary)
# -----------------------------------------------------------------------------

# Cache the SentenceTransformer model across calls (heavy ~80MB download)
_MODEL_CACHE: Dict[str, Any] = {}


def _get_sentence_model(model_name: str = "all-MiniLM-L6-v2", download_timeout: Optional[float] = None):
    """Lazy-load + cache the sentence-transformers model.

    First call downloads ~80MB. Subsequent calls use disk cache.

    download_timeout: optional seconds to wait on the model download
        before raising TimeoutError (so caller can fall back to handroll
        per paper-agent v4 principle: "after 5 minutes, stop iterating,
        surface to user"). None = no timeout (default sentence-transformers
        behavior — retries up to 5 times with exponential backoff).
    """
    if model_name in _MODEL_CACHE:
        return _MODEL_CACHE[model_name]
    if not _ensure_bertopic():
        raise RuntimeError("BERTopic not available")

    if download_timeout is None:
        model = SentenceTransformer(model_name)
    else:
        # Honor the timeout via a background thread. SentenceTransformer's
        # underlying huggingface_hub download uses retries internally;
        # we wrap with a thread + timeout join to enforce the cap.
        import threading
        result = {}
        error = {}

        def _load():
            try:
                result["model"] = SentenceTransformer(model_name)
            except Exception as e:
                error["e"] = e

        t = threading.Thread(target=_load, daemon=True)
        t.start()
        t.join(timeout=download_timeout)
        if t.is_alive():
            raise TimeoutError(
                f"sentence-transformers download of '{model_name}' exceeded "
                f"{download_timeout}s timeout. Falling back to handroll."
            )
        if error:
            raise error["e"]
        model = result.get("model")
        if model is None:
            raise RuntimeError(f"SentenceTransformer({model_name!r}) returned None")

    _MODEL_CACHE[model_name] = model
    return model


def _cluster_with_bertopic(docs: List[str], filenames: List[str], n: int, extra_stopwords: Optional[List[str]] = None) -> Tuple[List[int], Any, List[str]]:
    """Run BERTopic. Returns (topic_ids, model, warnings).

    topic_ids: -1 = outlier, 0+ = cluster id

    extra_stopwords: domain-specific stopwords added to CountVectorizer
                     (e.g. corpus tool names, file extensions). [P1-4 v3.8.0]
    """
    if not _ensure_bertopic():
        raise RuntimeError("BERTopic not available")
    warnings: List[str] = []
    # Configure for small corpora
    umap_model = UMAP(
        n_neighbors=min(3, n - 1) if n > 1 else 1,
        n_components=min(2, max(1, n - 1)),
        min_dist=0.0,
        random_state=42,
    )
    hdbscan_model = HDBSCAN(
        min_cluster_size=2,
        min_samples=1,
        prediction_data=True,
    )
    model = BERTopic(
        verbose=False,
        umap_model=umap_model,
        hdbscan_model=hdbscan_model,
        calculate_probabilities=False,
    )
    # If corpus is Chinese-heavy, attach a CountVectorizer with our stopwords
    # to BERTopic's internal c-TF-IDF step.  This dramatically improves keyword
    # quality for Chinese corpora (default CountVectorizer uses English
    # stop_words only).
    if docs and any(_is_chinese_heavy(d) for d in docs):
        try:
            from sklearn.feature_extraction.text import CountVectorizer
            cn_stops = _load_cn_stopwords()
            from sklearn.feature_extraction import _stop_words as sklearn_sw
            all_stops = list(sklearn_sw.ENGLISH_STOP_WORDS)
            if cn_stops:
                all_stops.extend(list(cn_stops))
            if extra_stopwords:
                all_stops.extend(extra_stopwords)
            if len(all_stops) > len(sklearn_sw.ENGLISH_STOP_WORDS):  # only override if extended
                vectorizer_model = CountVectorizer(stop_words=all_stops)
                model = BERTopic(
                    verbose=False,
                    umap_model=umap_model,
                    hdbscan_model=hdbscan_model,
                    calculate_probabilities=False,
                    vectorizer_model=vectorizer_model,
                )
        except Exception as e:
            warnings.append(f"cn_vectorizer_setup_failed:{type(e).__name__}")
    try:
        topics, probs = model.fit_transform(docs)
    except Exception as e:
        warnings.append(f"bertopic_fit_failed:{type(e).__name__}:{str(e)[:200]}")
        raise
    # BERTopic labels outliers as -1; if all are -1, force into one topic
    unique = set(topics)
    if unique == {-1} or len(unique - {-1}) == 0:
        warnings.append("bertopic_all_outliers_forced_single_topic")
        topics = [0] * len(topics)
    elif len(unique - {-1}) == 1 and -1 in unique:
        # Single cluster + outliers: keep as 1 cluster + outliers (don't force merge)
        pass
    return list(topics), model, warnings


# -----------------------------------------------------------------------------
# Stage 3b: Hand-roll TF-IDF + Jaccard + Agglomerative (fallback)
# -----------------------------------------------------------------------------

def _jaccard_matrix(concept_sets: List[set], n: int) -> Any:
    import numpy as np
    mat = np.zeros((n, n), dtype=float)
    for i in range(n):
        for j in range(n):
            if i == j:
                mat[i, j] = 1.0
                continue
            a = concept_sets[i]
            b = concept_sets[j]
            if not a and not b:
                mat[i, j] = 0.0
                continue
            inter = len(a & b)
            union = len(a | b)
            mat[i, j] = inter / union if union else 0.0
    return mat


def _hybrid_similarity(tfidf_mat, concept_sets, alpha=0.4) -> Any:
    import numpy as np
    from sklearn.metrics.pairwise import cosine_similarity
    n = len(concept_sets)
    if tfidf_mat is None:
        tfidf_sim = np.zeros((n, n), dtype=float)
    else:
        tfidf_sim = cosine_similarity(tfidf_mat)
    jaccard = _jaccard_matrix(concept_sets, n)
    has_concept = np.array([len(cs) > 0 for cs in concept_sets], dtype=float)
    both_have = np.outer(has_concept, has_concept)
    hybrid = alpha * jaccard + (1.0 - alpha) * tfidf_sim
    sim = np.where(both_have > 0, hybrid, tfidf_sim)
    np.fill_diagonal(sim, 1.0)
    return sim


def _select_k(similarity, k_min=2, k_max=8) -> int:
    import numpy as np
    from sklearn.cluster import AgglomerativeClustering
    from sklearn.metrics import silhouette_score
    n = similarity.shape[0]
    if n < 5:
        return 1
    k_hi = min(k_max, n - 1)
    k_lo = max(k_min, 2)
    if k_hi < k_lo:
        return 1
    dist = 1.0 - similarity
    np.fill_diagonal(dist, 0.0)
    dist = np.clip(dist, 0.0, 2.0)
    best_k = k_lo
    best_score = -1.0
    for k in range(k_lo, k_hi + 1):
        try:
            ac = AgglomerativeClustering(n_clusters=k, metric="precomputed", linkage="average")
            labels = ac.fit_predict(dist)
            if len(set(labels)) < 2:
                continue
            score = silhouette_score(dist, labels, metric="precomputed")
            if score > best_score:
                best_score = score
                best_k = k
        except Exception:
            continue
    if best_score < 0.02:
        return 1
    return best_k


def _cluster_labels(similarity, k, filenames):
    import numpy as np
    from sklearn.cluster import AgglomerativeClustering
    dist = 1.0 - similarity
    np.fill_diagonal(dist, 0.0)
    dist = np.clip(dist, 0.0, 2.0)
    ac = AgglomerativeClustering(n_clusters=k, metric="precomputed", linkage="average")
    return list(ac.fit_predict(dist))


def _build_tfidf_matrix(papers):
    from sklearn.feature_extraction.text import TfidfVectorizer
    docs = []
    filenames = []
    for p in papers:
        text = p.get("text", "") or ""
        title = p.get("title", "") or ""
        abstract = _extract_abstract(text)
        combined = f"{title} {title} {abstract}".strip()
        if not combined:
            combined = p.get("filename", "")
        # Apply Chinese tokenization for Chinese-heavy corpora
        if _is_chinese_heavy(combined):
            combined = _tokenize_chinese(combined)
        docs.append(combined)
        filenames.append(p["filename"])
    if not docs:
        return None, []
    # Build stopwords set: union of "english" (sklearn) + Chinese stopwords
    cn_stops = _load_cn_stopwords()
    effective_max_df = 1.0 if len(docs) < 2 else 0.95
    vec = TfidfVectorizer(
        stop_words="english",  # sklearn built-in
        ngram_range=(1, 2),
        max_features=2000,
        min_df=1,
        max_df=effective_max_df,
        lowercase=True,
        token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z+\-#]{2,}\b",
    )
    # Manually filter Chinese stopwords post-tokenization by re-building docs
    # (jieba has already split + filtered, but for any remaining CN stop words
    # in CN-tokenized docs, post-filter via count_vectorizer)
    # Quick approach: re-build the vocabulary with our stop words
    if cn_stops and any(_is_chinese_heavy(d) for d in docs):
        # Combine sklearn's English stop words with our Chinese ones
        from sklearn.feature_extraction import _stop_words as sklearn_stopwords
        combined_stops = list(sklearn_stopwords.ENGLISH_STOP_WORDS) + list(cn_stops)
        vec = TfidfVectorizer(
            stop_words=combined_stops,
            ngram_range=(1, 2),
            max_features=2000,
            min_df=1,
            max_df=effective_max_df,
            lowercase=True,
            token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z+\-#]{2,}\b",
        )
    try:
        mat = vec.fit_transform(docs)
    except ValueError:
        return None, []
    return mat, filenames


def _label_topics_fallback(clusters, tfidf_mat, filenames, concept_data, papers_by_filename):
    from collections import Counter
    from sklearn.feature_extraction.text import TfidfVectorizer
    clusters_set = sorted(set(clusters))
    topics = []
    for cid in clusters_set:
        member_files = [filenames[i] for i, c in enumerate(clusters) if c == cid]
        member_papers = [papers_by_filename[f] for f in member_files if f in papers_by_filename]
        combined_text = " ".join(
            (p.get("title", "") + " " + _extract_abstract(p.get("text", "") or ""))
            for p in member_papers
        )
        concept_counter = Counter()
        concept_score = {}
        for f in member_files:
            cd = concept_data.get(f)
            if not cd:
                continue
            for c in cd.get("concepts", []):
                cname = c.get("name", "")
                if not cname:
                    continue
                concept_counter[cname] += 1
                concept_score[cname] = max(concept_score.get(cname, 0), c.get("score", 0))
        top_concepts = [
            {"name": n, "papers_count": cnt, "max_score": round(concept_score.get(n, 0), 3)}
            for n, cnt in concept_counter.most_common(5)
        ]
        try:
            vec = TfidfVectorizer(
                stop_words="english",
                ngram_range=(1, 2),
                max_features=20,
                min_df=1,
                max_df=1.0,
                lowercase=True,
                token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z+\-#]{2,}\b",
            )
            if combined_text.strip():
                ctfidf = vec.fit_transform([combined_text])
                names = vec.get_feature_names_out()
                scores = ctfidf.toarray()[0]
                top_kw_idx = scores.argsort()[::-1][:8]
                top_keywords = [names[i] for i in top_kw_idx if scores[i] > 0]
            else:
                top_keywords = []
        except Exception:
            top_keywords = []
        if top_concepts:
            label_seed = top_concepts[0]["name"]
        elif top_keywords:
            label_seed = " / ".join(top_keywords[:2])
        else:
            label_seed = f"Cluster {cid + 1}"
        years = [p.get("year") for p in member_papers if p.get("year")]
        year_range = f"{min(years)}-{max(years)}" if years else ""
        venue_counter = Counter(p.get("venue", "") for p in member_papers if p.get("venue"))
        top_venues = [v for v, _ in venue_counter.most_common(3)]
        topics.append({
            "topic_id": cid + 1,
            "label": label_seed,
            "keywords": top_keywords,
            "top_concepts": top_concepts,
            "paper_count": len(member_files),
            "year_range": year_range,
            "top_venues": top_venues,
            "filenames": member_files,
        })
    return topics


def _cluster_cohesion(similarity, labels):
    import numpy as np
    cohesion = {}
    for cid in sorted(set(labels)):
        idxs = [i for i, c in enumerate(labels) if c == cid]
        if len(idxs) < 2:
            cohesion[cid] = 1.0
            continue
        sub = similarity[np.ix_(idxs, idxs)]
        n = len(idxs)
        if n > 1:
            mask = ~np.eye(n, dtype=bool)
            cohesion[cid] = float(sub[mask].mean())
        else:
            cohesion[cid] = 1.0
    return cohesion


def _cluster_with_handroll(papers, concept_data, warnings, extra_stopwords=None):
    """Hand-rolled TF-IDF + Jaccard + Agglomerative. Used when BERTopic fails."""
    tfidf_mat, filenames = _build_tfidf_matrix(papers)
    if tfidf_mat is None:
        warnings.append("handroll_tfidf_empty")
    concept_sets = [
        set(c.get("concept_id", "") for c in concept_data.get(f, {}).get("concepts", []))
        for f in filenames
    ]
    similarity = _hybrid_similarity(tfidf_mat, concept_sets, alpha=0.4)
    k = _select_k(similarity)
    if k == 1:
        warnings.append(f"handroll_k=1_for_{len(filenames)}_papers")
        clusters = [0] * len(filenames)
    else:
        clusters = _cluster_labels(similarity, k, filenames)
    papers_by_filename = {p["filename"]: p for p in papers}
    topics = _label_topics_fallback(clusters, tfidf_mat, filenames, concept_data, papers_by_filename)
    cohesion = _cluster_cohesion(similarity, clusters)
    for t in topics:
        cid_zero = t["topic_id"] - 1
        t["cohesion_score"] = round(cohesion.get(cid_zero, 0.0), 3)
    return topics, clusters


# -----------------------------------------------------------------------------
# Stage 4: Topic labeling for BERTopic output
# -----------------------------------------------------------------------------

def _bertopic_to_schema(bertopic_topics: Dict[int, List[Tuple[str, float]]],
                        topic_ids: List[int], filenames: List[str],
                        papers: List[Dict],
                        model) -> List[Dict]:
    """Convert BERTopic internal format to topics.json schema."""
    from collections import Counter
    # Group filenames by topic id (-1 = outliers)
    by_topic: Dict[int, List[str]] = {}
    for tid, fn in zip(topic_ids, filenames):
        by_topic.setdefault(tid, []).append(fn)
    papers_by_filename = {p["filename"]: p for p in papers}
    topics = []
    for tid, member_files in sorted(by_topic.items(), key=lambda x: (x[0] == -1, x[0])):
        member_papers = [papers_by_filename[f] for f in member_files if f in papers_by_filename]
        # BERTopic keyword list: list of (word, weight) tuples
        kw_list = bertopic_topics.get(tid, [])
        top_keywords = [w for w, _ in kw_list[:8]]
        # OpenAlex concepts aggregated across members
        concept_counter = Counter()
        concept_score = {}
        for f in member_files:
            cd = _get_concept_data_for_file(f)
            if not cd:
                continue
            for c in cd.get("concepts", []):
                cname = c.get("name", "")
                if not cname:
                    continue
                concept_counter[cname] += 1
                concept_score[cname] = max(concept_score.get(cname, 0), c.get("score", 0))
        top_concepts = [
            {"name": n, "papers_count": cnt, "max_score": round(concept_score.get(n, 0), 3)}
            for n, cnt in concept_counter.most_common(5)
        ]
        # Label: top 3 BERTopic keywords joined, or top OpenAlex concept
        if top_keywords:
            label_seed = " / ".join(top_keywords[:3])
        elif top_concepts:
            label_seed = top_concepts[0]["name"]
        else:
            label_seed = f"Topic {tid + 1}" if tid >= 0 else "Outliers"
        # Cohesion: not directly computed by BERTopic; use 0.5 as default
        cohesion = 0.5  # BERTopic doesn't expose intra-cluster similarity directly
        years = [p.get("year") for p in member_papers if p.get("year")]
        year_range = f"{min(years)}-{max(years)}" if years else ""
        venue_counter = Counter(p.get("venue", "") for p in member_papers if p.get("venue"))
        top_venues = [v for v, _ in venue_counter.most_common(3)]
        topics.append({
            "topic_id": tid + 2 if tid == -1 else tid + 1,  # -1 outliers → 0, others → 1-indexed
            "topic_index": tid,  # BERTopic's internal id (-1 = outliers)
            "label": label_seed,
            "keywords": top_keywords,
            "top_concepts": top_concepts,
            "paper_count": len(member_files),
            "year_range": year_range,
            "top_venues": top_venues,
            "filenames": member_files,
            "cohesion_score": cohesion,
            "is_outlier_cluster": tid == -1,
        })
    # Sort: non-outliers first by paper_count desc, then outliers
    topics.sort(key=lambda t: (t.get("is_outlier_cluster", False), -t["paper_count"]))
    # Re-index topic_id after sort (1, 2, 3, ...) so callers see consistent numbering
    for new_id, t in enumerate(topics, start=1):
        t["topic_id"] = new_id
    return topics


# Internal concept data accessor (set by cluster_topics before calling this)
_CONCEPT_DATA_INTERNAL: Dict[str, Dict] = {}


def _get_concept_data_for_file(filename: str) -> Dict:
    return _CONCEPT_DATA_INTERNAL.get(filename, {})


# -----------------------------------------------------------------------------
# Public entry point
# -----------------------------------------------------------------------------

def cluster_topics(
    corpus_dir: Path,
    output_path: Optional[Path] = None,
    alpha: float = 0.4,  # only used by hand-roll fallback
    word_count_min: int = 1000,
    force_method: str = "auto",  # "auto" | "bertopic" | "handroll"
    model_name: str = "all-MiniLM-L6-v2",
    # ---- [P1-4] v3.8.0 polish: pluggable label generation ----
    label_method: str = "auto",  # "auto" | "ctfidf" | "handroll" | "custom"
    custom_labels: Optional[Dict[int, str]] = None,  # {topic_id: label_str}
    domain_stopwords: Optional[List[str]] = None,  # extra stopwords for c-TF-IDF
    # ---- [P1-4 v3.8.3] ----
    bertopic_timeout: Optional[float] = 60.0,  # seconds; None = no timeout
) -> Dict:
    """Cluster papers in corpus_dir by topic.

    Algorithm: BERTopic (sentence-transformers + UMAP + HDBSCAN) by default;
    falls back to hand-rolled TF-IDF + Jaccard + Agglomerative if BERTopic
    is not installed, the corpus is too small (n<5), or fit fails.

    Pluggable label generation (v3.8.0+):
      - label_method: which generator to use ("auto" = ctfidf)
      - custom_labels: {topic_id: label_str} overrides auto labels
      - domain_stopwords: corpus-specific noise terms (tool names, file
                          extensions) added to c-TF-IDF stop_words
      - bertopic_timeout: seconds to wait on sentence-transformers model
                          download before falling back to handroll.
                          Default 60s (per paper-agent v4 principle: "after
                          5 minutes, surface to user" — but for individual
                          ops we want faster fallback).

    Returns the same topics.json schema regardless of method.
    """
    global _CONCEPT_DATA_INTERNAL
    warnings: List[str] = []
    method_used = "handroll"  # default

    # [P1-4 v3.8.0] label_method drives force_method:
    #   auto / ctfidf / custom → use BERTopic (default)
    #   handroll → use hand-rolled TF-IDF (skip BERTopic)
    if label_method == "handroll":
        force_method = "handroll"

    k_actual = 1

    # Step A: walk corpus, extract text + metadata
    papers = build_corpus_index(corpus_dir, word_count_min)
    if not papers:
        warnings.append("empty_corpus")
        return {
            "corpus_dir": str(corpus_dir),
            "generated_at": datetime.now().isoformat(),
            "n_papers": 0,
            "methodology": "bertopic-with-handroll-fallback-v1",
            "method_used": "handroll",
            "warnings": warnings,
            "topics": [],
            "concept_data": {},
        }

    # Attach text to each paper
    for p in papers:
        td = extract_text(Path(p["path"]))
        p["text"] = td.get("text", "") or ""

    # Step B: build concept index via OpenAlex
    concept_data, failed = _build_concept_index(papers)
    _CONCEPT_DATA_INTERNAL = concept_data
    if failed:
        warnings.append(f"openalex_missing_for_{len(failed)}_papers")
    if not concept_data:
        warnings.append("no_openalex_concepts_available")

    # [P1-4 v3.8.0] Auto-mine domain stopwords from corpus if not provided
    if domain_stopwords is None:
        try:
            from .labels.domain_stopwords import extract_domain_stopwords
            domain_stopwords = extract_domain_stopwords(papers, top_n=20)
            if domain_stopwords:
                warnings.append(f"auto_mined_{len(domain_stopwords)}_domain_stopwords")
        except Exception as e:
            warnings.append(f"domain_stopwords_auto_mine_failed:{type(e).__name__}")
            domain_stopwords = []

    # Step C: decide method
    n = len(papers)
    if force_method == "auto":
        # Lazy-probe BERTopic only when auto-selected
        bertopic_ok = _ensure_bertopic()
    elif force_method == "bertopic":
        bertopic_ok = _ensure_bertopic()
    else:
        bertopic_ok = False
    use_bertopic = (
        force_method == "bertopic" or
        (force_method == "auto" and bertopic_ok and n >= 5)
    )
    if force_method == "handroll":
        use_bertopic = False
    if not bertopic_ok and force_method == "bertopic":
        warnings.append(f"bertopic_requested_but_not_available:{_BERTOPIC_IMPORT_ERROR}")
        use_bertopic = False
    if n < 5:
        warnings.append(f"n_papers={n}_below_5_using_handroll_for_stability")
        use_bertopic = False

    # Step D: cluster
    if use_bertopic:
        try:
            docs, filenames, papers_with_text = _build_docs(papers)
            _get_sentence_model(model_name, download_timeout=bertopic_timeout)  # warm cache
            topic_ids, model, bt_warnings = _cluster_with_bertopic(
                docs, filenames, n, extra_stopwords=domain_stopwords
            )
            warnings.extend(bt_warnings)
            bertopic_topics = {tid: model.get_topic(tid) for tid in set(topic_ids)}
            topics = _bertopic_to_schema(bertopic_topics, topic_ids, filenames, papers, model)
            # Outliers re-merging: if outliers >= 50% of corpus, force them into
            # the largest cluster (BERTopic's default would leave them isolated)
            outlier_topics = [t for t in topics if t.get("is_outlier_cluster")]
            if outlier_topics:
                outlier_count = sum(t["paper_count"] for t in outlier_topics)
                if outlier_count >= n * 0.4 and len(topics) > 1:
                    warnings.append(f"merging_{outlier_count}_outliers_to_largest_cluster")
                    # Move all outliers' filenames to largest non-outlier cluster
                    non_outliers = [t for t in topics if not t.get("is_outlier_cluster")]
                    if non_outliers:
                        largest = max(non_outliers, key=lambda t: t["paper_count"])
                        for ot in outlier_topics:
                            largest["filenames"].extend(ot["filenames"])
                            largest["paper_count"] += ot["paper_count"]
                        topics = [t for t in topics if not t.get("is_outlier_cluster")]
                        # Re-sort and re-index
                        topics.sort(key=lambda t: t["paper_count"], reverse=True)
                        for new_id, t in enumerate(topics, start=1):
                            t["topic_id"] = new_id
            method_used = "bertopic"
            k_actual = len([t for t in topics if not t.get("is_outlier_cluster")])
            if k_actual == 0:
                k_actual = 1
        except Exception as e:
            warnings.append(f"bertopic_failed_fallback_to_handroll:{type(e).__name__}:{str(e)[:150]}")
            topics, _ = _cluster_with_handroll(papers, concept_data, warnings, extra_stopwords=domain_stopwords)
            method_used = "handroll"
            k_actual = len(topics)
    else:
        topics, _ = _cluster_with_handroll(papers, concept_data, warnings, extra_stopwords=domain_stopwords)
        k_actual = len(topics)

    # Apply custom label overrides (v3.8.0+ — see pa_cli/labels/custom.py)
    if custom_labels:
        try:
            from .labels import CustomLabelGenerator
            gen = CustomLabelGenerator(custom_labels=custom_labels)
            topics = gen.generate(
                papers=papers, clusters=[],  # not used by post-processor
                topics=topics,
            )
            warnings.append(f"custom_labels_applied_for_{len(custom_labels)}_topics")
        except Exception as e:
            warnings.append(f"custom_labels_failed:{type(e).__name__}:{str(e)[:100]}")

    # Build concept_data summary for downstream consumers
    concept_data_summary: Dict[str, Dict] = {}
    for f, cd in concept_data.items():
        concept_data_summary[f] = {
            "doi": cd.get("doi", ""),
            "title": cd.get("title", ""),
            "year": cd.get("year"),
            "venue": cd.get("venue", ""),
            "cited_by_count": cd.get("cited_by_count", 0),
            "concept_ids": [c["concept_id"] for c in cd.get("concepts", [])],
            "concept_names": [c["name"] for c in cd.get("concepts", [])],
            "openalex_url": cd.get("openalex_url", ""),
        }

    result = {
        "corpus_dir": str(corpus_dir),
        "generated_at": datetime.now().isoformat(),
        "n_papers": n,
        "methodology": "bertopic-with-handroll-fallback-v1",
        "method_used": method_used,
        "model_name": model_name if method_used == "bertopic" else None,
        "label_method": label_method,  # [P1-4 v3.8.0] pluggable label gen
        "k": k_actual,
        "warnings": warnings,
        "custom_labels": {str(k): v for k, v in (custom_labels or {}).items()},
        "domain_stopwords_count": len(domain_stopwords) if domain_stopwords else 0,
        "topics": topics,
        "concept_data": concept_data_summary,
    }

    # Write output
    if output_path is None:
        output_path = Path(corpus_dir) / "topics.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(_jsonify(result), f, indent=2, ensure_ascii=False)

    return result


def _jsonify(obj):
    """Recursively convert numpy types to native Python for JSON serialization."""
    import numpy as np
    if isinstance(obj, dict):
        return {k: _jsonify(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonify(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.ndarray,)):
        return obj.tolist()
    return obj