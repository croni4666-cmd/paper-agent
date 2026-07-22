"""bench/v01/_gen_labeling_views.py — Generate per-query markdown views for Mavis to read and label."""
import json
from pathlib import Path

BENCH_DIR = Path("bench/v01")
SYSTEM_OUT_DIR = BENCH_DIR / "system_outputs"
LABELING_DIR = BENCH_DIR / "_labeling"
LABELING_DIR.mkdir(parents=True, exist_ok=True)


def fmt_abstract(abstract: str, max_len: int = 600) -> str:
    if not abstract:
        return "_[no abstract — judge by title+venue+year only]_"
    return abstract[:max_len] + ("..." if len(abstract) > max_len else "")


def main():
    files = sorted(SYSTEM_OUT_DIR.glob("q*.json"))
    print(f"[gen] {len(files)} system outputs")

    for f in files:
        snap = json.loads(f.read_text(encoding="utf-8"))
        qid = snap["query_id"]
        query = snap["query"]
        results = snap["results"]
        n_with_abs = sum(1 for r in results if r.get("abstract"))
        n_no_doi = sum(1 for r in results if not r.get("doi"))

        lines = []
        lines.append(f"# {qid} — labeling view")
        lines.append("")
        lines.append(f"**Query:** {query}")
        lines.append(f"**Topic:** {snap.get('topic_bucket', '')} | **Source:** {snap.get('source', '')}")
        lines.append(f"**Candidates:** {len(results)} | with abstract: {n_with_abs} | no DOI (skip): {n_no_doi}")
        lines.append("")
        lines.append("---")
        lines.append("")

        for r in results:
            doi = r.get("doi", "") or "[no-DOI]"
            title = r.get("title", "")
            venue = r.get("venue", "")
            year = r.get("year") or "?"
            cites = r.get("citation_count", 0)
            engines = ",".join(r.get("engines_found_in", []))
            abstract = fmt_abstract(r.get("abstract", ""))

            lines.append(f"## rank {r['rank']:>2} | {doi}")
            lines.append(f"**{title}**")
            lines.append(f"_{venue}, {year} | cited {cites} | {engines}_")
            lines.append("")
            lines.append(abstract)
            lines.append("")

        out_path = LABELING_DIR / f"{qid}.md"
        out_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"[gen] wrote {len(files)} labeling views to {LABELING_DIR}")


if __name__ == "__main__":
    main()
