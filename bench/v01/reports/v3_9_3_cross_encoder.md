# v3.9.3 Cross-encoder (BGE-reranker) Report

> Generated 2026-07-13 by `pa_cli/cross_encoder.py` per ROADMAP [P0-7].
> Compares biencoder-only (v3.9.0) vs biencoder → BGE-rerank (v3.9.3) on 25 v3.9.0 queries.

## Method

- **Biencoder baseline**: SentenceTransformer('all-MiniLM-L6-v2') cosine on (query, candidate) — no token interaction
- **BGE-rerank (new)**: BAAI/bge-reranker-base, XLM-RoBERTa-base + classification head, L×L attention across query+candidate
- **Pipeline**: take biencoder top-30 → cross-encoder rerank → final ranking
- **Model size**: 1.06 GB (F32, 278M params)
- **CPU inference**: ~50-100ms per (query, candidate) pair; top-30 rerank ~2-3s per query

## Side-by-side metrics (n=25 queries)

| Method | NDCG@10 | Recall@10 | Precision@10 |
|---|---:|---:|---:|
| biencoder (v3.9.0 baseline) | 0.7205 | 0.6683 | 0.4680 |
| bge-rerank (v3.9.3 new) | 0.6928 | 0.6569 | 0.4560 |
| **Δ (bge - biencoder)** | **-0.0277** | **-0.0114** | **-0.0120** |

## Per-query breakdown

| Query | biencoder NDCG@10 | bge-rerank NDCG@10 | Δ |
|---|---:|---:|---:|
| q004 | 0.4386 | 0.7563 | **+0.3177** |
| q007 | 0.6410 | 0.9576 | **+0.3166** |
| q015 | 0.5119 | 0.7645 | **+0.2526** |
| q022 | 0.6434 | 0.8078 | **+0.1644** |
| q006 | 0.6368 | 0.7906 | **+0.1538** |
| q024 | 0.4220 | 0.5709 | **+0.1490** |
| q008 | 0.8487 | 0.9783 | **+0.1296** |
| q003 | 0.7090 | 0.8090 | **+0.1000** |
| q020 | 0.6806 | 0.7252 | **+0.0445** |
| q021 | 0.7519 | 0.7942 | **+0.0423** |
| q025 | 0.7310 | 0.7473 | **+0.0163** |
| q011 | 0.8845 | 0.8842 | **-0.0003** |
| q014 | 0.5958 | 0.5774 | **-0.0184** |
| q023 | 0.8353 | 0.8148 | **-0.0205** |
| q018 | 0.6905 | 0.6314 | **-0.0591** |
| q017 | 0.7111 | 0.6264 | **-0.0847** |
| q009 | 0.5882 | 0.4954 | **-0.0928** |
| q016 | 1.0000 | 0.8438 | **-0.1562** |
| q010 | 1.0000 | 0.8098 | **-0.1902** |
| q001 | 0.5373 | 0.3458 | **-0.1915** |
| q005 | 0.7641 | 0.5417 | **-0.2224** |
| q013 | 0.7441 | 0.5044 | **-0.2398** |
| q019 | 0.8905 | 0.5921 | **-0.2984** |
| q012 | 0.8350 | 0.4471 | **-0.3879** |
| q002 | 0.9219 | 0.5050 | **-0.4169** |

## 3-tier honest audit (per MEMORY.md discipline)

- ✅ **Verified on real data**: pipeline runs end-to-end on 25 v3.9.0 queries, model loaded from local cache
- ✅ **Verified architecture**: BGE-reranker inference works, smoke test passed (irrelevant=0, relevant=0.95)
- ⚠️ **Δ NDCG@10 = -0.0277 on n=25**: per memory discipline 'Don't overclaim n<100 metric deltas', treat as noise estimate
- ❌ **NOT a 'finding'**: single point estimate, no significance test, no holdout

## 5-check Global Rule audit

1. ✅ Runs for $0 (one-time 1.06 GB local download via clash proxy, no per-call API)
2. ✅ No hosted service
3. ✅ Maintenance: ~250 LOC new in pa_cli/cross_encoder.py
4. ✅ No publish obligation
5. ✅ Free-tier degradation: if BGE download fails, system falls back to bi-encoder-only rerank

## Layer architecture

Cross-encoder sits at **Layer 3 (Rerank)** as the second-stage reranker after bi-encoder.
Pipeline: `bi-encoder top-30 → BGE-rerank → final top-K`
