"""
bench/v01/_migrate_doi_canonical.py — Migrate labels.json + labels_clean.json to canonical DOIs.

ROADMAP [P0-4] (added 2026-07-13, executed 2026-07-13):
Apply canonicalize_doi() to all DOI keys in:
  - bench/v01/labels.json
  - bench/v01/labels_clean.json
  - bench/v01/spot_check/_overrides.json (audit log DOIs)

Effect: case-variant duplicates collapse into single canonical key; 5 typo'd
Frontiers DOIs (10.3380 → 10.3389) get fixed.

Output: writes back in-place + emits a rename report.
"""
import json
import sys
from pathlib import Path

# Make pa_cli importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pa_cli.doi import canonicalize_doi, normalize_labels_dict  # noqa: E402

BENCH_DIR = Path(r"G:\minimax - workspace\Paper agent\bench\v01")
FILES = [
    BENCH_DIR / "labels.json",
    BENCH_DIR / "labels_clean.json",
    BENCH_DIR / "spot_check" / "_overrides.json",
]


def migrate_labels_file(path: Path) -> dict:
    """Migrate a labels.json / labels_clean.json file in-place. Returns rename_map."""
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if "labels" not in data:
        print(f"  SKIP {path.name}: no 'labels' key")
        return {}
    new_labels, rename_map = normalize_labels_dict(data["labels"])
    n_renamed = len(rename_map)
    n_collapsed = 0  # count cases where old/new DOI list had different lengths after
    n_pre = sum(len(v) for v in data["labels"].values())
    n_post = sum(len(v) for v in new_labels.values())
    n_collapsed = n_pre - n_post - n_renamed  # some "renames" might not exist in candidates

    data["labels"] = new_labels
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  MIGRATED {path.name}: {n_pre} → {n_post} keys, {n_renamed} renamed, {max(0, n_collapsed)} collapsed")
    return rename_map


def migrate_overrides_file(path: Path) -> dict:
    """Migrate _overrides.json (audit log) — DOIs live in entries[].doi."""
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    rename_map: dict[str, str] = {}
    for qid, entries in data.items():
        for entry in entries:
            old_doi = entry.get("doi")
            if not old_doi:
                continue
            new_doi = canonicalize_doi(old_doi)
            if new_doi != old_doi:
                rename_map[old_doi] = new_doi
                entry["doi"] = new_doi
                entry["doi_canonicalized_from"] = old_doi
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  MIGRATED {path.name}: {len(rename_map)} DOIs renamed")
    return rename_map


def main():
    print(f"[P0-4 migrate] scanning {len(FILES)} files")
    all_renames: dict[str, str] = {}
    for f in FILES:
        if "overrides" in f.name:
            rmap = migrate_overrides_file(f)
        else:
            rmap = migrate_labels_file(f)
        for k, v in rmap.items():
            if k in all_renames and all_renames[k] != v:
                print(f"  CONFLICT: {k} → {all_renames[k]} vs {v} (using first)")
            else:
                all_renames[k] = v

    print(f"\n[P0-4 migrate] total: {len(all_renames)} unique DOI renames")
    if all_renames:
        for old, new in sorted(all_renames.items()):
            print(f"  {old} → {new}")

    # Save rename report
    report_path = BENCH_DIR / "doi_canonicalization_report.json"
    report_path.write_text(
        json.dumps(all_renames, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n[P0-4 migrate] wrote {report_path}")


if __name__ == "__main__":
    main()
