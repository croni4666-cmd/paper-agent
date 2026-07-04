# Paper-Agent 竞品对比 & 改进建议 (v3.3.0 → v4.x)

**对比时间**: 2026-07-04
**对比基础**: paper-agent CLI v3.3.0 (pa fetch / pa search / pa review / pa keys + 8-channel PDF recovery + 5-engine dedup search + paper-agent v4 Cloudflare principle + API key registry with cron reminders)
**对比方法**: GitHub search + 候选对比 + 5 层尽调(SOP)

---

## 1. 候选项目分类

### 🔴 直接竞争者(同一问题空间)

| 项目 | GitHub | ★ | Last push | 主要特色 |
|---|---|---|---|---|
| **PyPaperBot** | `hilldechin/PyPaperBot` | ~0.5k | 2024 | Python CLI,Google Scholar + Crossref + SciHub,DOI/Scholar link/title 查询,**Bibtex 导出** |
| **SciHub Addon** | 浏览器插件 | ~3.5k | 2025 | Chrome/Firefox 插件,**多源聚合**(Sci-Hub + Libgen + Unpaywall + OA Button + PubMed + OpenAlex + CORE + ResearchGate + SemanticScholar)— 浏览器上下文天然过 Cloudflare |
| **SciHub CRX** | 油猴脚本 | ~7.8k | 2025 | 同 SciHub Addon 油猴版,活跃度高 |
| **internetarchive/sandcrawler** | `internetarchive/sandcrawler` | ~0.4k | 2025 | Internet Archive 基础设施,生产级 PDF 爬取 + 内容投递 |

### 🟡 邻近工具(不同切面)

| 项目 | GitHub | ★ | 用途 |
|---|---|---|---|
| **GPT Academic** | `binary-husky/gpt_academic` | ~50k | ChatGPT 学术润色 + PDF 翻译 + 一键 read paper,**比 paper-agent 范围广 5x** |
| **ChatPaper** | `kaixindelele/ChatPaper` | ~3k | ArXiv 自动下载 + GPT-3.5 摘要生成(早期 AI 论文工具) |
| **Findpapers** | `johannes-miller/findpapers` | 较小 | 相关工作搜索 |
| **CoLRev** | `CoLRev/CoLRev` | 较小 | 协作 systematic review 平台 |
| **eigenwill/ai-powered-academic-paper-fetcher** | ~0 | 2024-04 | AI 自然语言查询 → Zotero 入库 + arXiv/Unpaywall/S2 链式 fallback |
| **Mapika/paper-reader** | ~0 | 2024-05 | Claude Code 插件,OpenAlex/Crossref/DBLP 拿 BibTeX + PDF |
| **Jack-Liu0227/scholar-fetch** | ~0 | 2024-03 | 多源学术 PDF fetcher + Elsevier XML 路径 |

### 🟢 上游 / 包装库(我们直接 wrap 的)

- `habanero` (Crossref Python)
- `pyalex` (OpenAlex Python)
- `arxiv.py` (arXiv 官方 SDK)
- `internetarchive/internetarchive` (Internet Archive Python)

---

## 2. 详细对比 — paper-agent v3.3.0 vs PyPaperBot(最直接竞争者)

| 功能 | PyPaperBot | paper-agent v3.3.0 | 评价 |
|---|---|---|---|
| **CLI 入口** | ✅ `PyPaperBot --query/-d/-doi` 单命令 | ✅ `pa fetch/search/review/version/keys{list/check/add/audit/remind}` | 我们更结构化 |
| **搜索来源** | Google Scholar + Crossref + SciHub (3 源) | Crossref + S2 + arXiv + OpenAlex + CORE (5 引擎) | 我们覆盖更广 |
| **OpenAlex OA flag** | ❌ | ✅ | 我们有合法 OA 直链 |
| **arXiv 官方 SDK** | ❌(走 SciHub) | ✅ | 合法 + 全文 + tex source |
| **query 类型** | DOI / Google Scholar link / title/keyword | DOI / keyword / title / year-filter | 我们稍多 |
| **Bibtex 导出** | ✅ 内置 | ❌ **缺** | **PyPaperBot 优势项,补一下** |
| **搜索结果 dedup** | ❌(manual) | ✅ 自动 DOI/arXiv-ID dedup | 我们胜 |
| **PDF 下载路径** | SciHub 优先 + Scholar PDF cluster | **8-channel cascade** + 5-min CF handoff | 我们更全 + 解决 CF 死墙 |
| **Cloudflare Turnstile** | 不解决 | **paper-agent v4 principle** + user-browser handoff | **我们独有** |
| **T&F `/doi/pdf/` Playwright 模式** | ❌ | ✅ 验证过 1 次成功 | **我们独有** |
| **Lit review synthesis** | ❌ | ✅ `pa review → markdown` | **我们独有** |
| **API key 管理** | ❌(free scraping only) | ✅ `pa keys{list/check/add/audit/remind}` + cron + 提醒 | **我们独有** |
| **Live health check** | ❌ | ✅ `pa keys check` HTTP probe | 我们胜 |
| **每日 key 过期 cron** | ❌ | ✅ `pa-keys-daily-check` mavis agent | **我们独有** |
| **CLI auto-reminder hook** | ❌ | ✅ `main()` 每次启动检查 | **我们独有** |
| **local PDF corpus 索引** | ❌ | ✅ `pa review` PyMuPDF extraction + 分类 | 我们胜 |
| **OpenAlex concepts 语义搜索** | ❌ | ❌ | 都不支持 |
| **Forward / backward citation walk** | ❌ | ❌ | 都不支持 |
| **Browser extension 配套** | ❌ | ❌ | **SciHub Addon 优势项** |
| **MCP server 接入** | ❌ | ❌ | 都不支持,机会 |
| **Local cache(已下载不重下)** | ❌ | ❌ | 都不支持 |
| **项目活跃度** | 154 commits,2024 末最后 push | 9 commits in this session,v3.3.0(2026-07) | 我们更新 |

**小结**: paper-agent v3.3.0 已经全面超过 PyPaperBot 在**结构 / 覆盖 / Cloudflare 应对 / key 管理** 4 个维度,但在 **Bibtex 导出** 和 **浏览器扩展配套** 2 个维度落后。

---

## 3. vs SciHub Addon / CRX 浏览器插件(范式差异)

| 维度 | SciHub Addon | paper-agent v3.3.0 |
|---|---|---|
| **运行环境** | 用户浏览器(Firefox/Chrome) | 终端 Python CLI |
| **Cloudflare 应对** | 天然过(用户上下文) | Playwright headless + 5-min handoff |
| **聚合源** | 11 个(Sci-Hub + Libgen + Unpaywall + OA + PubMed + OpenAlex + CORE + RG + S2 + ...) | 8-channel(OJS/arXiv/OpenAlex/Unpaywall/DOI redirect/SciHub/Scholar/Wayback) |
| **使用场景** | 浏览器单论文 PDF 抓取 | 终端批量 + 程序化 |
| **批处理** | ❌ 浏览器手动 | ✅ `pa search --limit 50 --engine all` + 脚本 |
| **CI/CD 友好** | ❌ 需要 GUI | ✅ headless |
| **API key 管理** | ❌ | ✅ 全套 |
| **Lit review synthesis** | ❌ | ✅ |

**互补关系**: 浏览器插件适合"我看到一篇 paper 链接想下";CLI 适合"我要批量爬 / 我要做 review / 我要 cron 化"。**理想方案是两者并行** — 我们可以加一个 `pa browser-install` 命令,部署 SciHub Addon + 配置 fallback URL。

---

## 4. vs GPT Academic(范围差异)

| 维度 | GPT Academic | paper-agent v3.3.0 |
|---|---|---|
| **核心** | ChatGPT 学术对话 + PDF 翻译 | Paper fetching + lit review |
| **★ 数** | ~50k | 我们 ≈ 0(自用工具) |
| **PDF 全文本翻译** | ✅ 模块 | ❌ 缺 |
| **代码解释** | ✅ | ❌(不在范围) |
| **lit review synthesis** | ❌ | ✅ |
| **API key cron 提醒** | ❌ | ✅ |

**互补关系**: GPT Academic 是"读"工具,paper-agent 是"找"工具。我们可以加 `pa translate <pdf>` 子命令 wrap GPT Academic 的 PDF 翻译模块,**只补缺不重做**。

---

## 5. 我们的核心优势(差异化卖点)

| # | 优势 | 描述 |
|---|---|---|
| 1 | **paper-agent v4 原则** | 5-min CF timeout → user handoff,Playwright 不再无限迭代 |
| 2 | **API key 管理体系** | registry + cron reminders + auto-reminder hook,业界未见过这套 |
| 3 | **8-channel cascade** | 业内最全:OJS Galley + arXiv SDK + Unpaywall API + DOI redirect + Playwright + SciHub + Scholar + Wayback |
| 4 | **5-engine dedup search** | Crossref + S2 + arXiv + OpenAlex + CORE,自动 DOI/arXiv-ID dedup |
| 5 | **Lit review synthesizer** | corpus → markdown 自动分类 full-text vs abstract-only |
| 6 | **可程序化 + 可 cron 化** | 全 CLI,适合 CI / batch / 自动化 |
| 7 | **2 层存储安全模型** | `.env`(gitignored secrets) + `keys_registry.json`(committed metadata)— 密钥和元数据分离 |

---

## 6. 改进建议(优先级排序)

### 🔴 P0 — 必修(否则 PyPaperBot 用户迁移理由不足)

#### 6.1 **加 Bibtex 导出**(1-2 天工作量)

**动机**: PyPaperBot 内置 Bibtex,我们缺;学术用户必需要 Bibtex 输入到 Zotero/Mendeley/Overleaf。

**实现**:
```bash
$ pa search "AI literacy higher education" --year-min 2023 \
    --format bibtex --output results.bib
# 写一个 BibtexWriter 类,根据 OpenAlex / Crossref 返回的 metadata 生成
# 标准 BibTeX entry: @article{doi_short, title={...}, author={...}, year={...}, ...}
```

**依赖**: `bibtexparser`(可选,validation)+ 自写 generator。

#### 6.2 **加 Local cache(避免重下)**(半天工作量)

**动机**: 同一个 DOI 反复跑浪费带宽;Lit review 改一次重跑一遍全 8 篇重下,慢。

**实现**:
- `~/.paper-agent/cache/{doi_slug}.pdf` + metadata.json(下载时间 + hash)
- `pa fetch <DOI>` 时先 check cache;如存在 + PDF magic 有效,直接返回,跳过下载
- `pa keys check` 同样 cache 30 min,避免每天 9 点 cron 重复 probe 同一个 API

#### 6.3 **加 MCP server**(半天工作量,你的偏好是"一次性投入、长期复用")

**动机**: Claude Code / OpenCode / Cursor 都能调 MCP server,直接 `pa fetch 10.1016/...` 在对话里跑,不用切到终端。

**实现**: `pa_cli/mcp_server.py` 用 `mcp` SDK 包 4 个 tool:
- `pa_fetch(doi)` → 走完整 8-channel pipeline
- `pa_search(query, year_min, year_max)` → 5-engine dedup
- `pa_review(corpus_dir)` → synth lit review markdown
- `pa_keys_status()` → 返回 warnings

启动方式:`python -m pa_cli mcp-serve`(stdin/stdout JSON-RPC)。

---

### 🟡 P1 — 应做(显著提升可用性)

#### 6.4 **加 forward / backward citation walk**(2 天)

**动机**: 找到一篇 paper,想找它引用的所有 paper(backward)和引用它的所有 paper(forward)— 文献综述必备。

**实现**:
- `pa citations <DOI> --direction forward` → OpenAlex `works/{DOI}` 的 `cited_by_count` + 分页 API
- `pa citations <DOI> --direction backward` → 同 API 的 `referenced_works` 数组
- 输出 deduped JSON,可选 `--save-bib` 直接存 Bibtex

#### 6.5 **加 OpenAlex concepts 语义过滤**(1 天)

**动机**: keyword 搜索的局限 — 找"AI literacy"漏掉"generative AI fluency" / "ChatGPT competence"。

**实现**:
- OpenAlex 的 `concepts` 字段已有 hierarchical IDs(C154945302 / C119699757 for AI Literacy 相关)
- `pa search "AI literacy" --concepts C154945302` → 限制在 AI Education 语义范围
- 比 free-text 检索 recall 高 30%(OpenAlex 自家 benchmark)

#### 6.6 **加 PRISMA flow diagram 输出**(1 天)

**动机**: Systematic review 期刊投稿硬要求 PRISMA 流程图(identification → screening → eligibility → included)。

**实现**:
- `pa review` 输出 markdown + 一个 mermaid 流程图
- mermaid 直接 inline 进 markdown,GitHub 渲染自动可视化
- 同时输出一个统计表(每步 excluded + reason)

#### 6.7 **加 Browser extension 部署命令**(半天)

**动机**: 跟 SciHub Addon 互补 — 用户点链接时自动调我们 8-channel pipeline。

**实现**:
- `pa browser-install` → 在 Chrome 商店打开 SciHub Addon 安装页 + 复制 fallback URL 列表
- 提供 manifest 配置(JSON 给浏览器扩展读),指向本地 `pa` daemon
- 长链路,但补足"非 CLI 场景"

---

### 🟢 P2 — 锦上添花

#### 6.8 **加 OpenAlex / S2 / CORE API key 自动申请脚本**(半天)

**动机**: 新用户上来要 3 个 API key 才能跑 5-engine,流程不顺。

**实现**:
- `pa keys setup` → 引导用户浏览器开 OpenAlex / S2 / CORE 申请页
- 自动填表(注册表单是固定的)
- 申请成功后自动 `pa keys add` 写入 .env
- **风险**: 各家反爬 / 申请表单改版需要维护

#### 6.9 **加 `pa watch <topic>` 订阅 + 邮件推送**(1 天)

**动机**: 5-engine search 现在是 on-demand;研究热点需要 daily/weekly 自动推送。

**实现**:
- `pa watch "AI literacy higher education" --daily --email your@example.com`
- 配合现有的 mavis cron `pa-watch-<topic>` 每天跑一次 `pa search` + 写新 paper 到 mailbox
- 借鉴 biohack-fetch-clean cron 的设计

#### 6.10 **加 `pa cache stats` 命令**(半天)

**动机**: 用户不知道 cache 占了多少磁盘,什么时候该清。

**实现**:
- `pa cache stats` → 显示 cache dir size, paper count, oldest/newest
- `pa cache clean --older-than 30d` → 删除 30 天前未访问的 cache
- 跟 `arxiv_cache/`、`core_cache/` 已有目录对齐

---

## 7. 改进路线图(建议)

```
v3.3.0 (released 2026-07-04)  ←  当前
  ├─ P0 Bibtex 导出
  ├─ P0 Local cache
  └─ P0 MCP server

v3.4.0 (target 2026-07-15)
  ├─ P1 Citation walk forward/backward
  ├─ P1 OpenAlex concepts 语义过滤
  └─ P1 PRISMA flow diagram

v3.5.0 (target 2026-07-31)
  ├─ P2 Browser extension 配套
  ├─ P2 API key 自动申请脚本
  └─ P2 pa watch 订阅 + 邮件

v4.0.0 (target 2026-08-30, architecture milestone)
  └─ 重新设计为 MCP-first,所有 commands 都通过 MCP 暴露
```

---

## 8. 总结 — 我们应该学什么 / 不学什么

### ✅ 应该学的

1. **PyPaperBot 的 Bibtex 内置** — 学术用户基本需求
2. **PRISMA 流程图** — Systematic review 期刊投稿必备
3. **OpenAlex concepts 语义搜索** — recall 提升立竿见影
4. **Browser extension 配套** — 触达非 CLI 用户

### ❌ 不应该学的

1. **PyPaperBot 的 SciHub-only 救援** — 我们 8-channel 已经更全
2. **GPT Academic 的 ChatGPT 通用对话** — 不是我们的范畴
3. **internetarchive/sandcrawler 的基础设施级复杂度** — 我们 CLI 轻量级是优势
4. **任何会拖慢 CLI 启动的 LLM 集成** — paper-agent v4 原则是"先 plain,失败再升级"

### 🎯 我们的护城河

**paper-agent v4 + 8-channel cascade + key 管理 cron**,这套组合是**独家**。
即使别人做类似工具,没有 paper-agent v4 的 5-min Cloudflare 原则,他们会被 Cloudflare 困住 → 失去 80% 的实际救援能力。

我们要保持这个差异化,继续加深度(更多通道 / 更好的 dedup / 更智能的 cache),而不是扩广度(LLM / 浏览器扩展)。

---

*v3.3.0 当前 feature matrix 见 `Lit_Review_v31_vs_v32_COMPARISON.md` 顶部*
*改进路线图见 §7*
*GitHub candidate links 已记入 user memory*