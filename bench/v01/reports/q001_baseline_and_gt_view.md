# q001 — AI tutoring systems K-12 — baseline + ground truth view

**Query:** "AI tutoring systems and their effect on K-12 student learning outcomes"
**Candidate pool:** 30 papers from `pa search` (5 engines × limit-30, deduped to 105 raw, top-30)
**Labels:** Mavis (title-only, no abstracts) — 3 relevant / 11 marginal / 16 irrelevant

---

## Full ranking — pa search's order

> 排序 = 按 OpenAlex 的 relevance score (大概率 popularity + citation-weighted).
> **Top-10 全部是 high-citation popular papers，但 0 篇真相关。**

| rank | cite | yr | label | title |
|---:|---:|---:|:---:|:---|
| 1 | 5330 | 2023 | MAR | ChatGPT for good? On opportunities and challenges of large language models for education |
| 2 | 1791 | 2017 | IRR | Exploring the impact of artificial intelligence on teaching and learning in higher education |
| 3 | 1549 | 1998 | IRR | Scientific Discovery Learning with Computer Simulations of Conceptual Domains |
| 4 | 1414 | 2023 | IRR | Artificial intelligence in higher education: the state of the field |
| 5 | 1019 | 2022 | IRR | Towards Personalized Federated Learning |
| 6 | 940 | 2023 | MAR | New Era of Artificial Intelligence in Education: Towards a Sustainable Multifaceted Revolution |
| 7 | 870 | 2022 | IRR | Human-in-the-loop machine learning: a state of the art |
| 8 | 831 | 2024 | MAR | Embracing the future of Artificial Intelligence in the classroom: AI literacy, prompt engineering, critical thinking |
| 9 | 769 | 2023 | IRR | Challenges and Opportunities of Generative AI for Higher Education as Explained by ChatGPT |
| 10 | 737 | 2012 | IRR | The Knowledge‐Learning‐Instruction Framework: Bridging the Science‐Practice Chasm to Enhance Robust Student Learning |
| 11 | 715 | 2021 | IRR | The impact of artificial intelligence on learner–instructor interaction in online learning |
| 12 | 598 | 2023 | IRR | Teachers' AI digital competencies and twenty-first century skills in the post-pandemic world |
| 13 | 576 | 2023 | IRR | Enhancing academic writing skills and motivation: ChatGPT in AI-assisted language learning for EFL students |
| 14 | 510 | 2018 | IRR | Students' perception of Kahoot!'s influence on teaching and learning |
| **15** | **484** | **2023** | **REL** | **Do AI chatbots improve students learning outcomes? Evidence from a meta‐analysis** |
| 16 | 474 | 2023 | MAR | AI-generated feedback on writing: insights into efficacy and ENL student preference |
| 17 | 453 | 2023 | IRR | The impact of AI writing tools on the content and organization of students' writing: EFL teachers' perspective |
| 18 | 438 | 2023 | MAR | Artificial intelligence in language instruction: impact on English learning achievement, L2 motivation, self-regulated learning |
| 19 | 398 | 2023 | MAR | Impact of AI assistance on student agency |
| 20 | 395 | 2022 | IRR | The impact of a virtual teaching assistant (chatbot) on students' learning in Ghanaian higher education |
| 21 | 343 | 2022 | MAR | AI-Based Personalized E-Learning Systems: Issues, Challenges, and Solutions |
| 22 | 337 | 2023 | IRR | Integration of artificial intelligence performance prediction and learning analytics to improve student learning in online engineering course |
| 23 | 275 | 2023 | MAR | Supporting students' self-regulated learning in online learning using artificial intelligence applications |
| **24** | **260** | **2014** | **REL** | **A Multimedia Adaptive Tutoring System for Mathematics that Addresses Cognition, Metacognition and Affect** |
| 25 | 257 | 2024 | MAR | Leveraging AI in E-Learning: Personalized Learning and Adaptive Assessment through Cognitive Neuropsychology |
| 26 | 256 | 2022 | IRR | Effect of Artificial Intelligence Tutoring vs Expert Instruction on Learning Simulated Surgical Skills Among Medical Students |
| 27 | 241 | 2023 | IRR | Role of AI in Education |
| 28 | 226 | 2024 | MAR | Generative AI for Customizable Learning Experiences |
| 29 | 197 | 2005 | MAR | Fostering the Intelligent Novice: Learning From Errors With Metacognitive Tutoring |
| **30** | **156** | **2024** | **REL** | **From chatting to self-educating: Can AI tools boost student learning outcomes?** |

**Legend:** REL = relevant (label=2) · MAR = marginal (label=1) · IRR = irrelevant (label=0)

---

## 模式一: 排序按引用排, 不按相关性

| 真相关 (REL) | rank | cite | 摘要情况 |
|---|---:|---:|---|
| #15 AI chatbots meta-analysis | 15 | 484 | 直接对题 |
| #24 Adaptive math tutoring | 24 | 260 | 经典 ITS, K-12 math |
| #30 AI tools + outcomes | 30 | 156 | 直接对题 |

→ **3 篇真相关全部埋在前 1/2 之后**。#15 离前 10 还差 5 位, #30 直接在最后。

## 模式二: 主题错位 (7 篇 — pa 拉错)

| rank | 错位类型 | 标题 | 应该是 |
|---:|---|---|:---:|
| 3 | 时代错位 (1998, no AI) | Scientific Discovery Learning... | IRR ✓ |
| 5 | 学科错位 (ML not edu) | Towards Personalized Federated Learning | IRR ✓ |
| 7 | 学科错位 (ML not edu) | Human-in-the-loop machine learning | IRR ✓ |
| 10 | 主题错位 (learning sci not AI) | Knowledge-Learning-Instruction Framework | IRR ✓ |
| 14 | 工具错位 (Kahoot not AI) | Students' perception of Kahoot! | IRR ✓ |

## 模式三: 水平错位 (7 篇 — 全是 higher-ed)

| rank | 标题 | 错在 |
|---:|---|---|
| 2 | AI impact on teaching in higher ed | "higher education" 在 title |
| 4 | AI in higher ed: state of the field | "higher education" 在 title |
| 9 | GenAI for Higher Education | "Higher Education" 在 title |
| 13 | ChatGPT for EFL students | EFL 通常 higher ed |
| 20 | chatbot in Ghanaian higher ed | "higher education" 在 title |
| 22 | AI in online engineering course | engineering = higher ed |
| 26 | AI Tutoring for Medical Students | Medical students = higher ed |

→ **pa 没做 K-12 vs higher-ed 过滤**。这些 paper 跟 query 相关但 level 不对, 标 IRR 是为了 "K-12 真相关" 的精确度。

## 模式四: 边界 MAR — 我自己没把握, 让你看

| rank | 标题 | 标 MAR 原因 | 实际可能是 |
|---:|---|---|:---:|
| 8 | AI literacy in classroom | pedagogy not outcomes | MAR ✓ (没 abstract 确认 level, 但 AI literacy ≠ tutoring) |
| 16 | AI-generated feedback on writing (ENL) | level unclear | 如果 K-12 → REL; 如果 higher-ed → MAR |
| 18 | AI in language instruction + L2 achievement | level unclear | 同上, K-12 教英语的国家很多 |
| 21 | AI-Based Personalized E-Learning | level unclear | methodology paper, 倾向 MAR |
| 23 | AI in self-regulated online learning | level unclear | 同上 |
| 25 | AI e-learning + adaptive assessment | level unclear | 同上 |

→ **#16, #18, #21, #23, #25 这 5 篇没 abstract 我只能猜 level**, 有可能错标。要确认只能拉 abstract 看。

## 模式五: 真相关候选 — 我标 MAR 但可能是 REL

| rank | 标题 | 标 MAR 原因 | 实际可能是 |
|---:|---|---|:---:|
| 1 | ChatGPT for good? LLM in education | "broad survey, not K-12" | 如果 survey 里有 K-12 章节 → MAR; 全 higher-ed → IRR |
| 6 | New Era of AI in Education | "broad review" | 同上 |
| 28 | Generative AI for Customizable Learning | "level unclear" | K-12 customizable learning → 可能 REL |
| 29 | Metacognitive Tutoring (2005) | "pre-AI, not K-12 specific" | "intelligent novice" 暗示 ITS, classic 教学理论 |

→ **没 abstract 我都得猜**。我倾向保守标 MAR, 让 eval 的 ndcg 处理 graded gain, 不会污染 recall。

---

## v4 要打的具体靶子 (按 lift 期望排序)

| 模块 | 期望 lift | 怎么打到这个 baseline |
|---|---|---|
| **BM25 词法** | +15% on rare terms | "K-12" / "tutoring" / "learning outcomes" 这些词加权 |
| **Cross-encoder rerank** | +12-18% precision | 把 5330 引的 ChatGPT 综述 (#1) 排到 #20+, 把 484 引的 AI chatbots meta (#15) 排到 top-5 |
| **Light MoE routing** | +5-10% precision | topic classifier 区分 "broad LLM in edu" vs "K-12 tutoring outcomes", 用不同 expert prompt 调权重 |
| **PaSa-lite** | +10-15% recall | query expansion "AI tutoring" → "intelligent tutoring system K-12 adaptive learning outcome", 多引出真相关 (#15 类 paper) |

→ 排序用 citation 排序 → 用真相关性排序: **直接换 BM25 就能把 #15, #24, #30 拉上去**, 不需要 LLM。

---

## 我标 labels 时的不确定性 (诚实)

**稳的 (信心 80%+):**
- 3 篇 REL (#15, #24, #30): 标题完全对题, 不会错
- 模式三 7 篇 IRR: title 明写 "higher education" 不会错
- 模式二 5 篇 IRR: 学科/时代明显错

**有信心的 MAR (信心 60-70%):**
- #1, #6, #28: 标题像泛论, 大概率含 higher-ed 偏多, MAR 合理

**真的在猜 (信心 30-50%):**
- #8, #16, #18, #21, #23, #25: 6 篇 "level unclear" 边界 paper, 没 abstract 我都得猜

→ **结论: labels 噪声主要在 MAR 边界, REL/IRR 的边界稳**。但 6 篇边界 paper 的 label 一改, ndcg 数字会跳 (recall 不太会跳, 因为 REL 数还是 3)。
