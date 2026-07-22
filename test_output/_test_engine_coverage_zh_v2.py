"""v3.9.7.9+ 引擎覆盖度对比 (2026-07-15) v2
==============================================
修复:
- S2 加 5s sleep 避开 rate limit
- CORE 拿 403 直接报错 (key 失效)
- 只跑能用的引擎: OpenAlex + Crossref + S2 (slow)

3 个中文真实 query, report cite/abstract coverage
"""
import sys, os, time
sys.path.insert(0, r'G:\minimax - workspace\Paper agent')
from pa_cli.search import (
    search_openalex, search_semanticscholar, search_crossref, search_core,
)

QUERIES = [
    ("数字普惠金融 家庭消费", "经济学"),
    ("长期护理保险 人口老龄化", "保险学"),
    ("金融科技 中小银行", "金融学"),
]

YEAR_MIN, YEAR_MAX, LIMIT = 2022, 2024, 20


def coverage_stats(results, label):
    if not results:
        print(f"  [{label}] EMPTY")
        return None
    n = len(results)
    cite_n = sum(1 for r in results if (r.get("cited_by_count") or 0) > 0)
    has_abs = 0
    for r in results:
        if r.get("abstract"):
            has_abs += 1
        elif r.get("tldr"):
            has_abs += 0.5
    top1 = max((r.get("cited_by_count") or 0) for r in results)
    return {
        "n": n,
        "cite_pct": round(cite_n / n * 100, 1),
        "abs_pct": round(has_abs / n * 100, 1),
        "top1_cite": top1,
    }


def run_query(query, area):
    print(f"\n{'=' * 60}")
    print(f"Query: {query}  ({area})")
    print('=' * 60)

    by_engine = {}

    # OpenAlex
    print("  [openalex] ...", end=" ", flush=True)
    r = search_openalex(query, YEAR_MIN, YEAR_MAX, LIMIT)
    by_engine["openalex"] = r
    s = coverage_stats(r, "openalex")
    print(f"n={s['n']} cite={s['cite_pct']}% abs={s['abs_pct']}% top1={s['top1_cite']}" if s else "EMPTY")

    time.sleep(2)

    # Crossref
    print("  [crossref] ...", end=" ", flush=True)
    r = search_crossref(query, YEAR_MIN, YEAR_MAX, LIMIT)
    by_engine["crossref"] = r
    s = coverage_stats(r, "crossref")
    print(f"n={s['n']} cite={s['cite_pct']}% abs={s['abs_pct']}% top1={s['top1_cite']}" if s else "EMPTY")

    # S2 - 加 6s sleep 避开 1 RPS limit
    print("  [s2] (slow 6s) ...", end=" ", flush=True)
    time.sleep(6)
    r = search_semanticscholar(query, YEAR_MIN, YEAR_MAX, LIMIT)
    by_engine["s2"] = r
    s = coverage_stats(r, "s2")
    print(f"n={s['n']} cite={s['cite_pct']}% abs={s['abs_pct']}% top1={s['top1_cite']}" if s else "EMPTY")

    # CORE - 先检测 key
    core_key = os.environ.get("CORE_API_KEY", "")
    if core_key:
        print("  [core] ...", end=" ", flush=True)
        time.sleep(2)
        r = search_core(query, YEAR_MIN, YEAR_MAX, LIMIT)
        by_engine["core"] = r
        s = coverage_stats(r, "core")
        print(f"n={s['n']} cite={s['cite_pct']}% abs={s['abs_pct']}% top1={s['top1_cite']}" if s else "EMPTY")
    else:
        print("  [core] SKIPPED (no key)")

    # DEDUP
    seen_titles = set()
    deduped = []
    for name, lst in by_engine.items():
        for r in lst:
            t = (r.get("title") or "").strip().lower()[:80]
            if t and t not in seen_titles:
                seen_titles.add(t)
                r2 = dict(r)
                r2["_first_seen"] = name
                deduped.append(r2)
    s = coverage_stats(deduped, "DEDUP")
    if s:
        print(f"  [DEDUP   ] n={s['n']}  cite={s['cite_pct']}%  abs={s['abs_pct']}%  top1={s['top1_cite']}")

    return by_engine, deduped


def main():
    all_stats = []
    for q, area in QUERIES:
        by_eng, dedup = run_query(q, area)
        s = coverage_stats(dedup, "DEDUP")
        if s:
            s["query"] = q
            s["area"] = area
            all_stats.append(s)

    print("\n\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"{'Query':<30s} {'Area':<8s} {'n':>3s}  {'cite%':>6s}  {'abs%':>6s}  {'top1':>5s}")
    for s in all_stats:
        print(f"{s['query']:<30s} {s['area']:<8s} {s['n']:3d}  {s['cite_pct']:5.1f}%  {s['abs_pct']:5.1f}%  {s['top1_cite']:5d}")


if __name__ == "__main__":
    main()
