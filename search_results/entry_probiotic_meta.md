# Entry Preview — probiotic-multi-strain-2026-08-03-001

> 📄 **同目录还有 JSON 版** `entry_probiotic_meta.json`（机器读用）
> 👉 这个 **Markdown 版是给人看的 source of truth**，JSON 是派生

---

## 元信息

| 字段 | 值 |
|------|----|
| **qid** | `probiotic-multi-strain-2026-08-03-001` |
| **query** | `multi-strain probiotic gut health meta-analysis` |
| **domain** | medical |
| **difficulty** | medium |
| **project** | global |
| **source** | manual-pa-search |
| **n_candidates** | 30 |
| **added_at** | 2026-08-03T20:16:00+08:00 |
| **added_by** | user |
| **schema_version** | v1 |

### Notes（来源说明）

> 来自本对话 2026-08-01 真实 5 轮 search（5 引擎合并去重），top 30 by citations。
> **不刻意重搜**——按 user 指示只用本对话实际看到的论文。
> Candidate 排序 = 客观被引数排序，不挑选。

---

## 📊 Mavis 建议 label 分布

| Label | 含义 | 篇数 | 占比 |
|-------|------|------|------|
| **3** | 高度相关 | 4 | 13% |
| **2** | 相关 | 9 | 30% |
| **1** | 边缘 | 4 | 13% |
| **0** | 不相关 | 13 | 43% |

> **13% 高度相关**——按"multi-strain 严格匹配"算，比较挑剔。整体可用，LTR 训练需要各种 label 分布。

---

## ✍️ User 打分操作指南

| 操作 | 怎么做 |
|------|------|
| **改打分** | 直接改对应行的 `User 打分` 列（数字 0-3 或 `-` = 不确定）|
| **改完告诉我** | "看 entry" → 我读 .md → 同步 .json |
| **跳过** | 留 `-`，最终 `pa sample-pool label` 仍用 Mavis 建议值 |

**Label 含义**：0=不相关 / 1=边缘 / 2=相关 / 3=高度相关（与 Mavis label 同标准，可对比）

**评估场景建议**：
- ✅ **同意 Mavis** → 直接抄 Mavis 数字
- ⚠️ **不同意** → 写你的数字，label_notes 写理由
- ❓ **不确定** → 留 `-`，跳过

---

## 📋 30 Candidates

> 列顺序：# / 标题（截 70 字符） / 年 / 被引 / 期刊（截） / **Mavis L** / **User 打分** / 一句话理由

| # | 标题 | 年 | 被引 | 期刊 | Mavis L | User 打分 | 一句话理由 |
|---|------|---|------|------|---------|----------|----------|
| 1 | Enterotypes of the Human Gut **Mycobiome** | 2023 | 5000 | Nature | 0 | `-` | gut **fungi**，不是 bacterial probiotic |
| 2 | Gut microbiota in human metabolic health and disease | 2020 | 4659 | Nat Rev Microbiol | 1 | `-` | 菌群综述，**不**是 multi-strain |
| 3 | ISAPP consensus on scope of "probiotic" | 2020 | 2091 | NRGH | 1 | `-` | 概念定义，**不**是 multi-strain 实验 |
| 4 | Genus **Alistipes** review | 2020 | 1709 | Front Immunol | 0 | `-` | 单菌属综述 |
| 5 | Microbiota–gut–brain in **neurodegeneration** | 2024 | 1023 | STTT | 0 | `-` | neurodegenerative，**不**是 multi-strain |
| 6 | Anti-Inflammatory Probiotics in Gut Inflammation | 2021 | 896 | Front Immunol | 2 | `-` | probiotics 综述（含多菌株）|
| 7 | ISAPP consensus on **postbiotics** | 2021 | 848 | NRGH | 1 | `-` | 概念定义 |
| 8 | Probiotics Mechanism on Immune Cells | 2023 | 835 | Cells | 2 | `-` | 机制综述（含 multi-strain 提及）|
| 9 | The **gut–liver** axis | 2023 | 644 | Nat Rev Microbiol | 0 | `-` | gut-liver，**不**是 multi-strain |
| 10 | Journey of the Probiotic Bacteria | 2023 | 600 | Microorganisms | 2 | `-` | probiotics 综述（multi-strain 视角）|
| 11 | Probiotics in **Alcoholic Liver** Disease | 2023 | 600 | Front Pharmacol | 0 | `-` | 单一疾病应用 |
| 12 | Role of Probiotics in **Aquaculture** | 2023 | 600 | Zenodo | 0 | `-` | 水产，**不**是 human gut |
| 13 | Gut Microbiota and **Alzheimer's** Disease | 2023 | 600 | Book | 0 | `-` | Alzheimer 应用 |
| 14 | Gut Microbiome and **Metabolic Syndrome** | 2023 | 600 | CRC | 0 | `-` | Metabolic，**不**是 multi-strain |
| 15 | How Probiotics Affect the Microbiota | 2020 | 532 | Front Cell Infect Microbiol | 2 | `-` | probiotics 综述（多菌株）|
| 16 | Probiotics and Microbiota-Gut-Brain (Psychiatry) | 2020 | 341 | Curr Nutr Rep | 0 | `-` | psychiatry 应用 |
| 17 | Probiotic genus **Lactobacillus** review | 2022 | 313 | Front Pharmacol | 1 | `-` | Lactobacillus **单属**，不是 multi-strain |
| 18 | **Multi-Strain Probiotics: Synergy among Isolates** | 2021 | 211 | Biology | 3 | `-` | ⭐ **直接 multi-strain 综述** |
| 19 | In Silico PTML Multi-Strain Discovery | 2025 | 125 | Pharmaceuticals | 0 | `-` | in silico，非 human |
| 20 | Probiotics in **Vaccines** | 2024 | 125 | Vaccines | 0 | `-` | 疫苗应用 |
| 21 | Gut Microbiome and **Hypertension** | 2023 | 125 | NR Nephrol | 0 | `-` | hypertension |
| 22 | **Bifidobacterium longum alone or in multi-strain** | 2023 | 96 | Gut Microbes | 3 | `-` | ⭐ **single vs multi-strain 对比 RCT** |
| 23 | Probiotic supplementation on GI motility | 2023 | 53 | Gut Pathogens | 2 | `-` | 本对话 3 sub-agent 解读过 |
| 24 | **Multi-strain probiotic on anxiety/depression** | 2024 | 49 | Microbiome | 3 | `-` | ⭐ **multi-strain 临床 RCT** |
| 25 | Multi-Strain Inoculation (**Eucalyptus**) | 2026 | 30 | World J Microbiol | 0 | `-` | 植物 |
| 26 | Multi-strain preserves intestinal epithelial | 2025 | 8 | Front Microbiol | 2 | `-` | multi-strain 临床前 |
| 27 | Bifidobacterium in **NAFLD** meta-analysis | 2025 | 8 | IJMS | 2 | `-` | meta-analysis（NAFLD）|
| 28 | Multi-strain probiotic **cheese** | 2021 | 7 | LWT | 2 | `-` | 发酵乳相关 |
| 29 | Multi-strain **LAB** combination | 2025 | 7 | Folia Microbiol | 2 | `-` | multi-strain LAB |
| 30 | **Single vs Multi-Strain on Glycaemic Control (T2D)** | — | 2 | Appl Biosci | 3 | `-` | ⭐ **直接 single vs multi-strain 对比** |

---

## 🟢⭐ 4 篇"高度相关"（Mavis 标 3）— 关键论文

| Rank | DOI | 一句话 |
|------|-----|--------|
| 18 | 10.3390/biology10040322 | **直接 multi-strain 综述** — "Multi-Strain Probiotics: Synergy among Isolates" |
| 22 | 10.1080/19490976.2023.2186098 | **B. longum single vs multi-strain RCT** — 经典对照 |
| 24 | 10.1186/s40168-024-01752-w | **Multi-strain + 脑-肠轴 RCT** — Microbiome 期刊 |
| 30 | 10.3390/applbiosci5010006 | **Single vs Multi-Strain 对比 T2D** |

---

## 🎯 你可以做的 4 件事

### 🟢 A. 改 .md 后告诉 Mavis 同步 .json

直接在 `User 打分` 列填 0/1/2/3 或 `-`，然后说"看 entry"。

### 🟡 B. 用 `pa sample-pool label` 单独覆盖某条

```powershell
python -m pa sample-pool label --qid probiotic-multi-strain-2026-08-03-001 --rank 1 --label 0 --confirm-y
```

### 🟠 C. 全部接受 Mavis 建议

```powershell
cd "G:\minimax - workspace\Paper agent"
python -m pa_cli sample-pool add --from-file search_results\entry_probiotic_meta.json --confirm-y
```

### 🟣 D. 自定义 .json 后 add

直接编辑 `entry_probiotic_meta.json`，改完跑 C。

---

## 📁 文件清单

| 文件 | 大小 | 用途 |
|------|------|------|
| `search_results\entry_probiotic_meta.md` | ~9 KB | **人读 / source of truth** |
| `search_results\entry_probiotic_meta.json` | ~14 KB | **机器读**，`pa sample-pool add --from-file` 源 |
| `search_results\meta_analysis.json` | 45 KB | 5 引擎合并的原始 56 篇 |
