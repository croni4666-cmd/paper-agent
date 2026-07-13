# Spot-Check: q013

**Query**: `transformer-based protein structure prediction methods`

## How to fill in

For each row below, decide if Mavis's `mavis_label` is correct. Override the `user_label` column (0/1/2) if you disagree, and add a short `user_note` explaining why.

Scoring:
- **0** = not relevant to the query
- **1** = partial / related but not directly on topic
- **2** = directly relevant (paper is *about* this query)

Tips:
- Title alone is often enough; only read abstract if title is ambiguous
- 5-15 sec per row. If you can do 30 rows in 10 min, full 25-query pass ≈ 1.5-3 hr
- **Mavis labels are already 70-80% accurate** based on title scan. Focus on disagreements, not agreement checks

---

### #1 — `10.1126/science.abj8754`

**Title**: Accurate prediction of protein structures and interactions using a three-track neural network  
**Year**: 2021 | **Venue**: Science | **Citations**: 5741

**Abstract**: DeepMind presented notably accurate predictions at the recent 14th Critical Assessment of Structure Prediction (CASP14) conference. We explored network architectures that incorporate related ideas and obtained the best performance with a three-track network in which information...

**Mavis label**: `2` — DIRECTLY three-track NN for protein structure prediction (RoseTTAFold), transformer-adjacent

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #2 — `10.1038/s41587-021-01156-3`

**Title**: SignalP 6.0 predicts all five types of signal peptides using protein language models  
**Year**: 2022 | **Venue**: Nature Biotechnology | **Citations**: 2800

**Abstract**: Signal peptides (SPs) are short amino acid sequences that control protein secretion and translocation in all living organisms. SPs can be predicted from sequence data, but existing algorithms are unable to detect all known types of SPs. We introduce SignalP 6.0, a machine...

**Mavis label**: `1` — SignalP 6.0 protein language model, signal peptides not structure

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #3 — `10.1093/nar/gkae1010`

**Title**: UniProt: the Universal Protein Knowledgebase in 2025  
**Year**: 2024 | **Venue**: Nucleic Acids Research | **Citations**: 2043

**Abstract**: The aim of the UniProt Knowledgebase (UniProtKB; https://www.uniprot.org/) is to provide users with a comprehensive, high-quality and freely accessible set of protein sequences annotated with functional information. In this publication, we describe ongoing changes to our...

**Mavis label**: `0` — UniProt 2025 database, not structure prediction

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #4 — `10.1038/s41592-021-01252-x`

**Title**: Effective gene expression prediction from sequence by integrating long-range interactions  
**Year**: 2021 | **Venue**: Nature Methods | **Citations**: 1309

**Abstract**: How noncoding DNA determines gene expression in different cell types is a major unsolved problem, and critical downstream applications in human genetics depend on improved solutions. Here, we report substantially improved gene expression prediction accuracy from DNA sequences...

**Mavis label**: `0` — Enformer gene expression, not protein structure

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #5 — `10.1038/s41592-019-0598-1`

**Title**: Unified rational protein engineering with sequence-based deep representation learning  
**Year**: 2019 | **Venue**: Nature Methods | **Citations**: 1183

**Abstract**: _(no abstract)_

**Mavis label**: `1` — Rational protein engineering, not structure prediction

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #6 — `10.1038/s41586-023-06139-9`

**Title**: Transfer learning enables predictions in network biology  
**Year**: 2023 | **Venue**: Nature | **Citations**: 1058

**Abstract**: _(no abstract)_

**Mavis label**: `0` — Transfer learning network biology, not protein structure

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #7 — `10.1093/bioinformatics/btac020`

**Title**: ProteinBERT: a universal deep-learning model of protein sequence and function  
**Year**: 2022 | **Venue**: Bioinformatics | **Citations**: 986

**Abstract**: SUMMARY: Self-supervised deep language modeling has shown unprecedented success across natural language tasks, and has recently been repurposed to biological sequences. However, existing models and pretraining methods are designed and optimized for text analysis. We introduce...

**Mavis label**: `1` — ProteinBERT, not structure prediction specifically

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #8 — `10.1093/nar/gkae1082`

**Title**: InterPro: the protein sequence classification resource in 2025  
**Year**: 2024 | **Venue**: Nucleic Acids Research | **Citations**: 916

**Abstract**: InterPro (https://www.ebi.ac.uk/interpro) is a freely accessible resource for the classification of protein sequences into families. It integrates predictive models, known as signatures, from multiple member databases to classify sequences into families and predict the presence...

**Mavis label**: `0` — InterPro 2025 protein classification, not structure

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #9 — `10.1038/s41467-022-32007-7`

**Title**: ProtGPT2 is a deep unsupervised language model for protein design  
**Year**: 2022 | **Venue**: Nature Communications | **Citations**: 785

**Abstract**: Protein design aims to build novel proteins customized for specific purposes, thereby holding the potential to tackle many environmental and biomedical problems. Recent progress in Transformer-based architectures has enabled the implementation of language models capable of...

**Mavis label**: `1` — ProtGPT2 protein design, not structure

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #10 — `10.1093/nar/gkac278`

**Title**: DeepLoc 2.0: multi-label subcellular localization prediction using protein language models  
**Year**: 2022 | **Venue**: Nucleic Acids Research | **Citations**: 718

**Abstract**: The prediction of protein subcellular localization is of great relevance for proteomics research. Here, we propose an update to the popular tool DeepLoc with multi-localization prediction and improvements in both performance and interpretability. For training and validation, we...

**Mavis label**: `0` — DeepLoc 2.0 subcellular localization, not structure

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #11 — `10.1038/s41586-024-08328-6`

**Title**: Accurate predictions on small data with a tabular foundation model  
**Year**: 2025 | **Venue**: Nature | **Citations**: 680

**Abstract**: Abstract Tabular data, spreadsheets organized in rows and columns, are ubiquitous across scientific fields, from biomedicine to particle physics to economics and climate science 1,2 . The fundamental prediction task of filling in missing values of a label column based on the...

**Mavis label**: `0` — Tabular foundation model, not protein

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #12 — `10.1186/s12859-019-3220-8`

**Title**: Modeling aspects of the language of life through transfer-learning protein sequences  
**Year**: 2019 | **Venue**: BMC Bioinformatics | **Citations**: 641

**Abstract**: BACKGROUND: Predicting protein function and structure from sequence is one important challenge for computational biology. For 26 years, most state-of-the-art approaches combined machine learning and evolutionary information. However, for some applications retrieving related...

**Mavis label**: `1` — Language of life transfer learning, not structure specifically

**Your judgment**:

- [x] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 序列预测而非结构预测

---

### #13 — `10.1093/bioinformatics/btaa880`

**Title**: MolTrans: Molecular Interaction Transformer for drug–target interaction prediction  
**Year**: 2020 | **Venue**: Bioinformatics | **Citations**: 610

**Abstract**: MOTIVATION: Drug-target interaction (DTI) prediction is a foundational task for in-silico drug discovery, which is costly and time-consuming due to the need of experimental search over large drug compound space. Recent years have witnessed promising progress for deep learning in...

**Mavis label**: `0` — MolTrans DTI prediction, not protein structure

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #14 — `10.1093/bioinformatics/btaa524`

**Title**: TransformerCPI: improving compound–protein interaction prediction by sequence-based deep learning with self-attention mechanism and label reversal experiments  
**Year**: 2020 | **Venue**: Bioinformatics | **Citations**: 574

**Abstract**: MOTIVATION: Identifying compound-protein interaction (CPI) is a crucial task in drug discovery and chemogenomics studies, and proteins without three-dimensional structure account for a large part of potential biological targets, which requires developing methods using only...

**Mavis label**: `0` — TransformerCPI compound-protein interaction, not structure

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #15 — `10.1038/s41588-023-01465-0`

**Title**: Genome-wide prediction of disease variant effects with a deep protein language model  
**Year**: 2023 | **Venue**: Nature Genetics | **Citations**: 444

**Abstract**: Predicting the effects of coding variants is a major challenge. While recent deep-learning models have improved variant effect prediction accuracy, they cannot analyze all coding variants due to dependency on close homologs or software limitations. Here we developed a workflow...

**Mavis label**: `1` — ESM1b variant effects, related to protein LM not structure specifically

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #16 — `10.1038/s41587-022-01432-w`

**Title**: Single-sequence protein structure prediction using a language model and deep learning  
**Year**: 2022 | **Venue**: Nature Biotechnology | **Citations**: 427

**Abstract**: _(no abstract)_

**Mavis label**: `2` — DIRECTLY single-sequence protein structure prediction using LM

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #17 — `10.1093/nar/gkac439`

**Title**: NetSurfP-3.0: accurate and fast prediction of protein structural features by protein language models and deep learning  
**Year**: 2022 | **Venue**: Nucleic Acids Research | **Citations**: 376

**Abstract**: Recent advances in machine learning and natural language processing have made it possible to profoundly advance our ability to accurately predict protein structures and their functions. While such improvements are significantly impacting the fields of biology and biotechnology...

**Mavis label**: `1` — NetSurfP-3.0 protein structural features, related but not transformer-based

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #18 — `10.1093/nar/gkab354`

**Title**: PredictProtein - Predicting Protein Structure and Function for 29 Years  
**Year**: 2021 | **Venue**: Nucleic Acids Research | **Citations**: 264

**Abstract**: Since 1992 PredictProtein (https://predictprotein.org) is a one-stop online resource for protein sequence analysis with its main site hosted at the Luxembourg Centre for Systems Biomedicine (LCSB) and queried monthly by over 3,000 users in 2020. PredictProtein was the first...

**Mavis label**: `1` — PredictProtein, classic tool not transformer

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #19 — `10.1016/j.ccell.2023.08.002`

**Title**: Transformer-based biomarker prediction from colorectal cancer histology: A large-scale multicentric study  
**Year**: 2023 | **Venue**: Cancer Cell | **Citations**: 250

**Abstract**: Deep learning (DL) can accelerate the prediction of prognostic biomarkers from routine pathology slides in colorectal cancer (CRC). However, current approaches rely on convolutional neural networks (CNNs) and have mostly been validated on small patient cohorts. Here, we develop...

**Mavis label**: `0` — Transformer biomarker CRC histology, not protein

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #20 — `10.1038/s41598-022-12201-9`

**Title**: Prediction of protein–protein interaction using graph neural networks  
**Year**: 2022 | **Venue**: Scientific Reports | **Citations**: 245

**Abstract**: Proteins are the essential biological macromolecules required to perform nearly all biological processes, and cellular functions. Proteins rarely carry out their tasks in isolation but interact with other proteins (known as protein-protein interaction) present in their...

**Mavis label**: `0` — PPI graph NN, not structure prediction

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #21 — `10.1038/s41598-020-79682-4`

**Title**: Transformer neural network for protein-specific de novo drug generation as a machine translation problem  
**Year**: 2021 | **Venue**: Scientific Reports | **Citations**: 224

**Abstract**: Drug discovery for a protein target is a very laborious, long and costly process. Machine learning approaches and, in particular, deep generative networks can substantially reduce development time and costs. However, the majority of methods imply prior knowledge of protein...

**Mavis label**: `1` — Transformer de novo drug generation, not structure

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #22 — `10.1038/s41467-023-42528-4`

**Title**: trRosettaRNA: automated prediction of RNA 3D structure with transformer network  
**Year**: 2023 | **Venue**: Nature Communications | **Citations**: 211

**Abstract**: Abstract RNA 3D structure prediction is a long-standing challenge. Inspired by the recent breakthrough in protein structure prediction, we developed trRosettaRNA, an automated deep learning-based approach to RNA 3D structure prediction. The trRosettaRNA pipeline comprises two...

**Mavis label**: `1` — trRosettaRNA RNA structure, not protein

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #23 — `10.1038/s41524-023-01016-5`

**Title**: TransPolymer: a Transformer-based language model for polymer property predictions  
**Year**: 2023 | **Venue**: npj Computational Materials | **Citations**: 188

**Abstract**: Abstract Accurate and efficient prediction of polymer properties is of great significance in polymer design. Conventionally, expensive and time-consuming experiments or simulations are required to evaluate polymer functions. Recently, Transformer models, equipped with...

**Mavis label**: `0` — TransPolymer, not protein

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #24 — `10.1038/s43588-022-00373-3`

**Title**: Single-sequence protein structure prediction using supervised transformer protein language models  
**Year**: 2022 | **Venue**: Nature Computational Science | **Citations**: 147

**Abstract**: _(no abstract)_

**Mavis label**: `2` — DIRECTLY single-sequence protein structure prediction with supervised transformer

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #25 — `10.1093/bib/bbab564`

**Title**: AlphaFold2-aware protein–DNA binding site prediction using graph transformer  
**Year**: 2021 | **Venue**: Briefings in Bioinformatics | **Citations**: 134

**Abstract**: Protein-DNA interactions play crucial roles in the biological systems, and identifying protein-DNA binding sites is the first step for mechanistic understanding of various biological activities (such as transcription and repair) and designing novel drugs. How to accurately...

**Mavis label**: `1` — AlphaFold2-aware protein-DNA binding, not structure prediction

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #26 — `10.1101/2021.07.31.454572`

**Title**: Protein language model embeddings for fast, accurate, alignment-free protein structure prediction  
**Year**: 2021 | **Venue**: bioRxiv | **Citations**: 123

**Abstract**: All state-of-the-art (SOTA) protein structure predictions rely on evolutionary information captured in multiple sequence alignments (MSAs), primarily on evolutionary couplings (co-evolution). Such information is not available for all proteins and is computationally expensive to...

**Mavis label**: `2` — DIRECTLY protein LM embeddings for alignment-free structure prediction

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #27 — `10.34133/research.0240`

**Title**: A Transformer-Based Ensemble Framework for the Prediction of Protein–Protein Interaction Sites  
**Year**: 2023 | **Venue**: Research | **Citations**: 97

**Abstract**: The identification of protein-protein interaction (PPI) sites is essential in the research of protein function and the discovery of new drugs. So far, a variety of computational tools based on machine learning have been developed to accelerate the identification of PPI sites....

**Mavis label**: `0` — Transformer PPI sites, not structure

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #28 — `10.1093/bioinformatics/btad718`

**Title**: DeepProSite: structure-aware protein binding site prediction using ESMFold and pretrained language model  
**Year**: 2023 | **Venue**: Bioinformatics | **Citations**: 92

**Abstract**: MOTIVATION: Identifying the functional sites of a protein, such as the binding sites of proteins, peptides, or other biological components, is crucial for understanding related biological processes and drug design. However, existing sequence-based methods have limited predictive...

**Mavis label**: `1` — DeepProSite binding site using ESMFold, related to structure

**Your judgment**:

- [x] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 1. 如果是“结构预测”论文（比如 AlphaFold2, ESMFold 团队自己写的论文）

- **输入：** 氨基酸序列。
- **最终输出（Output）：** 几千个原子的 $X, Y, Z$ **三维坐标（连续数值）**。
- **Loss 函数：** FAPE Loss（结构对齐误差）或坐标点之间的均方误差（MSE）。
- **技术核心：** 在解决极其复杂的“物理折叠”和“几何等变”问题。

### 2. 你看到的这篇论文（基于 ESMFold 的位点预测）

- **输入：** 氨基酸序列。
- **最终输出（Output）：** 一个一维的**概率数组（0 到 1 之间的概率值）**。比如序列长 100，它就输出 100 个概率。
- **Loss 函数：** 最传统的**交叉熵损失（Cross Entropy Loss）**，也就是大模型搞文本分类、垃圾邮件分类用的那个 Loss。
- **技术核心：** 是一个地道的“特征融合与下游分类”任务。

### 那它为什么要扯上 ESMFold？（它的真实小算盘）

它调用 ESMFold，纯粹是为了“白嫖”特征。

这就好比你要写一篇“预测一部电影会不会爆火”的 NLP 论文：

1. 你手里只有电影的**纯文本剧本**（对应蛋白质序列）。
2. 你嫌直接分析剧本太单薄，于是你把剧本丢给了一个开源的 AI 绘图模型（对应 ESMFold），让它自动生成了 10 张**电影海报/剧照**（对应 3D 结构）。
3. 然后你把剧本里的文字特征，和 AI 绘图模型生成的剧照特征拼在一起，训练了一个分类器，去预测票房是高还是低（对应结合位点 0 或 1）。

**在这个过程中，你的目标自始至终都是“预测票房（位点分类）”，你根本不在乎、也不去研究怎么做出更好的绘图模型（结构预测）。你只是把绘图模型当成了你论文里的一个“高级特征提取器”。**

所以你的直觉是百分之百对的。它就是披着“结构”外衣的、不折不扣的、针对特定数据集的**节点二分类深度学习模型**。

---

### #29 — `10.1021/acs.jcim.2c00060`

**Title**: Structure-Aware Multimodal Deep Learning for Drug–Protein Interaction Prediction  
**Year**: 2022 | **Venue**: Journal of Chemical Information and Modeling | **Citations**: 80

**Abstract**: Identifying drug-protein interactions (DPIs) is crucial in drug discovery, and a number of machine learning methods have been developed to predict DPIs. Existing methods usually use unrealistic data sets with hidden bias, which will limit the accuracy of virtual screening...

**Mavis label**: `0` — DPI prediction STAMP-DPI, not structure

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #30 — `10.1093/bioinformatics/btad208`

**Title**: Combining protein sequences and structures with transformers and equivariant graph neural networks to predict protein function  
**Year**: 2023 | **Venue**: Bioinformatics | **Citations**: 73

**Abstract**: MOTIVATION: Millions of protein sequences have been generated by numerous genome and transcriptome sequencing projects. However, experimentally determining the function of the proteins is still a time consuming, low-throughput, and expensive process, leading to a large protein...

**Mavis label**: `1` — Protein function transformers EGNN, not structure specifically

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---
