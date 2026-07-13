# Spot-Check: q008

**Query**: `drug repurposing using graph neural networks`

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

### #1 — `10.1093/bioinformatics/bty294`

**Title**: Modeling polypharmacy side effects with graph convolutional networks  
**Year**: 2018 | **Venue**: Bioinformatics | **Citations**: 1398

**Abstract**: Motivation: The use of drug combinations, termed polypharmacy, is common to treat patients with complex diseases or co-existing conditions. However, a major consequence of polypharmacy is a much higher risk of adverse side effects for the patient. Polypharmacy side effects...

**Mavis label**: `1` — GCN for polypharmacy side effects, related to drug interactions not repurposing

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #2 — `10.1093/bioinformatics/btaa921`

**Title**: GraphDTA: predicting drug–target binding affinity with graph neural networks  
**Year**: 2020 | **Venue**: Bioinformatics | **Citations**: 1157

**Abstract**: SUMMARY: The development of new drugs is costly, time consuming and often accompanied with safety issues. Drug repurposing can avoid the expensive and lengthy process of drug development by finding new uses for already approved drugs. In order to repurpose drugs effectively, it...

**Mavis label**: `1` — GNN for drug-target binding (GraphDTA), mentions repurposing but DTI focus

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #3 — `10.1007/s10462-023-10465-9`

**Title**: Knowledge Graphs: Opportunities and Challenges  
**Year**: 2023 | **Venue**: Artificial Intelligence Review | **Citations**: 615

**Abstract**: With the explosive growth of artificial intelligence (AI) and big data, it has become vitally important to organize and represent the enormous volume of knowledge appropriately. As graph data, knowledge graphs accumulate and convey knowledge of the real world. It has been...

**Mavis label**: `0` — Knowledge graphs survey, not GNN drug repurposing

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #4 — `10.1038/s41597-023-01960-3`

**Title**: Building a knowledge graph to enable precision medicine  
**Year**: 2023 | **Venue**: Scientific Data | **Citations**: 446

**Abstract**: Developing personalized diagnostic strategies and targeted treatments requires a deep understanding of disease biology and the ability to dissect the relationship between molecular and genetic factors and their phenotypic consequences. However, such knowledge is fragmented...

**Mavis label**: `1` — KG for precision medicine, not GNN drug repurposing

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #5 — `10.1016/j.asoc.2020.106691`

**Title**: Automated medical diagnosis of COVID-19 through EfficientNet convolutional neural network  
**Year**: 2020 | **Venue**: Applied Soft Computing | **Citations**: 395

**Abstract**: _(no abstract)_

**Mavis label**: `0` — EfficientNet COVID diagnosis, CNN not GNN drug repurposing

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #6 — `10.1038/s43586-024-00294-7`

**Title**: Graph neural networks  
**Year**: 2024 | **Venue**: Nature Reviews Methods Primers | **Citations**: 355

**Abstract**: _(no abstract)_

**Mavis label**: `1` — GNN methods primer, not drug repurposing

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #7 — `10.1039/c9sc04336e`

**Title**: Target identification among known drugs by deep learning from heterogeneous networks  
**Year**: 2020 | **Venue**: Chemical Science | **Citations**: 350

**Abstract**: = 0.43 μM) of human retinoic-acid-receptor-related orphan receptor-gamma t (ROR-γt). Furthermore, by specifically targeting ROR-γt, topotecan reveals a potential therapeutic effect in a mouse model of multiple sclerosis. In summary, deepDTnet offers a powerful network-based deep...

**Mavis label**: `1` — deepDTnet for target ID, drug repurposing related but DL not GNN

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #8 — `10.1371/journal.pcbi.1005690`

**Title**: TopologyNet: Topology based deep convolutional and multi-task neural networks for biomolecular property predictions  
**Year**: 2017 | **Venue**: PLoS Computational Biology | **Citations**: 346

**Abstract**: Although deep learning approaches have had tremendous success in image, video and audio processing, computer vision, and speech recognition, their applications to three-dimensional (3D) biomolecular structural data sets have been hindered by the geometric and biological...

**Mavis label**: `0` — TopologyNet biomolecular properties, not drug repurposing

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #9 — `10.1093/bib/bbab159`

**Title**: Utilizing graph machine learning within drug discovery and development  
**Year**: 2021 | **Venue**: Briefings in Bioinformatics | **Citations**: 287

**Abstract**: Graph machine learning (GML) is receiving growing interest within the pharmaceutical and biotechnology industries for its ability to model biomolecular structures, the functional relationships between them, and integrate multi-omic datasets - amongst other data types. Herein, we...

**Mavis label**: `2` — DIRECTLY graph ML for drug discovery + repurposing review

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #10 — `10.1038/s41467-021-27137-3`

**Title**: A unified drug–target interaction prediction framework based on knowledge graph and recommendation system  
**Year**: 2021 | **Venue**: Nature Communications | **Citations**: 256

**Abstract**: Prediction of drug-target interactions (DTI) plays a vital role in drug development in various areas, such as virtual screening, drug repurposing and identification of potential drug side effects. Despite extensive efforts have been invested in perfecting DTI prediction,...

**Mavis label**: `2` — DIRECTLY KGE_NFM KG + recommendation for DTI drug repurposing

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #11 — `10.24963/ijcai.2018/468`

**Title**: Interpretable Drug Target Prediction Using Deep Neural Representation  
**Year**: 2018 | **Venue**:  | **Citations**: 248

**Abstract**: The identification of drug-target interactions (DTIs) is a key task in drug discovery, where drugs are chemical compounds and targets are proteins. Traditional DTI prediction methods are either time consuming (simulation-based methods) or heavily dependent on domain expertise...

**Mavis label**: `1` — DTI prediction deep learning, not GNN drug repurposing

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #12 — `10.1039/c9sc03414e`

**Title**: DEEPScreen: high performance drug–target interaction prediction with convolutional neural networks using 2-D structural compound representations  
**Year**: 2020 | **Venue**: Chemical Science | **Citations**: 245

**Abstract**: screening of the chemogenomic space, to provide novel DTIs which can be experimentally pursued. The source code, trained "ready-to-use" prediction models, all datasets and the results of this study are available at ; https://github.com/cansyl/DEEPscreen.

**Mavis label**: `1` — DEEPScreen CNN for DTI, not GNN drug repurposing

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #13 — `10.1093/bioinformatics/btz600`

**Title**: Discovering protein drug targets using knowledge graph embeddings  
**Year**: 2019 | **Venue**: Bioinformatics | **Citations**: 225

**Abstract**: MOTIVATION: Computational approaches for predicting drug-target interactions (DTIs) can provide valuable insights into the drug mechanism of action. DTI predictions can help to quickly identify new promising (on-target) or unintended (off-target) effects of drugs. However,...

**Mavis label**: `1` — KG embeddings for protein drug targets, not GNN drug repurposing

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #14 — `10.1038/s42256-020-00285-9`

**Title**: A deep learning framework for high-throughput mechanism-driven phenotype compound screening and its application to COVID-19 drug repurposing  
**Year**: 2021 | **Venue**: Nature Machine Intelligence | **Citations**: 223

**Abstract**: _(no abstract)_

**Mavis label**: `1` — DL framework COVID drug repurposing, not GNN specifically

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #15 — `10.1016/j.jbi.2021.103696`

**Title**: Drug repurposing for COVID-19 via knowledge graph completion  
**Year**: 2021 | **Venue**: Journal of Biomedical Informatics | **Citations**: 210

**Abstract**: _(no abstract)_

**Mavis label**: `1` — KG completion for COVID drug repurposing, not GNN

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #16 — `10.1038/s41591-024-03233-x`

**Title**: A foundation model for clinician-centered drug repurposing  
**Year**: 2024 | **Venue**: Nature Medicine | **Citations**: 176

**Abstract**: Drug repurposing—identifying new therapeutic uses for approved drugs—is often a serendipitous and opportunistic endeavour to expand the use of drugs for new diseases. The clinical utility of drug-repurposing artificial intelligence (AI) models remains limited because these...

**Mavis label**: `2` — DIRECTLY TxGNN graph foundation model for zero-shot drug repurposing

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #17 — `10.1038/s41597-023-01974-x`

**Title**: Evaluating explainability for graph neural networks  
**Year**: 2023 | **Venue**: Scientific Data | **Citations**: 155

**Abstract**: As explanations are increasingly used to understand the behavior of graph neural networks (GNNs), evaluating the quality and reliability of GNN explanations is crucial. However, assessing the quality of GNN explanations is challenging as existing graph datasets have no or...

**Mavis label**: `0` — GNN explainability, not drug repurposing

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #18 — `10.1038/s41467-021-27138-2`

**Title**: Network medicine for disease module identification and drug repurposing with the NeDRex platform  
**Year**: 2021 | **Venue**: Nature Communications | **Citations**: 141

**Abstract**: Traditional drug discovery faces a severe efficacy crisis. Repurposing of registered drugs provides an alternative with lower costs and faster drug development timelines. However, the data necessary for the identification of disease modules, i.e. pathways and sub-networks...

**Mavis label**: `1` — NeDRex network medicine for drug repurposing, not GNN specifically

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #19 — `10.1038/s41401-022-00996-2`

**Title**: DrugRep: an automatic virtual screening server for drug repurposing  
**Year**: 2022 | **Venue**: Acta Pharmacologica Sinica | **Citations**: 127

**Abstract**: _(no abstract)_

**Mavis label**: `1` — DrugRep virtual screening, not GNN drug repurposing

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #20 — `10.1038/s41467-023-39301-y`

**Title**: Biomedical knowledge graph learning for drug repurposing by extending guilt-by-association to multiple layers  
**Year**: 2023 | **Venue**: Nature Communications | **Citations**: 109

**Abstract**: Computational drug repurposing aims to identify new indications for existing drugs by utilizing high-throughput data, often in the form of biomedical knowledge graphs. However, learning on biomedical knowledge graphs can be challenging due to the dominance of genes and a small...

**Mavis label**: `1` — Biomedical KG drug repurposing (multi-layer GBA), not GNN

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #21 — `10.3390/cancers15102705`

**Title**: Hybrid Quantum Neural Network for Drug Response Prediction  
**Year**: 2023 | **Venue**: Cancers | **Citations**: 107

**Abstract**: Cancer is one of the leading causes of death worldwide. It is caused by various genetic mutations, which makes every instance of the disease unique. Since chemotherapy can have extremely severe side effects, each patient requires a personalized treatment plan. Finding the...

**Mavis label**: `0` — Hybrid quantum NN for drug response, not GNN drug repurposing

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #22 — `10.18653/v1/2021.naacl-demos.8`

**Title**: COVID-19 Literature Knowledge Graph Construction and Drug Repurposing Report Generation  
**Year**: 2021 | **Venue**:  | **Citations**: 106

**Abstract**: Qingyun Wang, Manling Li, Xuan Wang, Nikolaus Parulian, Guangxing Han, Jiawei Ma, Jingxuan Tu, Ying Lin, Ranran Haoran Zhang, Weili Liu, Aabhas Chauhan, Yingjun Guan, Bangzheng Li, Ruisong Li, Xiangchen Song, Yi Fung, Heng Ji, Jiawei Han, Shih-Fu Chang, James Pustejovsky,...

**Mavis label**: `1` — COVID-19 literature KG + drug repurposing, NLP not GNN

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #23 — `10.1093/bib/bbad431`

**Title**: Drug repositioning based on weighted local information augmented graph neural network  
**Year**: 2023 | **Venue**: Briefings in Bioinformatics | **Citations**: 103

**Abstract**: Drug repositioning, the strategy of redirecting existing drugs to new therapeutic purposes, is pivotal in accelerating drug discovery. While many studies have engaged in modeling complex drug-disease associations, they often overlook the relevance between different node...

**Mavis label**: `2` — DIRECTLY DRAGNN weighted local info GNN for drug repositioning

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #24 — `10.1371/journal.pcbi.1010812`

**Title**: A dual graph neural network for drug–drug interactions prediction based on molecular structure and interactions  
**Year**: 2023 | **Venue**: PLoS Computational Biology | **Citations**: 97

**Abstract**: Expressive molecular representation plays critical roles in researching drug design, while effective methods are beneficial to learning molecular representations and solving related problems in drug discovery, especially for drug-drug interactions (DDIs) prediction. Recently, a...

**Mavis label**: `1` — GNN for DDI prediction, not drug repurposing

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #25 — `10.1093/bib/bbac578`

**Title**: Metapath-aggregated heterogeneous graph neural network for drug–target interaction prediction  
**Year**: 2023 | **Venue**: Briefings in Bioinformatics | **Citations**: 71

**Abstract**: Drug-target interaction (DTI) prediction is an essential step in drug repositioning. A few graph neural network (GNN)-based methods have been proposed for DTI prediction using heterogeneous biological data. However, existing GNN-based methods only aggregate information from...

**Mavis label**: `1` — Heterogeneous GNN for DTI, not drug repurposing

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #26 — `10.1038/s41598-021-02353-5`

**Title**: Drug repurposing for COVID-19 using graph neural network and harmonizing multiple evidence  
**Year**: 2021 | **Venue**: Scientific Reports | **Citations**: 68

**Abstract**: Since the 2019 novel coronavirus disease (COVID-19) outbreak in 2019 and the pandemic continues for more than one year, a vast amount of drug research has been conducted and few of them got FDA approval. Our objective is to prioritize repurposable drugs using a pipeline that...

**Mavis label**: `2` — DIRECTLY GNN + COVID drug repurposing (Sci Rep)

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #27 — `10.1016/j.compbiomed.2022.105992`

**Title**: A computational approach to drug repurposing using graph neural networks  
**Year**: 2022 | **Venue**: Computers in Biology and Medicine | **Citations**: 54

**Abstract**: _(no abstract)_

**Mavis label**: `2` — DIRECTLY computational drug repurposing using GNN

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #28 — `10.1093/bioinformatics/btab191`

**Title**: Drug repurposing against breast cancer by integrating drug-exposure expression profiles and drug–drug links based on graph neural network  
**Year**: 2021 | **Venue**: Bioinformatics | **Citations**: 53

**Abstract**: MOTIVATION: Breast cancer is one of the leading causes of cancer deaths among women worldwide. It is necessary to develop new breast cancer drugs because of the shortcomings of existing therapies. The traditional discovery process is time-consuming and expensive. Repositioning...

**Mavis label**: `2` — DIRECTLY GraphRepur GNN for breast cancer drug repurposing

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #29 — `10.21203/rs.3.rs-114758/v1`

**Title**: Drug Repurposing for COVID-19 using Graph Neural Network with Genetic, Mechanistic, and Epidemiological Validation  
**Year**: 2020 | **Venue**: Research Square | **Citations**: 33

**Abstract**: Amid the pandemic of 2019 novel coronavirus disease (COVID-19) infected by SARS-CoV-2, a vast amount of drug research for prevention and treatment has been quickly conducted, but these efforts have been unsuccessful thus far. Our objective is to prioritize repurposable drugs...

**Mavis label**: `2` — DIRECTLY GNN for COVID drug repurposing (preprint)

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #30 — `10.1109/jbhi.2023.3328337`

**Title**: AntiViralDL: Computational Antiviral Drug Repurposing Using Graph Neural Network and Self-Supervised Learning  
**Year**: 2023 | **Venue**: IEEE Journal of Biomedical and Health Informatics | **Citations**: 21

**Abstract**: Viral infections have emerged as significant public health concerns for decades. Antiviral drugs, specifically designed to combat these infections, have the potential to reduce the disease burden substantially. However, traditional drug development methods, based on biological...

**Mavis label**: `2` — DIRECTLY AntiViralDL GNN + self-supervised for antiviral drug repurposing

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---
