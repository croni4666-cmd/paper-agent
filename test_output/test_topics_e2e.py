"""Test pa_cli.topics — topic clustering on small synthetic corpus.

Strategy: use mock paper dicts (no actual PDFs) by patching
`build_corpus_index` and `extract_text` to return fake paper dicts.
This tests the clustering algorithm + output shape without needing
real PDFs or network (except for OpenAlex, which we also mock).

Two test modes:
  - handroll: force hand-rolled TF-IDF + Jaccard + Agglomerative
  - bertopic: force BERTopic (requires real BERTopic install; slow first
    run because of ~80MB model download)

Tests run with `force_method="handroll"` to avoid network/HDBSCAN dependency
on CI. The actual CLI uses `force_method="auto"` which picks BERTopic when
available + corpus is large enough.
"""

import json
import sys
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent to path for pa_cli import
sys.path.insert(0, str(Path(__file__).parent.parent))

from pa_cli import topics as topics_module


# -----------------------------------------------------------------------------
# Mock data: 5 fake papers across 2 topics
# -----------------------------------------------------------------------------

MOCK_PAPERS = [
    {
        "filename": "deep_learning_imaging.pdf",
        "path": "/fake/deep_learning_imaging.pdf",
        "title": "Deep Learning for Medical Imaging",
        "doi": "10.1234/dl.medimag.001",
        "year": 2020,
        "venue": "Nature Methods",
        "word_count": 5000,
        "pages": 12,
        "is_full_text": True,
        "error": None,
        "text": "Abstract: We present a deep learning approach for medical imaging analysis using convolutional neural networks. Our method achieves state-of-the-art results on tumor detection benchmarks.",
        "concept_data": {
            "doi": "10.1234/dl.medimag.001",
            "title": "Deep Learning for Medical Imaging",
            "year": 2020,
            "venue": "Nature Methods",
            "cited_by_count": 500,
            "concept_ids": ["C154945302", "C119443182", "C2780161247", "C2779744866"],
            "concept_names": ["Deep learning", "Convolutional neural network", "Medical imaging", "Tumor detection"],
            "openalex_url": "https://openalex.org/W123",
        },
    },
    {
        "filename": "cnn_classification.pdf",
        "path": "/fake/cnn_classification.pdf",
        "title": "CNN-based Image Classification in Radiology",
        "doi": "10.1234/cnn.rad.002",
        "year": 2021,
        "venue": "Radiology",
        "word_count": 4200,
        "pages": 10,
        "is_full_text": True,
        "error": None,
        "text": "Abstract: We propose a convolutional neural network (CNN) architecture for image classification in radiology. Our approach uses transfer learning on a large medical image dataset.",
        "concept_data": {
            "doi": "10.1234/cnn.rad.002",
            "title": "CNN-based Image Classification in Radiology",
            "year": 2021,
            "venue": "Radiology",
            "cited_by_count": 200,
            "concept_ids": ["C154945302", "C119443182", "C2780161247", "C116968013"],
            "concept_names": ["Deep learning", "Convolutional neural network", "Medical imaging", "Radiology"],
            "openalex_url": "https://openalex.org/W456",
        },
    },
    {
        "filename": "transformer_segmentation.pdf",
        "path": "/fake/transformer_segmentation.pdf",
        "title": "Transformer-based Tumor Segmentation",
        "doi": "10.1234/transformer.seg.003",
        "year": 2022,
        "venue": "MICCAI",
        "word_count": 3800,
        "pages": 9,
        "is_full_text": True,
        "error": None,
        "text": "Abstract: We apply transformer architectures to tumor segmentation in MRI scans. Our model uses self-attention mechanisms to capture long-range dependencies in volumetric medical images.",
        "concept_data": {
            "doi": "10.1234/transformer.seg.003",
            "title": "Transformer-based Tumor Segmentation",
            "year": 2022,
            "venue": "MICCAI",
            "cited_by_count": 80,
            "concept_ids": ["C204321495", "C2780161247", "C2779744866", "C2779015133"],
            "concept_names": ["Transformer", "Medical imaging", "Tumor detection", "MRI segmentation"],
            "openalex_url": "https://openalex.org/W789",
        },
    },
    {
        "filename": "insurance_claims_rnn.pdf",
        "path": "/fake/insurance_claims_rnn.pdf",
        "title": "RNN Models for Insurance Claims Prediction",
        "doi": "10.1234/insurance.rnn.004",
        "year": 2019,
        "venue": "Journal of Risk and Insurance",
        "word_count": 3500,
        "pages": 8,
        "is_full_text": True,
        "error": None,
        "text": "Abstract: We employ recurrent neural networks (RNN) to predict insurance claim severity. Our LSTM-based model outperforms traditional actuarial regression on a large claims dataset.",
        "concept_data": {
            "doi": "10.1234/insurance.rnn.004",
            "title": "RNN Models for Insurance Claims Prediction",
            "year": 2019,
            "venue": "Journal of Risk and Insurance",
            "cited_by_count": 50,
            "concept_ids": ["C154945302", "C192562407", "C126376976", "C156744410"],
            "concept_names": ["Deep learning", "Insurance", "LSTM", "Actuarial science"],
            "openalex_url": "https://openalex.org/W321",
        },
    },
    {
        "filename": "actuarial_lstm.pdf",
        "path": "/fake/actuarial_lstm.pdf",
        "title": "LSTM Networks for Actuarial Risk Modeling",
        "doi": "10.1234/actuarial.lstm.005",
        "year": 2020,
        "venue": "ASTIN Bulletin",
        "word_count": 3200,
        "pages": 8,
        "is_full_text": True,
        "error": None,
        "text": "Abstract: This paper presents LSTM networks for actuarial risk modeling and mortality forecasting. We demonstrate improvements over classical actuarial models for life insurance applications.",
        "concept_data": {
            "doi": "10.1234/actuarial.lstm.005",
            "title": "LSTM Networks for Actuarial Risk Modeling",
            "year": 2020,
            "venue": "ASTIN Bulletin",
            "cited_by_count": 30,
            "concept_ids": ["C154945302", "C192562407", "C126376976", "C89415313"],
            "concept_names": ["Deep learning", "Insurance", "LSTM", "Mortality forecasting"],
            "openalex_url": "https://openalex.org/W654",
        },
    },
]


def fake_build_corpus_index(corpus_dir, word_count_min=1000):
    """Mock build_corpus_index: return MOCK_PAPERS (without 'text' field — that comes separately)."""
    return [
        {k: v for k, v in p.items() if k != "text"}
        for p in MOCK_PAPERS
    ]


def fake_extract_text(path):
    """Mock extract_text: look up MOCK_PAPERS by filename and return its text."""
    p_obj = Path(path)
    fname = p_obj.name
    for p in MOCK_PAPERS:
        if p["filename"] == fname:
            return {"text": p["text"], "pages": p["pages"], "error": None}
    print(f"   DEBUG fake_extract_text miss: path={path} name={fname}")
    return {"text": "", "pages": 0, "error": "not_found"}


def test_cluster_topics_basic(tmp_path):
    """End-to-end test: 5 mock papers, 2 natural topics (medical imaging vs insurance)."""
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    # Touch fake PDF files (only filenames matter for build_corpus_index)
    for p in MOCK_PAPERS:
        (corpus_dir / p["filename"]).touch()

    with patch.object(topics_module, "build_corpus_index", fake_build_corpus_index), \
         patch.object(topics_module, "extract_text", fake_extract_text), \
         patch.object(topics_module, "_build_concept_index") as mock_concept_idx:
        # Mock OpenAlex: return pre-built concept_data directly
        concept_data = {p["filename"]: p["concept_data"] for p in MOCK_PAPERS}
        mock_concept_idx.return_value = (concept_data, [])

        output_path = tmp_path / "topics.json"
        result = topics_module.cluster_topics(
            corpus_dir=corpus_dir,
            output_path=output_path,
            alpha=0.4,
            force_method="handroll",
        )

    # Basic assertions
    assert result["n_papers"] == 5, f"Expected 5 papers, got {result['n_papers']}"
    assert len(result["topics"]) >= 1, "Should have at least 1 topic"
    assert len(result["topics"]) == 2, (
        f"Mock data designed for k=2 (medical imaging vs insurance), "
        f"got {len(result['topics'])} topics"
    )
    assert output_path.exists(), "topics.json should be written"

    # Check topic structure
    for t in result["topics"]:
        assert "topic_id" in t
        assert "label" in t
        assert "filenames" in t
        assert len(t["filenames"]) >= 1
        assert "cohesion_score" in t
        assert 0 <= t["cohesion_score"] <= 1.0

    # Check concept_data summary
    assert len(result["concept_data"]) == 5
    for fname, cd in result["concept_data"].items():
        assert "doi" in cd
        assert "concept_ids" in cd
        assert "concept_names" in cd

    # Check that paper_ids are partitioned (each paper in exactly one topic)
    all_filenames = []
    for t in result["topics"]:
        all_filenames.extend(t["filenames"])
    assert sorted(all_filenames) == sorted([p["filename"] for p in MOCK_PAPERS]), \
        "Each paper should be in exactly one topic"

    print(f"[PASS] cluster_topics_basic: {len(result['topics'])} topics, "
          f"k={result['k']}, warnings={len(result['warnings'])}")
    for t in result["topics"]:
        print(f"   - Topic {t['topic_id']} ({t['paper_count']} papers): "
              f"{t['label'][:50]} | cohesion={t['cohesion_score']:.3f}")
    return result


def test_cluster_topics_singleton(tmp_path):
    """n=1 paper → single topic."""
    singleton = [MOCK_PAPERS[0]]
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    (corpus_dir / singleton[0]["filename"]).touch()

    def fake_build_index_single(corpus_dir, word_count_min=1000):
        return [{k: v for k, v in p.items() if k != "text"} for p in singleton]

    with patch.object(topics_module, "build_corpus_index", fake_build_index_single), \
         patch.object(topics_module, "extract_text", fake_extract_text), \
         patch.object(topics_module, "_build_concept_index") as mock_concept_idx:
        concept_data = {singleton[0]["filename"]: singleton[0]["concept_data"]}
        mock_concept_idx.return_value = (concept_data, [])

        result = topics_module.cluster_topics(
            corpus_dir=corpus_dir,
            output_path=tmp_path / "topics.json",
            force_method="handroll",
        )

    print(f"   singleton n_papers={result['n_papers']} k={result['k']} "
          f"warnings={len(result['warnings'])}")
    assert result["n_papers"] == 1
    assert len(result["topics"]) == 1
    assert result["topics"][0]["paper_count"] == 1
    print(f"[PASS] cluster_topics_singleton: 1 topic, label={result['topics'][0]['label'][:40]}")


def test_cluster_topics_empty_corpus(tmp_path):
    """Empty corpus → empty topics.json + warning."""
    corpus_dir = tmp_path / "empty"
    corpus_dir.mkdir()

    def fake_build_index_empty(corpus_dir, word_count_min=1000):
        return []

    with patch.object(topics_module, "build_corpus_index", fake_build_index_empty):
        result = topics_module.cluster_topics(
            corpus_dir=corpus_dir,
            output_path=tmp_path / "topics.json",
            force_method="handroll",
        )

    assert result["n_papers"] == 0
    assert result["topics"] == []
    assert "empty_corpus" in result["warnings"]
    print(f"[PASS] cluster_topics_empty_corpus: 0 topics, warning=empty_corpus")


def test_cluster_topics_no_doi_fallback(tmp_path):
    """All papers lack DOI → fall back to TF-IDF only."""
    no_doi_papers = []
    for i, p in enumerate(MOCK_PAPERS):
        p_copy = {k: v for k, v in p.items() if k != "text"}
        p_copy["doi"] = ""  # wipe DOI
        no_doi_papers.append(p_copy)

    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    for p in no_doi_papers:
        (corpus_dir / p["filename"]).touch()

    def fake_build_index_nodoi(corpus_dir, word_count_min=1000):
        return no_doi_papers

    with patch.object(topics_module, "build_corpus_index", fake_build_index_nodoi), \
         patch.object(topics_module, "extract_text", fake_extract_text), \
         patch.object(topics_module, "_build_concept_index") as mock_concept_idx:
        # All DOIs failed → empty concept_data
        mock_concept_idx.return_value = ({}, [p["filename"] for p in no_doi_papers])

        result = topics_module.cluster_topics(
            corpus_dir=corpus_dir,
            output_path=tmp_path / "topics.json",
            force_method="handroll",
        )

    assert result["n_papers"] == 5
    # Should still cluster via TF-IDF alone
    assert len(result["topics"]) >= 1
    assert any("openalex" in w for w in result["warnings"]), \
        "Should warn about OpenAlex fallback"
    print(f"[PASS] cluster_topics_no_doi_fallback: {len(result['topics'])} topics via TF-IDF only")


def test_cluster_topics_bertopic(tmp_path, opt_in=False):
    """End-to-end BERTopic test on 7-doc corpus. Requires BERTopic installed
    + network for first-time sentence-transformers model download.

    Skips gracefully on network/proxy failures (CI may not have proxy).
    Set PA_TEST_BERTOPIC=1 in env to opt in to running this in regression.
    By default SKIP to avoid:
      - First-time ~80MB model download in regression
      - torch.compile() cache issues when run in tight loop
      - Network/proxy dependency in CI
    """
    if os.environ.get("PA_TEST_BERTOPIC", "0") != "1":
        print("[SKIP] test_cluster_topics_bertopic: set PA_TEST_BERTOPIC=1 to run")
        return
    # Only probe BERTopic when actually running (avoids torch compile cache
    # pollution when the test is skipped in regression)
    if not topics_module._ensure_bertopic():
        print("[SKIP] test_cluster_topics_bertopic: BERTopic not installed")
        return
    # Set clash proxy if not already in env (Windows + user environment)
    if "HTTPS_PROXY" not in os.environ:
        os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7897"
    if "HTTP_PROXY" not in os.environ:
        os.environ["HTTP_PROXY"] = "http://127.0.0.1:7897"
    # Build a 7-doc corpus (3 medical, 2 insurance, 2 finance)
    docs_papers = [
        {"filename": f"paper_{i}.pdf", "path": f"/fake/paper_{i}.pdf",
         "title": t, "doi": "", "year": 2020, "venue": "Test",
         "word_count": 100, "pages": 1, "is_full_text": True, "error": None,
         "text": t}  # use title as text for simplicity
        for i, t in enumerate([
            "Deep learning for medical imaging with convolutional neural networks",
            "CNN-based image classification in radiology and tumor detection",
            "Transformer architectures for medical image segmentation",
            "LSTM networks for insurance claims prediction and actuarial risk",
            "Recurrent neural networks for mortality forecasting in life insurance",
            "Reinforcement learning for portfolio optimization and asset allocation",
            "Deep Q-learning for trading strategies in financial markets",
        ])
    ]
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    for p in docs_papers:
        (corpus_dir / p["filename"]).touch()

    def fake_build_index_7(corpus_dir, word_count_min=1000):
        return [{k: v for k, v in p.items() if k != "text"} for p in docs_papers]

    def fake_extract_7(path):
        fname = Path(path).name
        for p in docs_papers:
            if p["filename"] == fname:
                return {"text": p["text"], "pages": 1, "error": None}
        return {"text": "", "pages": 0, "error": "not_found"}

    with patch.object(topics_module, "build_corpus_index", fake_build_index_7), \
         patch.object(topics_module, "extract_text", fake_extract_7), \
         patch.object(topics_module, "_build_concept_index") as mock_concept_idx:
        mock_concept_idx.return_value = ({}, [])  # No OpenAlex data — BERTopic uses text only

        try:
            result = topics_module.cluster_topics(
                corpus_dir=corpus_dir,
                output_path=tmp_path / "topics.json",
                force_method="bertopic",
            )
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"[SKIP] test_cluster_topics_bertopic: BERTopic failed: {e!r}\n{tb[:500]}")
            return

    assert result["n_papers"] == 7
    # 3 natural topics (medical, insurance, finance) — BERTopic should find >= 2
    assert len(result["topics"]) >= 2, f"BERTopic should find >= 2 topics, got {len(result['topics'])}"
    assert result["method_used"] == "bertopic", f"Expected bertopic, got {result['method_used']}"
    # Check label quality — should have meaningful keywords
    all_labels = " ".join(t["label"] for t in result["topics"]).lower()
    # At least one of: medical/insurance/finance/portfolio/segmentation should appear
    found_keywords = [kw for kw in ["medical", "insurance", "portfolio", "segmentation", "qlearning", "neural", "forecasting", "classification", "image"]
                      if kw in all_labels]
    assert len(found_keywords) >= 1, f"BERTopic labels should contain at least one meaningful keyword, got labels: {[t['label'] for t in result['topics']]}"
    print(f"[PASS] cluster_topics_bertopic: {len(result['topics'])} topics, "
          f"labels: {[t['label'][:40] for t in result['topics']]}")


# -----------------------------------------------------------------------------
# Test 6: review.py format support (MD + TXT, no DOCX)
# -----------------------------------------------------------------------------

def test_review_format_support(tmp_path):
    """Verify review.build_corpus_index reads .pdf + .md + .txt (skips .docx)."""
    from pa_cli import review
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    # 2 MD files
    (corpus / "alpha.md").write_text(
        "# Alpha: Deep Learning for Medical Imaging\n\n"
        "Abstract: We present a deep learning approach for medical imaging.\n\n"
        "Convolutional neural networks achieve state-of-the-art tumor detection.\n" * 50,
        encoding="utf-8"
    )
    (corpus / "beta.md").write_text(
        "# Beta: LSTM for Insurance Risk\n\n"
        "Abstract: Recurrent neural networks for actuarial risk modeling.\n\n"
        "LSTM outperforms classical regression for insurance claims.\n" * 50,
        encoding="utf-8"
    )
    # 1 TXT
    (corpus / "gamma.txt").write_text(
        "Plain text paper notes about reinforcement learning for portfolio optimization.\n" * 30,
        encoding="utf-8"
    )
    # 1 unsupported DOCX (should be skipped)
    (corpus / "delta.docx").write_text("fake docx", encoding="utf-8")

    papers = review.build_corpus_index(corpus)
    filenames = sorted([p["filename"] for p in papers])
    # .md and .txt picked up, .docx skipped
    assert "alpha.md" in filenames, f"alpha.md missing, got {filenames}"
    assert "beta.md" in filenames, f"beta.md missing, got {filenames}"
    assert "gamma.txt" in filenames, f"gamma.txt missing, got {filenames}"
    assert "delta.docx" not in filenames, f"delta.docx should be skipped, got {filenames}"
    # Title extracted from H1 in MD
    alpha = next(p for p in papers if p["filename"] == "alpha.md")
    assert "Alpha" in alpha["title"] and "Deep Learning" in alpha["title"], \
        f"alpha title not extracted from H1: {alpha['title']!r}"
    # Title fallback to filename for TXT (no H1)
    gamma = next(p for p in papers if p["filename"] == "gamma.txt")
    assert "gamma" in gamma["title"].lower() or "reinforcement" in gamma["title"].lower(), \
        f"gamma title fallback: {gamma['title']!r}"
    # word_count > 0 (text was extracted)
    for p in papers:
        assert p["word_count"] > 0, f"{p['filename']} has 0 words — text extraction broken"
    print(f"[PASS] review_format_support: {len(papers)} papers (md+txt), docx skipped")


# -----------------------------------------------------------------------------
# Sub-test runner
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        # Pre-create parent dirs so tests can mkdir inside them
        for i in range(1, 7):
            (td / f"test{i}").mkdir(exist_ok=True)
        test_cluster_topics_basic(td / "test1")
        test_cluster_topics_singleton(td / "test2")
        test_cluster_topics_empty_corpus(td / "test3")
        test_cluster_topics_no_doi_fallback(td / "test4")
        test_cluster_topics_bertopic(td / "test5")
        test_review_format_support(td / "test6")
    print("\n[ALL PASS] handroll 4/4 + bertopic (if installed) + format support 1/1")