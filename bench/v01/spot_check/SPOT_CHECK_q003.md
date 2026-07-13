# Spot-Check: q003

**Query**: `vector quantized representations for document retrieval`

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

### #1 — `10.1038/s41592-019-0686-2`

**Title**: SciPy 1.0: fundamental algorithms for scientific computing in Python  
**Year**: 2020 | **Venue**: Nature Methods | **Citations**: 38284

**Abstract**: SciPy is an open-source scientific computing library for the Python programming language. Since its initial release in 2001, SciPy has become a de facto standard for leveraging scientific algorithms in Python, with over 600 unique code contributors, thousands of dependent...

**Mavis label**: `0` — SciPy library paper, not VQ for retrieval

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #2 — `10.1145/3326362`

**Title**: Dynamic Graph CNN for Learning on Point Clouds  
**Year**: 2019 | **Venue**: ACM Transactions on Graphics | **Citations**: 6770

**Abstract**: Point clouds provide a flexible geometric representation suitable for countless applications in computer graphics; they also comprise the raw output of most 3D data acquisition devices. While hand-designed features on point clouds have long been proposed in graphics and vision,...

**Mavis label**: `0` — Dynamic graph CNN for point clouds, not document VQ

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #3 — `10.1145/276698.276876`

**Title**: Approximate nearest neighbors  
**Year**: 1998 | **Venue**:  | **Citations**: 4192

**Abstract**: The nearest neighbor problem is the follolving: Given a set of n points P = (PI, . . . ,p,} in some metric space X, preprocess P so as to efficiently answer queries which require finding bhe point in P closest to a query point q E X. We focus on the particularly interesting case...

**Mavis label**: `1` — Approximate nearest neighbors foundations, related to retrieval but no VQ

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #4 — `10.1007/s11263-019-01247-4`

**Title**: Deep Learning for Generic Object Detection: A Survey  
**Year**: 2019 | **Venue**: International Journal of Computer Vision | **Citations**: 2785

**Abstract**: Abstract Object detection, one of the most fundamental and challenging problems in computer vision, seeks to locate object instances from a large number of predefined categories in natural images. Deep learning techniques have emerged as a powerful strategy for learning feature...

**Mavis label**: `0` — Object detection survey, not retrieval

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #5 — `10.1186/s40537-014-0007-7`

**Title**: Deep learning applications and challenges in big data analytics  
**Year**: 2015 | **Venue**: Journal Of Big Data | **Citations**: 2588

**Abstract**: Abstract Big Data Analytics and Deep Learning are two high-focus of data science. Big Data has become important as many organizations both public and private have been collecting massive amounts of domain-specific information, which can contain useful information about problems...

**Mavis label**: `0` — Deep learning big data, not retrieval

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #6 — `10.1016/j.neucom.2019.10.118`

**Title**: A comprehensive survey on support vector machine classification: Applications, challenges and trends  
**Year**: 2020 | **Venue**: Neurocomputing | **Citations**: 2289

**Abstract**: _(no abstract)_

**Mavis label**: `0` — SVM survey, not retrieval

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #7 — ``

**Title**: NetVLAD: CNN architecture for weakly supervised place recognition  
**Year**: 2015 | **Venue**: arXiv (Cornell University) | **Citations**: 1621

**Abstract**: _(no abstract)_

**Mavis label**: `?` — (no reason)

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #8 — `10.1006/jvci.1999.0413`

**Title**: Image Retrieval: Current Techniques, Promising Directions, and Open Issues  
**Year**: 1999 | **Venue**: Journal of Visual Communication and Image Representation | **Citations**: 1593

**Abstract**: _(no abstract)_

**Mavis label**: `1` — Image retrieval 1999, old, no VQ

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #9 — `10.3390/rs71114680`

**Title**: Transferring Deep Convolutional Neural Networks for the Scene Classification of High-Resolution Remote Sensing Imagery  
**Year**: 2015 | **Venue**: Remote Sensing | **Citations**: 1211

**Abstract**: Learning efficient image representations is at the core of the scene classification task of remote sensing imagery. The existing methods for solving the scene classification task, based on either feature coding approaches with low-level hand-engineered features or unsupervised...

**Mavis label**: `0` — Remote sensing CNN scene classification, not VQ for retrieval

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #10 — `10.1609/aaai.v28i1.8952`

**Title**: Supervised Hashing for Image Retrieval via Image Representation Learning  
**Year**: 2014 | **Venue**: Proceedings of the AAAI Conference on Artificial Intelligence | **Citations**: 1007

**Abstract**: Hashing is a popular approximate nearest neighbor search approach for large-scale image retrieval. Supervised hashing, which incorporates similarity/dissimilarity information on entity pairs to improve the quality of hashing function learning, has recently received increasing...

**Mavis label**: `1` — Supervised hashing for image retrieval, not document VQ

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #11 — `10.1609/aaai.v31i1.10958`

**Title**: SummaRuNNer: A Recurrent Neural Network Based Sequence Model for Extractive Summarization of Documents  
**Year**: 2017 | **Venue**: Proceedings of the AAAI Conference on Artificial Intelligence | **Citations**: 959

**Abstract**: We present SummaRuNNer, a Recurrent Neural Network (RNN) based sequence model for extractive summarization of documents and show that it achieves performance better than or comparable to state-of-the-art. Our model has the additional advantage of being very interpretable, since...

**Mavis label**: `0` — SummaRuNNer extractive summarization, not retrieval

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #12 — `10.1109/cvpr.2016.572`

**Title**: NetVLAD: CNN Architecture for Weakly Supervised Place Recognition  
**Year**: 2016 | **Venue**:  | **Citations**: 648

**Abstract**: We tackle the problem of large scale visual place recognition, where the task is to quickly and accurately recognize the location of a given query photograph. We present the following four principal contributions. First, we develop a convolutional neural network (CNN)...

**Mavis label**: `0` — NetVLAD place recognition, not document

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #13 — `10.1109/cvpr42600.2020.00877`

**Title**: ActBERT: Learning Global-Local Video-Text Representations  
**Year**: 2020 | **Venue**:  | **Citations**: 408

**Abstract**: In this paper, we introduce ActBERT for self-supervised learning of joint video-text representations from unlabeled data. First, we leverage global action information to catalyze the mutual interactions between linguistic texts and local regional objects. It uncovers global and...

**Mavis label**: `0` — ActBERT video-text, not VQ for retrieval

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #14 — `10.18653/v1/2022.naacl-main.272`

**Title**: ColBERTv2: Effective and Efficient Retrieval via Lightweight Late Interaction  
**Year**: 2022 | **Venue**: Proceedings of the 2022 Conference of the North American Chapter of the Association for Computational Linguistics: Human Language Technologies | **Citations**: 282

**Abstract**: Keshav Santhanam, Omar Khattab, Jon Saad-Falcon, Christopher Potts, Matei Zaharia. Proceedings of the 2022 Conference of the North American Chapter of the Association for Computational Linguistics: Human Language Technologies. 2022.

**Mavis label**: `1` — ColBERTv2 (duplicate of #14, late interaction retrieval)

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #15 — `10.1109/cvpr.2009.5206529`

**Title**: Efficient representation of local geometry for large scale object retrieval  
**Year**: 2009 | **Venue**: 2009 IEEE Conference on Computer Vision and Pattern Recognition | **Citations**: 265

**Abstract**: State of the art methods for image and object retrieval exploit both appearance (via visual words) and local geometry (spatial extent, relative pose). In large scale problems, memory becomes a limiting factor - local geometry is stored for each feature detected in each image and...

**Mavis label**: `0` — Local geometry for object retrieval, not VQ for document

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #16 — `10.1145/3394486.3403305`

**Title**: Embedding-based Retrieval in Facebook Search  
**Year**: 2020 | **Venue**:  | **Citations**: 263

**Abstract**: Search in social networks such as Facebook poses different challenges than in classical web search: besides the query text, it is important to take into account the searcher's context to provide relevant results. Their social graph is an integral part of this context and is a...

**Mavis label**: `1` — Embedding-based retrieval at Facebook, not VQ

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #17 — `10.1109/tip.2016.2564638`

**Title**: Supervised Matrix Factorization Hashing for Cross-Modal Retrieval  
**Year**: 2016 | **Venue**: IEEE Transactions on Image Processing | **Citations**: 250

**Abstract**: The target of cross-modal hashing is to embed heterogeneous multimedia data into a common low-dimensional Hamming space, which plays a pivotal part in multimedia retrieval due to the emergence of big multimodal data. Recently, matrix factorization has achieved great success in...

**Mavis label**: `0` — Cross-modal hashing, not VQ for document

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #18 — `10.1109/tmm.2018.2832602`

**Title**: Predicting Visual Features From Text for Image and Video Caption Retrieval  
**Year**: 2018 | **Venue**: IEEE Transactions on Multimedia | **Citations**: 191

**Abstract**: This paper strives to find amidst a set of sentences the one best describing the content of a given image or video. Different from existing works, which rely on a joint subspace for their image and video caption retrieval, we propose to do so in a visual space exclusively. Apart...

**Mavis label**: `0` — Predicting visual features from text, not VQ retrieval

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #19 — `10.18653/v1/2021.naacl-main.241`

**Title**: COIL: Revisit Exact Lexical Match in Information Retrieval with Contextualized Inverted List  
**Year**: 2021 | **Venue**:  | **Citations**: 174

**Abstract**: Classical information retrieval systems such as BM25 rely on exact lexical match and carry out search efficiently with inverted list index. Recent neural IR models shifts towards soft semantic matching all query document terms, but they lose the computation efficiency of exact...

**Mavis label**: `1` — COIL exact lexical match, document retrieval but no VQ

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #20 — `10.24963/ijcai.2018/396`

**Title**: Unsupervised Deep Hashing via Binary Latent Factor Models for Large-scale Cross-modal Retrieval  
**Year**: 2018 | **Venue**:  | **Citations**: 170

**Abstract**: Despite its great success, matrix factorization based cross-modality hashing suffers from two problems: 1) there is no engagement between feature learning and binarization; and 2) most existing methods impose the relaxation strategy by discarding the discrete constraints when...

**Mavis label**: `0` — Unsupervised deep hashing, cross-modal, not VQ for document

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #21 — `10.1109/cvpr.2019.00523`

**Title**: Semantically Tied Paired Cycle Consistency for Zero-Shot Sketch-Based Image Retrieval  
**Year**: 2019 | **Venue**:  | **Citations**: 165

**Abstract**: Zero-shot sketch-based image retrieval (SBIR) is an emerging task in computer vision, allowing to retrieve natural images relevant to sketch queries that might not been seen in the training phase. Existing works either require aligned sketch-image pairs or inefficient memory...

**Mavis label**: `0` — Zero-shot sketch-based image retrieval, not VQ

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #22 — `10.1111/cogs.12047`

**Title**: Optimization and Quantization in Gradient Symbol Systems: A Framework for Integrating the Continuous and the Discrete in Cognition  
**Year**: 2013 | **Venue**: Cognitive Science | **Citations**: 141

**Abstract**: Mental representations have continuous as well as discrete, combinatorial properties. For example, while predominantly discrete, phonological representations also vary continuously; this is reflected by gradient effects in instrumental studies of speech production. Can an...

**Mavis label**: `0` — Optimization quantization in cognitive science, not VQ for retrieval

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #23 — `10.18653/v1/2022.acl-long.203`

**Title**: Unsupervised Corpus Aware Language Model Pre-training for Dense Passage Retrieval  
**Year**: 2022 | **Venue**: Proceedings of the 60th Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers) | **Citations**: 139

**Abstract**: Recent research demonstrates the effectiveness of using fine-tuned language models (LM) for dense retrieval. However, dense retrievers are hard to train, typically requiring heavily engineered fine-tuning pipelines to realize their full potential. In this paper, we identify and...

**Mavis label**: `1` — Dense passage retrieval, not VQ specifically

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #24 — `10.1109/access.2023.3295776`

**Title**: Information Retrieval: Recent Advances and Beyond  
**Year**: 2023 | **Venue**: IEEE Access | **Citations**: 130

**Abstract**: This paper provides an extensive and thorough overview of the models and techniques utilized in the first and second stages of the typical information retrieval processing chain. Our discussion encompasses the current state-of-the-art models, covering a wide range of methods and...

**Mavis label**: `1` — Information retrieval survey, broad, may cover VQ

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #25 — `10.5121/iju.2012.3202`

**Title**: Content Based Video Retrieval Systems  
**Year**: 2012 | **Venue**: International Journal of UbiComp | **Citations**: 101

**Abstract**: With the development of multimedia data types and available bandwidth there is huge demand of video retrieval systems, as users shift from text based retrieval systems to content based retrieval systems. Selection of extracted features play an important role in content based...

**Mavis label**: `0` — Content-based video retrieval, not document VQ

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #26 — `10.1007/978-3-030-01177-2_12`

**Title**: Legal Document Retrieval using Document Vector Embeddings and Deep Learning  
**Year**: 2018 | **Venue**: Advances in Intelligent Systems and Computing | **Citations**: 89

**Abstract**: _(no abstract)_

**Mavis label**: `1` — Legal document retrieval with embeddings, document but not VQ

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #27 — `10.1007/s10278-012-9495-1`

**Title**: Content-Based Retrieval of Focal Liver Lesions Using Bag-of-Visual-Words Representations of Single- and Multiphase Contrast-Enhanced CT Images  
**Year**: 2012 | **Venue**: Journal of Digital Imaging | **Citations**: 84

**Abstract**: _(no abstract)_

**Mavis label**: `0` — Medical image CBIR, not VQ for document

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #28 — `10.1007/s10916-016-0659-2`

**Title**: Medical Image Retrieval Using Vector Quantization and Fuzzy S-tree  
**Year**: 2016 | **Venue**: Journal of Medical Systems | **Citations**: 80

**Abstract**: The aim of the article is to present a novel method for fuzzy medical image retrieval (FMIR) using vector quantization (VQ) with fuzzy signatures in conjunction with fuzzy S-trees. In past times, a task of similar pictures searching was not based on searching for similar content...

**Mavis label**: `2` — DIRECTLY Medical image retrieval using VQ (closest analog to document VQ)

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #29 — `10.1109/icdar.2013.114`

**Title**: Writer Identification and Writer Retrieval Using the Fisher Vector on Visual Vocabularies  
**Year**: 2013 | **Venue**: 2013 12th International Conference on Document Analysis and Recognition | **Citations**: 72

**Abstract**: In this paper a method for writer identification and writer retrieval is presented. Writer identification is the task of identifying the writer of a document out of a database of known writers. In contrast to identification, writer retrieval is the task of finding documents in a...

**Mavis label**: `1` — Fisher Vector for writer retrieval, VQ-adjacent, document

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---

### #30 — `10.1145/3488560.3498443`

**Title**: Learning Discrete Representations via Constrained Clustering for Effective and Efficient Dense Retrieval  
**Year**: 2022 | **Venue**: Proceedings of the Fifteenth ACM International Conference on Web Search and Data Mining | **Citations**: 59

**Abstract**: Dense Retrieval (DR) has achieved state-of-the-art first-stage ranking effectiveness. However, the efficiency of most existing DR models is limited by the large memory cost of storing dense vectors and the time-consuming nearest neighbor search (NNS) in vector space. Therefore,...

**Mavis label**: `2` — DIRECTLY Product Quantization for dense retrieval (RepCONC) - core VQ for document retrieval

**Your judgment**:

- [ ] **0** (not relevant) — agree / change to: ____
- [ ] **1** (partial) — agree / change to: ____
- [ ] **2** (directly relevant) — agree / change to: ____

**User label**: `___`  
**User note** (optional, only if disagree): 

---
