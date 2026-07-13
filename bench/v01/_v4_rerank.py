"""
bench/v01/_v4_rerank.py — v4 multi-condition rerank stack.

Conditions supported (CLI: --condition {bm25|biencoder|combined|prf|random}):
  - bm25        : pure BM25 (sanity check, matches _bm25_rerank.py)
  - biencoder   : pure bi-encoder cosine (sentence-transformers all-MiniLM-L6-v2, cached)
  - combined    : 0.5 * BM25_norm + 0.5 * bi-encoder_norm
  - prf         : pseudo-relevance feedback (Rocchio) using BM25 top-5 docs to expand query
  - random      : random shuffle (ablation baseline)

For each query, take the 30 candidates from system_outputs/, rerank them per condition,
write to system_outputs_<condition>/.  Then eval.py computes per-condition metrics.

ROADMAP [P1-5] (v3.9.1, 2026-07-13): Added `--recency-mode` flag (strict|moderate|off).
Applies user-defined rule: papers >10y old need cite > mean+2std; >20y need cite > mean+2.5std.
Older papers with high bi-encoder relevance can escape the downweight.

HF offline mode forced: model is cached locally from v3.8.0. If you need to redownload,
unset HF_HUB_OFFLINE.
"""
import argparse
import json
import math
import os
import random
import re
import sys
from collections import Counter
from pathlib import Path

# Force HF offline before any HF/transformers import
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

# Add project root to path so we can import pa_cli
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT))

from pa_cli.recency import RecencyConfig, apply_recency_to_results  # noqa: E402

BENCH_DIR = Path(r"G:\minimax - workspace\Paper agent\bench\v01")
SYSTEM_IN = BENCH_DIR / "system_outputs"

CONDITION_OUT_DIRS = {
    "bm25": "system_outputs_bm25",
    "biencoder": "system_outputs_biencoder",
    "combined": "system_outputs_combined",
    "prf": "system_outputs_prf",
    "random": "system_outputs_random",
}


# ---------- Tokenizer (shared with _bm25_rerank.py) ----------
STOP = {
    "a", "an", "the", "and", "or", "but", "if", "of", "to", "in", "on", "at",
    "for", "with", "by", "from", "as", "is", "are", "was", "were", "be", "been",
    "being", "this", "that", "these", "those", "it", "its", "they", "their", "them",
    "we", "our", "us", "i", "you", "your", "he", "she", "his", "her",
    "do", "does", "did", "have", "has", "had", "can", "could", "would", "should",
    "may", "might", "will", "shall", "not", "no", "than", "then", "so",
}


def tokenize(text: str) -> list[str]:
    if not text:
        return []
    text = text.lower()
    tokens = re.findall(r"[a-z0-9]+", text)
    return [t for t in tokens if t not in STOP and len(t) > 1]


# ---------- BM25 (shared) ----------
class BM25:
    def __init__(self, k1=1.5, b=0.75):
        self.k1, self.b = k1, b
        self.docs, self.doc_lens, self.avgdl = [], [], 0
        self.df, self.n_docs, self.idf = Counter(), 0, {}

    def fit(self, docs):
        self.docs = docs
        self.n_docs = len(docs)
        self.doc_lens = [len(d) for d in docs]
        self.avgdl = sum(self.doc_lens) / self.n_docs if self.n_docs else 1
        self.df = Counter()
        for d in docs:
            for term in set(d):
                self.df[term] += 1
        for term, df in self.df.items():
            self.idf[term] = math.log(1 + (self.n_docs - df + 0.5) / (df + 0.5))

    def score(self, query, doc_idx):
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


def doc_text(r: dict) -> str:
    return (r.get("title", "") or "") + " " + (r.get("abstract", "") or "")


# ---------- Bi-encoder (lazy singleton) ----------
_BIENC = None


def get_biencoder():
    """Lazy-load sentence-transformers all-MiniLM-L6-v2 (cached locally from v3.8.0)."""
    global _BIENC
    if _BIENC is None:
        from sentence_transformers import SentenceTransformer
        _BIENC = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    return _BIENC


def biencoder_scores(query: str, results: list[dict]) -> list[float]:
    """Cosine similarity of (query, candidate title+abstract) embeddings."""
    model = get_biencoder()
    texts = [doc_text(r) for r in results]
    # encode_query + encode_documents in one call
    embs = model.encode([query] + texts, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False)
    q_emb = embs[0]
    d_embs = embs[1:]
    return [float((q_emb * d_embs[i]).sum()) for i in range(len(texts))]


# ---------- PRF (Rocchio) ----------
def prf_expand_query(query: str, results: list[dict], bm25_scores: list[float], top_k: int = 5, n_terms: int = 8) -> str:
    """Take top-K BM25 docs, extract their top-N distinctive terms, append to query.

    Standard Rocchio-style pseudo-relevance feedback. No external model.
    """
    q_tokens = set(tokenize(query))
    # Pick top-K by BM25
    indexed = sorted(enumerate(results), key=lambda x: bm25_scores[x[0]], reverse=True)[:top_k]
    # Term frequency across top-K
    tf = Counter()
    for idx, _ in indexed:
        for tok in tokenize(doc_text(results[idx])):
            if tok not in q_tokens and len(tok) > 3:
                tf[tok] += 1
    # Top-N most frequent (rough)
    expansion = " ".join([t for t, _ in tf.most_common(n_terms)])
    return query + " " + expansion


# ---------- Normalization (min-max per query) ----------
def normalize(scores: list[float]) -> list[float]:
    if not scores:
        return scores
    lo, hi = min(scores), max(scores)
    if hi - lo < 1e-9:
        return [0.5] * len(scores)
    return [(s - lo) / (hi - lo) for s in scores]


# ---------- Per-condition rerank ----------
def rerank(snap: dict, condition: str, alpha: float = 0.5, recency_mode: str = "off") -> dict:
    query = snap["query"]
    results = snap["results"]
    n = len(results)
    if n == 0:
        return snap

    # Always compute BM25 (needed for bm25 / combined / prf)
    q_tokens = tokenize(query)
    bm25_scores = [0.0] * n
    if q_tokens:
        docs = [tokenize(doc_text(r)) for r in results]
        bm = BM25()
        bm.fit(docs)
        bm25_scores = [bm.score(q_tokens, i) for i in range(n)]

    # Compute biencoder scores if needed
    bi_scores = None
    if condition in ("biencoder", "combined"):
        bi_scores = biencoder_scores(query, results)

    # Compute final scores
    if condition == "bm25":
        final = bm25_scores
    elif condition == "biencoder":
        final = bi_scores or [0.0] * n
    elif condition == "combined":
        bm_n = normalize(bm25_scores)
        bi_n = normalize(bi_scores or [0.0] * n)
        final = [alpha * bm_n[i] + (1 - alpha) * bi_n[i] for i in range(n)]
    elif condition == "prf":
        # Rocchio: expand query, re-BM25
        expanded = prf_expand_query(query, results, bm25_scores)
        exp_tokens = tokenize(expanded)
        if exp_tokens:
            docs = [tokenize(doc_text(r)) for r in results]
            bm = BM25()
            bm.fit(docs)
            final = [bm.score(exp_tokens, i) for i in range(n)]
        else:
            final = bm25_scores
    elif condition == "random":
        final = [random.random() for _ in range(n)]
    else:
        raise ValueError(f"Unknown condition: {condition}")

    # ROADMAP [P1-5] (v3.9.1): apply recency filter (downweights old papers, rescues high-relevance ones)
    # Multiplies final score by recency factor in [0.1, 1.0].
    # Re-rank by adjusted final score desc.
    recency_config = RecencyConfig(mode=recency_mode)
    if recency_mode != "off":
        # Convert to a list of dicts to apply recency
        results_with_score = []
        for i, r in enumerate(results):
            r2 = dict(r)
            r2["v4_score"] = final[i]
            results_with_score.append(r2)
        adjusted, field_warn = apply_recency_to_results(
            results_with_score,
            bi_scores=bi_scores,
            config=recency_config,
        )
        if field_warn:
            print(f"  {snap.get('query_id', '?')}: {field_warn}", file=sys.stderr)
        # Use adjusted scores for ranking
        adjusted_score_map = {id(r): r["v4_score"] for r in adjusted}
        # Re-rank by adjusted score
        indexed = sorted(
            enumerate(adjusted),
            key=lambda x: x[1]["v4_score"],
            reverse=True,
        )
        new_results = []
        for new_rank, (orig_idx, r) in enumerate(indexed, start=1):
            nr = dict(r)
            nr["rank"] = new_rank
            nr["orig_rank"] = r["rank"]
            nr["v4_score"] = round(r["v4_score"], 6)
            if bm25_scores:
                nr["bm25_score"] = round(bm25_scores[orig_idx], 4)
            if bi_scores is not None:
                nr["biencoder_score"] = round(bi_scores[orig_idx], 4)
            new_results.append(nr)
    else:
        # No recency filter: original behavior
        indexed = list(enumerate(results))
        indexed.sort(key=lambda x: final[x[0]], reverse=True)
        new_results = []
        for new_rank, (orig_idx, r) in enumerate(indexed, start=1):
            nr = dict(r)
            nr["rank"] = new_rank
            nr["orig_rank"] = r["rank"]
            nr["v4_score"] = round(final[orig_idx], 6)
            if bm25_scores:
                nr["bm25_score"] = round(bm25_scores[orig_idx], 4)
            if bi_scores is not None:
                nr["biencoder_score"] = round(bi_scores[orig_idx], 4)
            new_results.append(nr)

    new_snap = dict(snap)
    new_snap["results"] = new_results
    new_snap["config"] = f"v4-{condition}-recency-{recency_mode}"
    new_snap["generated_at"] = __import__("datetime").datetime.now().isoformat(timespec="seconds")
    return new_snap


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--condition", required=True,
                        choices=["bm25", "biencoder", "combined", "prf", "random"])
    parser.add_argument("--alpha", type=float, default=0.5,
                        help="Combined weight: alpha * BM25 + (1-alpha) * biencoder")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (random condition only)")
    parser.add_argument("--recency-mode", default="off", choices=["off", "strict", "moderate"],
                        help="ROADMAP [P1-5]: downweight old papers. strict=0.1x for >20y+low cite, moderate=0.5x")
    args = parser.parse_args()

    random.seed(args.seed)

    out_dir_name = CONDITION_OUT_DIRS[args.condition]
    out_dir = BENCH_DIR / out_dir_name
    out_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(SYSTEM_IN.glob("q*.json"))
    print(f"[v4/{args.condition}] reranking {len(files)} system outputs (alpha={args.alpha}, recency={args.recency_mode})")

    for f in files:
        snap = json.loads(f.read_text(encoding="utf-8"))
        new_snap = rerank(snap, args.condition, alpha=args.alpha, recency_mode=args.recency_mode)
        out_path = out_dir / f.name  # preserve .json extension (f.stem strips it)
        out_path.write_text(json.dumps(new_snap, ensure_ascii=False, indent=2), encoding="utf-8")
        top3 = [(r["rank"], r["doi"], r.get("v4_score", 0)) for r in new_snap["results"][:3]]
        print(f"  {f.stem}: top-3 = {top3}")

    print(f"[v4/{args.condition}] done. {len(files)} files in {out_dir}")


if __name__ == "__main__":
    main()
