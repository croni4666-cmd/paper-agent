"""
v3.9.7.9+ 引擎覆盖度对比测试 (2026-07-15)
============================================
3 个中文真实 query 跑 4 个引擎 (OpenAlex / S2 / Crossref / CORE)
报告: dedup 数量, cite>0 %, abstract 非空 %, top-1 cite

参考: 之前已验证 v3.9.7.8 用 6 engines 跑, 中文 cite ~30-46% / abstract ~18-31%
本测试目标: 4 个免费引擎 vs 6 engines 差距
"""
import sys
import os
import json
from pathlib import Path

# 把 paper-agent 加入 path
PA_ROOT = Path(r"G:\minimax - workspace\Paper agent")
sys.path.insert(0, str(PA_ROOT))

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
    # 兼容 abstract 字段
    has_abs = 0
    for r in results:
        if r.get("abstract"):
            has_abs += 1
        elif r.get("tldr"):  # S2 tldr 算半个 abstract
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
    print(f"Year: {YEAR_MIN}-{YEAR_MAX}, Limit: {LIMIT}")
    print('=' * 60)

    engines = {
        "openalex": lambda: search_openalex(query, YEAR_MIN, YEAR_MAX, LIMIT),
        "s2":       lambda: search_semanticscholar(query, YEAR_MIN, YEAR_MAX, LIMIT),
        "crossref": lambda: search_crossref(query, YEAR_MIN, YEAR_MAX, LIMIT),
        "core":     lambda: search_core(query, YEAR_MIN, YEAR_MAX, LIMIT),
    }

    by_engine = {}
    for name, fn in engines.items():
        try:
            r = fn()
        except Exception as e:
            print(f"  [{name}] ERROR: {e}")
            r = []
        by_engine[name] = r
        s = coverage_stats(r, name)
        if s:
            print(f"  [{name:9s}] n={s['n']:3d}  cite={s['cite_pct']:5.1f}%  abs={s['abs_pct']:5.1f}%  top1={s['top1_cite']}")

    # 全部 dedup (按 title)
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
        print(f"  [DEDUP    ] n={s['n']:3d}  cite={s['cite_pct']:5.1f}%  abs={s['abs_pct']:5.1f}%  top1={s['top1_cite']}")

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
    print("SUMMARY: 4 免费引擎 (OpenAlex + S2 + Crossref + CORE) 中文 coverage")
    print("=" * 60)
    print(f"{'Query':30s} {'Area':8s} {'n':>3s}  {'cite%':>6s}  {'abs%':>6s}  {'top1':>5s}")
    for s in all_stats:
        print(f"{s['query']:30s} {s['area']:8s} {s['n']:3d}  {s['cite_pct']:5.1f}%  {s['abs_pct']:5.1f}%  {s['top1_cite']:5d}")


if __name__ == "__main__":
    main()
