# q026-q050 User-Provided Queries — DRAFT (Mavis brainstorm, 2026-07-14)

> **重要**: 这 25 个 query 是 Mavis 根据 user profile 的 5 大方向 (数据分析 / 经济学 / 金融保险 / 健康营养 / biohack) 草拟的, **不是你的真实研究问题**。请 review + 改 `query` 字段成你真正想 search 的问题。
>
> **怎么用**:
> 1. 在这个 .md 文件里直接编辑 (VS Code / Notepad++ / 任何文本编辑器)
> 2. 改完保存
> 3. 把整张表 (或指定行) 粘贴回对话, 我会写进 `bench/v01/queries.json` 的 q026-q050
> 4. 或者直接告诉我 "替换 q026 为 XXX, 删除 q031", 我执行
>
> **不强制分布** — 这是建议, 你可以根据真实研究兴趣集中或分散

---

## 字段说明

- `id`: q026-q050 (必须保留)
- `query`: 你的真实 research question, 改!
- `topic_bucket`: 6 选 1
  - `econ` — 经济学 (劳动、宏观、计量)
  - `ml` — 机器学习 / NLP / CV
  - `bio` — 生物医学 / 营养 / 健康
  - `social` — 社科 / 行为 / 心理
  - `cross` — 跨界 (例如 ML+经济, 健康+行为)
  - `edu_ai` — AI+教育
- `difficulty_hint`: 4 选 1
  - `broad` — 关键词多, 领域宽, 易出噪声
  - `technical` — CS/ML/统计 jargon
  - `methodology` — 方法论 (e.g. "Bayesian structural time series")
  - `rare_terms` — 有特定作者/方法名 (e.g. "Acemoglu Restrepo")

---

## 25 query draft

| id   | query                                                        | topic_bucket | difficulty_hint |
| ---- | ------------------------------------------------------------ | ------------ | --------------- |
| q026 | 自然语言处理中对于细致情绪状态的划分，以及情绪转换矩阵（譬如：羡慕转化成嫉妒再转化成生气等等） | ml           | methodology     |
| q027 | 数据处理中对于文本的情绪连续性与媒体刺激物之间的关系（譬如：一段文本描写带有的情绪事实上是由某种外在刺激展开的，那么如何提取两者的特征，证明它们的因果关系呢） | ml           | technical       |
| q028 | 珀尔的因果图的相关前沿研究                                   | ml           | broad           |
| q029 | 我们自己做的paper agent 如何提升其效能，采用哪些模型         | ml           | technical       |
| q030 | 表格基础模型的教育应用（如何降低经济学学生学习数据分析的难度） | ml           | broad           |
| q031 | 新能源汽车销售与石油价格之间是否存在严格得因果关系，在美伊战争背景条件下如何做冲击性检验 | econ         | rare_terms      |
| q032 | 东数西算当前实行情况如何？究竟有多少互联网企业使用这种方案？在此背景下，提出东数东算得条件成熟吗？ | econ         | technical       |
| q033 | 灵活就业人数逐年上升对于社会保险的影响                       | econ         | broad           |
| q034 | 中国社会在低GDP成长率情况下遇到综合困境会导致最终导向        | econ         | methodology     |
| q035 | 人工智能究竟是取代劳动力造成大量失业，还是最终会产生大量新的工作岗位 | econ         | broad           |
| q036 | 灵活就业人数稳定逐年上升对于社会消费心理的影响               | cross        | technical       |
| q037 | 中国社会在面临社会保障耗尽、生育率冰点、政府债务暴涨、地方化债失利、灵活就业激增，会有哪些可能的心理变化，参考日本和墨西哥。由经济导向心理变化，由心理变化支撑解释社会变化 | cross        | rare_terms      |
| q038 | 终极意义上，人工智能是否会永久改变人类价值观的改变，从经济学、心理学、社会学、博弈论角度出发 | cross        | broad           |
| q039 | 北美基督教是否真的褪色了？基督教对于社会的影响正在消失吗？马克思韦伯的工作伦理是否仍然支撑当前的美国社会？ | cross        | technical       |
| q040 | 中国社会的奶茶经济（包括著名的上市公司，蜜雪，茶姬，古茗等等）对于中国人的健康影响与肥胖影响 | cross        | methodology     |
| q041 | 肝豆状核性变的研究综述以及患者生存概率追溯，有哪些补充剂能够日常维持生存或者提高患者生活质量，运动与饮食注意事项是什么，现代疗法治愈可能性研究 | bio          | methodology     |
| q042 | 干燥综合症的原因以及干燥综合症如何保养，注意事项是什么       | bio          | broad           |
| q043 | 地中海贫血因子携带者对于身体的影响，运动方式的注意           | bio          | broad           |
| q044 | 糖前期患者的阻止发展以及回退策略                             | bio          | technical       |
| q045 | 减肥食谱以及断食科学性综述                                   | bio          | rare_terms      |
| q046 | 少子化背景下，社会对于陪伴型机器人的依赖心理以及排斥         | social       | broad           |
| q047 | 恋爱综艺节目或者二次元擦边手机游戏（包括男性和女性）会促进婚恋吗？机理研究 媒体是否有效 情感分析 | social       | technical       |
| q048 | 全民基本收入是否会滋生懒汉心理？还是具有促进社会责任加速生产 | social       | methodology     |
| q049 | AI诞生之后，中小学教培是否面临即将被完全取代                 | social       | rare_terms      |
| q050 | 当前的社会形态是否比20世纪的社会形态带给人们更多的精神疾病不论是轻度的还是重度的 | social       | broad           |

---

## 分布统计

| dimension | 值 | 数量 |
|---|---|---:|
| topic_bucket | ml | 5 |
| topic_bucket | econ | 5 |
| topic_bucket | cross | 5 |
| topic_bucket | bio | 5 |
| topic_bucket | social | 5 |
| difficulty_hint | broad | 9 |
| difficulty_hint | technical | 7 |
| difficulty_hint | methodology | 5 |
| difficulty_hint | rare_terms | 4 |

---

## 改完怎么给我

**Option 1** (推荐): 改完保存 .md, 在对话里告诉我:
- "全接受, 写进 queries.json" — 我直接用
- "替换 q026 为 XXX" — 我替换
- "删除 q031, 替换 q032 为 YYY" — 我执行

**Option 2**: 复制改完的整张表, 粘贴对话

**Option 3**: 直接告诉我哪些行号要改, 我执行

---

## 改完会跑啥

1. 我把 q026-q050 写进 `bench/v01/queries.json`
2. 跑 v3.9.0 v4_rerank 看 candidate pool 多样性变化
3. Re-run v3.9.7.1 的 4+2 在 n=50 上 (MoE class_weight + Cross-encoder Wilcoxon)
4. 给你 n=50 三层 honest 报告 (✅ verified / ⚠️ unverified / ❌ hollow)

预计 5-10 分钟 total。
