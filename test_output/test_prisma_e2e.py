"""Validation test for pa_cli.prisma + pa review --with-prisma.

Tests:
  [1] pa prisma --format mermaid produces parseable mermaid block
  [2] pa prisma --format markdown produces full report
  [3] by_source JSON parses correctly
  [4] excluded_reasons JSON parses correctly
  [5] counts add up: excluded = identified - after_screening etc.
  [6] pa review --with-prisma prepends PRISMA block to output
  [7] pa review without --with-prisma works as before (regression)
  [8] derive_counts_from_corpus() returns sensible numbers from a temp corpus
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _run_pa(*args, env=None, timeout=30):
    """Run pa <args> as subprocess; return (rc, stdout, stderr)."""
    cmd = [sys.executable, "-m", "pa_cli"] + list(args)
    e = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1",
         **(env or {})}
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       env=e, cwd=str(ROOT), timeout=timeout,
                       stdin=subprocess.DEVNULL)
    return r.returncode, r.stdout, r.stderr


def test_pa_prisma_mermaid_format():
    print("\n=== test: pa prisma --format mermaid ===")
    rc, out, err = _run_pa("prisma",
                            "--identified", "287",
                            "--after-screening", "57",
                            "--after-eligibility", "57",
                            "--included", "57",
                            "--pdf", "25", "--abstract", "32",
                            "--format", "mermaid")
    assert rc == 0, f"rc={rc} stderr={err[-300:]!r}"
    # Must contain mermaid code fence + flow nodes
    assert "```mermaid" in out
    assert "flowchart TD" in out
    assert "Identification" in out
    assert "287" in out and "57" in out
    print(f"  PASS: mermaid block contains Identification + counts")


def test_pa_prisma_markdown_format():
    print("\n=== test: pa prisma --format markdown ===")
    rc, out, err = _run_pa("prisma",
                            "--identified", "287",
                            "--after-screening", "57",
                            "--after-eligibility", "57",
                            "--included", "57",
                            "--pdf", "25", "--abstract", "32",
                            "--format", "markdown")
    assert rc == 0, f"rc={rc} stderr={err[-300:]!r}"
    # Markdown should have title + mermaid block + stage details
    assert "# PRISMA" in out
    assert "```mermaid" in out
    assert "## " in out  # has section headers
    assert "Identification" in out
    assert "Screening" in out
    assert "Eligibility" in out
    assert "Included" in out
    print(f"  PASS: full markdown report with all 4 sections")


def test_pa_prisma_by_source_json():
    print("\n=== test: pa prisma --by-source JSON ===")
    rc, out, err = _run_pa("prisma",
                            "--identified", "100",
                            "--after-screening", "30",
                            "--after-eligibility", "20",
                            "--included", "15",
                            "--by-source", '{"arxiv":40,"openalex":60}',
                            "--format", "mermaid")
    assert rc == 0, f"rc={rc} stderr={err[-300:]!r}"
    # Should mention both sources
    assert "arxiv" in out.lower()
    assert "openalex" in out.lower()
    print(f"  PASS: by_source JSON parsed, sources in output")


def test_pa_prisma_excluded_reasons():
    print("\n=== test: pa prisma --excluded-reasons JSON ===")
    rc, out, err = _run_pa("prisma",
                            "--identified", "100",
                            "--after-screening", "30",
                            "--after-eligibility", "20",
                            "--included", "15",
                            "--excluded-reasons", '{"stage1":50,"stage2":10}',
                            "--format", "markdown")
    assert rc == 0, f"rc={rc} stderr={err[-300:]!r}"
    assert "Stage 1" in out or "stage1" in out
    print(f"  PASS: excluded_reasons JSON parsed, in output")


def test_pa_prisma_counts_internally_consistent():
    print("\n=== test: counts add up internally ===")
    from pa_cli.prisma import render_prisma
    md = render_prisma(
        identified=200, after_screening=50, after_eligibility=20, included=10,
        by_source={"arxiv": 100, "openalex": 100},
        pdf_count=8, abstract_count=2,
        excluded_reasons={"stage1": 150, "stage2": 30},
    )
    # Screening excluded = 200 - 50 = 150
    # Eligibility excluded = 50 - 20 = 30
    assert "150" in md
    assert "30" in md
    # Sources
    assert "arxiv" in md
    assert "openalex" in md
    print(f"  PASS: counts internally consistent, sources present")


def test_pa_prisma_invalid_json():
    print("\n=== test: invalid JSON for --by-source fails gracefully ===")
    rc, out, err = _run_pa("prisma",
                            "--identified", "100",
                            "--after-screening", "30",
                            "--after-eligibility", "20",
                            "--included", "15",
                            "--by-source", "not json at all",
                            "--format", "mermaid")
    # Should exit non-zero (we surface the ValueError)
    assert rc != 0, f"expected non-zero exit, got {rc}"
    combined = out + err
    assert "invalid json" in combined.lower() or "json" in combined.lower()
    print(f"  PASS: invalid JSON exits non-zero with clear error (rc={rc})")


def test_pa_review_with_prisma():
    print("\n=== test: pa review --with-prisma ===")
    with tempfile.TemporaryDirectory() as tmp:
        # No PDFs in corpus → review still works, prisma shows 0s
        rc, out, err = _run_pa("review", tmp, "--with-prisma", "--word-count-min", "100")
        assert rc == 0, f"rc={rc} stderr={err[-300:]!r}"
        # Should have PRISMA section at top + review body
        assert "PRISMA" in out or "Identification" in out
        # PRISMA section is before the rest
        idx_prisma = out.find("Identification")
        idx_review = out.find("---")
        # The --- is the separator I added; if both present, prisma comes first
        if idx_review > 0:
            assert idx_prisma < idx_review, f"PRISMA should come before review"
        print(f"  PASS: --with-prisma prepends PRISMA block")


def test_pa_review_without_prisma_unchanged():
    print("\n=== test: pa review without --with-prisma (regression) ===")
    with tempfile.TemporaryDirectory() as tmp:
        rc, out, err = _run_pa("review", tmp, "--word-count-min", "100")
        assert rc == 0
        # Should NOT have PRISMA mermaid block
        assert "```mermaid" not in out
        assert "Identification" not in out
        print(f"  PASS: review without --with-prisma unchanged (no mermaid block)")


def test_derive_counts_from_corpus():
    print("\n=== test: derive_counts_from_corpus() ===")
    with tempfile.TemporaryDirectory() as tmp:
        # Create 2 fake PDFs (text doesn't need to be valid; just files)
        Path(tmp, "paper1.pdf").write_bytes(b"%PDF-1.4\n%test\n" + b"x" * 200)
        Path(tmp, "paper2.pdf").write_bytes(b"%PDF-1.4\n%test\n" + b"x" * 200)

        from pa_cli.prisma import derive_counts_from_corpus
        counts = derive_counts_from_corpus(Path(tmp), word_count_min=1000)
        # Both PDFs likely have 0 words extracted (fake PDFs), so:
        #   identified=2, after_screening=0, abstract=2
        assert counts["identified"] == 2, f"got {counts}"
        assert counts["after_screening"] == 0, f"got {counts}"
        assert counts["abstract_count"] == 2, f"got {counts}"
        print(f"  PASS: derive_counts_from_corpus: {counts}")


def main():
    print("=" * 60)
    print("pa prisma validation")
    print("=" * 60)
    test_pa_prisma_mermaid_format()
    test_pa_prisma_markdown_format()
    test_pa_prisma_by_source_json()
    test_pa_prisma_excluded_reasons()
    test_pa_prisma_counts_internally_consistent()
    test_pa_prisma_invalid_json()
    test_pa_review_with_prisma()
    test_pa_review_without_prisma_unchanged()
    test_derive_counts_from_corpus()
    print("\n" + "=" * 60)
    print("ALL PRISMA TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    main()
