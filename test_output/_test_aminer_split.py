"""Quick AMiner test after split logic"""
import sys
sys.path.insert(0, r'G:\minimax - workspace\Paper agent')
from pa_cli.aminer_channel import search_aminer

QUERIES = [
    ("数字普惠金融 家庭消费", "经济学"),
    ("长期护理保险 人口老龄化", "保险学"),
    ("金融科技 中小银行", "金融学"),
]

for q, area in QUERIES:
    print(f"\n=== {q} ({area}) ===")
    r = search_aminer(q, 2022, 2024, 20)
    if not r:
        print("EMPTY")
        continue
    if "error" in r[0]:
        print(f"ERROR: {r[0]}")
        continue
    n = len(r)
    cite_n = sum(1 for x in r if (x.get("cited_by_count") or 0) > 0)
    abs_n = sum(1 for x in r if x.get("abstract"))
    print(f"n={n}  cite>0: {cite_n}/{n} ({cite_n/n*100:.1f}%)  abs: {abs_n}/{n}")
    for x in r[:3]:
        title = x.get("title", "")[:50]
        venue = x.get("venue", "")[:25]
        bkt = x.get("cited_bucket", "?")
        ph = x.get("matched_phrase", "?")
        print(f"  - {title}  ({venue})  y={x.get('year')}  bkt={bkt}  ph={ph}")
