# q026-q050 v3 — 共通性扩展到 international (2026-07-14 22:25)

> **v2 → v3 改动**:
> 1. 中文 query 中**有共通性的** (灵活就业 / 综合困境 / 消费心理 / 少子化 / AI 教培) 扩展到国际 — 加国际 anchor + 跨国比较
> 2. **中国特色** 的 (东数西算 / 综艺二次元) 严格保留, 不妥协
> 3. v2 的 difficulty_hint 调整保留
> 4. v2 的 措辞/深化建议保留
>
> **新 MoE 评估预测** (v3 调整后):
> - **真正 international / English-searchable** query: 23 个 (从 16 → 23, +7)
> - **保留中国特色** query: 2 个 (q032 东数西算, q047 综艺+二次元)
> - **part 中国** query: 1 个 (q040 奶茶 — SSB 框架通用 + 品牌 specific)
> - **预估 n=50 后**: openalex 占比可能从 96% → 80-85%, 其他 engine 占比上升, MoE class diversity 提升

---

## v3 中文 query 通用化调整 (7 个)

| id | v2 query | v3 query (通用化) | 共通性 / 保留理由 |
| --- | --- | --- | --- |
| q033 | 灵活就业人数逐年上升对于社会保险的影响 | gig economy workforce growth impact on social insurance systems comparative OECD and China | gig economy + social insurance 是国际议题, OECD 国家都有, 跨国比较有研究 |
| q034 | 中国社会在低 GDP 成长率情况下遇到综合困境会导致最终导向 | low GDP growth + aging + debt crisis combined policy response paths comparative Japan lost decades and current China | "low growth + aging + debt" 综合困境是国际议题, Japan 失落 30 年是核心 anchor |
| q036 | 灵活就业人数稳定逐年上升对于社会消费心理的影响 | gig economy worker consumption behavior savings rate risk preference cross-country | gig worker 消费行为 + 储蓄倾向, 国际有劳动经济学研究 |
| q037 | 中国综合困境 + 日本墨西哥心理变化 | economic decline induced psychological change and behavioral shift comparative Japan lost decades and Mexico crisis social trust | "economic decline → psychological change" 是国际议题, Japan + Mexico 都是 anchor |
| q040 | 中国奶茶经济 (蜜雪, 茶姬, 古茗) 健康影响 | sugar-sweetened beverage (SSB) consumption health effects obesity Chinese cohort, China bubble tea brand case studies | SSB 框架通用, 国际有 SSB 税 + 健康大量研究; China bubble tea 是中国 specific case |
| q046 | 少子化背景下陪伴型机器人依赖心理 | aging society companion robot social attachment rejection comparative Japan South Korea Europe | aging + companion robot 是国际议题, Japan + Korea + EU 都有研究 |
| q049 | AI 教培是否即将被完全取代 | AI tutor K-12 teacher displacement employment evidence cross-country | AI in education + teacher displacement 是国际议题, 跨国比较 |

**保留中国特色** (不妥协):
- q032 东数西算 — 严格中国政策
- q047 综艺 + 二次元游戏 — 中国/亚洲文化 specific

---

## v3 final 25 行

| id   | v3 query                                                                                              | topic_bucket | difficulty_hint |
| ---- | ------------------------------------------------------------------------------------------------------ | ------------ | --------------- |
| q026 | 自然语言处理中对于细致情绪状态的划分，以及情绪转换矩阵 (譬如：羡慕转化成嫉妒再转化成生气等等)            | ml           | technical       |
| q027 | 数据处理中对于文本的情绪连续性与媒体刺激物之间的关系 (譬如：如何提取两者的特征，证明它们的因果关系)    | ml           | technical       |
| q028 | 珀尔的因果图的相关前沿研究                                                                              | ml           | rare_terms      |
| q029 | 我们自己做的 paper agent 如何提升其效能，采用哪些模型                                                   | ml           | methodology     |
| q030 | 表格基础模型的教育应用 (如何降低经济学学生学习数据分析的难度)                                          | ml           | technical       |
| q031 | 新能源汽车销售与国际原油价格的 Granger 因果 / SVAR 检验                                                | econ         | methodology     |
| q032 | 东数西算当前实行情况如何？究竟有多少互联网企业使用这种方案？东数东算的条件成熟吗？                       | econ         | broad           |
| q033 | gig economy workforce growth impact on social insurance systems comparative OECD and China            | econ         | broad           |
| q034 | low GDP growth + aging + debt crisis combined policy response paths comparative Japan lost decades and current China | econ         | broad           |
| q035 | 人工智能究竟是取代劳动力造成大量失业，还是最终会产生大量新的工作岗位 (Acemoglu Restrepo anchor)        | econ         | broad           |
| q036 | gig economy worker consumption behavior savings rate risk preference cross-country                    | cross        | broad           |
| q037 | economic decline induced psychological change and behavioral shift comparative Japan lost decades and Mexico crisis social trust | cross        | methodology     |
| q038 | 终极意义上，人工智能是否会永久改变人类价值观的改变 (AI alignment human values game theory anchor)       | cross        | broad           |
| q039 | 北美基督教是否真的褪色了？马克思韦伯的工作伦理是否仍然支撑当前的美国社会？                              | cross        | rare_terms      |
| q040 | sugar-sweetened beverage (SSB) consumption health effects obesity Chinese cohort, China bubble tea brand case studies | cross        | broad           |
| q041 | 肝豆状核性变的研究综述以及患者生存概率追溯 (Wilson's disease)                                          | bio          | rare_terms      |
| q042 | 干燥综合症的原因以及干燥综合症如何保养 (Sjögren's syndrome)                                            | bio          | rare_terms      |
| q043 | 地中海贫血因子携带者对于身体的影响 (thalassemia trait carrier)                                          | bio          | rare_terms      |
| q044 | 糖前期患者的阻止发展以及回退策略 (prediabetes reversal interventions lifestyle metformin RCT)            | bio          | rare_terms      |
| q045 | 减肥食谱以及断食科学性综述 (intermittent fasting vs calorie restriction weight loss RCT)                | bio          | methodology     |
| q046 | aging society companion robot social attachment rejection comparative Japan South Korea Europe          | social       | technical       |
| q047 | 恋爱综艺节目或者二次元擦边手机游戏 (包括男性和女性) 会促进婚恋吗？机理研究 媒体是否有效 情感分析       | social       | methodology     |
| q048 | 全民基本收入是否会滋生懒汉心理 (UBI Finland Kenya experiment anchor)                                   | social       | broad           |
| q049 | AI tutor K-12 teacher displacement employment evidence cross-country                                   | social       | broad           |
| q050 | 当前社会形态是否比 20 世纪带给人们更多精神疾病 (mental illness prevalence 1990-2020 cohort meta)        | social       | broad           |

---

## v3 评估后预估

| metric | v1 (n=25) | v3 (n=50) 预期 |
|---|---:|---:|
| international/english query | 0 | 23 (q031-q046 通用化后) |
| 中文中国特色 query | n/a | 2 (q032, q047) |
| 预估 openalex 占比 (candidate pool) | 96% | 80-85% |
| 预估 MoE class diversity | 1 engine | 3-4 engines (openalex + arxiv + s2 + crossref) |
| Wilcoxon 显著性 power | 0.20 (n=25) | 0.55+ (n=50) |
| LTR 5-fold CV 稳定性 | n=25 too small | n=50 borderline acceptable |

**结论**: v3 让 n=50 评估有**实质性提升空间**, 不再是 noise

---

## 下一步

**Option A**: 全接受 v3 → 我直接写进 queries.json, 跑 n=50 v4_rerank + 4+2 评估
**Option B**: 微调某些行 → 告诉我 "q033 改 X", "q040 加 Y"
**Option C**: 关于 CNKI 接入 (你说有渠道 + cookies + playwright)
  - C1: 写 ROADMAP [P*-N] CNKI 接入 spec
  - C2: 给我 cookies 怎么传 (PS1 export / .json file / 你直接登录后导出)
  - C3: 实现 cnki_channel.py (类比 pa_cli/fetch.py 的 8-channel cascade, 加 cnki 作为 9th)
