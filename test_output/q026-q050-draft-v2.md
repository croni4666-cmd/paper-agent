# q026-q050 v2 — Mavis adjustments (2026-07-14 21:25)

> **v1 → v2 改动**:
> 1. 调整 19 行的 `difficulty_hint` (理由在表后)
> 2. 对部分 query 做 3 种处理: 保留 / 深化 / 换英文 (见每行注释)
> 3. 保留你的中文, 因为是你真实研究问题
>
> **v3.9.0 真实限制** (重要, 决定 MoE 评估能否有信号):
> - 5 search engine (openalex / s2 / crossref / arxiv / core) 全是英文索引
> - 中文 specific query (东数西算 / 奶茶 / 灵活就业) → 5 engine 找不到中文 paper → candidate pool 多样性不增加 → MoE class imbalance 仍然 96% openalex → **MoE 评估还是 noise**
> - 想 n=50 后 MoE 真 work, 要么 (a) query 改成英文, 要么 (b) 扩 search engine (CNKI / WanFang)
> - 4 个 deferred 项目的 unblock 取决于**英文 query 比例**

---

## v2 调整后的 25 行

| id   | query (你的原版) + 调整建议                                                  | topic_bucket | v2 difficulty | 调整说明 |
| ---- | ----------------------------------------------------------------------------- | ------------ | ------------- | -------- |
| q026 | 自然语言处理中对于细致情绪状态的划分，以及情绪转换矩阵 (譬如：羡慕转化成嫉妒再转化成生气等等) | ml           | **technical** | v1=methodology, 改 technical: 关心 "transition matrix" 实现, 是具体技术, 不是方法论比较 |
| q027 | 数据处理中对于文本的情绪连续性与媒体刺激物之间的关系 (譬如：如何提取两者的特征，证明它们的因果关系) | ml           | technical (保留) | 涉及 causal inference + 特征提取, technical OK |
| q028 | 珀尔的因果图的相关前沿研究                                                    | ml           | **rare_terms** | v1=broad, 改 rare_terms: "Pearl" + "因果图" 是 specific term。query 措辞 OK, 中文保留, 候选 search 词: "Judea Pearl causal diagram recent advances" |
| q029 | 我们自己做的 paper agent 如何提升其效能，采用哪些模型                          | ml           | **methodology** | v1=technical, 改 methodology: 关心 "如何提升" 整体方法论 (architecture / eval / optimization), 不是具体 model 名。query 措辞 OK 但需深化: "paper-agent v4 evaluation benchmark lift" |
| q030 | 表格基础模型的教育应用 (如何降低经济学学生学习数据分析的难度)                 | ml           | **technical** | v1=broad, 改 technical: "表格基础模型" 是 specific technical term (TabPFN / TabICL)。建议加英文: "tabular foundation models TabPFN education pedagogy" |
| q031 | 新能源汽车销售与石油价格之间是否存在严格的因果关系，在美伊战争背景条件下如何做冲击性检验 | econ         | **methodology** | v1=rare_terms, 改 methodology: "美伊战争 2026" 是未来事件无 paper, 建议深化去掉战争背景 → "新能源汽车销售与国际原油价格的 Granger 因果 / SVAR 检验" |
| q032 | 东数西算当前实行情况如何？究竟有多少互联网企业使用这种方案？东数东算的条件成熟吗？ | econ         | **broad** | v1=technical, 改 broad: 中国 data center policy, 无 specific methodology。**警告**: 此 query 中文 specific, 5 英文 engine 找不到 paper |
| q033 | 灵活就业人数逐年上升对于社会保险的影响                                       | econ         | broad (保留) | policy/econ 宽问题, OK |
| q034 | 中国社会在低 GDP 成长率情况下遇到综合困境会导致最终导向                        | econ         | **broad** | v1=methodology, 改 broad: "导致最终导向" 模糊, 无 specific methodology。**警告**: 中文 specific, 5 engine 找不到 paper。query 建议深化: "China low GDP growth + 地方债 + 人口下降 政策响应路径" |
| q035 | 人工智能究竟是取代劳动力造成大量失业，还是最终会产生大量新的工作岗位         | econ         | broad (保留) | AI labor debate 经典 wide question。建议加 specific anchor: "Acemoglu Restrepo task-based model empirical" |
| q036 | 灵活就业人数稳定逐年上升对于社会消费心理的影响                               | cross        | **broad** | v1=technical, 改 broad: 心理学影响, 无 specific methodology。**警告**: 中文 specific, 5 engine 找不到 paper |
| q037 | 中国社会在面临社会保障耗尽、生育率冰点、政府债务暴涨、地方化债失利、灵活就业激增，会有哪些可能的心理变化，参考日本和墨西哥。由经济导向心理变化，由心理变化支撑解释社会变化 | cross        | **methodology** | v1=rare_terms, 改 methodology: 关心 "心理变化如何解释社会变化" methodology, 不是 specific author。**警告**: 中文 specific, 但 "日本失落 30 年" 有部分英文 paper |
| q038 | 终极意义上，人工智能是否会永久改变人类价值观的改变，从经济学、心理学、社会学、博弈论角度出发 | cross        | broad (保留) | 哲学/sociology 模糊问题。建议加 anchor: "AI alignment human values game theory" |
| q039 | 北美基督教是否真的褪色了？基督教对于社会的影响正在消失吗？马克思韦伯的工作伦理是否仍然支撑当前的美国社会？ | cross        | **rare_terms** | v1=technical, 改 rare_terms: "Weber" + "Protestant work ethic" 是 specific terms。建议加英文: "Weber Protestant ethic secularization United States" |
| q040 | 中国社会的奶茶经济 (蜜雪，茶姬，古茗等等) 对于中国人的健康影响与肥胖影响     | cross        | **broad** | v1=methodology, 改 broad: 关心 "健康影响", 无 specific methodology。**警告**: 中文 specific, 5 engine 找不到 paper。建议加 methodology anchor: "sugar-sweetened beverage consumption obesity Chinese cohort" |
| q041 | 肝豆状核性变的研究综述以及患者生存概率追溯，有哪些补充剂能够日常维持生存或者提高患者生活质量，运动与饮食注意事项是什么，现代疗法治愈可能性研究 | bio          | **rare_terms** | v1=methodology, 改 rare_terms: "Wilson's disease" 是 specific disease (肝豆状核变性 = Wilson's disease)。query 有 4 sub-question 混在一起, 建议**拆 2-3 个 query** 后续。中文保留 |
| q042 | 干燥综合症的原因以及干燥综合症如何保养，注意事项是什么                       | bio          | **rare_terms** | v1=broad, 改 rare_terms: "Sjögren's syndrome" (干燥综合症) 是 specific disease。建议加英文: "Sjogren syndrome etiology management lifestyle" |
| q043 | 地中海贫血因子携带者对于身体的影响，运动方式的注意                           | bio          | **rare_terms** | v1=broad, 改 rare_terms: "thalassemia" (地中海贫血) 是 specific disease。建议加英文: "thalassemia trait carrier exercise physiology" |
| q044 | 糖前期患者的阻止发展以及回退策略                                             | bio          | **rare_terms** | v1=technical, 改 rare_terms: "prediabetes" (糖前期) 是 specific medical term。建议深化: "prediabetes reversal interventions lifestyle metformin RCT" |
| q045 | 减肥食谱以及断食科学性综述                                                   | bio          | **methodology** | v1=rare_terms, 改 methodology: "科学性综述" 暗示 systematic review methodology, 不是 specific author。建议深化: "intermittent fasting vs calorie restriction weight loss RCT systematic review" |
| q046 | 少子化背景下，社会对于陪伴型机器人的依赖心理以及排斥                         | social       | **technical** | v1=broad, 改 technical: "companion robot" (陪伴型机器人) 是 specific term。建议加英文: "companion robot aging society Japan China" |
| q047 | 恋爱综艺节目或者二次元擦边手机游戏 (包括男性和女性) 会促进婚恋吗？机理研究 媒体是否有效 情感分析 | social       | **methodology** | v1=technical, 改 methodology: 关心 "机理研究 + 媒体是否有效" methodology, 不是具体技术。建议**拆 2 个 query** (综艺 vs 二次元游戏) |
| q048 | 全民基本收入是否会滋生懒汉心理？还是具有促进社会责任加速生产                 | social       | **broad** | v1=methodology, 改 broad: 经典 wide behavioral question。建议加 anchor: "UBI behavioral effects Finland Kenya experiment labor supply" |
| q049 | AI 诞生之后，中小学教培是否面临即将被完全取代                               | social       | **broad** | v1=rare_terms, 改 broad: wide prediction, 无 specific term。建议加 anchor: "AI tutor K-12 teacher displacement employment evidence" |
| q050 | 当前的社会形态是否比 20 世纪的社会形态带给人们更多的精神疾病不论是轻度的还是重度的 | social       | broad (保留) | wide comparison。建议深化: "mental illness prevalence trend 1990-2020 cross-country cohort meta-analysis" |

---

## 调整后分布 (v2)

| topic_bucket | 数量 | difficulty_hint | 数量 |
|---|---:|---|---:|
| ml | 5 | broad | 9 |
| econ | 5 | technical | 6 |
| cross | 5 | methodology | 6 |
| bio | 5 | rare_terms | 4 |
| social | 5 | | |

对比 v1: difficulty 从 (9/7/5/4) 调整为 (9/6/6/4), technical 减少, methodology 增加 — 更准确反映 query 真实粒度。

---

## 中文 specific query 警告 (影响 n=50 评估)

5 search engine 找不到 paper 的 query (9 个, 这些 query 不会让 MoE class diversity 提升):

- q032 (东数西算) — 政策, 主要是中文报告
- q034 (低 GDP 综合困境) — 中国特定
- q036 (灵活就业 + 消费心理) — 中国特定
- q037 (综合 + 日本墨西哥) — 部分英文 (Japan) 可
- q038 (AI 价值观) — 哲学 wide, 英文有但 specific author 少
- q040 (奶茶经济) — 中国 specific
- q046 (陪伴机器人) — 中日都有, 部分英文可
- q047 (综艺 + 二次元游戏) — 中国/日本 specific
- q049 (AI 教培) — 中国 specific, 英文有 AI in education 但少 "displacement" 论调

**真正能 unblock MoE class diversity 的** 是 16 个英文-searchable query (q026-q031, q033, q035, q039, q041-q045, q048, q050)。这些的 paper candidate 会分散在 5 engine。

---

## 怎么确认 v2

**Option A** (推荐): 全接受 → 我直接写进 queries.json (同时保留 user 备注)

**Option B**: 改某些行 → 告诉我 "q031 改成 X", "q041 拆成 X1 + X2"

**Option C**: 中文 specific 警告要 expand → 告诉我加 CNKI/WanFang 作为 6-7 engine (新 ROADMAP item)

**Option D**: 跳过中文 warning → 接受 9 query 找不到 paper, 跑完报告会说 MoE 提升有限

---

## v2 写进 queries.json 之后会跑啥

1. **n=50 v4_rerank** — 25 query × 30 candidates × 5 conditions = 3,750 candidate
2. **MoE [P1-11.1] n=50 re-run** — 看 class diversity 提升 (但仅限 16 个英文-searchable)
3. **Cross-encoder [P0-7.1] n=50 Wilcoxon** — 50 paired queries, 显著性 power 大幅提升
4. **LTR [P0-6.1] n=50 re-run** — 5-fold CV with proper sample size
5. **n=50 三层 honest 报告** (✅ verified / ⚠️ unverified / ❌ hollow)

预计 10-15 分钟 total。
