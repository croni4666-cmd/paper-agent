import json
from pathlib import Path
from collections import Counter

q_path = Path(r"G:\minimax - workspace\Paper agent\bench\v01\queries.json")
combined_dir = Path(r"G:\minimax - workspace\Paper agent\bench\v01\system_outputs_combined")

queries = json.load(open(q_path, encoding="utf-8"))["queries"]
q026_q050 = {q["id"]: q for q in queries if int(q["id"][1:]) >= 26}
print(f"q026-q050 queries: {len(q026_q050)}")
diff = Counter(q["difficulty_hint"] for q in q026_q050.values())
print(f"Difficulty hints: {dict(diff)}")
topic = Counter(q["topic_bucket"] for q in q026_q050.values())
print(f"Topic buckets: {dict(topic)}")

for qid in sorted(q026_q050.keys(), key=lambda x: int(x[1:])):
    fp = combined_dir / f"{qid}.json"
    if fp.exists():
        d = json.load(open(fp, encoding="utf-8"))
        n = len(d.get("results", []))
        sample_title = d.get("results", [{}])[0].get("title", "")[:50]
        sample_title_safe = sample_title.encode("ascii", "replace").decode("ascii")
        print(f"  {qid} ({q026_q050[qid]['difficulty_hint']:11s}): n={n:2d}, top={sample_title_safe!r}")
