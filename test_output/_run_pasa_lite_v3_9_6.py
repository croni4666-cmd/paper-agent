"""End-to-end runner for v3.9.6 [P2-6] PaSa-lite rule-based.

Per ROADMAP [P2-6] (added 2026-07-13, shipped in v3.9.6).

Demonstrates PaSa-lite on first 5 queries of v3.9.0 bench.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pa_cli.pasa_lite import run_pasa_lite, PaSaLiteConfig, generate_pasa_lite_report


def main():
    bench_dir = ROOT / "bench" / "v01"
    reports_dir = bench_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    config = PaSaLiteConfig(
        n_query_variants=3,
        n_rounds=2,
        n_results_per_round=10,  # reduced from 20 for speed
        use_concepts=True,
        use_prf=True,
        use_citation_walk=False,  # disabled for demo (was hanging on 404)
        citation_walk_limit=5,
    )

    # Load queries from v3.9.0 bench — only 3 for demo speed
    cond_dir = bench_dir / "system_outputs_combined"
    qfiles = sorted([p for p in cond_dir.iterdir() if p.is_file() and p.suffix == ""])[:3]

    print(f"[v3.9.6 PaSa-lite] Running on {len(qfiles)} queries...")
    print(f"  config: {config}")

    results_per_query = []
    for qfile in qfiles:
        qid = qfile.stem
        obj = json.loads(qfile.read_text(encoding="utf-8"))
        q_text = obj.get("query", "")
        if not q_text:
            continue
        print(f"  {qid}: {q_text[:80]}...")

        try:
            result = run_pasa_lite(q_text, config=config)
            result["qid"] = qid
            result["n_variants_generated"] = len(result["variants"])
            results_per_query.append(result)
            print(f"    variants: {result['n_variants_generated']}, pool: {result['candidate_pool_size']}, cite_added: {result['citation_walk_added']}")
        except Exception as e:
            print(f"    ERROR: {e}")

    # Save report
    md = generate_pasa_lite_report(results_per_query, config)
    md_path = reports_dir / "v3_9_6_pasa_lite.md"
    md_path.write_text(md, encoding="utf-8")
    print(f"\n  Report: {md_path}")

    # Save raw results
    raw_path = reports_dir / "v3_9_6_pasa_lite.json"
    raw_path.write_text(
        json.dumps(
            [
                {k: v for k, v in r.items() if k != "rounds_per_variant"}
                for r in results_per_query
            ],
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"  Raw: {raw_path}")

    # Summary
    if results_per_query:
        print(f"\n{'='*60}")
        print(f"SUMMARY (n={len(results_per_query)} queries)")
        print(f"{'='*60}")
        avg_v = sum(r["n_variants_generated"] for r in results_per_query) / len(results_per_query)
        avg_p = sum(r["candidate_pool_size"] for r in results_per_query) / len(results_per_query)
        avg_c = sum(r["citation_walk_added"] for r in results_per_query) / len(results_per_query)
        print(f"  Avg variants: {avg_v:.1f}")
        print(f"  Avg candidate pool: {avg_p:.1f}")
        print(f"  Avg citations added: {avg_c:.1f}")
        print(f"  PaSa coverage estimate: 50-60% (per ROADMAP [P2-6] re-estimate)")


if __name__ == "__main__":
    main()
