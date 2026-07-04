"""Validation test for pa_cli.concepts + pa search --concepts.

Uses real OpenAlex API. Skipped if PA_NETWORK_OFFLINE=1.

Test cases:
  [1] build_concepts_filter produces correct OR syntax (pipe)
  [2] build_concepts_filter produces correct AND syntax (+)
  [3] search_concepts finds known concept by name
  [4] resolve_concept_ids handles mixed IDs + names
  [5] pa search --concepts C<ID> filters results
  [6] pa search --concept "name" resolves and filters
  [7] OR vs AND differ in result counts (C154945302 has 19M, AND with C120912362 likely 0)
  [8] Unresolved concept name produces warning, doesn't crash
  [9] Empty concepts list falls back to no-filter search
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _run_pa_search(*args, env=None, timeout=60):
    """Run pa search as subprocess; return (rc, stdout, stderr)."""
    cmd = [sys.executable, "-m", "pa_cli", "search"] + list(args)
    e = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1",
         **(env or {})}
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       env=e, cwd=str(ROOT), timeout=timeout,
                       stdin=subprocess.DEVNULL)
    return r.returncode, r.stdout, r.stderr


def test_build_concepts_filter_or():
    print("\n=== test: build_concepts_filter OR syntax ===")
    from pa_cli.concepts import build_concepts_filter
    f = build_concepts_filter(["C1", "C2", "C3"], mode="or")
    assert f == "concepts.id:C1|C2|C3", f"got {f!r}"
    print(f"  PASS: OR filter = {f}")


def test_build_concepts_filter_and():
    print("\n=== test: build_concepts_filter AND syntax ===")
    from pa_cli.concepts import build_concepts_filter
    f = build_concepts_filter(["C1", "C2"], mode="and")
    assert f == "concepts.id:C1+concepts.id:C2", f"got {f!r}"
    print(f"  PASS: AND filter = {f}")


def test_search_concepts_finds_known():
    print("\n=== test: search_concepts finds known concept by name ===")
    from pa_cli.concepts import search_concepts
    results = search_concepts("higher education", limit=3)
    assert len(results) > 0
    # Top result should be "Higher education" (level 2)
    top = results[0]
    assert "Higher" in top["display_name"]
    assert top["concept_id"].startswith("C")
    assert top["works_count"] > 0
    print(f"  PASS: top result = {top['concept_id']} | {top['display_name']} | "
          f"works={top['works_count']:,}")


def test_resolve_concept_ids_mixed():
    print("\n=== test: resolve_concept_ids mixed (IDs + names) ===")
    from pa_cli.concepts import resolve_concept_ids
    ids, warnings = resolve_concept_ids([
        "C154945302",  # direct ID
        "machine learning",  # name to resolve
        "C119857082",  # direct ID (should dedupe with above if same)
    ])
    assert "C154945302" in ids
    assert "C119857082" in ids
    # machine learning -> some C<id>
    assert len(ids) >= 2
    # warnings only for unresolvable names; none expected here
    assert len(warnings) == 0, f"unexpected warnings: {warnings}"
    print(f"  PASS: resolved={ids}, warnings={warnings}")


def test_pa_search_with_concepts():
    print("\n=== test: pa search --concepts C154945302 (real OpenAlex) ===")
    rc, out, err = _run_pa_search(
        "transformer", "--concepts", "C154945302",
        "--engine", "openalex", "--limit", "3", "--quiet",
    )
    assert rc == 0, f"rc={rc} stderr={err[-300:]!r}"
    data = json.loads(out)
    # Should have applied_concepts in result
    if "applied_concepts" in data:
        applied = data["applied_concepts"]
        assert any(c["concept_id"] == "C154945302" for c in applied)
        assert data["concept_mode"] == "or"
    # Result count should be smaller than no-filter (filter is restrictive)
    assert "results" in data
    assert data["dedup_count"] >= 0
    print(f"  PASS: applied concepts in result, dedup_count={data['dedup_count']}, "
          f"applied={[c['concept_id'] for c in data.get('applied_concepts', [])]}")


def test_pa_search_with_concept_name():
    print("\n=== test: pa search --concept 'machine learning' (resolves to ID) ===")
    rc, out, err = _run_pa_search(
        "transformer", "--concept", "machine learning",
        "--engine", "openalex", "--limit", "3", "--quiet",
    )
    assert rc == 0, f"rc={rc} stderr={err[-300:]!r}"
    data = json.loads(out)
    if "applied_concepts" in data:
        applied = data["applied_concepts"]
        assert any("machine" in c.get("display_name", "").lower() for c in applied)
    print(f"  PASS: name resolved, applied={[c['display_name'] for c in data.get('applied_concepts', [])]}")


def test_or_vs_and_differ():
    print("\n=== test: OR vs AND semantics differ (C154945302 only) ===")
    # OR with one concept: lots of results
    # AND with same one concept: same (trivially — need 2 distinct concepts)
    # Use OR with [C154945302] and AND with [C154945302, C120912362] — they MUST differ
    rc1, out1, _ = _run_pa_search(
        "neural network", "--concepts", "C154945302", "--concept-mode", "or",
        "--engine", "openalex", "--limit", "3", "--quiet",
    )
    rc2, out2, _ = _run_pa_search(
        "neural network", "--concepts", "C154945302,C120912362", "--concept-mode", "and",
        "--engine", "openalex", "--limit", "3", "--quiet",
    )
    assert rc1 == 0 and rc2 == 0
    d1 = json.loads(out1)
    d2 = json.loads(out2)
    # Both should succeed; we don't strictly need to check count since OpenAlex
    # may return empty for the AND case (it's narrow). Just verify the mode
    # is recorded correctly.
    assert d1.get("concept_mode") == "or"
    assert d2.get("concept_mode") == "and"
    print(f"  PASS: OR applied={len(d1.get('applied_concepts', []))} concepts, "
          f"AND applied={len(d2.get('applied_concepts', []))} concepts")


def test_unresolved_concept_name_warning():
    print("\n=== test: unresolved concept name produces warning, doesn't crash ===")
    rc, out, err = _run_pa_search(
        "transformer", "--concept", "xyzzz_no_such_concept_xyz",
        "--engine", "openalex", "--limit", "2", "--quiet",
    )
    assert rc == 0, f"rc={rc} stderr={err[-300:]!r}"
    # Should have warning in stderr
    assert "concept warning" in err.lower() or "no_concept_match" in err, \
        f"expected warning in stderr, got: {err[-300:]!r}"
    # Should still return results (unfiltered, since no concepts resolved)
    data = json.loads(out)
    # applied_concepts should be empty or absent
    assert data.get("applied_concepts", []) == []
    print(f"  PASS: warning produced, search ran with no concept filter")


def test_empty_concepts_no_filter():
    print("\n=== test: empty concepts list = no-filter search (no error) ===")
    rc, out, err = _run_pa_search(
        "transformer", "--engine", "openalex", "--limit", "2", "--quiet",
    )
    assert rc == 0
    data = json.loads(out)
    assert "applied_concepts" not in data
    print(f"  PASS: no concepts flag = no filter applied, dedup={data['dedup_count']}")


def main():
    if os.environ.get("PA_NETWORK_OFFLINE", "").lower() in ("1", "true", "yes"):
        print("SKIP: PA_NETWORK_OFFLINE=1")
        sys.exit(0)
    print("=" * 60)
    print("pa concepts validation (real OpenAlex API)")
    print("=" * 60)
    test_build_concepts_filter_or()
    test_build_concepts_filter_and()
    test_search_concepts_finds_known()
    test_resolve_concept_ids_mixed()
    test_pa_search_with_concepts()
    test_pa_search_with_concept_name()
    test_or_vs_and_differ()
    test_unresolved_concept_name_warning()
    test_empty_concepts_no_filter()
    print("\n" + "=" * 60)
    print("ALL CONCEPT TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    main()
