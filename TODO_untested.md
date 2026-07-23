# paper-agent v3.1 — 发布说明 + TODO 路线图 (ARCHIVED)

> **⛔ ARCHIVED 2026-07-23**: This document is from the **v3.1 era (2026-07-03)** —
> the very first version of paper-agent as a Python package. All 5 TODO items
> listed below were **shipped long ago** (most by v3.9.0, all by v3.9.7.4).
> Kept for historical reference only.
>
> **Current state** (v3.9.11.3, 2026-07-23):
> - v3.1 item 1.1 (OpenAlex get_by_doi timeout wrap): shipped in v3.9.5
> - v3.1 item 1.2 (真研究方向 topic config + 跑一次): shipped via `pa project` phase 1 (v3.9.10.8)
> - v3.1 item 1.3 (`pa` CLI wrapper): shipped in v3.3.0
> - v3.1 item 4.2 (PDFPool 4 缺口): closed across v3.9.5-v3.9.7.6 (CNKI/CORE/Sci-Hub all probed)
> - v3.1 item 4.3 (跨项目 transfer 缺): partially shipped (`pa fetch-batch`, `pa project`,
>   `pa build`); no cron/email push (Global Rule blocks)
>
> See `ROADMAP.md` "Versioned roadmap summary" for full v3.3.0 → v3.9.11.3 history.
>
> For current TODO, see `TODO.md` (slim version, v3.9.11.3 era).

---

# paper-agent v3.1 — 发布说明 + TODO 路线图 (HISTORICAL, original content below)

> **发布日期**: 2026-07-03
> **前一版本**: v3.0 (Phase 5 — relevance ranking + 稳定性 fix, 2026-07-03)
> **本次增量 v3.1**: 3 个真 silent bug 修复 (实测发现)

---

## 🐛 v3.1 修了 3 个 Phase 4/5 真 bug

实测触发的修复 — 不是承诺代码,是真 bug:

### 修复 1: OpenAlex 不再浪费 90s

**修法**: `searchers/openalex.py` 不再 raise `RateLimitError`,直接 `return []`。
**理由**: 之前 raise → 外层 `with_retry(max_attempts=3, max_delay=30)` 跑 3 × 30s = 90s,然后仍然 0 papers 收场。
**改成**: `return []` → `with_retry` 看到 success 不重试 → 立刻下一个 searcher。

### 修复 2: Crossref `year=None` 60% → 1.3%

**修法** (两层 root cause):
- (a) `_extract_year` 加 `created` + `deposited` 兜底 (Crossref 新 record 经常只有这两个字段)
- (b) Crossref search `select=` 列表加 `published-online / issued / published`(原本漏了!)

**影响**: 之前 65.8% year 已知,现在 **98.7%**;Stage 3 通过率 15 → 23 papers,因为年份 check 真能 filter 了。

### 修复 3: EPMC `resultList` (v3.0.1 已修)

EPMC v6.9 把 `responseList` → `resultList`。代码用旧名 forever 返 0。
**修法**: dual-fallback (`data.get('resultList', data.get('responseList', {}))`)。
**剩余问题**: europepmc.org 服务侧仍 connection-drop,server 反爬,不是代码 bug。

---

## 🧪 v3.1 实测成绩

| 维度 | v3.0 | **v3.1** |
|---|---|---|
| 搜索时间 | 74.1s | **64.0s** |
| 真 source diversity | 2 (crossref + openalex) | **3-4** (crossref + S2 + OpenAlex + merged) |
| Year coverage | 65.8% | **98.7%** |
| Stage 3 通过 papers | 15 | **23** |
| Top-1 relevance | 0.302 | 0.296 (不同 run,top 集合稳定) |

跨 source merge 真 work: `crossref+semanticscholar` 出现在 source attribution 里,验证 DOI dedup 真触发 `_merge_paper`。

---

## 🚧 v3.1 仍未修的 (按 ROI 排)

### 1.1 [next,15 行] OpenAlex `get_by_doi` 走的慢路径

OpenAlex search path 修了 90s,但 `get_by_doi` 单 lookup 也调 pyalex,没 timeout wrap,可能 hang。简单套 ThreadPoolExecutor timeout=15s。

### 1.2 [用户验证,15 min] 真研究方向 topic config + 跑一次

screening.py keywords + topic config 全给 AI Education hard-coded。换到用户真研究方向(经济学 / 计算机 / 教育学),stage 1-3 通过率 + rel TF-IDF ranking 是否准,**没测过**。

### 1.3 [cli,~200 行] `pa` 命令行 wrapper

v3.0 的 1.3 优先级,加 `pa search/rank/papers/cite` 子命令。~2h 工作。

---

## 📦 v4.0 (下一个大版本) — 同 v3.0 路线图

### 4.1 [突然发现:**Phase 1 真 work**] 我之前 surface 探错,实际大部分可用

| 模块 | 之前的判断 | 实际 probe 后状态 |
|---|---|---|
| `prisma.py` | 没测 | ✅ `generate_markdown` 真 work (Mermaid PRISMA 图) |
| `quality_scorer.py` | 没测 | ✅ `score_paper` 真 work (7 维 scores) |
| `field_extractor.py` | 没测 | ✅ `extract_from_paper` 真 work (8 维字段抽取) |
| `topic_modeler.py` | 没测 | ✅ `run_nmf` 真 work (NMF 主题聚类) |
| `prompt_improver.py` | 没测 | ⚠️ signature OK 没真跑 |
| `role_reflector.py` | 没测 | ⚠️ signature OK 没真跑 |
| `ml_predictor.py` | 没测 | ❌ 纯 sklearn re-export,没自家逻辑 |

健全探法: 用 `inspect.signature` 列 module 所有 callables,而不仅仅是 `dir(mod)[:5]` 抓 import pollution。

### 4.2 [PDFPool 缺口] 4 个 provider 真不 work

| Provider | 实际状态 | 根因 |
|---|---|---|
| unpaywall | ✅ 真下到 1 篇 644KB | — |
| arxiv | ✅ 真下到 1 篇 2.2MB | — |
| semantic_scholar_pdf | ⚠️ 仅 OA papers 有 | 付费墙必然 None |
| europe_pmc | ⚠️ bug 修了,服务仍 drop | 服务侧 |
| biorxiv_medrxiv | ❌ 任何 UA 403 | server 反爬 |
| scihub | ❌ 15 mirrors fail-fast 真 DOIs | mirrors 都死了 |
| `enable_publisher_direct` step | stub (`pass`) | — |
| `CloakBrowser` opt-in | stub (`pass`) | — |

### 4.3 [完全没做] 跨项目 transfer 缺

- ❌ `--title` 全文 resolve 没写
- ❌ BibTeX export 没写
- ❌ NDJSON output 没写
- ❌ Checkpoint / resume on daemon crash
- ❌ Cron + 自动通知 (邮件 / 飞书)
- ❌ CI / pytest
- ❌ Docker / packaging

---

## 💡 跨项目元方法学 (v3.0/v3.1 累计学到的,长期 transfer)

1. **找 GitHub 仓库优先级**: **名人项目 (habanero s.c.k, pyalex, paper-fetch) > 高 star 250+ 长 commit 500+ > 内容匹配**
2. **能用现有 lib 时别 hand-roll**: wrap habanero/pyalex/arxiv.py,5 个 hand-roll searcher = 重造轮子
3. **production 现实从 production tool README 找**比从 habanero docs 找有用:`%PDF` magic / SSRF defense / 50MB cap / Cloudflare opt-in
4. **修顺序**: ① grep `_legacy_` ② 直接调每个 component ③ 不假设多 source 返同论文 (DOI 实测 0 重叠) ④ 看 lib 内部 retry vs 外层 retry 是否 storm
5. **别太相信你的"未测"假设**: 用 `inspect.signature` 列 module 所有 callables,而不仅仅是 `dir(mod)[:3]` 抓 import pollution
6. **API 响应改字段名时是 silent bug** (`hitCount > 0` 但 `results = []`)。production 上线前必查 hitCount vs results
7. **lib `select=` 限制字段时,默认 select 不一定覆盖**你要用的字段,必查响应实测

(全部已 append 进 `~/.mavis/agents/mavis/memory/MEMORY.md`)

---

## 🎯 你的下一步 (按 ROI)

如果你只挑 3 件事做,挑这 3 件 ROI 最高:

1. **真研究方向 topic config + 跑一次** (验 ranking 在你领域是否准) — 15min
2. **`pa` CLI** (日常用方便) — 200 行,2h
3. **`OpenAlex get_by_doi` 套 timeout 15s** (单 lookup 防御 hang) — 15 行,5min

v3.1 实际把搜索稳定性大幅提升,所谓"4 searcher 多样性"真的出现了(S2 真返 28 papers + dedup merge)。Phase 4/5 真的修干净了。
