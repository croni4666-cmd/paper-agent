"""Cross-encoder reranker using BGE-reranker.

Per ROADMAP [P0-7] (added 2026-07-13, completed 2026-07-13 in v3.9.3).

Wraps BAAI/bge-reranker-base (~278MB) via sentence-transformers.CrossEncoder.

Why cross-encoder:
- Bi-encoder (current) embeds query and candidate separately, then cosine similarity
  → no token-level interaction, no L×L attention
- Cross-encoder concatenates query + candidate as single input, runs transformer
  with full L×L attention → captures token-level semantic match
- Standard IR practice: bi-encoder to retrieve top 100-1000, then cross-encoder
  to rerank top 30-100 → expected +5-15% on recall@10

Network fallback:
- Default HuggingFace endpoint may be slow or blocked in CN
- Set HF_ENDPOINT=https://hf-mirror.com as env var to use Chinese mirror
- We test for this and fall back automatically

5-check Global Rule audit: 5/5 pass
 1. $0 cost (one-time ~278MB local download, no per-call API)
 2. No hosted service
 3. Maintenance: ~250 LOC
 4. No publish obligation
 5. Free-tier degradation: if HF download fails, fall back to bi-encoder-only
    rerank (the system still works, just with lower accuracy)
"""
from __future__ import annotations

import os
import shutil
import urllib.request
from pathlib import Path
from typing import Optional

# Default HF endpoint (CN users: set HF_ENDPOINT=https://hf-mirror.com)
DEFAULT_HF_ENDPOINT = "https://huggingface.co"
HF_MIRROR_CN = "https://hf-mirror.com"

# BGE-reranker-base from BAAI
BGE_MODEL_NAME = "BAAI/bge-reranker-base"
BGE_FILES = [
    "config.json",
    "model.safetensors",
    "tokenizer.json",
    "tokenizer_config.json",
    "vocab.txt",
    "special_tokens_map.json",
]
# Optional: pytorch_model.bin (alternative to safetensors)
BGE_FILES_ALT = [
    "pytorch_model.bin",
    "config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "vocab.txt",
    "special_tokens_map.json",
]

DEFAULT_CACHE_DIR = Path.home() / ".paper-agent" / "models" / "bge-reranker-base"


def setup_hf_endpoint() -> str:
    """Ensure HF_ENDPOINT is set. Returns the endpoint URL.

    If HF_ENDPOINT is unset, defaults to https://huggingface.co.
    CN users should set HF_ENDPOINT=https://hf-mirror.com in their env.
    """
    endpoint = os.environ.get("HF_ENDPOINT", DEFAULT_HF_ENDPOINT)
    os.environ["HF_ENDPOINT"] = endpoint
    return endpoint


def check_sentence_transformers() -> None:
    """Raise informative error if sentence-transformers not installed."""
    try:
        import sentence_transformers
    except ImportError as e:
        raise ImportError(
            "sentence-transformers is required for pa_cli.cross_encoder. "
            "Install with: pip install sentence-transformers"
        ) from e


def is_model_downloaded(cache_dir: Path = DEFAULT_CACHE_DIR) -> bool:
    """Check if the BGE model files are present in cache_dir."""
    if not cache_dir.exists():
        return False
    # Need at least config.json + one of (model.safetensors, pytorch_model.bin)
    has_config = (cache_dir / "config.json").exists()
    has_weights = (cache_dir / "model.safetensors").exists() or (cache_dir / "pytorch_model.bin").exists()
    has_tokenizer = (cache_dir / "tokenizer.json").exists()
    return has_config and has_weights and has_tokenizer


def download_file(url: str, target: Path, timeout: int = 60) -> None:
    """Download a single file with progress indication."""
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        return
    print(f"  Downloading {target.name} from {url}...")
    try:
        urllib.request.urlretrieve(url, target)
    except Exception as e:
        raise RuntimeError(
            f"Failed to download {target.name} from {url}: {e}\n"
            f"Tip: set HF_ENDPOINT=https://hf-mirror.com for Chinese networks."
        ) from e


def ensure_model_downloaded(
    cache_dir: Path = DEFAULT_CACHE_DIR,
    prefer_endpoint: Optional[str] = None,
) -> Path:
    """Download BGE-reranker-base if not present. Returns path to model dir.

    Strategy:
    1. Check if model is already cached locally
    2. Try preferred endpoint (or HF_ENDPOINT env var)
    3. On failure, fall back to CN mirror (https://hf-mirror.com)
    """
    setup_hf_endpoint()
    if is_model_downloaded(cache_dir):
        return cache_dir

    endpoints_to_try = []
    if prefer_endpoint:
        endpoints_to_try.append(prefer_endpoint)
    if os.environ.get("HF_ENDPOINT") and os.environ["HF_ENDPOINT"] != prefer_endpoint:
        endpoints_to_try.append(os.environ["HF_ENDPOINT"])
    if DEFAULT_HF_ENDPOINT not in endpoints_to_try:
        endpoints_to_try.append(DEFAULT_HF_ENDPOINT)
    if HF_MIRROR_CN not in endpoints_to_try:
        endpoints_to_try.append(HF_MIRROR_CN)

    last_error = None
    for endpoint in endpoints_to_try:
        for fname in BGE_FILES:
            target = cache_dir / fname
            url = f"{endpoint}/{BGE_MODEL_NAME}/resolve/main/{fname}"
            try:
                download_file(url, target)
            except Exception as e:
                last_error = e
                # Roll back partial download and try next endpoint
                if cache_dir.exists():
                    shutil.rmtree(cache_dir, ignore_errors=True)
                break
        else:
            # All files downloaded successfully
            return cache_dir

    raise RuntimeError(
        f"Failed to download BGE-reranker-base from any endpoint. "
        f"Last error: {last_error}\n"
        f"Endpoints tried: {endpoints_to_try}\n"
        f"Tip: set HF_ENDPOINT=https://hf-mirror.com for Chinese networks."
    )


class BGEReranker:
    """Wrapper around sentence-transformers.CrossEncoder for BGE-reranker-base.

    Usage:
        reranker = BGEReranker()  # downloads if needed
        score = reranker.score(query, candidate_text)
        scores = reranker.score_batch(query, [c1_text, c2_text, ...])
    """
    def __init__(
        self,
        model_path: Optional[Path] = None,
        max_length: int = 512,
        auto_download: bool = True,
    ):
        check_sentence_transformers()
        if model_path is None:
            if auto_download:
                model_path = ensure_model_downloaded()
            else:
                model_path = DEFAULT_CACHE_DIR
        from sentence_transformers import CrossEncoder
        self.model = CrossEncoder(str(model_path), max_length=max_length)

    def score(self, query: str, candidate_text: str) -> float:
        """Score a single (query, candidate) pair. Returns raw cross-encoder score."""
        return float(self.model.predict([(query, candidate_text)])[0])

    def score_batch(self, query: str, candidates: list) -> list:
        """Score query against multiple candidate texts. Returns list of float scores."""
        pairs = [(query, str(c)) for c in candidates]
        return [float(s) for s in self.model.predict(pairs)]

    def rerank(
        self,
        query: str,
        candidates: list,
        text_extractor: Optional[callable] = None,
        top_k: Optional[int] = None,
    ) -> list:
        """Rerank candidates using cross-encoder.

        Args:
            query: query string
            candidates: list of candidate dicts (or any objects)
            text_extractor: function (cand) -> str for getting text from candidate.
                            Default: uses 'title' + 'abstract' if present.
            top_k: if set, return only top-k after rerank. Default: all (re-sorted).

        Returns:
            candidates re-sorted by cross-encoder score (descending).
            Each candidate is augmented with 'cross_encoder_score' field (if dict).
        """
        if text_extractor is None:
            def text_extractor(c):
                if isinstance(c, dict):
                    title = c.get("title", "") or ""
                    abstract = c.get("abstract", "") or ""
                    return f"{title}. {abstract}".strip(". ")
                return str(c)

        texts = [text_extractor(c) for c in candidates]
        scores = self.score_batch(query, texts)

        # Attach scores and sort
        if all(isinstance(c, dict) for c in candidates):
            for c, s in zip(candidates, scores):
                c["cross_encoder_score"] = s
            reranked = sorted(candidates, key=lambda x: -x.get("cross_encoder_score", 0))
        else:
            reranked = sorted(
                [(*[c], s) if not isinstance(c, tuple) else (c[0], s)
                 for c, s in zip(candidates, scores)],
                key=lambda x: -x[1],
            )

        if top_k is not None:
            reranked = reranked[:top_k]
        return reranked
