"""Quick test: download BGE-reranker-base and verify cross-encoder works."""
import os
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"  # Use CN mirror
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pa_cli.cross_encoder import BGEReranker, ensure_model_downloaded, DEFAULT_CACHE_DIR

print(f"Cache dir: {DEFAULT_CACHE_DIR}")
print(f"Downloading model if needed...")
model_path = ensure_model_downloaded()
print(f"  model_path: {model_path}")
print(f"  is_downloaded check: ", end="")
from pa_cli.cross_encoder import is_model_downloaded
print(is_model_downloaded())

print(f"\nLoading BGEReranker...")
reranker = BGEReranker()
print(f"  model loaded")

# Quick smoke test
query = "AI tutoring systems in K-12 education"
candidates = [
    "AI-powered learning technologies are increasingly being used to automate and scaffold learning activities.",
    "A new species of frog was discovered in the Amazon rainforest.",
    "The impact of artificial intelligence on learner-instructor interaction in online learning.",
    "Climate change effects on coral reef ecosystems in the Pacific Ocean.",
    "Generative AI tools like ChatGPT are transforming K-12 classrooms across the United States.",
]
print(f"\nSmoke test: scoring 5 candidates...")
scores = reranker.score_batch(query, candidates)
for c, s in zip(candidates, scores):
    snippet = c[:80] + ("..." if len(c) > 80 else "")
    print(f"  {s:+.4f}  {snippet}")

# Sanity: relevant ones should score higher
print(f"\nExpected: AI + education candidates score higher than climate/frog")
