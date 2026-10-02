"""Unit and integration tests for M5 measured evaluation, calibration, and prediction joins."""
import json
import sqlite3
import unittest
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from click.testing import CliRunner

from pa_cli.cli import main
from pa_cli.evidence import _hash
from pa_cli.jev_eval_join import (
    brier_score,
    evaluate_run,
    load_predictions_from_db,
    load_predictions_from_json,
    wilson_score_interval,
)
from pa_cli.jev_evaluation import APP_ID as EVAL_APP_ID
from pa_cli.shadow import APP_ID as SHADOW_APP_ID


class TestJevEvalJoin(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_wilson_interval_bounds_and_properties(self):
        low, high = wilson_score_interval(0, 0)
        self.assertEqual((low, high), (0.0, 0.0))

        # 5 out of 10
        low, high = wilson_score_interval(5, 10, confidence=0.95)
        self.assertAlmostEqual(low, 0.2366, places=2)
        self.assertAlmostEqual(high, 0.7634, places=2)
        self.assertTrue(0.0 <= low <= 0.5 <= high <= 1.0)

        # 0 out of 20
        low, high = wilson_score_interval(0, 20, confidence=0.95)
        self.assertEqual(low, 0.0)
        self.assertLess(high, 0.20)

        # 20 out of 20
        low, high = wilson_score_interval(20, 20, confidence=0.95)
        self.assertGreater(low, 0.80)
        self.assertEqual(high, 1.0)

    def test_brier_score(self):
        self.assertIsNone(brier_score([], []))
        self.assertEqual(brier_score([1.0, 0.0], [1, 0]), 0.0)
        self.assertEqual(brier_score([0.0, 1.0], [1, 0]), 1.0)
        self.assertEqual(brier_score([0.5, 0.5], [1, 0]), 0.25)

    def _create_mock_eval_db(self, path: Path):
        with closing(sqlite3.connect(path)) as conn:
            conn.executescript(f"""
            PRAGMA application_id={EVAL_APP_ID};
            CREATE TABLE cases (
                case_id TEXT PRIMARY KEY,
                study_id TEXT NOT NULL,
                split TEXT NOT NULL,
                details TEXT NOT NULL
            );
            CREATE TABLE exposures (
                event_id TEXT PRIMARY KEY,
                study_id TEXT NOT NULL,
                operator TEXT NOT NULL,
                evidence_reference TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE judgment_freeze (
                singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                operator TEXT NOT NULL,
                reference TEXT NOT NULL,
                created_at TEXT NOT NULL,
                snapshot TEXT NOT NULL,
                snapshot_hash TEXT NOT NULL
            );
            """)

            # Cases:
            # 1. calib-1 (pos, study-1)
            # 2. calib-2 (neg, study-2)
            # 3. holdout-1 (pos, study-3)
            # 4. holdout-2 (neg, study-4)
            # 5. holdout-3 (abstain, study-5)
            # 6. holdout-4 (pos, study-6, exposed!)
            snapshot = [
                {
                    "case_id": "case-c1", "study_id": "study-1", "split": "calibration",
                    "judgments": [{"outcome": "label", "label": "yes"}], "resolution": None
                },
                {
                    "case_id": "case-c2", "study_id": "study-2", "split": "calibration",
                    "judgments": [{"outcome": "label", "label": "no"}], "resolution": None
                },
                {
                    "case_id": "case-h1", "study_id": "study-3", "split": "holdout",
                    "judgments": [{"outcome": "label", "label": "yes"}], "resolution": None
                },
                {
                    "case_id": "case-h2", "study_id": "study-4", "split": "holdout",
                    "judgments": [{"outcome": "label", "label": "no"}], "resolution": None
                },
                {
                    "case_id": "case-h3", "study_id": "study-5", "split": "holdout",
                    "judgments": [{"outcome": "abstain", "label": None}], "resolution": None
                },
                {
                    "case_id": "case-h4", "study_id": "study-6", "split": "holdout",
                    "judgments": [{"outcome": "label", "label": "yes"}], "resolution": None
                },
            ]

            # Record exposure for study-6 (must exclude case-h4 from holdout)
            conn.execute(
                "INSERT INTO exposures VALUES (?,?,?,?,?)",
                ("exp-1", "study-6", "op", "leak_incident", "2026-09-30T00:00:00Z")
            )

            conn.execute(
                "INSERT INTO judgment_freeze VALUES (1,?,?,?,?,?)",
                ("op", "evidence_ref", "2026-09-30T00:00:00Z", json.dumps(snapshot), _hash(snapshot))
            )
            conn.commit()

    def _create_mock_shadow_db(self, path: Path):
        with closing(sqlite3.connect(path)) as conn:
            conn.executescript(f"""
            PRAGMA application_id={SHADOW_APP_ID};
            CREATE TABLE requests (
                request_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                artifact_sha256 TEXT NOT NULL,
                packet_json TEXT NOT NULL,
                provenance_json TEXT NOT NULL,
                rubric_json TEXT NOT NULL,
                provider_json TEXT NOT NULL
            );
            CREATE TABLE suggestions (
                request_id TEXT PRIMARY KEY,
                answer_json TEXT NOT NULL,
                synthetic INTEGER NOT NULL
            );
            """)

    def test_evaluate_run_with_synthetic_protection(self):
        eval_db = self.root / "eval.sqlite"
        self._create_mock_eval_db(eval_db)

        preds = {
            "predictions": [
                {"case_id": "case-c1", "p_yes": 0.90, "is_synthetic": True},
                {"case_id": "case-c2", "p_yes": 0.10, "is_synthetic": True},
                {"case_id": "case-h1", "p_yes": 0.85, "is_synthetic": True},
                {"case_id": "case-h2", "p_yes": 0.15, "is_synthetic": True},
                {"case_id": "case-h3", "p_yes": 0.70, "is_synthetic": True},
                {"case_id": "case-h4", "p_yes": 0.95, "is_synthetic": True},
            ]
        }
        pred_file = self.root / "preds.json"
        pred_file.write_text(json.dumps(preds), encoding="utf-8")

        # 1. Rejects synthetic without explicit flag
        with self.assertRaises(ValueError) as ctx:
            evaluate_run(eval_db, pred_file, allow_synthetic=False)
        self.assertIn("synthetic fixtures", str(ctx.exception).lower())

        # 2. Succeeds with explicit allow_synthetic=True
        report = evaluate_run(eval_db, pred_file, allow_synthetic=True, target_fnr=0.10)
        self.assertTrue(report["is_synthetic_fixture"])
        self.assertIn("WARNING: Evaluated against synthetic fixture", report["notice"])

        # Check holdout accounting
        acc = report["holdout_accounting"]
        self.assertEqual(acc["total_holdout_cases"], 4)
        self.assertEqual(acc["exposed_cases_excluded"], 1)  # case-h4 excluded
        self.assertEqual(acc["human_abstentions"], 1)       # case-h3 abstained
        self.assertEqual(acc["missing_predictions"], 0)
        self.assertEqual(acc["evaluated_cases"], 2)         # case-h1 and case-h2

        # Confusion matrix: case-h1 (pos, pred 0.85 -> TP), case-h2 (neg, pred 0.15 -> TN)
        cm = report["confusion_matrix"]
        self.assertEqual(cm["true_positives"], 1)
        self.assertEqual(cm["true_negatives"], 1)
        self.assertEqual(cm["false_positives"], 0)
        self.assertEqual(cm["false_negatives"], 0)

        # Performance metrics
        perf = report["performance_metrics"]
        self.assertEqual(perf["accuracy"], 1.0)
        self.assertEqual(perf["precision"], 1.0)
        self.assertEqual(perf["recall"], 1.0)
        self.assertEqual(perf["error_rate"], 0.0)
        self.assertEqual(len(perf["error_rate_ci_95"]), 2)
        self.assertLessEqual(perf["brier_score"], 0.05)

    def test_cli_invocation(self):
        eval_db = self.root / "eval.sqlite"
        self._create_mock_eval_db(eval_db)

        preds = {
            "predictions": [
                {"case_id": "case-c1", "p_yes": 0.90, "is_synthetic": True},
                {"case_id": "case-c2", "p_yes": 0.10, "is_synthetic": True},
                {"case_id": "case-h1", "p_yes": 0.85, "is_synthetic": True},
                {"case_id": "case-h2", "p_yes": 0.15, "is_synthetic": True},
            ]
        }
        pred_file = self.root / "preds.json"
        pred_file.write_text(json.dumps(preds), encoding="utf-8")

        with patch("pa_cli.keys.load_env_into_environ", return_value=0), patch("pa_cli.keys.cmd_remind", return_value=0):
            res = CliRunner().invoke(main, [
                "jev", "evaluation-score",
                "--eval-db", str(eval_db),
                "--pred", str(pred_file),
                "--allow-synthetic",
            ])
            self.assertEqual(res.exit_code, 0, res.output)
            out_json = json.loads(res.output)
            self.assertEqual(out_json["schema_version"], "m5-evaluation-report-1")
            self.assertIn("report_hash", out_json)

    def test_extract_p_yes_semantic_correctness(self):
        from pa_cli.jev_eval_join import extract_p_yes
        # Positive classes
        self.assertEqual(extract_p_yes({"probabilities": {"included": 0.01, "excluded": 0.99}}), 0.01)
        self.assertEqual(extract_p_yes({"probabilities": {"yes": 0.85, "no": 0.15}}), 0.85)
        self.assertEqual(extract_p_yes({"probabilities": {"relevant": 0.70}}), 0.70)
        # Negative classes only
        self.assertEqual(extract_p_yes({"probabilities": {"excluded": 0.99}}), 0.01)
        self.assertEqual(extract_p_yes({"probabilities": {"no": 0.80}}), 0.20)
        # Explicit p_yes override
        self.assertEqual(extract_p_yes({"p_yes": 0.42, "probabilities": {"included": 0.99}}), 0.42)
        # Unrecognized classes must raise ValueError, NOT take max
        with self.assertRaises(ValueError):
            extract_p_yes({"probabilities": {"cat": 0.9, "dog": 0.1}})

    def test_json_shapes_and_case_id_keyed(self):
        from pa_cli.jev_eval_join import load_predictions_from_json
        # 1. Bare list
        p1 = self.root / "bare_list.json"
        p1.write_text(json.dumps([
            {"case_id": "c1", "p_yes": 0.9},
            {"case_id": "c2", "p_yes": 0.1},
        ]), encoding="utf-8")
        res1 = load_predictions_from_json(p1)
        self.assertEqual(set(res1.keys()), {"c1", "c2"})
        self.assertEqual(res1["c1"]["p_yes"], 0.9)

        # 2. Case_id keyed dict
        p2 = self.root / "keyed_dict.json"
        p2.write_text(json.dumps({
            "c1": {"p_yes": 0.9},
            "c2": {"probabilities": {"included": 0.05, "excluded": 0.95}},
        }), encoding="utf-8")
        res2 = load_predictions_from_json(p2)
        self.assertEqual(set(res2.keys()), {"c1", "c2"})
        self.assertEqual(res2["c1"]["p_yes"], 0.9)
        self.assertEqual(res2["c2"]["p_yes"], 0.05)

    def test_real_lifecycle_freeze_and_evaluate(self):
        import test_jev_evaluation as fixture
        from pa_cli.jev_evaluation import assign_review
        from pa_cli.jev_judgments import submit_judgment, freeze_judgments
        from pa_cli.jev_eval_join import evaluate_run

        # Setup real evaluation database using formal fixture
        fix = fixture.JevEvaluationTests()
        fix.setUp()
        eval_db = fix.evaluation

        # Assign and submit judgments for real cases
        a1 = assign_review(eval_db, fix.review_id, reviewer='r1', operator='op', no_prior_exposure=True)['assignment_id']
        submit_judgment(eval_db, fix._entry('s1', a1, reviewer='r1', label='yes'), human_confirmed=True)

        # Freeze using formal freeze_judgments interface (creates real judgment_freeze with singleton=1)
        freeze_res = freeze_judgments(eval_db, operator='op', evidence_reference='ref1', human_review_confirmed=True)
        self.assertIn('snapshot_hash', freeze_res)

        # Predictions file targeting the real frozen case
        pred_file = self.root / "real_pred.json"
        pred_file.write_text(json.dumps([
            {"case_id": "synthetic-case-1", "p_yes": 0.95, "is_synthetic": True}
        ]), encoding="utf-8")

        # Now run evaluate_run on the real frozen database!
        report = evaluate_run(eval_db, pred_file, allow_synthetic=True)
        self.assertEqual(report["schema_version"], "m5-evaluation-report-1")
        self.assertIn("report_hash", report)


if __name__ == "__main__":
    unittest.main()
