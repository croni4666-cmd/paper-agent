"""v3.9.8.0 baseline 对比 — 5 engines vs 6 engines (with AMiner)
3 个 query, 测 cite/abstract 覆盖"""
import sys, time
sys.path.insert(0, r'G:\minimax - workspace\Paper agent')
from pa_cli.search import (
    search_openalex, search_semanticscholar, search_crossref, search_core,
)
from pa_cli.aminer_channel import search_aminer

QUERIES = [
    ("数字普惠金融 家庭消费", "经济学"),
    ("长期护理保险 人口老龄化", "保险学"),
    ("金融科技 中小银行", "金融学"),
]

YEAR_MIN, YEAR_MAX, LIMIT = 2022, 2024, 20


def coverage(results, label):
    if not results:
        print(f"  [{label:8s}] EMPTY")
        return None
    if "error" in results[0]:
        print(f"  [{label:8s}] ERR: {results[0]['error']}")
        return None
    n = len(results)
    cite_n = sum(1 for r in results if (r.get("cited_by_count") or 0) > 0)
    abs_n = sum(1 for r in results if r.get("abstract"))
    top1 = max((r.get("cited_by_count") or 0) for r in results)
    return {
        "n": n, "cite_pct": round(cite_n/n*100, 1),
        "abs_pct": round(abs_n/n*100, 1), "top1": top1,
    }


def run(q, area, with_aminer):
    print(f"\n=== {q} ({area}) {'[with AMiner]' if with_aminer else '[baseline 5 engines]'} ===")
    engines = {
        "openalex": lambda: search_openalex(q, YEAR_MIN, YEAR_MAX, LIMIT),
        "crossref": lambda: search_crossref(q, YEAR_MIN, YEAR_MAX, LIMIT),
    }
    if with_aminer:
        engines["aminer"] = lambda: search_aminer(q, YEAR_MIN, YEAR_MAX, LIMIT)
    time.sleep(1)
    engines["s2"] = lambda: search_semanticscholar(q, YEAR_MIN, YEAR_MAX, LIMIT)
    if with_aminer:
        engines["core"] = lambda: search_core(q, YEAR_MIN, YEAR_MAX, LIMIT)

    by_e = {}
    for name, fn in engines.items():
        r = fn()
        by_e[name] = r
        s = coverage(r, name)
        if s:
            print(f"  [{name:8s}] n={s['n']:3d}  cite={s['cite_pct']:5.1f}%  abs={s['abs_pct']:5.1f}%  top1={s['top1']}")
        time.sleep(1)

    # DEDUP
    seen = set()
    dedup = []
    for name, lst in by_e.items():
        for r in lst or []:
            t = (r.get("title") or "").strip().lower()[:80]
            if t and t not in seen:
                seen.add(t)
                r2 = dict(r)
                r2["_first_seen"] = name
                dedup.append(r2)
    s = coverage(dedup, "DEDUP")
    if s:
        print(f"  [DEDUP   ] n={s['n']:3d}  cite={s['cite_pct']:5.1f}%  abs={s['abs_pct']:5.1f}%  top1={s['top1']}")
    return dedup


for q, area in QUERIES:
    run(q, area, with_aminer=False)  # baseline
    run(q, area, with_aminer=True)   # with AMiner
