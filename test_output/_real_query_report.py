"""real_query_report.py — Show what user gets in 课题 workflow (3 realistic queries)."""
import json
from pathlib import Path
from collections import defaultdict

# Match files to query labels
file_query_map = {
    "_real_digital_finance": ("数字普惠金融 + 家庭消费", "经济学 (你的 ch1+ch2 方向)"),
    "_real_ltc_insurance":   ("长期护理保险 + 人口老龄化", "保险学 (东方学院方向)"),
    "_real_fintech_bank":     ("金融科技 + 中小银行", "金融学 (你常研究的领域)"),
}


def report(json_path, query_label, area_label):
    d = json.loads(json_path.read_text(encoding="utf-8"))
    results = d["results"]
    total = len(results)
    print(f"\n{'='*78}")
    print(f"  Q: {query_label}")
    print(f"     方向: {area_label}")
    print(f"  by_engine: {d.get('by_engine')}")
    print(f"  dedup: {total}")
    print(f"{'='*78}")
    if total == 0:
        return

    by_src = defaultdict(lambda: {"n": 0, "cite": 0, "inf": 0, "abs": 0, "tldr": 0})
    for r in results:
        s = r.get("source", "?")
        by_src[s]["n"] += 1
        if r.get("cited_by_count"): by_src[s]["cite"] += 1
        if r.get("influential_cite_count"): by_src[s]["inf"] += 1
        if r.get("abstract"): by_src[s]["abs"] += 1
        if r.get("tldr"): by_src[s]["tldr"] += 1

    print(f"\n  {'source':<18} {'n':>3} {'cite':>5} {'inf':>5} {'abs':>4} {'tldr':>5}")
    for s, c in sorted(by_src.items(), key=lambda x: -x[1]["n"]):
        print(f"    {s:<16} {c['n']:>3} {c['cite']:>5} {c['inf']:>5} {c['abs']:>4} {c['tldr']:>5}")
    cov = {k: sum(1 for r in results if r.get(k)) for k in ("cited_by_count", "influential_cite_count", "abstract", "tldr")}
    print(f"\n  整体覆盖率: cite={cov['cited_by_count']}/{total} ({100*cov['cited_by_count']/total:.0f}%), "
          f"inf={cov['influential_cite_count']}/{total} ({100*cov['influential_cite_count']/total:.0f}%), "
          f"abs={cov['abstract']}/{total} ({100*cov['abstract']/total:.0f}%), "
          f"tldr={cov['tldr']}/{total} ({100*cov['tldr']/total:.0f}%)")

    # Top-5 (user actually reads these)
    print(f"\n  Top-5 papers (按 cite 排序,前 5 你会读):")
    for i, r in enumerate(results[:5], 1):
        title = r.get("title", "")[:55]
        cite = r.get("cited_by_count", 0)
        inf = r.get("influential_cite_count", 0) or "-"
        has_abs = "Y" if r.get("abstract") else "N"
        has_tldr = "Y" if r.get("tldr") else "N"
        year = r.get("year", "-")
        venue = r.get("venue", "")[:22]
        src = r.get("source", "?")
        en = r.get("_enrichment", {})
        marker = " [enriched]" if en.get("s2_doi") else ""
        print(f"    {i}. [{src:<12}] {title}{marker}")
        print(f"       year={year} cite={cite} inf={inf} abs={has_abs} tldr={has_tldr} | {venue}")


# Find latest 3 files
files = sorted(Path("test_output").glob("_real_*_20260715_173450.json"),
              key=lambda p: p.stat().st_mtime, reverse=True)

# Print in subject order
for prefix in ["_real_digital_finance", "_real_ltc_insurance", "_real_fintech_bank"]:
    matching = [f for f in files if prefix in f.name]
    if not matching:
        continue
    f = matching[0]
    label, area = file_query_map[prefix]
    report(f, label, area)

print(f"\n{'='*78}")
print("  总结")
print(f"{'='*78}")
print("""
  3 个真实 query 测试(2022-2024, --enrich-top 10):
  - 数字普惠金融 + 家庭消费 (经济学方向)
  - 长期护理保险 + 人口老龄化 (保险学方向)
  - 金融科技 + 中小银行 (金融学方向)

  观察:
  - 每个 query 都有 CNKI 引擎结果,但 cite/abstract 都是 None(deprecated)
  - 4 个英文 engine 主导,cite/abstract 主要来自 Crossref/OpenAlex/S2
  - --enrich-top 10 给前 10 篇加了 S2 by-DOI 的深度 metadata
  - 中文 paper 仍然有 ~70% 缺 cite — 不可自动化,workflow split 决定走手工

  这是 v3.9.7.8 实际能给你的:**前 10 篇有完整 metadata,后面要再翻 cite 只能去原网站**。
""")
