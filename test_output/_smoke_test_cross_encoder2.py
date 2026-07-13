"""Smoke test: load BGE cross-encoder from local files and score."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pa_cli.cross_encoder import BGEReranker, DEFAULT_CACHE_DIR, is_model_downloaded

print(f"Cache dir: {DEFAULT_CACHE_DIR}")
print(f"is_model_downloaded: {is_model_downloaded()}")

print(f"\nLoading BGEReranker from local files...")
reranker = BGEReranker(auto_download=False)
print(f"  loaded successfully")

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

print(f"\nSanity check: AI + education candidates should score higher than climate/frog")
