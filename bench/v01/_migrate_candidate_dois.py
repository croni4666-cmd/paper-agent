"""
bench/v01/_migrate_candidate_dois.py — Apply canonicalize_doi() to all system_outputs_*.

ROADMAP [P0-4]: After labels.json + labels_clean.json migration, candidates in
system_outputs/ + system_outputs_bm25/ + system_outputs_biencoder/ + system_outputs_combined/
+ system_outputs_prf/ + system_outputs_random/ + system_outputs_prf/* directories
still have non-canonical DOIs (17 instances found across 9 query files).

This script rewrites all candidates to canonical form so eval.py can match correctly.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pa_cli.doi import canonicalize_doi  # noqa: E402

BENCH_DIR = Path(r"G:\minimax - workspace\Paper agent\bench\v01")
SUBDIRS = [
    "system_outputs",
    "system_outputs_bm25",
    "system_outputs_biencoder",
    "system_outputs_combined",
    "system_outputs_prf",
    "system_outputs_random",
]


def main():
    total_files = 0
    total_renamed = 0
    for sub in SUBDIRS:
        sub_path = BENCH_DIR / sub
        if not sub_path.exists():
            print(f"  SKIP {sub}/ (not found)")
            continue
        files = list(sub_path.glob("q*.json"))
        n_renamed_here = 0
        for f in files:
            data = json.loads(f.read_text(encoding="utf-8"))
            changed = False
            for r in data.get("results", []):
                doi = r.get("doi", "")
                if doi and doi != canonicalize_doi(doi):
                    r["doi"] = canonicalize_doi(doi)
                    n_renamed_here += 1
                    changed = True
            if changed:
                f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  {sub}/: {len(files)} files, {n_renamed_here} DOIs canonicalized")
        total_files += len(files)
        total_renamed += n_renamed_here
    print(f"\n[P0-4 migrate-candidates] total: {total_renamed} DOIs canonicalized across {total_files} files")


if __name__ == "__main__":
    main()
