"""
bench/v01/_bm25_rerank.py — BM25 rerank baseline candidates.

For each query, take the 30 candidates from system_outputs/, rerank them
by BM25 score using title + abstract as document, query string as query.
Save to system_outputs_bm25/.

This tests: is ranking the problem? If BM25 lifts recall@10 from 0.18 → 0.30+,
then yes, the baseline ranking is broken.
"""
import json
import re
import math
from collections import Counter
from pathlib import Path

BENCH_DIR = Path("bench/v01")
SYSTEM_IN = BENCH_DIR / "system_outputs"
SYSTEM_OUT = BENCH_DIR / "system_outputs_bm25"
SYSTEM_OUT.mkdir(parents=True, exist_ok=True)


def tokenize(text: str) -> list[str]:
    """Simple tokenizer: lowercase + split on non-alphanumeric + remove stopwords."""
    if not text:
        return []
    text = text.lower()
    # split on non-alphanumeric
    tokens = re.findall(r"[a-z0-9]+", text)
    # minimal English stopwords
    STOP = {
        "a", "an", "the", "and", "or", "but", "if", "of", "to", "in", "on", "at",
        "for", "with", "by", "from", "as", "is", "are", "was", "were", "be", "been",
        "being", "this", "that", "these", "those", "it", "its", "they", "their", "them",
        "we", "our", "us", "i", "you", "your", "he", "she", "his", "her",
        "do", "does", "did", "have", "has", "had", "can", "could", "would", "should",
        "may", "might", "will", "shall", "not", "no", "than", "then", "so",
    }
    return [t for t in tokens if t not in STOP and len(t) > 1]


class BM25:
    """Standard BM25 (Robertson) implementation."""
    def __init__(self, k1=1.5, b=0.75):
        self.k1 = k1
        self.b = b
        self.docs = []          # list of token lists
        self.doc_lens = []
        self.avgdl = 0
        self.df = Counter()     # document frequency per term
        self.n_docs = 0
        self.idf = {}

    def fit(self, docs: list[list[str]]):
        self.docs = docs
        self.n_docs = len(docs)
        self.doc_lens = [len(d) for d in docs]
        self.avgdl = sum(self.doc_lens) / self.n_docs if self.n_docs else 1
        self.df = Counter()
        for d in docs:
            for term in set(d):
                self.df[term] += 1
        # IDF with smoothing
        for term, df in self.df.items():
            self.idf[term] = math.log(1 + (self.n_docs - df + 0.5) / (df + 0.5))

    def score(self, query: list[str], doc_idx: int) -> float:
        d = self.docs[doc_idx]
        dl = self.doc_lens[doc_idx]
        tf = Counter(d)
        s = 0.0
        for q in query:
            if q not in tf:
                continue
            f = tf[q]
            idf = self.idf.get(q, 0)
            num = f * (self.k1 + 1)
            den = f + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
            s += idf * num / den
        return s


def rerank_query(snap: dict) -> dict:
    """Take a snapshot, rerank its results by BM25 against the query."""
    query = snap["query"]
    query_tokens = tokenize(query)
    if not query_tokens:
        return snap

    # Build docs from title + abstract
    docs = []
    for r in snap["results"]:
        text = (r.get("title", "") or "") + " " + (r.get("abstract", "") or "")
        docs.append(tokenize(text))

    bm25 = BM25(k1=1.5, b=0.75)
    bm25.fit(docs)

    # Score each candidate
    scores = []
    for i in range(len(snap["results"])):
        s = bm25.score(query_tokens, i)
        scores.append(s)

    # Re-rank by score desc (keep all 30, just reorder)
    indexed = list(enumerate(snap["results"]))
    indexed.sort(key=lambda x: scores[x[0]], reverse=True)

    new_results = []
    for new_rank, (orig_idx, r) in enumerate(indexed, start=1):
        new_r = dict(r)
        new_r["rank"] = new_rank
        new_r["bm25_score"] = round(scores[orig_idx], 4)
        new_r["orig_rank"] = r["rank"]
        new_results.append(new_r)

    new_snap = dict(snap)
    new_snap["results"] = new_results
    new_snap["config"] = "baseline-bm25"
    new_snap["generated_at"] = __import__("datetime").datetime.now().isoformat(timespec="seconds")
    return new_snap


def main():
    files = sorted(SYSTEM_IN.glob("q*.json"))
    print(f"[bm25] reranking {len(files)} system outputs")
    for f in files:
        snap = json.loads(f.read_text(encoding="utf-8"))
        new_snap = rerank_query(snap)
        out_path = SYSTEM_OUT / f.stem  # preserve q00X.json
        out_path.write_text(json.dumps(new_snap, ensure_ascii=False, indent=2), encoding="utf-8")
        # quick report: top-3 after rerank
        top3 = [(r["rank"], r["doi"], r["bm25_score"], r.get("title", "")[:50]) for r in new_snap["results"][:3]]
        print(f"  {f.stem}: top-3 = {top3}")
    print(f"[bm25] done. {len(files)} files in {SYSTEM_OUT}")


if __name__ == "__main__":
    main()
