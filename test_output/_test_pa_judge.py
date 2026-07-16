"""
[P3-1] e2e test: pa judge round-trip on a temp SQLite DB.

Validates:
  1. add() / add_bulk() / list_judgements() / stats() / export / import
  2. SQLite schema enforces (query, paper_key) UNIQUE
  3. Relevance validation (must be 0/1/2)
  4. bench-format export round-trips via import
  5. CLI subcommand registration (no actual subprocess calls)

Run:
  cd "G:\minimax - workspace\Paper agent"
  python test_output\_test_pa_judge.py
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pa_cli.judge import (  # noqa: E402
    add, add_bulk, list_judgements, stats,
    export_jsonl, export_bench_format, import_bench_format,
    RELEVANCE_LABELS, DEFAULT_DB,
)


# Sample bench-format fixture (matches bench/v01/labels.json shape)
BENCH_FIXTURE = {
    "_meta": {
        "version": "test-fixture",
        "labeled_by": "test",
        "method": "synthetic for unit test",
        "rubric": "0=irrelevant, 1=marginal, 2=relevant",
        "queries_covered": ["q001", "q002"],
    },
    "labels": {
        "q001": {
            "10.1016/j.lindif.2023.102274": {
                "label": 1,
                "reason": "test marginal"
            },
            "10.1186/s41039-017-0062-8": {
                "label": 0,
                "reason": "test irrelevant"
            },
            "10.1186/s41239-023-00392-8": {
                "label": 2,
                "reason": "test relevant"
            },
        },
        "q002": {
            "10.1234/test.5678": {
                "label": 2,
                "reason": "test relevant q002"
            },
        },
    },
}


class TestJudgeCore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "test_judgements.sqlite"

    def tearDown(self):
        self.tmp.cleanup()

    def test_add_single(self):
        rid = add(query="q001", paper_key="doi:10.123/abc",
                  relevance=2, reason="direct hit",
                  db_path=self.db)
        self.assertGreater(rid, 0)

    def test_add_invalid_relevance(self):
        with self.assertRaises(ValueError):
            add(query="q001", paper_key="x", relevance=5, db_path=self.db)
        with self.assertRaises(ValueError):
            add(query="q001", paper_key="x", relevance=-1, db_path=self.db)

    def test_add_empty_query_or_key(self):
        with self.assertRaises(ValueError):
            add(query="", paper_key="x", relevance=1, db_path=self.db)
        with self.assertRaises(ValueError):
            add(query="q", paper_key="", relevance=1, db_path=self.db)
        with self.assertRaises(ValueError):
            add(query="   ", paper_key="x", relevance=1, db_path=self.db)

    def test_upsert_overwrite(self):
        rid1 = add(query="q1", paper_key="k1", relevance=1, db_path=self.db)
        rid2 = add(query="q1", paper_key="k1", relevance=2, db_path=self.db)
        # Same id (overwrote), not a new row
        self.assertEqual(rid1, rid2)
        # list should show relevance=2
        rows = list_judgements(db_path=self.db)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["relevance"], 2)

    def test_upsert_no_overwrite_raises(self):
        add(query="q1", paper_key="k1", relevance=1, db_path=self.db)
        with self.assertRaises(ValueError):
            add(query="q1", paper_key="k1", relevance=2,
                overwrite=False, db_path=self.db)

    def test_list_filtered(self):
        add(query="q1", paper_key="a", relevance=0, db_path=self.db)
        add(query="q1", paper_key="b", relevance=1, db_path=self.db)
        add(query="q1", paper_key="c", relevance=2, db_path=self.db)
        add(query="q2", paper_key="d", relevance=2, db_path=self.db)

        all_rows = list_judgements(db_path=self.db)
        self.assertEqual(len(all_rows), 4)
        q1 = list_judgements(query="q1", db_path=self.db)
        self.assertEqual(len(q1), 3)
        rel2 = list_judgements(relevance=2, db_path=self.db)
        self.assertEqual(len(rel2), 2)
        rel0 = list_judgements(relevance=0, db_path=self.db)
        self.assertEqual(len(rel0), 1)

    def test_stats(self):
        add(query="q1", paper_key="a", relevance=0, db_path=self.db)
        add(query="q1", paper_key="b", relevance=1, db_path=self.db)
        add(query="q1", paper_key="c", relevance=2, db_path=self.db)
        add(query="q2", paper_key="d", relevance=2, db_path=self.db)
        s = stats(db_path=self.db)
        self.assertEqual(s["n_total"], 4)
        self.assertEqual(s["n_irrelevant"], 1)
        self.assertEqual(s["n_marginal"], 1)
        self.assertEqual(s["n_relevant"], 2)
        self.assertEqual(s["n_queries"], 2)
        # Top queries: q1 has 3, q2 has 1
        self.assertEqual(s["queries"][0][0], "q1")
        self.assertEqual(s["queries"][0][1], 3)

    def test_stats_per_query(self):
        add(query="q1", paper_key="a", relevance=0, db_path=self.db)
        add(query="q1", paper_key="b", relevance=1, db_path=self.db)
        s = stats(query="q1", db_path=self.db)
        self.assertEqual(s["n_total"], 2)
        self.assertEqual(s["n_irrelevant"], 1)
        self.assertEqual(s["n_marginal"], 1)
        self.assertEqual(s["n_relevant"], 0)
        self.assertEqual(s["n_queries"], 1)

    def test_bulk_add(self):
        items = [
            ("k1", "Title 1", 2, "hit"),
            ("k2", "Title 2", 1, "marginal"),
            ("k3", "Title 3", 0, "miss"),
        ]
        n_added, n_updated, n_skipped = add_bulk(
            query="bulk-q", items=items, db_path=self.db
        )
        self.assertEqual(n_added, 3)
        self.assertEqual(n_updated, 0)
        self.assertEqual(n_skipped, 0)
        s = stats(query="bulk-q", db_path=self.db)
        self.assertEqual(s["n_total"], 3)


class TestJudgeIO(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "test_io.sqlite"
        self.bench_json = Path(self.tmp.name) / "bench.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_import_bench_format(self):
        self.bench_json.write_text(
            json.dumps(BENCH_FIXTURE, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        n_added, n_updated, n_skipped = import_bench_format(
            self.bench_json, db_path=self.db
        )
        self.assertEqual(n_added, 4)  # 3 in q001 + 1 in q002
        self.assertEqual(n_updated, 0)
        self.assertEqual(n_skipped, 0)
        # Verify
        q1 = list_judgements(query="q001", db_path=self.db)
        self.assertEqual(len(q1), 3)
        # q001 has 1x rel=0, 1x rel=1, 1x rel=2
        s = stats(query="q001", db_path=self.db)
        self.assertEqual(s["n_irrelevant"], 1)
        self.assertEqual(s["n_marginal"], 1)
        self.assertEqual(s["n_relevant"], 1)

    def test_import_skips_invalid_relevance(self):
        bad = {
            "_meta": {"queries_covered": ["q"]},
            "labels": {
                "q": {
                    "k1": {"label": 5, "reason": "bad"},
                    "k2": {"label": 1, "reason": "ok"},
                }
            },
        }
        self.bench_json.write_text(json.dumps(bad), encoding="utf-8")
        n_added, n_updated, n_skipped = import_bench_format(
            self.bench_json, db_path=self.db
        )
        self.assertEqual(n_added, 1)  # only k2
        self.assertEqual(n_skipped, 1)

    def test_export_bench_format_round_trip(self):
        # Import fixture
        self.bench_json.write_text(
            json.dumps(BENCH_FIXTURE, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        import_bench_format(self.bench_json, db_path=self.db)
        # Re-export
        out = Path(self.tmp.name) / "round_trip.json"
        n_queries = export_bench_format(out, db_path=self.db)
        self.assertEqual(n_queries, 2)
        # Re-import to a new DB to verify shape
        new_db = Path(self.tmp.name) / "round_trip.sqlite"
        n_added, n_updated, n_skipped = import_bench_format(
            out, db_path=new_db
        )
        self.assertEqual(n_added, 4)
        self.assertEqual(n_updated, 0)

    def test_export_jsonl(self):
        add(query="q1", paper_key="k1", relevance=2, reason="hit",
            db_path=self.db)
        add(query="q1", paper_key="k2", relevance=0,
            db_path=self.db)
        out = Path(self.tmp.name) / "out.jsonl"
        n = export_jsonl(out, db_path=self.db)
        self.assertEqual(n, 2)
        # Each line is valid JSON
        lines = out.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 2)
        for line in lines:
            obj = json.loads(line)
            self.assertIn("query", obj)
            self.assertIn("paper_key", obj)
            self.assertIn("relevance", obj)
            self.assertIn("relevance_name", obj)


class TestJudgeCLI(unittest.TestCase):
    """Smoke-test that judge subcommands are wired into the CLI."""

    def test_judge_subcommands_registered(self):
        from click.testing import CliRunner
        from pa_cli.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["judge", "--help"])
        # Click's help may exit with code 0 even when there's an error in
        # help text rendering; the important thing is the subcommands show up
        output = result.output
        for sub in ("add", "bulk", "list", "stats", "export", "import"):
            self.assertIn(sub, output, f"subcommand {sub!r} not in judge --help output")

    def test_judge_add_via_cli(self):
        from click.testing import CliRunner
        from pa_cli.cli import main
        with tempfile.TemporaryDirectory() as tmpdir:
            db = Path(tmpdir) / "cli_test.sqlite"
            runner = CliRunner()
            result = runner.invoke(main, [
                "judge", "add",
                "--query", "test-q",
                "--key", "doi:10.123/abc",
                "--relevance", "2",
                "--reason", "cli smoke test",
                "--db", str(db),
            ])
            self.assertEqual(result.exit_code, 0, f"CLI failed: {result.output}")
            self.assertIn("added id=1", result.output)

    def test_judge_bulk_via_cli(self):
        from click.testing import CliRunner
        from pa_cli.cli import main
        with tempfile.TemporaryDirectory() as tmpdir:
            db = Path(tmpdir) / "cli_bulk.sqlite"
            # Use the demo bib
            bib = ROOT / "test_output" / "_demo_refs.bib"
            runner = CliRunner()
            result = runner.invoke(main, [
                "judge", "bulk", str(bib),
                "--query", "cli-bulk-test",
                "--relevance", "1",
                "--db", str(db),
                "--quiet",
            ])
            self.assertEqual(result.exit_code, 0, f"CLI failed: {result.output}")
            self.assertIn("added=3", result.output)

    def test_judge_stats_via_cli(self):
        from click.testing import CliRunner
        from pa_cli.cli import main
        with tempfile.TemporaryDirectory() as tmpdir:
            db = Path(tmpdir) / "cli_stats.sqlite"
            # Seed
            from pa_cli.judge import add
            add(query="stats-q", paper_key="k1", relevance=2, db_path=db)
            add(query="stats-q", paper_key="k2", relevance=1, db_path=db)
            runner = CliRunner()
            result = runner.invoke(main, [
                "judge", "stats",
                "--query", "stats-q",
                "--db", str(db),
            ])
            self.assertEqual(result.exit_code, 0)
            self.assertIn("Total judgements: 2", result.output)
            self.assertIn("relevant   (2): 1", result.output)
            self.assertIn("marginal   (1): 1", result.output)


if __name__ == "__main__":
    print(f"Using pa_cli from: {ROOT}")
    print(f"Default DB: {DEFAULT_DB}")
    print(f"Relevance scale: {RELEVANCE_LABELS}")
    print()
    unittest.main(verbosity=2)
