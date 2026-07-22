"""[v3.9.7.4-lib] Add an entry to one of the 3 lookup libraries.

Per user request 2026-07-22: P1-6 / P1-8 / P1-9 transformed into sample
libraries that user populates incrementally as they work on specific
课题 / 论文.

Libraries (all in bench/v01/):
- sub_topic_library.json (P1-6) — sub-topic decomposition lookup
- china_institution_exclusion.json (P1-8) — China political institutions blocklist
- country_metadata.json (P1-9) — country name -> ISO / region / tag

Usage:
    # Sub-topic
    python test_output/_add_lookup.py sub-topic \\
        --parent "AI-divide" \\
        --id "Acemoglu-AI-labor" \\
        --label "Acemoglu 2022 AI labor displacement" \\
        --queries-seen 1

    # China institution
    python test_output/_add_lookup.py china-inst \\
        --name "中国社会科学院世界经济与政治研究所" \\
        --category "political-research-institute"

    # Country
    python test_output/_add_lookup.py country \\
        --name "France" \\
        --iso FR \\
        --region "Europe" \\
        --tag "manufacturing-strong"
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(".")
BENCH = ROOT / "bench" / "v01"

LIBRARIES = {
    "sub-topic": {
        "path": BENCH / "sub_topic_library.json",
        "key": "user_added",
    },
    "china-inst": {
        "path": BENCH / "china_institution_exclusion.json",
        "key": "institutions",
    },
    "country": {
        "path": BENCH / "country_metadata.json",
        "key": "user_added",
    },
}


def add_sub_topic(args):
    data = json.loads(LIBRARIES["sub-topic"]["path"].read_text(encoding="utf-8-sig"))
    user_added = data.get("user_added", [])
    # Check if already exists
    for item in user_added:
        if item["id"] == args.id:
            print(f"  {args.id} already in user_added, incrementing queries_seen")
            item["queries_seen"] = item.get("queries_seen", 0) + 1
            break
    else:
        user_added.append({
            "id": args.id,
            "label": args.label,
            "parent": args.parent,
            "queries_seen": args.queries_seen,
            "verified": False,
            "added_date": "2026-07-22",
        })
    data["user_added"] = user_added
    LIBRARIES["sub-topic"]["path"].write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  [sub-topic] {args.id} added (parent={args.parent})")


def add_china_inst(args):
    data = json.loads(LIBRARIES["china-inst"]["path"].read_text(encoding="utf-8-sig"))
    institutions = data.get("institutions", [])
    for inst in institutions:
        if inst["name"] == args.name:
            print(f"  {args.name} already in blocklist")
            return
    institutions.append({
        "name": args.name,
        "category": args.category,
        "added_date": "2026-07-22",
    })
    data["institutions"] = institutions
    LIBRARIES["china-inst"]["path"].write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  [china-inst] {args.name} added (category={args.category})")


def add_country(args):
    data = json.loads(LIBRARIES["country"]["path"].read_text(encoding="utf-8-sig"))
    countries = data.get("countries", {})
    user_added = data.get("user_added", [])
    if args.name in countries:
        print(f"  {args.name} already in countries")
        return
    countries[args.name] = {
        "iso": args.iso,
        "region": args.region,
        "tag": args.tag,
    }
    user_added.append({
        "name": args.name,
        "iso": args.iso,
        "added_date": "2026-07-22",
    })
    data["countries"] = countries
    data["user_added"] = user_added
    LIBRARIES["country"]["path"].write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  [country] {args.name} ({args.iso}) added (region={args.region}, tag={args.tag})")


def main():
    parser = argparse.ArgumentParser(description="Add entry to one of 3 lookup libraries")
    subparsers = parser.add_subparsers(dest="library", required=True)

    # sub-topic
    p_st = subparsers.add_parser("sub-topic", help="P1-6 sub-topic decomposition")
    p_st.add_argument("--parent", required=True, help="Parent topic (e.g. 'AI-divide')")
    p_st.add_argument("--id", required=True, help="Sub-topic ID (e.g. 'Acemoglu-AI-labor')")
    p_st.add_argument("--label", required=True, help="Human-readable label")
    p_st.add_argument("--queries-seen", type=int, default=0, help="How many queries used this")

    # china-inst
    p_ci = subparsers.add_parser("china-inst", help="P1-8 China institution exclusion")
    p_ci.add_argument("--name", required=True, help="Institution name (full)")
    p_ci.add_argument("--category", default="political-research-institute",
                     choices=["political-research-institute", "marxism-school",
                              "central-party-school", "official-think-tank", "other"],
                     help="Institution category")

    # country
    p_co = subparsers.add_parser("country", help="P1-9 country metadata")
    p_co.add_argument("--name", required=True, help="Country name (English)")
    p_co.add_argument("--iso", required=True, help="ISO 3166-1 alpha-2 code (e.g. FR)")
    p_co.add_argument("--region", required=True, help="Region (e.g. 'Europe', 'East Asia')")
    p_co.add_argument("--tag", default="other",
                     help="Tag (e.g. 'manufacturing-strong', 'china-local')")

    args = parser.parse_args()

    if args.library == "sub-topic":
        add_sub_topic(args)
    elif args.library == "china-inst":
        add_china_inst(args)
    elif args.library == "country":
        add_country(args)

    print()
    print("Run `python test_output/_status_lookups.py` to see all 3 libraries")


if __name__ == "__main__":
    main()
