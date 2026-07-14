"""Parse v3 markdown table → queries.json q026-q050 entries, validate, write back."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V3_PATH = ROOT / "test_output" / "q026-q050-draft-v3.md"
QUERIES_PATH = ROOT / "bench" / "v01" / "queries.json"


def main():
    md = V3_PATH.read_text(encoding="utf-8")
    lines = md.splitlines()
    # Find the v3 final 25 行 table — starts at "## v3 final 25 行" header
    start = None
    for i, line in enumerate(lines):
        if "v3 final 25 行" in line or "v3 final 25 query" in line.lower():
            start = i + 1
            break
    if start is None:
        raise SystemExit("Could not find 'v3 final 25 行' header")
    # Collect table rows until blank line
    table_lines = []
    for line in lines[start:]:
        if line.startswith("|"):
            table_lines.append(line)
        elif table_lines and not line.startswith("|"):
            break
    # Skip header + separator
    rows = [l for l in table_lines if not l.startswith("| ---") and "---" not in l]
    # First row is header (id, query, topic_bucket, difficulty_hint)
    if "id" in rows[0].lower() and "query" in rows[0].lower():
        rows = rows[1:]
    # Parse
    new_queries = []
    for row in rows:
        cells = [c.strip() for c in row.split("|")]
        # cells[0] is empty (leading |), last is empty (trailing |)
        cells = [c for c in cells if c != ""]
        if len(cells) < 4:
            print(f"WARN: skipping malformed row: {row[:100]}")
            continue
        qid, q_text, topic, diff = cells[0], cells[1], cells[2], cells[3]
        if not re.match(r"^q0(2[6-9]|[3-4][0-9]|50)$", qid):
            print(f"WARN: unexpected id: {qid}")
            continue
        new_queries.append({
            "id": qid,
            "query": q_text,
            "topic_bucket": topic,
            "source": "user",
            "difficulty_hint": diff,
            "expected_relevant_dois": [],
            "notes": "(q026-q050 batch by user 2026-07-14, v3 commonality extension; CNKI integration pending [P0-9])"
        })
    print(f"Parsed {len(new_queries)} new queries from v3")
    if len(new_queries) != 25:
        raise SystemExit(f"Expected 25 queries, got {len(new_queries)}")

    # Distribution check
    from collections import Counter
    topics = Counter(q["topic_bucket"] for q in new_queries)
    diffs = Counter(q["difficulty_hint"] for q in new_queries)
    print(f"  topic_bucket: {dict(topics)}")
    print(f"  difficulty_hint: {dict(diffs)}")

    # Read existing queries.json
    obj = json.loads(QUERIES_PATH.read_text(encoding="utf-8"))
    existing_ids = {q["id"] for q in obj["queries"]}
    new_ids = {q["id"] for q in new_queries}
    overlap = existing_ids & new_ids
    if overlap:
        print(f"WARN: overlap with existing queries: {overlap}")
    # Replace q026-q050 in existing, keep q001-q025
    obj["queries"] = [q for q in obj["queries"] if not re.match(r"^q0(2[6-9]|[3-4][0-9]|50)$", q["id"])]
    obj["queries"].extend(new_queries)
    obj["queries"].sort(key=lambda q: int(q["id"][1:]))
    print(f"Total queries after merge: {len(obj['queries'])}")

    # Validate schema
    schema_keys = {"id", "query", "topic_bucket", "source", "difficulty_hint",
                   "expected_relevant_dois", "notes"}
    for q in obj["queries"]:
        missing = schema_keys - set(q.keys())
        if missing:
            print(f"WARN: {q['id']} missing keys: {missing}")
    # Update version
    obj["version"] = obj.get("version", "v0.1") + "+user-batch-q026-q050-2026-07-14"
    obj["schema_doc"] = obj.get("schema_doc", "") + " | n=50 (q001-q050, 25 user + 25 user)"

    # Backup
    backup = QUERIES_PATH.with_suffix(".json.bak-2026-07-14")
    backup.write_text(QUERIES_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"Backup: {backup}")

    # Write
    QUERIES_PATH.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Written: {QUERIES_PATH}")
    print(f"  Total queries: {len(obj['queries'])} (q001-q{q['id'][1:] if obj['queries'] else '000'})")


if __name__ == "__main__":
    main()
