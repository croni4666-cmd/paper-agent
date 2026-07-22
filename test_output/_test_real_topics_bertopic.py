"""Run pa review-topics on real corpus with BERTopic method."""
import sys
import os
import json
from pathlib import Path

os.environ.setdefault("HTTPS_PROXY", "http://127.0.0.1:7897")
os.environ.setdefault("HTTP_PROXY", "http://127.0.0.1:7897")

sys.path.insert(0, str(Path(__file__).parent.parent))

from pa_cli import topics as topics_module

CORPUS = Path(r"G:\Minmax - workspace\课件\ch1-econ-ppt")
OUT_PATH = Path(__file__).parent / "_real_topics_bertopic.json"


def main():
    # Disable OpenAlex (avoid network), enable BERTopic
    import pa_cli.topics as t
    orig_build = t._build_concept_index

    def no_concept_index(papers_list):
        return ({}, [p["filename"] for p in papers_list])

    t._build_concept_index = no_concept_index

    print("🔄 Running pa review-topics (method: BERTopic)...")
    try:
        result = topics_module.cluster_topics(
            corpus_dir=CORPUS,
            output_path=OUT_PATH,
            force_method="bertopic",
        )
    finally:
        t._build_concept_index = orig_build

    print(f"\n{'='*70}")
    print(f"  Result: method={result['method_used']}, k={result['k']}, n_papers={result['n_papers']}")
    print(f"  Model: {result.get('model_name', 'n/a')}")
    print(f"{'='*70}\n")
    for topic in result["topics"]:
        print(f"━━━ Topic {topic['topic_id']} ━━━ (cohesion: {topic.get('cohesion_score', 0)})")
        print(f"  Label:    {topic['label']}")
        print(f"  Keywords: {', '.join(topic['keywords'][:8])}")
        print(f"  Papers ({topic['paper_count']}):")
        for fn in topic["filenames"]:
            print(f"    - {fn}")
        print()

    print(f"Full topics.json saved: {OUT_PATH} ({OUT_PATH.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()