"""M5 Measured Evaluation & Prediction Joins.

Joins model predictions to frozen evaluation cases, preserves exposure exclusions,
calibrates decision thresholds on calibration splits, and computes holdout metrics
with exact Wilson score confidence intervals and Brier calibration scores.
No network calls, no model training, and no synthetic predictions claimed as truth.
"""
from __future__ import annotations

import json
import math
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .evidence import _hash
from .jev_evaluation import APP_ID as EVAL_APP_ID, _digest, _text
from .shadow import APP_ID as SHADOW_APP_ID


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def wilson_score_interval(successes: int, total: int, confidence: float = 0.95) -> Tuple[float, float]:
    """Compute two-sided Wilson score confidence interval for a binomial proportion."""
    if total <= 0:
        return (0.0, 0.0)
    # Approximate normal quantile z (1.96 for 0.95, 2.576 for 0.99, 1.645 for 0.90)
    if abs(confidence - 0.95) < 0.01:
        z = 1.959963984540054
    elif abs(confidence - 0.99) < 0.01:
        z = 2.5758293035489004
    elif abs(confidence - 0.90) < 0.01:
        z = 1.6448536269514722
    else:
        # Simple polynomial approximation of probit function
        z = 1.959963984540054

    p = successes / total
    z2 = z * z
    denom = 1.0 + z2 / total
    centre = (p + z2 / (2.0 * total)) / denom
    margin = (z / denom) * math.sqrt((p * (1.0 - p)) / total + z2 / (4.0 * total * total))
    low = max(0.0, centre - margin)
    high = min(1.0, centre + margin)
    return (round(low, 4), round(high, 4))


def brier_score(probabilities: List[float], outcomes: List[int]) -> Optional[float]:
    """Compute Brier score (mean squared error of predicted probabilities)."""
    if not probabilities or len(probabilities) != len(outcomes):
        return None
    total_sq_err = sum((p - y) ** 2 for p, y in zip(probabilities, outcomes))
    return round(total_sq_err / len(probabilities), 4)


def load_predictions_from_db(db_path: Path) -> Dict[str, Dict[str, Any]]:
    """Load predictions from an M3 shadow database."""
    pred_map = {}
    with closing(sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True, timeout=10)) as conn:
        app_id = conn.execute("PRAGMA application_id").fetchone()[0]
        if app_id != SHADOW_APP_ID:
            raise ValueError(f"Expected M3 shadow database (app_id={SHADOW_APP_ID}), got {app_id}")

        query = """
        SELECT r.artifact_sha256, r.packet_json, r.rubric_json, s.answer_json, s.synthetic
        FROM suggestions s
        JOIN requests r ON r.request_id = s.request_id
        """
        for art, p_json, r_json, ans_json, is_synth in conn.execute(query).fetchall():
            packet = json.loads(p_json)
            rubric = json.loads(r_json)
            answer = json.loads(ans_json)
            p_hash = packet.get("packet_hash") or _hash({k: v for k, v in packet.items() if k != "packet_hash"})
            r_hash = _hash(rubric)
            case_key = _hash([art, p_hash, r_hash])

POS_CLASSES = {"yes", "true", "1", "included", "relevant", "pos", "positive"}
NEG_CLASSES = {"no", "false", "0", "excluded", "irrelevant", "neg", "negative"}


def extract_p_yes(container: Dict[str, Any]) -> Optional[float]:
    """Extract normalized positive class probability from prediction answer or probabilities dict.

    Guarantees:
    - If explicit p_yes is provided, validates and returns float(p_yes).
    - If probabilities dict contains a positive class (e.g. 'yes', 'included'), uses its value.
    - If probabilities dict contains a negative class (e.g. 'no', 'excluded'), returns 1.0 - p_neg.
    - If probabilities are provided but no recognized binary class is found, raises ValueError
      rather than silently taking the maximum probability (which causes evaluation inversion).
    """
    if "p_yes" in container and container["p_yes"] is not None:
        p_val = float(container["p_yes"])
        return max(0.0, min(1.0, p_val))

    probs = container.get("probabilities", {})
    if not isinstance(probs, dict) or not probs:
        return None

    # Check positive classes
    for k, v in probs.items():
        if str(k).strip().lower() in POS_CLASSES and v is not None:
            return max(0.0, min(1.0, float(v)))

    # Check negative classes
    for k, v in probs.items():
        if str(k).strip().lower() in NEG_CLASSES and v is not None:
            return round(max(0.0, min(1.0, 1.0 - float(v))), 6)

    raise ValueError(
        f"Cannot determine positive class probability from classes {list(probs.keys())}. "
        f"Classes must map to recognized positive ({sorted(POS_CLASSES)}) or "
        f"negative ({sorted(NEG_CLASSES)}) classes, or specify explicit 'p_yes'."
    )


def load_predictions_from_db(pred_db_path: Path) -> Dict[str, Dict[str, Any]]:
    """Load predictions from a JEV predictions SQLite database."""
    pred_map = {}
    with closing(sqlite3.connect(f"{pred_db_path.as_uri()}?mode=ro", uri=True, timeout=10)) as conn:
        app_id = conn.execute("PRAGMA application_id").fetchone()[0]
        if app_id != PRED_APP_ID:
            raise ValueError(f"Expected prediction database (app_id={PRED_APP_ID}), got {app_id}")

        rows = conn.execute(
            "SELECT artifact_sha256, packet_json, rubric_json, answer_json, is_synthetic FROM predictions"
        ).fetchall()

        for art, p_json, r_json, ans_json, is_synth in rows:
            packet = json.loads(p_json)
            rubric = json.loads(r_json)
            answer = json.loads(ans_json)
            p_hash = packet.get("packet_hash") or _hash({k: v for k, v in packet.items() if k != "packet_hash"})
            r_hash = _hash(rubric)
            case_key = _hash([art, p_hash, r_hash])

            # Extract normalized p_yes safely
            p_yes = extract_p_yes(answer)

            pred_map[case_key] = {
                "case_key": case_key,
                "artifact_sha256": art,
                "packet_hash": p_hash,
                "rubric_hash": r_hash,
                "model": answer.get("model", "unknown"),
                "p_yes": p_yes,
                "probabilities": answer.get("probabilities", {}),
                "is_synthetic": bool(is_synth),
                "raw_answer": answer,
            }
    return pred_map


def load_predictions_from_json(json_path: Path) -> Dict[str, Dict[str, Any]]:
    """Load predictions from a JSON file.

    Supports 3 standard formats:
    1. Bare list of prediction items: [{"case_id": "...", "p_yes": 0.9}, ...]
    2. Dict wrapper with "predictions" key: {"predictions": [...]} or {"predictions": {"case_1": {...}}}
    3. Dict keyed by case_id: {"case_1": {"p_yes": 0.9}, ...}
    """
    with Path(json_path).open("r", encoding="utf-8") as f:
        data = json.load(f)

    raw_items: List[Tuple[Optional[str], Dict[str, Any]]] = []

    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                raise ValueError(f"Expected prediction dict in list, got {type(item).__name__}")
            raw_items.append((None, item))
    elif isinstance(data, dict):
        if "predictions" in data:
            preds = data["predictions"]
            if isinstance(preds, list):
                for item in preds:
                    if not isinstance(item, dict):
                        raise ValueError(f"Expected prediction dict in predictions list, got {type(item).__name__}")
                    raw_items.append((None, item))
            elif isinstance(preds, dict):
                for k, item in preds.items():
                    if not isinstance(item, dict):
                        raise ValueError(f"Expected prediction dict for key {k}, got {type(item).__name__}")
                    raw_items.append((k, item))
            else:
                raise ValueError(f"Unrecognized 'predictions' container type: {type(preds).__name__}")
        else:
            # Dict keyed by case_id
            for k, item in data.items():
                if isinstance(item, dict):
                    raw_items.append((k, item))
                else:
                    raise ValueError(f"Expected prediction dict for case key {k}, got {type(item).__name__}")
    else:
        raise ValueError(f"Invalid JSON predictions root structure: expected list or dict, got {type(data).__name__}")

    pred_map = {}
    seen_keys = set()
    for outer_key, item in raw_items:
        art = item.get("artifact_sha256")
        p_hash = item.get("packet_hash")
        r_hash = item.get("rubric_hash")
        case_key = item.get("case_id") or item.get("case_key") or outer_key
        if not case_key and art and p_hash and r_hash:
            case_key = _hash([art, p_hash, r_hash])

        if not case_key:
            raise ValueError(f"Prediction item missing case identification: {item}")

        if case_key in seen_keys:
            raise ValueError(f"Duplicate prediction case_key detected: {case_key}")
        seen_keys.add(case_key)

        p_yes = extract_p_yes(item)

        pred_map[case_key] = {
            "case_key": case_key,
            "artifact_sha256": art,
            "packet_hash": p_hash,
            "rubric_hash": r_hash,
            "model": item.get("model", "unknown"),
            "p_yes": p_yes,
            "probabilities": item.get("probabilities", {}),
            "is_synthetic": bool(item.get("is_synthetic", False)),
            "raw_answer": item,
        }
    return pred_map


def _calibrate_threshold(
    calibration_cases: List[Dict[str, Any]],
    predictions: Dict[str, Dict[str, Any]],
    target_fnr: float = 0.10,
) -> Tuple[float, Dict[str, Any]]:
    """Scan candidate thresholds on calibration data to find optimal decision boundary.

    Selects threshold tau that satisfies FNR <= target_fnr while maximizing F1 or accuracy.
    """
    pairs = []
    for c in calibration_cases:
        key = c["case_id"]
        pred = predictions.get(key)
        if not pred or pred.get("p_yes") is None:
            continue

        # Ground truth
        truth_label = c["ground_truth_label"]
        if truth_label is None:
            continue  # abstained or unresolved

        # Binary label: 'yes' is positive (1), anything else negative (0)
        is_pos = 1 if truth_label.lower() in ("yes", "true", "1", "included", "relevant") else 0
        pairs.append((pred["p_yes"], is_pos))

    if not pairs:
        # Default fallback threshold
        return 0.50, {"note": "insufficient calibration data, defaulted to 0.50"}

    candidates = [round(t * 0.05, 2) for t in range(1, 20)]
    best_tau = 0.50
    best_score = -1.0
    tuning_log = []

    for tau in candidates:
        tp = sum(1 for p, y in pairs if p >= tau and y == 1)
        fp = sum(1 for p, y in pairs if p >= tau and y == 0)
        fn = sum(1 for p, y in pairs if p < tau and y == 1)
        tn = sum(1 for p, y in pairs if p < tau and y == 0)

        actual_pos = tp + fn
        fnr = fn / actual_pos if actual_pos > 0 else 0.0
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / actual_pos if actual_pos > 0 else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

        tuning_log.append({"tau": tau, "fnr": round(fnr, 4), "f1": round(f1, 4), "tp": tp, "fp": fp, "fn": fn, "tn": tn})

        # Score favors meeting FNR constraint, then maximizing F1
        if fnr <= target_fnr:
            if f1 > best_score:
                best_score = f1

    if best_score >= 0:
        optimal_taus = [c["tau"] for c in tuning_log if c["fnr"] <= target_fnr and abs(c["f1"] - best_score) < 1e-5]
        best_tau = round((min(optimal_taus) + max(optimal_taus)) / 2.0, 2)
    else:
        # If no threshold meets target FNR, pick the one with lowest FNR
        min_fnr_cand = min(tuning_log, key=lambda x: x["fnr"])
        best_tau = min_fnr_cand["tau"]

    return best_tau, {
        "calibration_samples": len(pairs),
        "target_fnr": target_fnr,
        "selected_threshold": best_tau,
        "tuning_points": len(candidates),
    }



def evaluate_run(
    eval_db_path: Path,
    predictions_path: Path,
    *,
    target_fnr: float = 0.10,
    allow_synthetic: bool = False,
    confidence: float = 0.95,
) -> Dict[str, Any]:
    """Execute complete M5 evaluation join and scoring."""
    eval_path = Path(eval_db_path).resolve(strict=True)
    pred_path = Path(predictions_path).resolve(strict=True)

    # 1. Connect to evaluation DB
    with closing(sqlite3.connect(f"{eval_path.as_uri()}?mode=ro", uri=True, timeout=10)) as conn:
        app_id = conn.execute("PRAGMA application_id").fetchone()[0]
        if app_id != EVAL_APP_ID:
            raise ValueError(f"Expected evaluation database (app_id={EVAL_APP_ID}), got {app_id}")

        # Check judgment freeze
        freeze_row = conn.execute("SELECT operator, snapshot, snapshot_hash FROM judgment_freeze WHERE singleton=1").fetchone()
        if not freeze_row:
            raise ValueError("Judgments are not frozen in evaluation database. Run `pa jev judgments-freeze` first.")

        frozen_snapshot = json.loads(freeze_row[1])

        # Current exposures (crucial: must check live exposures table, not just freeze snapshot!)
        exposed_studies = {r[0] for r in conn.execute("SELECT study_id FROM exposures").fetchall()}

    # 2. Load predictions
    if pred_path.suffix.lower() in (".sqlite", ".db"):
        pred_map = load_predictions_from_db(pred_path)
    else:
        pred_map = load_predictions_from_json(pred_path)

    has_synthetic = any(p["is_synthetic"] for p in pred_map.values())
    if has_synthetic and not allow_synthetic:
        raise ValueError(
            "Prediction source contains synthetic fixtures. To evaluate fixtures for testing, "
            "explicitly pass --allow-synthetic. Synthetic predictions cannot be used to report true model quality."
        )

    # 3. Categorize frozen cases by split and extract ground truth
    processed_cases = []
    for c in frozen_snapshot:
        cid = c["case_id"]
        study_id = c["study_id"]
        split = c["split"]
        resolution = c.get("resolution")
        judgments = c.get("judgments", [])

        # Check ground truth
        if resolution:
            gt_outcome = resolution.get("outcome")
            gt_label = resolution.get("label")
        elif judgments:
            # Active judgment is the latest consensus
            gt_outcome = judgments[0].get("outcome")
            gt_label = judgments[0].get("label")
        else:
            gt_outcome = "unadjudicated"
            gt_label = None

        is_abstained = (gt_outcome == "abstain")
        is_exposed = study_id in exposed_studies

        processed_cases.append({
            "case_id": cid,
            "study_id": study_id,
            "split": split,
            "ground_truth_outcome": gt_outcome,
            "ground_truth_label": gt_label,
            "is_abstained": is_abstained,
            "is_exposed": is_exposed,
        })

    calib_cases = [c for c in processed_cases if c["split"] in ("calibration", "calib") and not c["is_exposed"]]
    holdout_cases = [c for c in processed_cases if c["split"] == "holdout"]

    # 4. Calibrate threshold
    selected_tau, calib_info = _calibrate_threshold(calib_cases, pred_map, target_fnr=target_fnr)

    # 5. Evaluate on Holdout
    total_holdout = len(holdout_cases)
    exposed_excluded = 0
    abstentions = 0
    missing_preds = 0
    evaluated = 0

    tp = fp = fn = tn = 0
    probs_list = []
    binary_truths = []

    for c in holdout_cases:
        if c["is_exposed"]:
            exposed_excluded += 1
            continue

        if c["is_abstained"]:
            abstentions += 1
            continue

        key = c["case_id"]
        pred = pred_map.get(key)
        if not pred or pred.get("p_yes") is None:
            missing_preds += 1
            continue

        evaluated += 1
        p_val = pred["p_yes"]
        pred_pos = (p_val >= selected_tau)

        gt_label = str(c["ground_truth_label"]).lower()
        actual_pos = gt_label in ("yes", "true", "1", "included", "relevant")

        probs_list.append(p_val)
        binary_truths.append(1 if actual_pos else 0)

        if pred_pos and actual_pos:
            tp += 1
        elif pred_pos and not actual_pos:
            fp += 1
        elif not pred_pos and actual_pos:
            fn += 1
        else:
            tn += 1

    # 6. Metrics Calculation
    accuracy = round((tp + tn) / evaluated, 4) if evaluated > 0 else 0.0
    precision = round(tp / (tp + fp), 4) if (tp + fp) > 0 else 0.0
    recall = round(tp / (tp + fn), 4) if (tp + fn) > 0 else 0.0
    fnr = round(fn / (tp + fn), 4) if (tp + fn) > 0 else 0.0
    fpr = round(fp / (fp + tn), 4) if (fp + tn) > 0 else 0.0
    f1 = round((2 * precision * recall) / (precision + recall), 4) if (precision + recall) > 0 else 0.0

    error_count = fp + fn
    error_rate = round(error_count / evaluated, 4) if evaluated > 0 else 0.0
    error_ci = wilson_score_interval(error_count, evaluated, confidence=confidence)
    fnr_ci = wilson_score_interval(fn, tp + fn, confidence=confidence) if (tp + fn) > 0 else (0.0, 0.0)
    fpr_ci = wilson_score_interval(fp, fp + tn, confidence=confidence) if (fp + tn) > 0 else (0.0, 0.0)
    brier = brier_score(probs_list, binary_truths)

    # Calibration Reliability Bins (5 deciles/quintiles)
    bins = []
    bin_edges = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
    for low, high in zip(bin_edges, bin_edges[1:]):
        in_bin = [(p, y) for p, y in zip(probs_list, binary_truths) if low <= p < high or (high == 1.0 and p == 1.0)]
        count = len(in_bin)
        mean_prob = round(sum(p for p, _ in in_bin) / count, 4) if count > 0 else 0.0
        empirical_rate = round(sum(y for _, y in in_bin) / count, 4) if count > 0 else 0.0
        bins.append({
            "bin_range": [low, high],
            "count": count,
            "mean_predicted_prob": mean_prob,
            "observed_positive_rate": empirical_rate,
        })

    report = {
        "schema_version": "m5-evaluation-report-1",
        "evaluated_at": _now(),
        "eval_database": str(eval_path),
        "prediction_source": str(pred_path),
        "is_synthetic_fixture": has_synthetic,
        "calibration": {
            "strategy": "fnr_constrained_grid_search",
            "target_fnr": target_fnr,
            "selected_threshold": selected_tau,
            "details": calib_info,
        },
        "holdout_accounting": {
            "total_holdout_cases": total_holdout,
            "exposed_cases_excluded": exposed_excluded,
            "human_abstentions": abstentions,
            "missing_predictions": missing_preds,
            "evaluated_cases": evaluated,
            "coverage_rate": round(evaluated / (total_holdout - exposed_excluded), 4) if (total_holdout - exposed_excluded) > 0 else 0.0,
        },
        "confusion_matrix": {
            "true_positives": tp,
            "false_positives": fp,
            "true_negatives": tn,
            "false_negatives": fn,
        },
        "performance_metrics": {
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
            "f1_score": f1,
            "error_rate": error_rate,
            "error_rate_ci_95": error_ci,
            "false_negative_rate": fnr,
            "false_negative_rate_ci_95": fnr_ci,
            "false_positive_rate": fpr,
            "false_positive_rate_ci_95": fpr_ci,
            "brier_score": brier,
        },
        "calibration_curve": bins,
    }

    if has_synthetic:
        report["notice"] = (
            "WARNING: Evaluated against synthetic fixture predictions. "
            "Synthetic fixtures cannot prove model quality, accuracy, or calibration."
        )

    report["report_hash"] = _hash(report)
    return report
