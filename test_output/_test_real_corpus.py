"""Quick test: run build_corpus_index on user's actual 课件 corpus.

Skips node_modules junk automatically (build_corpus_index only globs
*.pdf / *.md / *.txt, so node_modules READMEs are picked up but they're
small + obvious noise).
"""
import sys
from pathlib import Path

# Add parent for pa_cli import
sys.path.insert(0, str(Path(__file__).parent.parent))

from pa_cli import review

# Use a focused sub-corpus: ch1-econ-ppt/ minus node_modules
corpus = Path(r"G:\Minmax - workspace\课件\ch1-econ-ppt")
papers = review.build_corpus_index(corpus)
# Filter out node_modules (build_corpus_index doesn't auto-skip them)
papers = [p for p in papers if "node_modules" not in p["path"]]

print(f"Found {len(papers)} papers in {corpus} (excluding node_modules):")
for p in papers:
    title = p["title"][:60] if p["title"] else "(no title)"
    print(f"  - {p['filename']:50s} | {p['word_count']:5d} words | {title}")
print(f"\nTotal word count: {sum(p['word_count'] for p in papers):,}")
print(f"DOIs found: {sum(1 for p in papers if p['doi'])}")