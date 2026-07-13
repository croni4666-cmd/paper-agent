# Spot-Check: q006

**Query**: `long-context transformer attention degradation on long documents`

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

### #1 — `10.1609/aaai.v35i12.17325`

**Title**: Informer: Beyond Efficient Transformer for Long Sequence Time-Series Forecasting  
**Year**: 2021 | **Venue**: Proceedings of the AAAI Conference on Artificial Intelligence | **Citations**: 6162

**Abstract**: Many real-world applications require the prediction of long sequence time-series, such as electricity consumption planning. Long sequence time-series forecasting (LSTF) demands a high prediction capacity of the model, which is the ability to capture precise long-range dependency...

**Mavis label**: `1` — Long-sequence Transformer (Informer), but time-series not documents

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #2 — `10.18653/v1/2021.acl-long.353`

**Title**: Prefix-Tuning: Optimizing Continuous Prompts for Generation  
**Year**: 2021 | **Venue**:  | **Citations**: 2215

**Abstract**: Xiang Lisa Li, Percy Liang. Proceedings of the 59th Annual Meeting of the Association for Computational Linguistics and the 11th International Joint Conference on Natural Language Processing (Volume 1: Long Papers). 2021.

**Mavis label**: `0` — Prefix-tuning continuous prompts, not long-context attention

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #3 — `10.1038/s41467-020-17591-w`

**Title**: Earthquake transformer—an attentive deep-learning model for simultaneous earthquake detection and phase picking  
**Year**: 2020 | **Venue**: Nature Communications | **Citations**: 1082

**Abstract**: Earthquake signal detection and seismic phase picking are challenging tasks in the processing of noisy data and the monitoring of microearthquakes. Here we present a global deep-learning model for simultaneous earthquake detection and phase picking. Performing these two related...

**Mavis label**: `0` — Earthquake transformer, seismic not NLP

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #4 — `10.1162/tacl_a_00638`

**Title**: Lost in the Middle: How Language Models Use Long Contexts  
**Year**: 2024 | **Venue**: Transactions of the Association for Computational Linguistics | **Citations**: 957

**Abstract**: Abstract While recent language models have the ability to take long contexts as input, relatively little is known about how well they use longer context. We analyze the performance of language models on two tasks that require identifying relevant information in their input...

**Mavis label**: `2` — DIRECTLY Lost in the Middle - long context LM attention degradation paper

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #5 — `10.18653/v1/2020.emnlp-main.523`

**Title**: LUKE: Deep Contextualized Entity Representations with Entity-aware Self-attention  
**Year**: 2020 | **Venue**:  | **Citations**: 567

**Abstract**: Entity representations are useful in natural language tasks involving entities. In this paper, we propose new pretrained contextualized representations of words and entities based on the bidirectional transformer The proposed model treats words and entities in a given text as...

**Mavis label**: `0` — LUKE entity representations, not long-context attention

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #6 — `10.1609/aaai.v36i3.20158`

**Title**: Anchor DETR: Query Design for Transformer-Based Detector  
**Year**: 2022 | **Venue**: Proceedings of the AAAI Conference on Artificial Intelligence | **Citations**: 458

**Abstract**: In this paper, we propose a novel query design for the transformer-based object detection. In previous transformer-based detectors, the object queries are a set of learned embeddings. However, each learned embedding does not have an explicit physical meaning and we cannot...

**Mavis label**: `0` — Anchor DETR object detection, not NLP

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #7 — `10.1145/3485447.3512217`

**Title**: ET-BERT: A Contextualized Datagram Representation with Pre-training Transformers for Encrypted Traffic Classification  
**Year**: 2022 | **Venue**: Proceedings of the ACM Web Conference 2022 | **Citations**: 452

**Abstract**: Encrypted traffic classification requires discriminative and robust traffic representation captured from content-invisible and imbalanced traffic data for accurate classification, which is challenging but indispensable to achieve network security and network management. The...

**Mavis label**: `0` — ET-BERT encrypted traffic, not long-doc

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #8 — `10.3390/su7010988`

**Title**: Understanding and Enhancing Soil Biological Health: The Solution for Reversing Soil Degradation  
**Year**: 2015 | **Venue**: Sustainability | **Citations**: 434

**Abstract**: Our objective is to provide an optimistic strategy for reversing soil degradation by increasing public and private research efforts to understand the role of soil biology, particularly microbiology, on the health of our world’s soils. We begin by defining soil quality/soil...

**Mavis label**: `0` — Soil biology, off-topic (interesting - 'degradation' in title matched but content unrelated)

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #9 — `10.1609/aaai.v37i11.26538`

**Title**: TrOCR: Transformer-Based Optical Character Recognition with Pre-trained Models  
**Year**: 2023 | **Venue**: Proceedings of the AAAI Conference on Artificial Intelligence | **Citations**: 391

**Abstract**: Text recognition is a long-standing research problem for document digitalization. Existing approaches are usually built based on CNN for image understanding and RNN for char-level text generation. In addition, another language model is usually needed to improve the overall...

**Mavis label**: `0` — TrOCR text recognition, not long-context attention

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #10 — `10.18653/v1/2023.findings-emnlp.936`

**Title**: RWKV: Reinventing RNNs for the Transformer Era  
**Year**: 2023 | **Venue**:  | **Citations**: 310

**Abstract**: Bo Peng, Eric Alcaide, Quentin Anthony, Alon Albalak, Samuel Arcadinho, Stella Biderman, Huanqi Cao, Xin Cheng, Michael Chung, Leon Derczynski, Xingjian Du, Matteo Grella, Kranthi Gv, Xuzheng He, Haowen Hou, Przemyslaw Kazienko, Jan Kocon, Jiaming Kong, Bartłomiej Koptyra,...

**Mavis label**: `1` — RWKV RNN-Transformer alternative, related to long-context

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #11 — `10.18653/v1/p18-1117`

**Title**: Context-Aware Neural Machine Translation Learns Anaphora Resolution  
**Year**: 2018 | **Venue**:  | **Citations**: 307

**Abstract**: Standard machine translation systems process sentences in isolation and hence ignore extra-sentential information, even though extended context can both prevent mistakes in ambiguous cases and improve translation coherence. We introduce a context-aware neural machine translation...

**Mavis label**: `1` — Context-aware NMT, document-level, not attention degradation

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #12 — `10.1609/aaai.v34i07.6903`

**Title**: Decoupled Attention Network for Text Recognition  
**Year**: 2020 | **Venue**: Proceedings of the AAAI Conference on Artificial Intelligence | **Citations**: 304

**Abstract**: Text recognition has attracted considerable research interests because of its various applications. The cutting-edge text recognition methods are based on attention mechanisms. However, most of attention methods usually suffer from serious alignment problem due to its recurrency...

**Mavis label**: `0` — Decoupled attention for OCR, not long-doc

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #13 — `10.5194/wes-1-1-2016`

**Title**: Long-term research challenges in wind energy – a research agenda by the European Academy of Wind Energy  
**Year**: 2016 | **Venue**: Wind energy science | **Citations**: 297

**Abstract**: Abstract. The European Academy of Wind Energy (eawe), representing universities and institutes with a significant wind energy programme in 14 countries, has discussed the long-term research challenges in wind energy. In contrast to research agendas addressing short- to...

**Mavis label**: `0` — Wind energy long-term research, off-topic

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #14 — `10.18653/v1/d18-1325`

**Title**: Document-Level Neural Machine Translation with Hierarchical Attention Networks  
**Year**: 2018 | **Venue**:  | **Citations**: 276

**Abstract**: Neural Machine Translation (NMT) can be improved by including document-level contextual information. For this purpose, we propose a hierarchical attention model to capture the context in a structured and dynamic manner. The model is integrated in the original NMT architecture as...

**Mavis label**: `1` — Document-level NMT hierarchical attention, related to long context

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #15 — `10.3390/rs14122861`

**Title**: Swin-Transformer-Enabled YOLOv5 with Attention Mechanism for Small Object Detection on Satellite Images  
**Year**: 2022 | **Venue**: Remote Sensing | **Citations**: 213

**Abstract**: Object detection has made tremendous progress in natural images over the last decade. However, the results are hardly satisfactory when the natural image object detection algorithm is directly applied to satellite images. This is due to the intrinsic differences in the scale and...

**Mavis label**: `0` — Satellite imagery YOLO, not NLP long-doc

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #16 — `10.18653/v1/2022.findings-naacl.55`

**Title**: LongT5: Efficient Text-To-Text Transformer for Long Sequences  
**Year**: 2022 | **Venue**: Findings of the Association for Computational Linguistics: NAACL 2022 | **Citations**: 211

**Abstract**: Recent work has shown that either (1) increasing the input length or (2) increasing model size can improve the performance of Transformer-based neural models. In this paper, we present LongT5, a new model that explores the effects of scaling both the input length and model size...

**Mavis label**: `2` — DIRECTLY LongT5 long-input Transformer with TGlobal attention

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #17 — `10.1016/j.apenergy.2022.120565`

**Title**: Spatio-temporal wind speed forecasting using graph networks and novel Transformer architectures  
**Year**: 2022 | **Venue**: Applied Energy | **Citations**: 183

**Abstract**: To improve the security and reliability of wind energy production, short-term forecasting has become of utmost importance. This study focuses on multi-step spatio-temporal wind speed forecasting for the Norwegian continental shelf. In particular, the study considers 14 offshore...

**Mavis label**: `0` — Wind forecasting Transformer, not long-doc NLP

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #18 — `10.48550/arXiv.2507.02259`

**Title**: MemAgent: Reshaping Long-Context LLM with Multi-Conv RL-based Memory Agent  
**Year**: 2025 | **Venue**: arXiv.org | **Citations**: 180

**Abstract**: Despite improvements by length extrapolation, efficient attention and memory modules, handling infinitely long documents with linear complexity without performance degradation during extrapolation remains the ultimate challenge in long-text processing. We directly optimize for...

**Mavis label**: `2` — DIRECTLY MemAgent long-context LLM memory agent

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #19 — `10.4067/s0718-95162010000100004`

**Title**: BIOLOGICAL ASPECTS INVOLVED IN THE DEGRADATION OF ORGANIC POLLUTANTS  
**Year**: 2010 | **Venue**: Journal of soil science and plant nutrition | **Citations**: 179

**Abstract**: Worldwide use of pesticide has increased dramatically during the last two decades. As a consequence, pesticide residues and their transformation products are frequently found in groundwater and surface waters. This review summarizes information about polycyclic aromatic...

**Mavis label**: `0` — Organic pollutant degradation, chemistry, not NLP

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #20 — `10.18653/v1/2020.findings-emnlp.232`

**Title**: Blockwise Self-Attention for Long Document Understanding  
**Year**: 2020 | **Venue**:  | **Citations**: 150

**Abstract**: We present BlockBERT, a lightweight and efficient BERT model for better modeling longdistance dependencies. Our model extends BERT by introducing sparse block structures into the attention matrix to reduce both memory consumption and training/inference time, which also enables...

**Mavis label**: `2` — DIRECTLY BlockBERT block sparse attention for long documents

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #21 — `10.1145/3533767.3534367`

**Title**: jTrans: jump-aware transformer for binary code similarity detection  
**Year**: 2022 | **Venue**:  | **Citations**: 146

**Abstract**: Binary code similarity detection (BCSD) has important applications in various fields such as vulnerabilities detection, software component analysis, and reverse engineering. Recent studies have shown that deep neural networks (DNNs) can comprehend instructions or control-flow...

**Mavis label**: `0` — Binary code similarity (jTrans), not document

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #22 — `10.1093/jamia/ocac225`

**Title**: A comparative study of pretrained language models for long clinical text  
**Year**: 2022 | **Venue**: Journal of the American Medical Informatics Association | **Citations**: 139

**Abstract**: OBJECTIVE: Clinical knowledge-enriched transformer models (eg, ClinicalBERT) have state-of-the-art results on clinical natural language processing (NLP) tasks. One of the core limitations of these transformer models is the substantial memory consumption due to their full...

**Mavis label**: `2` — DIRECTLY long clinical text + transformer memory degradation

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #23 — `10.3390/s23052385`

**Title**: Vision Transformers in Image Restoration: A Survey  
**Year**: 2023 | **Venue**: Sensors | **Citations**: 133

**Abstract**: The Vision Transformer (ViT) architecture has been remarkably successful in image restoration. For a while, Convolutional Neural Networks (CNN) predominated in most computer vision tasks. Now, both CNN and ViT are efficient approaches that demonstrate powerful capabilities to...

**Mavis label**: `0` — Vision transformer image restoration, not NLP

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #24 — `10.18653/v1/2025.acl-long.127`

**Title**: Smarter, Better, Faster, Longer: A Modern Bidirectional Encoder for Fast, Memory Efficient, and Long Context Finetuning and Inference  
**Year**: 2025 | **Venue**:  | **Citations**: 129

**Abstract**: Benjamin Warner, Antoine Chaffin, Benjamin Clavié, Orion Weller, Oskar Hallström, Said Taghadouini, Alexis Gallagher, Raja Biswas, Faisal Ladhak, Tom Aarsen, Griffin Thomas Adams, Jeremy Howard, Iacopo Poli. Proceedings of the 63rd Annual Meeting of the Association for...

**Mavis label**: `2` — DIRECTLY long context finetuning/inference encoder (ModernBERT-style)

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #25 — `10.1145/3579371.3589057`

**Title**: FACT: FFN-Attention Co-optimized Transformer Architecture with Eager Correlation Prediction  
**Year**: 2023 | **Venue**:  | **Citations**: 98

**Abstract**: Transformer model is becoming prevalent in various AI applications with its outstanding performance. However, the high cost of computation and memory footprint make its inference inefficient. We discover that among the three main computation modules in a Transformer model (QKV...

**Mavis label**: `1` — FACT efficient Transformer, related to attention but not long-doc degradation

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #26 — `10.48550/arXiv.2402.16617`

**Title**: Long-Context Language Modeling with Parallel Context Encoding  
**Year**: 2024 | **Venue**: Annual Meeting of the Association for Computational Linguistics | **Citations**: 94

**Abstract**: Extending large language models (LLMs) to process longer inputs is crucial for a wide range of applications. However, the substantial computational cost of transformers and limited generalization of positional encoding restrict the size of their context window. We introduce...

**Mavis label**: `2` — DIRECTLY long-context LLM with parallel encoding (CEPE)

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #27 — `10.18653/v1/2024.acl-long.91`

**Title**: LongLLMLingua: Accelerating and Enhancing LLMs in Long Context Scenarios via Prompt Compression  
**Year**: 2024 | **Venue**:  | **Citations**: 70

**Abstract**: Huiqiang Jiang, Qianhui Wu, Xufang Luo, Dongsheng Li, Chin-Yew Lin, Yuqing Yang, Lili Qiu. Proceedings of the 62nd Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers). 2024.

**Mavis label**: `2` — DIRECTLY LongLLMLingua LLM long context prompt compression

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #28 — `10.1007/s11633-024-1393-8`

**Title**: Vision Transformers with Hierarchical Attention  
**Year**: 2024 | **Venue**: Machine Intelligence Research | **Citations**: 53

**Abstract**: Abstract This paper tackles the high computational/space complexity associated with multi-head self-attention (MHSA) in vanilla vision transformers. To this end, we propose hierarchical MHSA (H-MHSA), a novel approach that computes sell-attention in a hierarchical fashion....

**Mavis label**: `0` — Hierarchical attention vision transformer, not NLP

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #29 — `10.18653/v1/2020.emnlp-main.211`

**Title**: Losing Heads in the Lottery: Pruning Transformer Attention in Neural Machine Translation  
**Year**: 2020 | **Venue**:  | **Citations**: 50

**Abstract**: The attention mechanism is the crucial component of the transformer architecture. Recent research shows that most attention heads are not confident in their decisions and can be pruned after training. However, removing them before training a model results in lower quality. In...

**Mavis label**: `1` — Pruning Transformer attention heads, related but not long-doc

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #30 — `10.18653/v1/2020.emnlp-main.57`

**Title**: PAIR: Planning and Iterative Refinement in Pre-trained Transformers for Long Text Generation  
**Year**: 2020 | **Venue**:  | **Citations**: 44

**Abstract**: Pre-trained Transformers have enabled impressive breakthroughs in generating long and fluent text, yet their outputs are often "rambling" without coherently arranged content.

**Mavis label**: `2` — DIRECTLY PAIR pre-trained transformers for long text generation

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---
