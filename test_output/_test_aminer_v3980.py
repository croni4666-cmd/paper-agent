"""v3.9.8.0 AMiner 真实 API 验证
3 个中文 query, 看 AMiner 响应格式 + cite 覆盖率
"""
import sys
sys.path.insert(0, r'G:\minimax - workspace\Paper agent')
from pa_cli.aminer_channel import search_aminer
import json

QUERIES = [
    ("数字普惠金融 家庭消费", "经济学"),
    ("长期护理保险 人口老龄化", "保险学"),
    ("金融科技 中小银行", "金融学"),
]

YEAR_MIN, YEAR_MAX, LIMIT = 2022, 2024, 20

for q, area in QUERIES:
    print(f"\n{'=' * 60}")
    print(f"Query: {q}  ({area})")
    print('=' * 60)
    r = search_aminer(q, YEAR_MIN, YEAR_MAX, LIMIT)

    if not r:
        print("EMPTY")
        continue
    if isinstance(r, list) and len(r) == 1 and "error" in r[0]:
        print(f"ERROR: {r[0]}")
        continue

    print(f"Total: {len(r)}")
    n = len(r)
    cite_n = sum(1 for x in r if (x.get("cited_by_count") or 0) > 0)
    abs_n = sum(1 for x in r if x.get("abstract"))
    top1 = max((x.get("cited_by_count") or 0) for x in r)
    print(f"cite>0: {cite_n}/{n} ({cite_n/n*100:.1f}%)")
    print(f"abstract: {abs_n}/{n} ({abs_n/n*100:.1f}%)")
    print(f"top-1 cite: {top1}")

    # 打印前 3 个看字段
    for i, x in enumerate(r[:3]):
        print(f"\n  [{i+1}] {x.get('title','')[:60]}")
        print(f"      year={x.get('year')}  cite={x.get('cited_by_count')}")
        print(f"      venue={x.get('venue','')[:50]}")
        print(f"      doi={x.get('doi','')}")
        print(f"      abstract={x.get('abstract','')[:80]}")
        print(f"      authors={x.get('authors',[])[:3]}")
