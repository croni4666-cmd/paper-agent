"""[v3.9.7.4-lib] Remove an entry from one of the 3 lookup libraries.

Usage:
    python test_output/_remove_lookup.py sub-topic --id "Acemoglu-AI-labor"
    python test_output/_remove_lookup.py china-inst --name "中国社会科学院..."
    python test_output/_remove_lookup.py country --name "France"
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


def remove_sub_topic(args):
    path = LIBRARIES["sub-topic"]
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    user_added = data.get("user_added", [])
    new_list = [s for s in user_added if s["id"] != args.id]
    if len(new_list) == len(user_added):
        print(f"  {args.id} not in user_added")
        return
    data["user_added"] = new_list
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [sub-topic] {args.id} removed")


def remove_china_inst(args):
    path = LIBRARIES["china-inst"]
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    institutions = data.get("institutions", [])
    new_list = [s for s in institutions if s["name"] != args.name]
    if len(new_list) == len(institutions):
        print(f"  {args.name} not in institutions")
        return
    data["institutions"] = new_list
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [china-inst] {args.name} removed")


def remove_country(args):
    path = LIBRARIES["country"]
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    countries = data.get("countries", {})
    user_added = data.get("user_added", [])
    if args.name not in countries:
        print(f"  {args.name} not in countries")
        return
    del countries[args.name]
    new_user_added = [s for s in user_added if s["name"] != args.name]
    data["countries"] = countries
    data["user_added"] = new_user_added
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [country] {args.name} removed")


def main():
    parser = argparse.ArgumentParser(description="Remove entry from a lookup library")
    subparsers = parser.add_subparsers(dest="library", required=True)

    p_st = subparsers.add_parser("sub-topic")
    p_st.add_argument("--id", required=True)

    p_ci = subparsers.add_parser("china-inst")
    p_ci.add_argument("--name", required=True)

    p_co = subparsers.add_parser("country")
    p_co.add_argument("--name", required=True)

    args = parser.parse_args()

    if args.library == "sub-topic":
        remove_sub_topic(args)
    elif args.library == "china-inst":
        remove_china_inst(args)
    elif args.library == "country":
        remove_country(args)


if __name__ == "__main__":
    main()
