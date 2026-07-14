# paper-agent Benchmark — Personal Back-burner TODO

> User 个人 back-burner 列表,**跟 ROADMAP 区分**:
> - `ROADMAP.md` 是项目状态协议 (有 status transition 规则、Proposed/InProgress/Done 流程)
> - 本文件是 "user 想做但排在后面" 的事项,跟 ROADMAP 不冲突,但**主动推迟到现有 P0/P1 完成之后**
>
> **当前 back-burner 政策 (user 2026-07-15)**:
> 1. 完成现有 ROADMAP P0/P1 (CNKI [P0-9] + fulltext 3 features [P1-12] + n=100/200 expansion [P1-13]) 之前
> 2. **暂不考虑** 重新启用以下两个方案
> 3. 现有 ROADMAP 完成后,有机会再回头优化

## Back-burner items (deferred until existing P0/P1 done)

### 1. [BB-1] LTR (LambdaMART) — 重新评估 & 优化

- **Source**: v3.9.7.3 finding — LTR 输给 combined baseline (Δ = -0.0335 NDCG@10)
- **ROADMAP ref**: [P0-6]
- **Status**: code done, deprecated from default (2026-07-15)
- **Current verdict**: 100 LambdaMART trees on n=50 overfit; auto labels inflate combined baseline more than LTR
- **Re-activation gate** (after existing P0/P1 done):
  - [ ] Have n=200+ real labels (per [P1-13])
  - [ ] Try simpler ranking first: logistic regression / sklearn `RidgeClassifier` with pairwise loss
  - [ ] Try XGBoost ranker (alternative to LightGBM)
  - [ ] Try neural ranker (small transformer with pairwise loss)
  - [ ] Per-class LTR (one LTR per engine: openalex-LTR, crossref-LTR, etc.)
  - [ ] Re-evaluate with held-out test set (not 5-fold CV on same n=50)
- **Estimated time to re-evaluate**: 1-2 days
- **Why de-prioritized now**: LTR 不是 paper-agent 当前 bottleneck,CNKI 中文覆盖 + fulltext features 是更高杠杆

### 2. [BB-2] BGE-rerank — 重新评估 & 替代

- **Source**: v3.9.7.3 finding — BGE 显著差于 bi-encoder (Δ = -0.1064 NDCG@10, p=0.0008)
- **ROADMAP ref**: [P0-7]
- **Status**: code done, deprecated from default (2026-07-15)
- **Current verdict**: BGE-reranker-base (MS MARCO training) 跟 academic retrieval 分布不匹配; abstract-level 输 0.11 NDCG
- **Re-activation gate** (after existing P0/P1 done):
  - [ ] Try alternative cross-encoders on abstract-level:
    - `cross-encoder/ms-marco-MiniLM-L-12-v2` (larger MS MARCO model)
    - `BAAI/bge-reranker-large` (1.7 GB, larger BGE)
    - `BAAI/bge-reranker-v2-m3` (multilingual)
  - [ ] Try academic-domain rerankers:
    - `castorini/monoT5-base-msmarco` (T5-based reranker)
    - `sentence-transformers/ColBERT` (late interaction, more memory but better)
  - [ ] Try BGE on full text (per [P0-8] Layer 7) — current 2000-char truncation 可能不是 BGE 失败原因, 完整 full text 试试
  - [ ] Try hybrid: 0.5*BGE + 0.5*biencoder (per v3.9.7 deferred-to-backlog suggestion)
- **Estimated time to re-evaluate**: 1 day (one-time benchmark across 4-5 models on n=50 mixed labels)
- **Why de-prioritized now**: BGE 不是 bottleneck,CNKI + fulltext 是更高杠杆;且 Wilcoxon 已经显著 negative,需要更强 evidence 才能重新启用

## Not on this list (still in ROADMAP, actively pursued)

- [P0-9] CNKI 6th engine — highest-leverage current work
- [P0-10] n=50 mixed labels — done in v3.9.7.3 ✅
- [P0-11] BGE/LTR deprecation — done as decision ✅
- [P1-12] fulltext 3 features (citation_density, venue_score, cross_encoder) — proposed, in queue
- [P1-13] n=50 → n=100 → n=200 label expansion — proposed, in queue

## Notes for future re-activation

When user comes back to BB-1 or BB-2 (after existing P0/P1 done):
1. Re-read v3.9.7.3 three-tier audit (`bench/v01/reports/v3_9_7_3_three_tier.md`) for context
2. Check if n=200 real labels exist (per [P1-13] gate)
3. Run **paired test with holdout**, not 5-fold CV on same n=50 (per [P1-13] honest framing)
4. **Don't re-litigate** "is this method worth it" — focus on "what's the new evidence, and does it change verdict?"

Last updated: 2026-07-15 (after v3.9.7.3 evaluation)
