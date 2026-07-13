# paper-agent-bench-v0.1 — baseline 全量报告

**Date:** 2026-07-10
**Pipeline:** 25 queries × 30 candidates = 750 papers
**Abstract coverage:** 84% (626/750 enriched from OpenAlex)
**Labeled by:** Mavis (MiniMax LLM) with title + abstract + venue + year + citations

---

## 总体数字 (25 queries)

| Metric | mean | median | std |
|---|---:|---:|---:|
| recall@5 | 0.071 | 0.067 | 0.086 |
| **recall@10** | **0.182** | 0.222 | 0.146 |
| recall@20 | 0.509 | 0.500 | 0.229 |
| precision@10 | 0.180 | 0.100 | 0.185 |
| precision@20 | 0.228 | 0.200 | 0.194 |
| ndcg@10 | 0.362 | 0.331 | 0.207 |
| ndcg@20 | 0.486 | 0.480 | 0.175 |
| **map@10** | **0.089** | 0.035 | 0.119 |
| success@10 | 0.760 | 1.000 | 0.436 |
| **success@20** | **0.920** | 1.000 | 0.277 |

**一句话**: baseline 排序信号 = 引用数 ≠ 相关性。**top-10 平均只捞到 18% 的真相关**，top-20 才到 50%。

---

## Per-query 拆解

### Recall@10 排名 (好 → 差)

| Rank | Q | Topic | recall@10 | n_rel | 解读 |
|---:|---|---|---:|---:|---|
| 1 | q021 | Acemoglu automation | **0.500** | 6 | Acemoglu 经典论文高被引，pa 排得准 |
| 2 | q011 | FL healthcare | 0.385 | 13 | topic 明确，pa 找到大半 |
| 3 | q015 | Few-shot QA | 0.357 | 14 | LLM 时代热门 |
| 4 | q025 | AI bias education | 0.333 | 3 | topic 集中 |
| 5 | q009 | RCT digital health | 0.300 | 10 | topic 明确 |
| 5 | q024 | Acemoglu Restrepo | 0.300 | 10 | Acemoglu 高被引 |
| 7 | q017 | AI manufacturing | 0.286 | 7 | Industry 4.0 文献多 |
| 8 | q007 | Climate ag adaptation | 0.280 | 25 | topic 非常明确 |
| 9 | q014 | Inequality mobility | 0.267 | 15 | 教育流动性文献多 |
| 10 | q012 | Carbon pricing OECD | 0.250 | 4 | 文献清晰但低被引 |
| 10 | q013 | Protein structure | 0.250 | 4 | transformer 论文少 |
| 10 | q022 | ML labor polarization | 0.250 | 4 | 边界真相关 |
| 13 | q008 | Drug repurposing GNN | 0.222 | 9 | GNN 论文能找到 |
| 14 | q006 | Long-context transformer | 0.111 | 9 | attention degradation 论文埋在后面 |
| 14 | q016 | Gender wage gap | 0.143 | 14 | 经典多但排序乱 |
| 16 | q020 | ChatGPT higher ed | 0.091 | 11 | ChatGPT 论文极多但相关性散 |
| 17 | q023 | Adaptive learning RCT | 0.100 | 10 | RCT 论文少 |
| 18 | q010 | Trust pandemic | 0.083 | 12 | 信任政策论文多但散 |
| 19 | q019 | ITS adaptive | **0.053** | **19** | **19 篇真相关但都散在后面** |
| 20-25 | q001-q005, q018 | K-12 / 早期 | 0.000 | — | 早期 labels 受 title-only 影响 + 真相关都散 |

### 注意: q019 — 19 篇真相关但 recall@10 = 0.053

这是 baseline 排序的**典型问题**：
- query 是 "intelligent tutoring systems adaptive learning algorithms"
- pa 找到 30 篇候选，里面 **19 篇是真相关 (label=2)**
- 但 top-10 几乎全是 "Cybersecurity / IoT / Federated Learning / HCI / Edge Computing" 等高被引的 ML 综述
- 19 篇真相关都在 #14+ 的位置
- **66% 的 candidate pool 是真相关，但 baseline 几乎完全错过**

→ **修正 ranking = 巨大提升空间** (v4 reranker 攻击这个)

---

## 模式观察

### 1. baseline 排序靠"主题热度"而非"query 相关性"

| 现象 | 证据 |
|---|---|
| 高被引综述排前 | q001: #1 ChatGPT for good (5330 cites, MAR) > #15 AI chatbots meta (484 cites, REL) |
| 主题不相关的高被引论文挤占 top-10 | q019: top-5 全是 cybersecurity/edge/IoT 综述, 19 篇真相关在 #14+ |
| 经典目标 paper 排得准 | q021/q024: Acemoglu/Restrepo 论文在 top-10 |

### 2. 真相关"埋底"是常态

平均 recall@10 = 0.18 意味着 **82% 的真相关不在 top-10**。top-20 跳到 51% 意味着 **真相关大部分在 #11-20**。

→ **v4 BM25 词法兜底 + Cross-encoder rerank 的攻击点**:
- BM25 把 query 词 ("intelligent tutoring systems" / "K-12") 加权
- Rerank 拿 query + title 算真相关性，citations 滚

### 3. "K-12" / level-specific 是盲点

- q001 ("K-12 student learning") recall@10 = 0.000
- q018 ("AI education K-12 outcomes") recall@10 = 0.000
- q005 ("UBI labor supply") recall@10 = 0.000 (但 ndcg@10 = 0.000, 8 篇真相关全在 #10 后)

→ baseline **不会按 query 的 level / scope 过滤**，把"高等教育综述"当"K-12 实证"返回

### 4. Recall@5 极低 (0.07)

top-5 几乎全是 popularity 高的泛论文。**precision 集中在 #1-#5** 误把高被引的广义论文当"答案"。

---

## 25 个 query 里的赢家 / 输家

### 赢家 (recall@10 ≥ 0.3)
- q007 climate ag adaptation (0.28, n_rel=25) — topic 非常集中, 大量真相关
- q011 FL healthcare (0.385, n_rel=13) — FL 论文明确
- q014 inequality mobility (0.267, n_rel=15) — 教育流动性文献多
- q015 few-shot QA (0.357, n_rel=14) — LLM 时代热门
- q021 Acemoglu automation (0.5, n_rel=6) — 经典目标
- q024 Acemoglu Restrepo (0.3, n_rel=10) — 同上

### 输家 (recall@10 ≤ 0.1)
- q001 K-12 AI tutoring (0.000, n_rel=2) — 真相关散
- q002 automation gender wage (0.000, n_rel=3)
- q003 VQ retrieval (0.000, n_rel=2)
- q004 BSTS causal (0.000, n_rel=3)
- q005 UBI labor supply (0.000, n_rel=8) — 8 篇真相关全在后面
- q018 AI education outcomes (0.000, n_rel=1) — K-12 难
- q019 ITS adaptive (0.053, n_rel=19) — 19 篇散
- q020 ChatGPT higher ed (0.091, n_rel=11)
- q023 adaptive learning RCT (0.1, n_rel=10)

---

## v4 攻击点 (按 lift 期望排序)

| 模块 | 期望 lift | 攻击哪个失败模式 |
|---|---:|---|
| **BM25 词法** | +15% recall (平均), +30% on rare terms | q019/q005 — 把"K-12"/"tutoring"/"UBI" query 词加权 |
| **Cross-encoder rerank** | +12-18% precision | q001/q018 — 把 5330 引的 ChatGPT 综述排到后面 |
| **Light MoE routing** | +5-10% precision | q010/q023 — 区分 "broad AI" vs "specific subfield" 用不同 expert prompt |
| **PaSa-lite** | +10-15% recall | q005/q019 — query expansion "AI tutoring" → "intelligent tutoring system K-12 adaptive learning outcomes" |
| **LTR lambdarank** | +5-8% NDCG | 整体微调 ranking 权重 |

→ **预期 v4 总 lift**: recall@10 从 0.18 → 0.35+ (大约 +95%), ndcg@10 从 0.36 → 0.55+ (+53%)

---

## 三层诚实验证 (per Mavis discipline)

| 等级 | 内容 |
|---|---|
| ✅ **Verified on real data** | 1. 25 queries 全部跑通 (pa search 5 engines × top-30, dedup → 750) 2. 626/750 abstract 真实从 OpenAlex 反查 (84% 覆盖) 3. eval.py 9 个 metric 真实计算 4. 数字: recall@10=0.18, recall@20=0.51, ndcg@10=0.36 是真 |
| ⚠️ **Code works but unverified on real** | 1. **我的 labels 全靠 title+abstract 主观判断**, LLM bias 大 2. **边界 MAR (6-8 篇每 query) 我猜的**, user spot-check 可能改 10-15% 的 label 3. **少数 query 没用真相关 (n_rel=0)** 因为 label 边界 (例如 q005 我标 8 篇 REL 但 recall@10=0, 可能是我的 n_rel 标错了) |
| ❌ **Hollow / aspirational** | 1. "50 queries benchmark" — 只跑了 25/50, q026-q050 是 user 槽位 2. "Mavis pre-labels" — 是, 但没用 user spot-check 验证 3. "stage 4 全自动" — 是, 但 LLM 读 750 篇的质量参差 |

---

## 撞墙 / 局限

1. **pa search 5 engines 几乎都是 OpenAlex 主导** — 30 篇里 25-30 都只来自 OpenAlex，其他引擎的 contribution 很小（5-10%）。这意味着 25/25 queries 的 candidate pool 几乎 = "OpenAlex top-30 for the query"。
2. **CORE / arXiv / Crossref / S2 没有 abstract fallback** — 只有 OpenAlex 有 abstract 反查，其他 4 个 engine 的 abstract 必须靠原 search result 返回
3. **LLM label bias 不可避免** — 我自己标 750 篇, 系统性偏向 "看到 abstract 标题像 → 标 2" / "完全错 → 标 0"，对边界 MAR 把握不准
4. **n_rel per query 偏少** — 大部分 query 我只标 2-15 篇真相关，q019 标 19 是 outlier。如果 user spot-check 改 30%，n_rel 数字会变，recall/precision 数字也会变

---

## 交付物

- `bench/v01/system_outputs/q001-q025.json` — 750 candidate pool (25 queries × 30 papers)
- `bench/v01/labels.json` — 750 labels (label 0/1/2 + reason)
- `bench/v01/cache/abstracts/*.json` — 2325 OpenAlex 缓存 (含失败记录, 以后 re-run 免重抽)
- `bench/v01/reports/baseline_v0.{json,md}` — 完整 per-query + aggregate 报告
- `bench/v01/_labeling/q001-q025.md` — 25 个 labeling view (人手 spot-check 入口)
- `bench/v01/_batch_run.py` — pa search batch driver (以后 re-run 用)
- `bench/v01/_enrich_only.py` — abstract enrichment driver (缓存复用, 以后 re-run 免重抽)

---

## 下一步 (按 impact 排)

| 选项 | 时间 | 期望 lift |
|---|---|---|
| A. user spot-check labels.json (改 ~10-15% 边界 MAR) | 2-3 hr | 数字稳定, recall/precision 重新校准 |
| B. v4 BM25 词法重排 (不调 LLM) | 30 min | recall@10 0.18 → ~0.30 |
| C. v4 Cross-encoder rerank (Cohere Rerank v3 / BGE) | 1-2 hr | precision@10 0.18 → ~0.30 |
| D. v4 PaSa-lite query expansion (Mavis 扮双代理) | 2-3 hr | recall@10 0.18 → ~0.25 |
| E. 直接上 v4 完整 pipeline (MoE + rerank + BM25 + LTR) | 5-8 hr | recall@10 0.18 → ~0.40+ |

推荐: **先 B → A → C**  — 30 min BM25 看是不是 ranking 排坏, 然后 user spot-check 拿干净 ground truth, 然后上 reranker
