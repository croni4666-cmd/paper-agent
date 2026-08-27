"""Quick test of new aminer relevance scoring."""
import sys
sys.path.insert(0, r"G:\minimax - workspace\Paper agent")
from pa_cli.aminer_channel import _title_relevance_score, search_aminer, search_aminer_pro

# Test title_relevance_score
print("=== _title_relevance_score tests ===")
test_cases = [
    ("Wilson disease associated with ATP7B gene", "Wilson Disease"),
    ("Wilson's disease: a clinical review", "Wilson Disease"),
    ("Hepatolenticular Degeneration: Wilson disease", "Wilson Disease"),
    ("Dr. Wilson's recent work on COVID", "Wilson Disease"),
    ("Cardiovascular disease prevention", "Wilson Disease"),
    ("A review of statistical methods", "Wilson Disease"),
    ("数字普惠金融 家庭消费", "数字普惠金融 家庭消费"),
    ("数字普惠金融", "数字普惠金融 家庭消费"),
]
for title, query in test_cases:
    score = _title_relevance_score(title, query)
    print(f"  score={score:.3f} | title={title!r:50s} | query={query!r}")

# Test import of all new functions
print()
print("=== Function signature tests ===")
import inspect
for fn in [search_aminer, search_aminer_pro, _title_relevance_score]:
    sig = inspect.signature(fn)
    print(f"  {fn.__name__}{sig}")
