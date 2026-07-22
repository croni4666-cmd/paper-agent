"""[v3.9.7.4-lib] Status of the 3 lookup libraries (P1-6, P1-8, P1-9).

Per user request 2026-07-22: each lookup is a sample library that
user populates incrementally.

Usage:
    python test_output/_status_lookups.py
    python test_output/_status_lookups.py --library sub-topic
    python test_output/_status_lookups.py --library china-inst
    python test_output/_status_lookups.py --library country
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(".")
BENCH = ROOT / "bench" / "v01"

LIBRARIES = {
    "sub-topic": BENCH / "sub_topic_library.json",
    "china-inst": BENCH / "china_institution_exclusion.json",
    "country": BENCH / "country_metadata.json",
}


def status_sub_topic():
    path = LIBRARIES["sub-topic"]
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    topics = data.get("topics", {})
    user_added = data.get("user_added", [])

    print("=" * 70)
    print(f"[P1-6] Sub-topic decomposition library — {path.name}")
    print("=" * 70)
    n_seeded = sum(len(v) for v in topics.values())
    n_user = len(user_added)
    print(f"Seeded sub-topics: {n_seeded} (across {len(topics)} parent topics)")
    print(f"User-added sub-topics: {n_user}")
    print()
    print("Seeded by parent topic:")
    for parent, subs in topics.items():
        print(f"  {parent:15s} ({len(subs)} sub-topics)")
        for s in subs:
            print(f"    {s['id']:25s} {s['label']}")
    if user_added:
        print()
        print("User-added:")
        for s in user_added:
            print(f"  {s['id']:25s} {s['label']} (parent={s.get('parent')}, seen={s.get('queries_seen', 0)})")
    print()
    print("Add: python test_output/_add_lookup.py sub-topic --help")


def status_china_inst():
    path = LIBRARIES["china-inst"]
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    institutions = data.get("institutions", [])
    categories = data.get("categories", {})

    print("=" * 70)
    print(f"[P1-8] China institution exclusion blocklist — {path.name}")
    print("=" * 70)
    print(f"WARNING: {data.get('warning', '(no warning)')}")
    print()
    print(f"Institutions in blocklist: {len(institutions)}")
    if institutions:
        for inst in institutions:
            print(f"  [{inst.get('category', '?')}] {inst['name']}")
    else:
        print("  (empty - user has not added any institutions yet)")
        print()
        print("Examples (per ROADMAP [P1-8]):")
        for ex in data.get("user_added_examples", [])[:3]:
            print(f"  {ex}")
    print()
    print("Categories defined:")
    for cat, desc in categories.items():
        print(f"  {cat:30s} {desc}")
    print()
    print("Add: python test_output/_add_lookup.py china-inst --help")


def status_country():
    path = LIBRARIES["country"]
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    countries = data.get("countries", {})
    user_added = data.get("user_added", [])

    print("=" * 70)
    print(f"[P1-9] Country metadata library — {path.name}")
    print("=" * 70)
    print(f"Seeded countries: {len(countries)}")
    print(f"User-added countries: {len(user_added)}")
    print()
    print("Countries by region:")
    by_region = {}
    for name, info in countries.items():
        by_region.setdefault(info.get("region", "?"), []).append((name, info))
    for region in sorted(by_region):
        print(f"  {region}:")
        for name, info in sorted(by_region[region]):
            tag = info.get("tag", "?")
            print(f"    {info.get('iso', '??'):3s} {name:25s} [{tag}]")
    print()
    print("Tags used:")
    for tag in data.get("tags_used", []):
        print(f"  - {tag}")
    print()
    print("Add: python test_output/_add_lookup.py country --help")


def main():
    parser = argparse.ArgumentParser(description="Status of 3 lookup libraries")
    parser.add_argument("--library", choices=list(LIBRARIES.keys()),
                        help="Show only this library (default: all)")
    args = parser.parse_args()

    if args.library == "sub-topic" or args.library is None:
        print()
        status_sub_topic()
    if args.library == "china-inst" or args.library is None:
        print()
        status_china_inst()
    if args.library == "country" or args.library is None:
        print()
        status_country()


if __name__ == "__main__":
    main()
