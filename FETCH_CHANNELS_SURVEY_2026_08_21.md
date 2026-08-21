# Paper-Agent Fetch 渠道多元化调研报告 (A+B)

**日期**: 2026-08-21
**目的**: 对比 paper-agent 现有 9 个 fetch channels, 找出可新增的合法 / 半合法 PDF 渠道
**方法**: Cross-search-verify (双轨 web_search + 补集再搜)
**对比基准**: paper-agent v3.9.21.0

---

## Executive Summary

调研了 **12 个候选 PDF 渠道**, 6 个有公开免费 API 值得集成, 4 个推荐在 v3.9.22+ 加进 paper-agent。

**Top 4 推荐** (按 ROI 排序):
1. **Semantic Scholar `openAccessPdf`** — 投入 30 行, 收益覆盖 ~30% 论文
2. **bioRxiv/medRxiv** — 投入 80 行, 收益 ~50K 论文 (生物医学 preprint)
3. **OSF Preprints** — 投入 60 行, 收益 PsyArXiv/SocArXiv/EarthArXiv 25+ 学科
4. **CORE (re-add)** — 投入 100 行, 收益 36M+ full text (re-add v3.9.11.1 误删)

---

## A 集 (Round 1+2 双轨独立确认, ⭐⭐⭐ 高信任)

### A.1 Semantic Scholar `openAccessPdf` 字段
**Sources**: 5+ 独立资料 (Agents365 paper-fetch, 4Born/paper-fetch, dev.to 综述, S2 官方 API docs, Apify)

| Item | Value |
|---|---|
| **API URL** | `https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}?fields=openAccessPdf,externalIds` |
| **Method** | GET, JSON |
| **Auth** | 无 key: 100 req/5 min; `x-api-key: $S2_API_KEY`: 1 RPS |
| **返回字段** | `openAccessPdf.url` (PDF 直链) + `isOpenAccess` (bool) + `externalIds` (含 ArXiv/PMC/DOI) |
| **覆盖** | 200M+ papers, 跨学科 |
| **成功率** | ~30% papers 有 openAccessPdf (per multiple sources) |
| **法律** | ✅ 合法 (S2 由 Allen Institute 维护, 数据来源合规) |
| **paper-agent 现有** | ❌ `pa search` 用 S2, 但 `pa fetch` 没用 S2 openAccessPdf 字段 |
| **集成成本** | ⭐ 极低 (~30 行 + 5 行 test) |
| **建议版本** | v3.9.22.0 (MINOR) |

### A.2 bioRxiv / medRxiv API
**Sources**: 4+ 独立资料 (biorxiv-database GitHub skill, lobehub biorxiv API guide, ropensci medrxivr R package, apis.io OpenAPI spec)

| Item | Value |
|---|---|
| **API URL** | `https://api.biorxiv.org/details/{server}/{DOI}/na/json` 或 `https://api.medrxiv.org/details/...` |
| **Method** | GET, JSON |
| **server** | `biorxiv` 或 `medrxiv` |
| **DOI 模式** | `10.1101/*` (biorxiv), `10.1101/*` (medrxiv, 同一 prefix) |
| **Auth** | 无需 key, 无正式 rate limit |
| **返回字段** | `link_pdf` (PDF 直链) + `title` + `authors` + `abstract` + `category` + `date` + `version` |
| **PDF URL pattern** | `https://www.biorxiv.org/content/{version}.full.pdf` |
| **覆盖** | 200K+ biorxiv + 50K+ medrxiv (合计 ~250K preprints) |
| **法律** | ✅ 合法 (CSHL 维护, CC-BY 协议) |
| **paper-agent 现有** | ❌ 完全没接 |
| **集成成本** | ⭐⭐ 低 (~80 行 + 10 行 test) |
| **建议版本** | v3.9.22.0 (MINOR) |

### A.3 CORE API
**Sources**: 5+ 独立资料 (CORE 官方 docs, dev.to CORE API 综述, data.clawrxiv, publicapis.io, Nature Scientific Data 论文)

| Item | Value |
|---|---|
| **API URL (v3)** | `https://api.core.ac.uk/v3/works/{doi}` (单条) 或 `https://api.core.ac.uk/v3/search/works?q={doi}` |
| **Method** | GET, JSON |
| **Auth** | `Authorization: Bearer YOUR_API_KEY` (free, register at core.ac.uk/services/api) |
| **返回字段** | `downloadUrl` (PDF 直链) + `title` + `authors` + `year` + `doi` + `abstract` |
| **覆盖** | 260M+ metadata, 36M+ full text, 14K+ 数据提供方, 150+ 国家 |
| **Rate limit (free)** | 1 batch / 5 single per 10s, 1000/day (注册) / 100/day (未注册) |
| **法律** | ✅ 合法 (Open University 维护, 商业可用付费) |
| **paper-agent 现有** | ⚠️ v3.9.11.1 误删 (理由"OpenAlex 覆盖 4.7M" — 实际 CORE 有 36M full text, OpenAlex 没 full text) |
| **集成成本** | ⭐⭐ 低 (~100 行 + 12 行 test) |
| **建议版本** | v3.9.22.0 (re-add with proper justification) |
| **DEAD-CHECK** | ✅ CORE 仍 active, 2025-08 论文 (Nature Sci Data) 确认 |

### A.4 OSF Preprints API
**Sources**: 4+ 独立资料 (UALIB Cookbook R+Python, OSF 官方, lobehub OSF API, lobehub SHARE API)

| Item | Value |
|---|---|
| **API URL** | `https://api.osf.io/v2/preprints/?filter[doi]={doi}` 或 `https://api.osf.io/v2/preprints/{id}/` |
| **Method** | GET, JSON |
| **provider 列表** | osf, psyarxiv, socarxiv, eartharxiv, engrxiv, medarxiv, nutrixiv, biohackrxiv 等 25+ |
| **DOI 模式** | `10.31219/osf.io/*`, `10.31234/osf.io/*` |
| **Auth** | 无需 key (read), 增加 rate limit 需 token |
| **返回字段** | `attributes.title` + `attributes.doi` + `relationships.primary_file.links.related.href` (PDF API) → `files/{id}/versions/` → `links.download` (PDF 直链) |
| **覆盖** | 2M+ preprints across 25+ 学科 (PsyArXiv psychology, SocArXiv social, EarthArXiv earth) |
| **法律** | ✅ 合法 (Center for Open Science 维护, CC-BY 协议) |
| **paper-agent 现有** | ❌ 完全没接 |
| **集成成本** | ⭐⭐ 低 (~60 行 + 8 行 test) |
| **建议版本** | v3.9.23.0 (MINOR) |

### A.5 BASE (Bielefeld Academic Search Engine)
**Sources**: 4+ 独立资料 (lobehub BASE, BASE OAI 官方, aiagentivo BASE skill, beinstudies)

| Item | Value |
|---|---|
| **API URL** | `https://api.base-search.net/cgi-bin/BaseHttpSearchInterface.fcgi?func=PerformSearch&query={query}&format=json&hits=20` |
| **Method** | GET, JSON |
| **Auth** | **需 IP 注册 (form 申请, 1-2 天审核)** |
| **Search 字段** | `dctitle:`, `dccreator:`, `dcsubject:`, `dcyear:`, `dcrights:open` (OA filter), `dcoa:1` (OA only) |
| **返回字段** | `dclink` (PDF URL), `dcoa:1` (OA flag), `dcrights:open` (license) |
| **覆盖** | 400M+ docs, 11K+ content providers, 60% OA |
| **法律** | ✅ 合法 (Bielefeld University Library 维护) |
| **paper-agent 现有** | ❌ 完全没接 |
| **集成成本** | ⭐⭐⭐ 中 (需 IP 注册, 60 行 + 8 行 test) |
| **建议版本** | v3.9.24.0 (MINOR, gated by user IP registration) |

### A.6 ChemRxiv (Open Engage API)
**Sources**: 3+ 独立资料 (PyPI chemrxiv package, mlederbauer/chemrxiv GitHub, ACS ChemRxiv 介绍)

| Item | Value |
|---|---|
| **API** | Open Engage API (via `chemrxiv` PyPI wrapper, MIT) |
| **Method** | `client.item_by_doi(doi)` + `paper.download_pdf()` |
| **DOI 模式** | `10.26434/chemrxiv-*` |
| **Auth** | 无需 key |
| **覆盖** | 40K+ chemistry preprints |
| **法律** | ✅ 合法 (ACS + Cambridge + RSC + GDCh 联合) |
| **paper-agent 现有** | ❌ 完全没接 |
| **集成成本** | ⭐⭐ 低 (~50 行 + new dep `chemrxiv`) |
| **建议版本** | v3.9.23.0 (MINOR) |
| **Caveat** | 量级小 (40K), 价值在化学 discipline 专精度 |

---

## B 集 (补集再搜后双边确认, ⭐⭐⭐ 高信任)

### B.1 PMC OAI-PMH (already in paper-agent as pmc channel)
**确认**: PMC OAI-PMH v2.0 (2025-09 升级, base URL `https://pmc.ncbi.nlm.nih.gov/api/oai/v1/mh/`)
- paper-agent 走 `eutils.ncbi.nlm.nih.gov/efetch` 已工作, 走 OAI-PMH 是备选
- 价值: 大量 historical + full text bulk download 场景
- **paper-agent 状态**: ✅ 已有, 不需要新增

### B.2 DOAJ (Directory of Open Access Journals)
**确认**: 8,800+ journals, 1M+ articles, OAI-PMH endpoint
| Item | Value |
|---|---|
| **URL** | `https://doaj.org/api/articles/{doi}` (after registration) 或 OAI-PMH `https://doaj.org/oai` |
| **Value** | Metadata only, **无 full text** (跳转 publisher) |
| **法律** | ✅ 合法 |
| **集成价值** | ⭐⭐ 低 (只能拿 metadata, PDF 跳 publisher 还是受 paywall) |
| **建议** | ❌ 不集成 (无 full text 优势) |

### B.3 Zenodo
**确认**: 通用 OA 库, DOI `10.5281/zenodo.*`
| Item | Value |
|---|---|
| **API** | `https://zenodo.org/api/records/{id}` (公开) |
| **Value** | 主要 datasets + some preprints, 跨学科 |
| **法律** | ✅ 合法 (CERN 维护) |
| **集成价值** | ⭐⭐ 中 (datasets 多, papers 少) |
| **建议** | ❌ 不优先 (量小, 主要用户场景是 datasets) |

### B.4 SHARE Research API
**确认**: 200+ 仓储聚合 metadata, base `https://share.osf.io/api/v2`
| Item | Value |
|---|---|
| **Value** | metadata only, **不返 full text** (跳源) |
| **法律** | ✅ 合法 (Center for Open Science) |
| **建议** | ❌ 不集成 (metadata only) |

---

## 各自独有待验 (Round 1/2 only, ⭐⭐ 需 user 二次验证)

### 灰色渠道 (paper-agent 暂没接, 法律风险高)

#### 1. ResearchGate
- 公开 PDF 只在作者上传时, 没 public API
- 灰色: 不少作者上传违反 publisher 协议
- **建议**: ❌ 不集成 (playwright 自动化 + 法律风险)

#### 2. Academia.edu
- 同 ResearchGate, 免费 account 即可下载但有 Premium upsell
- 灰色
- **建议**: ❌ 不集成

#### 3. Sci-Net (sci-net.xyz)
- 没找到稳定 API, 经常换 mirror
- 灰色
- **建议**: ❌ 不集成 (稳定性差)

#### 4. LibGen / Z-Library
- 没 public API, 只有 mirror 列表
- 法律风险高
- **建议**: ❌ 不集成 (已超 Global Rule 边界)

### publisher-aware TDM APIs (ryanchen9732 提到的)
- **Elsevier TDM API**: 合法但需注册, 限于 Elsevier 期刊 (~3000 journals)
- **Wiley TDM API**: 合法但需注册, 限于 Wiley
- **Springer Nature TDM API**: 合法但需注册, 限于 Springer Nature
- **集成价值**: ⭐⭐⭐ 中 (大幅增加覆盖, 但每家都要注册 key, 维护成本高)
- **建议**: v3.10.0+ 评估 (需要 user 提供 institutional credentials)

### OpenAlex 已经有的 `pdf_url` 字段
- `pa search` 用的 openalex 已经有这个字段
- 实际 paper-agent 没用它
- **建议**: 立即优化 v3.9.22.0 (5 行代码)

---

## 集成优先级 + 实施计划

### Priority 1 (v3.9.22.0, MINOR) — Quick wins
- ✅ **S2 openAccessPdf** (~30 行, 30% 论文)
- ✅ **bioRxiv/medRxiv** (~80 行, 250K preprints)
- ✅ **openalex `pdf_url` 字段** (~5 行, 已 fetch 但没用)
- ✅ **CORE re-add** (~100 行, 36M+ full text, re-add v3.9.11.1 误删的)
- **总计**: ~215 行新代码, ~35 行新 test

### Priority 2 (v3.9.23.0, MINOR) — Discipline coverage
- ⭐ **OSF Preprints** (~60 行, 2M+ preprints, 25+ 学科)
- ⭐ **ChemRxiv** (~50 行 + 1 dep, 化学专精度)
- **总计**: ~110 行新代码, ~12 行新 test

### Priority 3 (v3.9.24.0, MINOR, gated) — 需要 user 行动
- ⭐ **BASE** (~60 行, 需 IP 注册, 400M+ docs)
- **总计**: ~60 行新代码, gated by user 提交 IP 注册申请

### Priority 4 (v3.10.0, MAJOR) — Publisher TDM
- ⭐⭐⭐ **Elsevier / Wiley / Springer Nature TDM APIs** (~300 行)
- 需要 user 提供 institutional credentials
- 大幅增加覆盖但需 key 管理

### Priority 0 (DEFERRED, 法律/灰色)
- ❌ ResearchGate, Academia.edu, Sci-Net, LibGen, Z-Library
- 不集成 (Global Rule 边界)

---

## 集成后 paper-agent channel 矩阵

| Channel | v3.9.21.0 | v3.9.22.0 | v3.9.23.0 | v3.9.24.0 | v3.10.0 |
|---|---|---|---|---|---|
| arxiv | ✅ | ✅ | ✅ | ✅ | ✅ |
| pmc | ✅ | ✅ | ✅ | ✅ | ✅ |
| pmc-pdf (jats_to_pdf) | ✅ | ✅ | ✅ | ✅ | ✅ |
| openalex | ✅ | ✅+pdf_url | ✅+pdf_url | ✅+pdf_url | ✅+pdf_url |
| unpaywall | ✅ | ✅ | ✅ | ✅ | ✅ |
| doi_redirect | ✅ | ✅ | ✅ | ✅ | ✅ |
| scihub | ✅ | ✅ | ✅ | ✅ | ✅ |
| annas | ✅ | ✅ | ✅ | ✅ | ✅ |
| cnki | ✅ | ✅ | ✅ | ✅ | ✅ |
| **S2 openAccessPdf** | ❌ | ✅ NEW | ✅ | ✅ | ✅ |
| **bioRxiv/medRxiv** | ❌ | ✅ NEW | ✅ | ✅ | ✅ |
| **CORE** | ❌ | ✅ RE-ADD | ✅ | ✅ | ✅ |
| **OSF** | ❌ | ❌ | ✅ NEW | ✅ | ✅ |
| **ChemRxiv** | ❌ | ❌ | ✅ NEW | ✅ | ✅ |
| **BASE** | ❌ | ❌ | ❌ | ✅ NEW | ✅ |
| **Elsevier/Wiley/SN TDM** | ❌ | ❌ | ❌ | ❌ | ✅ NEW |

**最终 15 个 channels** (从 9 扩到 15), 总覆盖率预估从当前 ~50% (OA + sci-hub fallback) → 80%+ (added 30M+ full text via CORE + 250K bioRxiv + 2M OSF + 30% S2 OA)

---

## 关键发现 & 教训

### 1. **CORE 误删错误** (v3.9.11.1)
- 当时删除理由: "OpenAlex 覆盖 4.7M papers"
- 实际: CORE 有 36M+ full text, OpenAlex 只有 metadata
- **Lesson**: 移除功能前先 cross-check 数据集大小, 不能假设 metadata 覆盖 = full text 覆盖
- **Action**: v3.9.22.0 re-add CORE, with proper justification in CHANGELOG

### 2. **S2 已有但没利用**
- paper-agent 早就有 S2 在 `pa search` 里
- 但 `pa fetch` 没用 S2 的 `openAccessPdf` 字段
- **Lesson**: 任何 metadata API 都应该看 `*Pdf*` 或 `*PDF*` 字段, 不止 metadata
- **Action**: v3.9.22.0 加 S2 openAccessPdf

### 3. **OpenAlex 已有 `pdf_url` 字段没利用**
- 类似 S2 情况
- **Lesson**: 当 fetch 走一个 channel 时, 优先用该 channel 的 `best_oa_location` / `pdf_url` 字段, 不止 cross-ref 找

### 4. **bioRxiv/medRxiv API 完全没接**
- 250K+ preprints, 100% 免费, no key
- 这是 paper-agent 多年漏掉的 source
- **Lesson**: pre-print server 不止 arxiv — bioRxiv, medRxiv, ChemRxiv, OSF 都有各自 API

### 5. **法律灰白分界清晰**
- ✅ 合法: Unpaywall, PMC, arxiv, bioRxiv, CORE, BASE, OSF, ChemRxiv, S2, ChemRxiv
- ⚠️ 灰色: sci-hub, annas, ResearchGate, Academia.edu
- ❌ 违法: LibGen, Z-Library (some jurisdictions)

### 6. **API rate limit 教训**
- 不要从 "1 single/10s" 这种限速 source cascade 多次 (CORE 限速严)
- 默认 mode 优先用 unlimited 源 (arxiv, pmc, openalex, S2 with key)
- 限速源放 explicit `--prefer X` mode

---

## 立即可行动 (Next Steps)

### Step 1: 实施 v3.9.22.0 (4 new channels)
- 写 `pa_cli/s2_pdf_channel.py` (S2 openAccessPdf)
- 写 `pa_cli/biorxiv_channel.py` (bioRxiv/medRxiv)
- 写 `pa_cli/core_channel.py` (CORE re-add)
- 改 `pa_cli/openalex_channel.py` (用 pdf_url 字段)
- 改 `pa_cli/cli.py` (--channels 默认 + channel_to_prefer)
- 改 `pa_cli/fetch.py` (cascade 集成)
- 写 tests (~35 行)
- 写 CHANGELOG + ROADMAP
- 5 篇真实 DOI e2e 验证

### Step 2: User 决策点
- [ ] 是 v3.9.22.0 MINOR (4 channel) 还是 v3.9.22.x PATCH series (1 channel at a time)?
- [ ] 是否要 (a) 立即把 pat 推 v3.9.20.0 + 20.1 + 21.0 然后我做 v3.9.22.0; (b) 等所有 4 channel 完了一起做 v3.9.22.0?
- [ ] 是否要尝试 push v3.9.21.0 release page (PATCH bump 通常不单独 release, 3.9.22.0 一起)?

### Step 3: 进一步 (v3.9.23.0)
- OSF Preprints
- ChemRxiv

### Step 4: User 行动 (gated)
- 申请 BASE IP 注册 (form 提交, 1-2 天)
- 申请 Elsevier/Wiley/SN TDM API 凭证 (需 institutional email)

---

**报告写于**: 2026-08-21
**下次更新**: 实施 v3.9.22.0 时
**相关文件**:
- `CHANGELOG.md` (待 v3.9.22.0 更新)
- `ROADMAP.md` (待 v3.9.22.0 更新)
- `pa_cli/fetch.py` (待集成新 channel)
- `pa_cli/cli.py` (待更新 default --channels)
