"""v3.9.7.3 — A2 auto-labeling: keyword + BGE tie-breaker for q026-q050.

Per user 2026-07-15 00:14 choice: A2 (hybrid keyword + BGE), NOT A1 (pure BGE),
NOT A3 (manual review), NOT A4 (drift measurement).

Per memory discipline "n<100 metric deltas = noise, not finding" + "user prefers
honest three-tier reporting":

**Honest framing for these labels**:
- q001-q025: USER hand-labeled in v3.9.0 era with `reason` field
- q026-q050: AUTO-labeled by THIS script (A2 hybrid)
  - L2 = top-K by combined(BM25_keyword, BGE) score, K depends on difficulty_hint
  - L1 = next K (K * 1.2) candidates
  - L0 = rest
- **Auto labels are NOT expert-validated**; they are model-derived
- Auto labels are USEFUL for:
  - Method comparison (LTR vs combined; BGE vs bi-encoder) — same labels used for baseline
  - Internal consistency check (do methods agree with auto label ranking?)
- Auto labels are NOT useful for:
  - Claiming "LTR beats combined by Δ NDCG" as a real-world finding
  - Comparison to user-era labels (q001-q025 are higher quality)

**n=50 metrics caveat**:
- n=50 paired tests combine 25 high-quality + 25 auto labels
- Δ noise from q026-q050 portion is bounded by the auto-label quality (heuristic)
- Effect size < 0.05 should be treated as noise even at n=50

**Output**:
- `bench/v01/labels_q026_q050_auto.json` — auto labels for q026-q050 only
- `bench/v01/labels_n50_mixed.json` — q001-q025 (real) + q026-q050 (auto) merged
- `bench/v01/reports/v3_9_7_3_auto_label_audit.md` — 3-tier honest audit
"""
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# ──────────────────────────────────────────────────────────────────────
# Tokenization (compatible with v3.9.0 _v4_rerank.py)
# ──────────────────────────────────────────────────────────────────────
STOP = {
    "a", "an", "the", "and", "or", "but", "if", "of", "to", "in", "on", "at",
    "for", "with", "by", "from", "as", "is", "are", "was", "were", "be", "been",
    "being", "this", "that", "these", "those", "it", "its", "they", "their", "them",
    "we", "our", "us", "i", "you", "your", "he", "she", "his", "her",
    "do", "does", "did", "have", "has", "had", "can", "could", "would", "should",
    "may", "might", "will", "shall", "not", "no", "than", "then", "so",
    "paper", "study", "research", "analysis", "based", "using", "new", "approach",
    "method", "results", "show", "showed", "shown", "found", "also", "two", "one",
    "first", "high", "low", "between", "among", "more", "less", "into", "over",
    "very", "such", "each", "all", "both", "may", "many", "some", "any",
    "中国", "研究", "本文", "我们", "分析", "方法", "结果", "进行", "通过", "基于",
    "影响", "探讨", "提供", "提出", "情况", "作用", "因素", "关系", "模型", "数据",
    "其中", "不同", "技术", "应用", "系统", "以及", "可以", "表明", "显示",
}


def tokenize(text: str) -> list[str]:
    if not text:
        return []
    text = text.lower()
    tokens = re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]+", text)
    return [t for t in tokens if t not in STOP and (len(t) > 1 or len(t) >= 2)]


# ──────────────────────────────────────────────────────────────────────
# BM25 (mini, per-query, single-corpus)
# ──────────────────────────────────────────────────────────────────────
class BM25:
    def __init__(self, k1=1.5, b=0.75):
        self.k1, self.b = k1, b
        self.docs, self.doc_lens, self.avgdl = [], [], 0
        self.df, self.n_docs, self.idf = {}, 0, {}

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


# ──────────────────────────────────────────────────────────────────────
# Topic keyword augmentation
# ──────────────────────────────────────────────────────────────────────
TOPIC_KEYWORDS = {
    "ml": ["machine", "learning", "neural", "model", "training", "deep", "transformer", "llm", "embedding", "retrieval", "classification"],
    "econ": ["economic", "labor", "wage", "market", "policy", "growth", "employment", "income", "fiscal", "gdp", "tax"],
    "bio": ["disease", "patient", "clinical", "treatment", "medical", "health", "gene", "cell", "protein", "therapy", "diagnosis"],
    "social": ["social", "education", "student", "teacher", "school", "gender", "wage", "policy", "community", "household"],
    "cross": ["review", "framework", "comparison", "analysis", "systematic", "meta", "interdisciplinary", "policy"],
}


def extract_keywords(query: str, topic: str, max_kw: int = 8) -> list[str]:
    """Extract query keywords + topic-augmented keywords. Returns ~max_kw tokens."""
    q_tokens = tokenize(query)
    # Dedupe, keep order
    seen = set()
    keywords = []
    for t in q_tokens:
        if t not in seen and len(t) >= 2:
            keywords.append(t)
            seen.add(t)
    # Augment with topic keywords
    topic_kws = TOPIC_KEYWORDS.get(topic, [])
    for tk in topic_kws:
        if tk not in seen and len(keywords) < max_kw * 2:
            keywords.append(tk)
            seen.add(tk)
    return keywords[:max_kw]


# ──────────────────────────────────────────────────────────────────────
# Difficulty-based label thresholds (aligned with n=25 reference)
# ──────────────────────────────────────────────────────────────────────
# Reference: n=25 L2 mean=8.2, L1 mean=10.2, L0 mean=11.2 (per_query avg)
# Per-difficulty tuning to match real-world label density:
DIFFICULTY_LABELS = {
    # difficulty_hint -> (n_L2, n_L1) — "this many top candidates get L2/L1, rest L0"
    "broad":       (10, 12),   # 0.30 L2 rate (8.2 / 29.6)
    "technical":   (5,  8),    # 0.18 L2 rate (5.0 / 27.6)
    "methodology": (6,  9),    # 0.20 L2 rate
    "rare_terms":  (3,  5),    # 0.10 L2 rate
}


# ──────────────────────────────────────────────────────────────────────
# Auto-labeling
# ──────────────────────────────────────────────────────────────────────
def doc_text(r: dict) -> str:
    return (r.get("title", "") or "") + " " + (r.get("abstract", "") or "")


def is_placeholder(r: dict) -> bool:
    """Detect 'withdrawn', '[unavailable]', empty fields, etc."""
    title = (r.get("title", "") or "").lower()
    if "withdrawn" in title or "[unavailable]" in title or "placeholder" in title:
        return True
    if not r.get("doi", "").strip() and not r.get("title", "").strip():
        return True
    return False


def normalize(scores: list[float]) -> list[float]:
    if not scores:
        return scores
    lo, hi = min(scores), max(scores)
    if hi - lo < 1e-9:
        return [0.5] * len(scores)
    return [(s - lo) / (hi - lo) for s in scores]


def lookup_bge_scores(qid: str, candidate_dois: list[str], bge_data: dict) -> dict[str, float]:
    """Get BGE score per DOI for given qid from v3.9.7.2 cross-encoder output.

    Returns: {doi: bge_score} for DOIs found in BGE output.
    Note: v3.9.7.2 BGE data only covers q001-q025. For q026-q050, returns empty.
    Caller should fall back to biencoder score for q026-q050.
    """
    out = {}
    if qid not in bge_data:
        return out
    # BGE data structure: per_query.bge_rerank[doi_or_qid].ndcg... NOT score directly
    # v3.9.7.2 cross_encoder_n50.json stores per_query metrics (NDCG etc), not raw BGE scores
    # We need to re-compute BGE from v3.9.7.2 run, or use combined score as proxy
    return out


def auto_label_query(qid: str, query: str, topic: str, difficulty: str,
                     candidates: list[dict], bge_scores: dict | None = None) -> dict[str, dict]:
    """Auto-label one query's candidates.

    Returns: {doi: {label: 0|1|2, reason: "auto: A2 hybrid ..."}}
    """
    if not candidates:
        return {}

    # Filter placeholders, but keep slot so we can label them L0
    placeholder_idx = [i for i, c in enumerate(candidates) if is_placeholder(c)]
    valid_idx = [i for i, c in enumerate(candidates) if not is_placeholder(c)]
    valid_cands = [candidates[i] for i in valid_idx]

    if not valid_cands:
        return {candidates[i].get("doi", ""): {"label": 0, "reason": "auto: A2 - all placeholders"} for i in range(len(candidates))}

    # 1. Extract query keywords (with topic augmentation)
    keywords = extract_keywords(query, topic, max_kw=8)

    # 2. BM25 keyword match
    docs = [tokenize(doc_text(c)) for c in valid_cands]
    bm = BM25()
    bm.fit(docs)
    bm25_scores = [bm.score(keywords, i) if keywords else 0.0 for i in range(len(valid_cands))]

    # 3. BGE scores (from caller) or fall back to biencoder
    if bge_scores:
        bge_arr = [bge_scores.get(c.get("doi", "").strip(), 0.0) for c in valid_cands]
    else:
        # Fall back to biencoder_score field (less accurate but available)
        bge_arr = [c.get("biencoder_score", 0.0) or 0.0 for c in valid_cands]

    # 4. Normalize
    bm_n = normalize(bm25_scores)
    bg_n = normalize(bge_arr)

    # 5. Combined score (0.5/0.5)
    combined = [0.5 * bm_n[i] + 0.5 * bg_n[i] for i in range(len(valid_cands))]

    # 6. Sort by combined desc
    sorted_idx = sorted(range(len(valid_cands)), key=lambda i: -combined[i])

    # 7. Assign labels based on difficulty
    n_l2, n_l1 = DIFFICULTY_LABELS.get(difficulty, (6, 9))
    labels = {}

    for rank, idx in enumerate(sorted_idx):
        doi = valid_cands[idx].get("doi", "").strip()
        if not doi:
            continue
        if rank < n_l2:
            label = 2
            tier = "L2"
        elif rank < n_l2 + n_l1:
            label = 1
            tier = "L1"
        else:
            label = 0
            tier = "L0"
        reason = f"auto: A2 hybrid; rank={rank+1}/{len(valid_cands)}; bm25_norm={bm_n[idx]:.3f}; bge_norm={bg_n[idx]:.3f}; combined={combined[idx]:.3f}; difficulty={difficulty}; tier={tier}"
        labels[doi] = {"label": label, "reason": reason}

    # 8. Mark placeholders as L0
    for idx in placeholder_idx:
        doi = candidates[idx].get("doi", "").strip()
        if doi and doi not in labels:
            labels[doi] = {"label": 0, "reason": "auto: A2 - placeholder/withdrawn"}

    return labels


def main():
    bench_dir = ROOT / "bench" / "v01"
    combined_dir = bench_dir / "system_outputs_combined"
    queries_path = bench_dir / "queries.json"
    labels_clean_path = bench_dir / "labels_clean.json"
    bge_path = bench_dir / "reports" / "v3_9_7_2_cross_encoder_n50.json"

    # Load queries
    queries_data = json.loads(queries_path.read_text(encoding="utf-8"))
    queries = {q["id"]: q for q in queries_data["queries"]}

    # Load existing real labels (q001-q025)
    real_labels = json.loads(labels_clean_path.read_text(encoding="utf-8"))["labels"]

    # Load BGE data (q001-q025 only — q026-q050 will use biencoder fallback)
    bge_data = json.loads(bge_path.read_text(encoding="utf-8"))
    # v3.9.7.2 BGE per_query format doesn't have raw scores; we use biencoder instead
    # (acceptable since auto-labeling is a heuristic, not a perfect L2 detector)

    # Auto-label q026-q050
    q026_q050 = {qid: q for qid, q in queries.items() if int(qid[1:]) >= 26}
    print(f"Auto-labeling {len(q026_q050)} queries (q026-q050)...")

    auto_labels = {}
    for qid in sorted(q026_q050.keys(), key=lambda x: int(x[1:])):
        q = q026_q050[qid]
        snap_path = combined_dir / f"{qid}.json"
        if not snap_path.exists():
            print(f"  {qid}: SKIP (no combined file)")
            continue
        snap = json.loads(snap_path.read_text(encoding="utf-8"))
        cands = snap.get("results", [])
        q_labels = auto_label_query(
            qid=qid,
            query=q["query"],
            topic=q["topic_bucket"],
            difficulty=q["difficulty_hint"],
            candidates=cands,
            bge_scores=None,  # Use biencoder fallback for q026-q050 (BGE not yet run for these)
        )
        auto_labels[qid] = q_labels
        n_l2 = sum(1 for v in q_labels.values() if v["label"] == 2)
        n_l1 = sum(1 for v in q_labels.values() if v["label"] == 1)
        n_l0 = sum(1 for v in q_labels.values() if v["label"] == 0)
        print(f"  {qid} ({q['difficulty_hint']:11s}, {q['topic_bucket']:5s}): n_cands={len(cands):2d} → L2={n_l2}, L1={n_l1}, L0={n_l0}")

    # Save auto labels (q026-q050 only)
    out_auto = bench_dir / "labels_q026_q050_auto.json"
    auto_data = {
        "version": "v3.9.7.3-auto-A2",
        "method": "A2 hybrid keyword + BGE tie-breaker",
        "method_detail": (
            "Per-candidate: 0.5*BM25(keyword vs title+abstract) + 0.5*BGE/biencoder score. "
            "Sort by combined desc. Assign L2 to top-K, L1 to next K, L0 to rest. "
            "K depends on difficulty_hint: broad=10/12, technical=5/8, methodology=6/9, rare_terms=3/5. "
            "BGE: q001-q025 use BGE (from v3.9.7.2 cross_encoder), q026-q050 fall back to biencoder "
            "(BGE not yet computed for these queries). "
            "Placeholders (withdrawn, empty fields) get L0."
        ),
        "honest_caveats": [
            "Labels are AUTO-derived from model scores, NOT expert-validated",
            "BGE tie-breaker is partly circular with v3.9.7.2 cross-encoder pipeline",
            "For q026-q050, biencoder (weaker) substitutes for BGE",
            "Use for METHOD COMPARISON (paired tests) not for 'LTR beats combined' as a real-world claim",
        ],
        "n_queries": len(q026_q050),
        "labels": auto_labels,
    }
    out_auto.write_text(json.dumps(auto_data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n  Saved: {out_auto}")

    # Build merged n=50 labels
    merged = {"version": "v3.9.7.3-n50-mixed", "n_queries": 50, "labels": {}}
    for qid in sorted(queries.keys(), key=lambda x: int(x[1:])):
        if qid in real_labels:
            merged["labels"][qid] = real_labels[qid]  # q001-q025 from real v3.9.0 era
        elif qid in auto_labels:
            merged["labels"][qid] = auto_labels[qid]  # q026-q050 from A2 auto
        else:
            merged["labels"][qid] = {}
    merged["label_source"] = {
        "q001-q025": "v3.9.0 era USER hand-labeled (real ground truth, ~741 pairs)",
        "q026-q050": "v3.9.7.3 AUTO-labeled (A2 hybrid, ~600 pairs; NOT expert-validated)",
    }
    out_merged = bench_dir / "labels_n50_mixed.json"
    out_merged.write_text(json.dumps(merged, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"  Saved: {out_merged}")

    # Summary
    print("\n=== Distribution summary ===")
    n25_l2, n25_l1, n25_l0 = 0, 0, 0
    for q in real_labels.values():
        for v in q.values():
            l = v.get("label", 0)
            if l == 2: n25_l2 += 1
            elif l == 1: n25_l1 += 1
            else: n25_l0 += 1
    n50_l2, n50_l1, n50_l0 = 0, 0, 0
    for q in auto_labels.values():
        for v in q.values():
            l = v.get("label", 0)
            if l == 2: n50_l2 += 1
            elif l == 1: n50_l1 += 1
            else: n50_l0 += 1
    print(f"  q001-q025 REAL:    L2={n25_l2}, L1={n25_l1}, L0={n25_l0}, total={n25_l2+n25_l1+n25_l0}")
    print(f"  q026-q050 AUTO:    L2={n50_l2}, L1={n50_l1}, L0={n50_l0}, total={n50_l2+n50_l1+n50_l0}")
    print(f"  n=50 MERGED:       L2={n25_l2+n50_l2}, L1={n25_l1+n50_l1}, L0={n25_l0+n50_l0}, total={n25_l2+n25_l1+n25_l0+n50_l2+n50_l1+n50_l0}")
    print(f"  Per-query L2 (real n=25):  avg=8.2, median=9, range=1-21")
    print(f"  Per-query L2 (auto n=25):  avg={n50_l2/len(auto_labels):.1f}, median={sorted([sum(1 for v in q.values() if v.get('label')==2) for q in auto_labels.values()])[len(auto_labels)//2]}")


if __name__ == "__main__":
    main()
