"""Statistical report consistency and heuristic verification (pa stats-check).

ROADMAP [P1-24] implementation:
Pure offline heuristic statistical verification (analogous to statcheck)
for parsing reported test statistics (t, F, chi2, z, r) and testing mathematical
consistency against reported p-values and degrees of freedom.

100% offline-first; pure Python mathematical CDFs (incomplete beta and gamma
via continued fractions) with machine-precision accuracy. Zero external API cost.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, List, Optional, Tuple


# ==============================================================================
# Pure Python High-Precision Special Functions
# ==============================================================================

def _betacf(a: float, b: float, x: float, max_iter: int = 200, eps: float = 1e-14) -> float:
    """Continued fraction for incomplete beta using modified Lentz's method."""
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < 1e-30:
        d = 1e-30
    d = 1.0 / d
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        # Even step
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + aa / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        h *= d * c

        # Odd step
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + aa / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        del_h = d * c
        h *= del_h
        if abs(del_h - 1.0) < eps:
            break
    return h


def _ibeta(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta function I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    factor = math.exp(
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
        + a * math.log(x) + b * math.log(1.0 - x)
    )
    if x < (a + 1.0) / (a + b + 2.0):
        return factor * _betacf(a, b, x) / a
    else:
        return 1.0 - factor * _betacf(b, a, 1.0 - x) / b


def _gammaser(a: float, x: float, max_iter: int = 200, eps: float = 1e-14) -> float:
    """Series expansion for lower incomplete gamma P(a, x)."""
    if x <= 0.0:
        return 0.0
    ap = a
    total = 1.0 / a
    delta = total
    for _ in range(1, max_iter + 1):
        ap += 1.0
        delta = delta * x / ap
        total += delta
        if abs(delta) < abs(total) * eps:
            break
    return total * math.exp(-x + a * math.log(x) - math.lgamma(a))


def _gammacf(a: float, x: float, max_iter: int = 200, eps: float = 1e-14) -> float:
    """Continued fraction for upper incomplete gamma Q(a, x) = 1 - P(a, x)."""
    b = x + 1.0 - a
    c = 1.0 / 1e-30
    d = 1.0 / b
    h = d
    for i in range(1, max_iter + 1):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < 1e-30:
            d = 1e-30
        c = b + an / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        del_h = d * c
        h *= del_h
        if abs(del_h - 1.0) < eps:
            break
    return math.exp(-x + a * math.log(x) - math.lgamma(a)) * h


def _igamma_q(a: float, x: float) -> float:
    """Upper regularized incomplete gamma Q(a, x) = 1 - P(a, x)."""
    if x <= 0.0:
        return 1.0
    if x < a + 1.0:
        return 1.0 - _gammaser(a, x)
    else:
        return _gammacf(a, x)


def compute_p_value(
    stat_type: str,
    stat_val: float,
    df1: Optional[float] = None,
    df2: Optional[float] = None,
) -> Tuple[float, float]:
    """Compute (two_tailed_p, one_tailed_p) for a given test statistic."""
    st = stat_type.lower()
    if st == "t":
        if df1 is None or df1 <= 0:
            return 1.0, 0.5
        x = df1 / (df1 + stat_val * stat_val)
        two_t = _ibeta(df1 / 2.0, 0.5, x)
        return two_t, two_t / 2.0

    elif st in ("f", "anova"):
        if stat_val <= 0 or df1 is None or df2 is None or df1 <= 0 or df2 <= 0:
            return 1.0, 1.0
        x = df2 / (df2 + df1 * stat_val)
        p = _ibeta(df2 / 2.0, df1 / 2.0, x)
        return p, p

    elif st in ("chi2", "χ2", "chi^2", "chisq", "chi-square"):
        if stat_val <= 0 or df1 is None or df1 <= 0:
            return 1.0, 1.0
        p = _igamma_q(df1 / 2.0, stat_val / 2.0)
        return p, p

    elif st == "z":
        z_abs = abs(stat_val)
        two_t = math.erfc(z_abs / math.sqrt(2.0))
        return two_t, two_t / 2.0

    elif st == "r":
        if abs(stat_val) >= 1.0:
            return 0.0, 0.0
        if df1 is None or df1 <= 0:
            return 1.0, 0.5
        denom = 1.0 - stat_val * stat_val
        if denom <= 0:
            return 0.0, 0.0
        t_val = stat_val * math.sqrt(df1 / denom)
        x = df1 / (df1 + t_val * t_val)
        two_t = _ibeta(df1 / 2.0, 0.5, x)
        return two_t, two_t / 2.0

    raise ValueError(f"Unsupported statistical test type: {stat_type}")


# ==============================================================================
# Data Structures
# ==============================================================================

@dataclass
class StatsCheckItem:
    """Represents a single parsed statistical test and its verification result."""
    stat_type: str
    stat_value: float
    df1: Optional[float]
    df2: Optional[float]
    p_reported_str: str
    p_reported: float
    p_operator: str
    p_computed: float
    p_computed_one_tailed: float
    is_consistent: bool
    is_decision_error: bool
    is_consistent_one_tailed: bool
    discrepancy: float
    status: str  # "consistent", "inconsistent", "decision_error"
    explanation: str
    raw_text: str
    context: str
    source: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StatsCheckSummary:
    """Summary of statistical verification across a document or corpus."""
    total_tests: int
    consistent_count: int
    inconsistent_count: int
    decision_error_count: int
    one_tailed_match_count: int
    consistency_rate: Optional[float]
    items: list[StatsCheckItem]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_tests": self.total_tests,
            "consistent_count": self.consistent_count,
            "inconsistent_count": self.inconsistent_count,
            "decision_error_count": self.decision_error_count,
            "one_tailed_match_count": self.one_tailed_match_count,
            "consistency_rate": round(self.consistency_rate, 4) if self.consistency_rate is not None else None,
            "items": [item.to_dict() for item in self.items],
        }


# ==============================================================================
# Consistency Checking Logic
# ==============================================================================

def check_p_consistency(
    p_rep_str: str,
    p_op: str,
    p_comp_two: float,
    p_comp_one: float,
    alpha: float = 0.05,
) -> Tuple[bool, bool, bool, str]:
    """Evaluate whether reported p-value matches computed p-value within rounding."""
    try:
        p_rep = float(p_rep_str)
    except ValueError:
        return False, False, False, "Invalid reported p-value format"

    # Determine decimal rounding tolerance
    if "." in p_rep_str:
        decimals = len(p_rep_str.split(".")[1])
    else:
        decimals = 0
    margin = 0.5 * (10 ** (-decimals)) if decimals > 0 else 0.05

    # Check two-tailed consistency
    if p_op in ("=", "=="):
        if p_rep == 0.0:
            consistent_two = p_comp_two < 0.001
        else:
            consistent_two = abs(p_comp_two - p_rep) <= margin
    elif p_op in ("<", "<=", "≤"):
        if p_op == "<":
            consistent_two = p_comp_two < p_rep
        else:
            consistent_two = p_comp_two <= p_rep
    elif p_op in (">", ">=", "≥"):
        if p_op == ">":
            consistent_two = p_comp_two > p_rep
        else:
            consistent_two = p_comp_two >= p_rep
    else:
        consistent_two = False

    # Check one-tailed consistency
    if p_op in ("=", "=="):
        if p_rep == 0.0:
            consistent_one = p_comp_one < 0.001
        else:
            consistent_one = abs(p_comp_one - p_rep) <= margin
    elif p_op in ("<", "<=", "≤"):
        if p_op == "<":
            consistent_one = p_comp_one < p_rep
        else:
            consistent_one = p_comp_one <= p_rep
    elif p_op in (">", ">=", "≥"):
        if p_op == ">":
            consistent_one = p_comp_one > p_rep
        else:
            consistent_one = p_comp_one >= p_rep
    else:
        consistent_one = False

    # Check Decision Error (flips statistical significance across alpha)
    # Did author claim significance at alpha?
    if p_op in ("<", "<=", "≤"):
        claimed_sig = p_rep <= alpha
    elif p_op in (">", ">=", "≥"):
        claimed_sig = False if p_rep >= alpha else (p_rep < alpha)
    else:
        claimed_sig = p_rep < alpha

    actual_sig = p_comp_two < alpha
    is_decision_error = (claimed_sig != actual_sig) and not consistent_two

    # Explanation message
    if consistent_two:
        explanation = f"Consistent within rounding tolerance (+/-{margin:.4g})"
    elif is_decision_error:
        tail_note = f" (Note: matches one-tailed test p = {p_comp_one:.4f})" if consistent_one else ""
        if claimed_sig and not actual_sig:
            explanation = (
                f"DECISION ERROR: Reported significant at p {p_op} {p_rep_str}, "
                f"but true computed two-tailed p = {p_comp_two:.4f} is non-significant (>= {alpha}){tail_note}"
            )
        else:
            explanation = (
                f"DECISION ERROR: Reported non-significant at p {p_op} {p_rep_str}, "
                f"but true computed two-tailed p = {p_comp_two:.4f} is significant (< {alpha}){tail_note}"
            )
    elif consistent_one and not consistent_two:
        explanation = f"Inconsistent for two-tailed test, but matches one-tailed test (p = {p_comp_one:.4f})"
    else:
        explanation = (
            f"Inconsistent: Reported p {p_op} {p_rep_str}, "
            f"computed two-tailed p = {p_comp_two:.4f}"
        )

    return consistent_two, is_decision_error, consistent_one, explanation


# ==============================================================================
# Text Parsing & Extraction Engine
# ==============================================================================

def normalize_stats_text(text: str) -> str:
    """Normalize full-width punctuation, Unicode math symbols, and minus signs."""
    t = text.replace("（", "(").replace("）", ")")
    t = t.replace("【", "[").replace("】", "]")
    t = t.replace("［", "[").replace("］", "]")
    t = t.replace("，", ",").replace("＝", "=")
    t = t.replace("：", ":").replace("；", ";")
    t = t.replace("−", "-").replace("–", "-").replace("—", "-")
    t = t.replace("＜", "<").replace("＞", ">")
    t = t.replace("≤", "<=").replace("≥", ">=")
    # Normalize italic math letters (t, F, z, r, p)
    t = t.replace("𝑡", "t").replace("𝑇", "T")
    t = t.replace("𝐹", "F").replace("𝑓", "f")
    t = t.replace("𝑧", "z").replace("𝑍", "Z")
    t = t.replace("𝑟", "r").replace("𝑅", "R")
    t = t.replace("𝑝", "p").replace("𝑃", "P")
    t = t.replace("χ", "chi").replace("Χ", "chi").replace("²", "2")
    return t


def extract_stats_from_text(
    text: str,
    source: str = "",
    alpha: float = 0.05,
) -> list[StatsCheckItem]:
    """Parse text and extract all reported statistical test expressions."""
    normalized = normalize_stats_text(text)
    items: list[StatsCheckItem] = []

    # Regex components
    # p-value component: e.g. ", p = .023" or " p < 0.001" or "; p <= .05"
    p_comp_pattern = r"(?:[,\s;]+)[pP]\s*([<>=]+)\s*(\d*\.?\d+(?:[eE][-+]?\d+)?)"

    # 1. t-test: t(df) = val, p ...
    t_regex = re.compile(
        r"\b[tT]\s*[\(\[]\s*(\d+(?:\.\d+)?)\s*[\)\]]\s*([=><]+)\s*(-?\d+(?:\.\d+)?)"
        + p_comp_pattern
    )
    for m in t_regex.finditer(normalized):
        df_str, t_op, t_val_str, p_op, p_val_str = m.groups()
        try:
            df = float(df_str)
            t_val = float(t_val_str)
            p_comp_two, p_comp_one = compute_p_value("t", t_val, df1=df)
            cons, dec_err, cons_one, expl = check_p_consistency(
                p_val_str, p_op, p_comp_two, p_comp_one, alpha=alpha
            )
            start_pos = max(0, m.start() - 60)
            end_pos = min(len(text), m.end() + 60)
            context = text[start_pos:end_pos].strip().replace("\n", " ")
            status = "decision_error" if dec_err else ("consistent" if cons else "inconsistent")

            items.append(
                StatsCheckItem(
                    stat_type="t",
                    stat_value=t_val,
                    df1=df,
                    df2=None,
                    p_reported_str=p_val_str,
                    p_reported=float(p_val_str),
                    p_operator=p_op,
                    p_computed=round(p_comp_two, 5),
                    p_computed_one_tailed=round(p_comp_one, 5),
                    is_consistent=cons,
                    is_decision_error=dec_err,
                    is_consistent_one_tailed=cons_one,
                    discrepancy=round(p_comp_two - float(p_val_str), 5),
                    status=status,
                    explanation=expl,
                    raw_text=m.group(0),
                    context=context,
                    source=source,
                )
            )
        except Exception:
            continue

    # 2. F-test: F(df1, df2) = val, p ...
    f_regex = re.compile(
        r"\b[fF]\s*[\(\[]\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*[\)\]]\s*([=><]+)\s*(-?\d+(?:\.\d+)?)"
        + p_comp_pattern
    )
    for m in f_regex.finditer(normalized):
        df1_str, df2_str, f_op, f_val_str, p_op, p_val_str = m.groups()
        try:
            df1 = float(df1_str)
            df2 = float(df2_str)
            f_val = float(f_val_str)
            p_comp_two, p_comp_one = compute_p_value("f", f_val, df1=df1, df2=df2)
            cons, dec_err, cons_one, expl = check_p_consistency(
                p_val_str, p_op, p_comp_two, p_comp_one, alpha=alpha
            )
            start_pos = max(0, m.start() - 60)
            end_pos = min(len(text), m.end() + 60)
            context = text[start_pos:end_pos].strip().replace("\n", " ")
            status = "decision_error" if dec_err else ("consistent" if cons else "inconsistent")

            items.append(
                StatsCheckItem(
                    stat_type="F",
                    stat_value=f_val,
                    df1=df1,
                    df2=df2,
                    p_reported_str=p_val_str,
                    p_reported=float(p_val_str),
                    p_operator=p_op,
                    p_computed=round(p_comp_two, 5),
                    p_computed_one_tailed=round(p_comp_one, 5),
                    is_consistent=cons,
                    is_decision_error=dec_err,
                    is_consistent_one_tailed=cons_one,
                    discrepancy=round(p_comp_two - float(p_val_str), 5),
                    status=status,
                    explanation=expl,
                    raw_text=m.group(0),
                    context=context,
                    source=source,
                )
            )
        except Exception:
            continue

    # 3. Chi-square: chi2(df) = val, p ... or chi-square(df) = val, p ...
    chi_regex = re.compile(
        r"(?:chi2|chi[-_\s]*square|chi\^2)\s*[\(\[]\s*(\d+(?:\.\d+)?)\s*[\)\]]\s*([=><]+)\s*(-?\d+(?:\.\d+)?)"
        + p_comp_pattern,
        re.IGNORECASE,
    )
    for m in chi_regex.finditer(normalized):
        df_str, chi_op, chi_val_str, p_op, p_val_str = m.groups()
        try:
            df = float(df_str)
            chi_val = float(chi_val_str)
            p_comp_two, p_comp_one = compute_p_value("chi2", chi_val, df1=df)
            cons, dec_err, cons_one, expl = check_p_consistency(
                p_val_str, p_op, p_comp_two, p_comp_one, alpha=alpha
            )
            start_pos = max(0, m.start() - 60)
            end_pos = min(len(text), m.end() + 60)
            context = text[start_pos:end_pos].strip().replace("\n", " ")
            status = "decision_error" if dec_err else ("consistent" if cons else "inconsistent")

            items.append(
                StatsCheckItem(
                    stat_type="chi2",
                    stat_value=chi_val,
                    df1=df,
                    df2=None,
                    p_reported_str=p_val_str,
                    p_reported=float(p_val_str),
                    p_operator=p_op,
                    p_computed=round(p_comp_two, 5),
                    p_computed_one_tailed=round(p_comp_one, 5),
                    is_consistent=cons,
                    is_decision_error=dec_err,
                    is_consistent_one_tailed=cons_one,
                    discrepancy=round(p_comp_two - float(p_val_str), 5),
                    status=status,
                    explanation=expl,
                    raw_text=m.group(0),
                    context=context,
                    source=source,
                )
            )
        except Exception:
            continue

    # 4. z-test: z = val, p ...
    z_regex = re.compile(
        r"\b[zZ]\s*([=><]+)\s*(-?\d+(?:\.\d+)?)" + p_comp_pattern
    )
    for m in z_regex.finditer(normalized):
        z_op, z_val_str, p_op, p_val_str = m.groups()
        try:
            z_val = float(z_val_str)
            p_comp_two, p_comp_one = compute_p_value("z", z_val)
            cons, dec_err, cons_one, expl = check_p_consistency(
                p_val_str, p_op, p_comp_two, p_comp_one, alpha=alpha
            )
            start_pos = max(0, m.start() - 60)
            end_pos = min(len(text), m.end() + 60)
            context = text[start_pos:end_pos].strip().replace("\n", " ")
            status = "decision_error" if dec_err else ("consistent" if cons else "inconsistent")

            items.append(
                StatsCheckItem(
                    stat_type="z",
                    stat_value=z_val,
                    df1=None,
                    df2=None,
                    p_reported_str=p_val_str,
                    p_reported=float(p_val_str),
                    p_operator=p_op,
                    p_computed=round(p_comp_two, 5),
                    p_computed_one_tailed=round(p_comp_one, 5),
                    is_consistent=cons,
                    is_decision_error=dec_err,
                    is_consistent_one_tailed=cons_one,
                    discrepancy=round(p_comp_two - float(p_val_str), 5),
                    status=status,
                    explanation=expl,
                    raw_text=m.group(0),
                    context=context,
                    source=source,
                )
            )
        except Exception:
            continue

    # 5. r (Pearson correlation): r(df) = val, p ...
    r_regex = re.compile(
        r"\b[rR]\s*[\(\[]\s*(\d+(?:\.\d+)?)\s*[\)\]]\s*([=><]+)\s*(-?\d+(?:\.\d+)?)"
        + p_comp_pattern
    )
    for m in r_regex.finditer(normalized):
        df_str, r_op, r_val_str, p_op, p_val_str = m.groups()
        try:
            df = float(df_str)
            r_val = float(r_val_str)
            p_comp_two, p_comp_one = compute_p_value("r", r_val, df1=df)
            cons, dec_err, cons_one, expl = check_p_consistency(
                p_val_str, p_op, p_comp_two, p_comp_one, alpha=alpha
            )
            start_pos = max(0, m.start() - 60)
            end_pos = min(len(text), m.end() + 60)
            context = text[start_pos:end_pos].strip().replace("\n", " ")
            status = "decision_error" if dec_err else ("consistent" if cons else "inconsistent")

            items.append(
                StatsCheckItem(
                    stat_type="r",
                    stat_value=r_val,
                    df1=df,
                    df2=None,
                    p_reported_str=p_val_str,
                    p_reported=float(p_val_str),
                    p_operator=p_op,
                    p_computed=round(p_comp_two, 5),
                    p_computed_one_tailed=round(p_comp_one, 5),
                    is_consistent=cons,
                    is_decision_error=dec_err,
                    is_consistent_one_tailed=cons_one,
                    discrepancy=round(p_comp_two - float(p_val_str), 5),
                    status=status,
                    explanation=expl,
                    raw_text=m.group(0),
                    context=context,
                    source=source,
                )
            )
        except Exception:
            continue

    return items


def summarize_findings(items: list[StatsCheckItem]) -> StatsCheckSummary:
    """Compute aggregate statistical consistency metrics."""
    total = len(items)
    consistent = sum(1 for it in items if it.is_consistent)
    inconsistent = sum(1 for it in items if not it.is_consistent and not it.is_decision_error)
    dec_err = sum(1 for it in items if it.is_decision_error)
    one_tailed = sum(1 for it in items if it.is_consistent_one_tailed and not it.is_consistent)
    rate = (consistent / total) if total > 0 else None

    return StatsCheckSummary(
        total_tests=total,
        consistent_count=consistent,
        inconsistent_count=inconsistent,
        decision_error_count=dec_err,
        one_tailed_match_count=one_tailed,
        consistency_rate=rate,
        items=items,
    )


# ==============================================================================
# PDF & Corpus Extraction
# ==============================================================================

def extract_stats_from_pdf(
    pdf_path: str | Path,
    alpha: float = 0.05,
) -> StatsCheckSummary:
    """Extract and check statistical tests from all pages of a PDF file."""
    p = Path(pdf_path)
    if not p.is_file():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    try:
        import fitz  # PyMuPDF
    except ImportError as e:
        raise RuntimeError("PyMuPDF is required for PDF text extraction. Install via `pip install pymupdf`.") from e

    doc = fitz.open(str(p))
    all_items: list[StatsCheckItem] = []
    for page_idx, page in enumerate(doc):
        text = page.get_text()
        if not text.strip():
            continue
        page_source = f"{p.name}:p{page_idx + 1}"
        page_items = extract_stats_from_text(text, source=page_source, alpha=alpha)
        all_items.extend(page_items)

    doc.close()
    return summarize_findings(all_items)


def extract_stats_from_project(
    project_slug: str,
    root: Optional[Path] = None,
    alpha: float = 0.05,
) -> dict[str, Any]:
    """Scan all full-text PDFs in a project corpus and generate a cross-paper audit."""
    from .project import DEFAULT_ROOT
    base_root = root or DEFAULT_ROOT
    proj_dir = base_root / project_slug
    if not proj_dir.is_dir():
        raise FileNotFoundError(f"Project directory not found: {proj_dir}")

    pdf_files = list(proj_dir.glob("*.pdf")) + list((proj_dir / "pdfs").glob("*.pdf"))
    per_paper: dict[str, dict[str, Any]] = {}
    total_items: list[StatsCheckItem] = []

    for pdf_path in sorted(pdf_files):
        summary = extract_stats_from_pdf(pdf_path, alpha=alpha)
        total_items.extend(summary.items)
        per_paper[pdf_path.name] = summary.to_dict()

    overall = summarize_findings(total_items)
    return {
        "project": project_slug,
        "total_papers_analyzed": len(pdf_files),
        "overall_summary": overall.to_dict(),
        "papers": per_paper,
    }


# ==============================================================================
# Report Formatters
# ==============================================================================

def format_stats_report(summary: StatsCheckSummary, fmt: str = "table") -> str:
    """Format verification summary as table, markdown, or json string."""
    fmt = fmt.lower()
    if fmt == "json":
        return json.dumps(summary.to_dict(), indent=2, ensure_ascii=False)

    lines: list[str] = []
    rate_str = f"{summary.consistency_rate * 100:.1f}%" if summary.consistency_rate is not None else "N/A"
    if fmt == "markdown":
        lines.append("# Statistical Report Consistency Verification Report\n")
        lines.append(f"- **Total Tests Found**: {summary.total_tests}")
        lines.append(f"- **Consistent Tests**: {summary.consistent_count} ({rate_str})")
        lines.append(f"- **Inconsistencies**: {summary.inconsistent_count}")
        lines.append(f"- **Decision Errors**: {summary.decision_error_count}")
        lines.append(f"- **One-Tailed Matches**: {summary.one_tailed_match_count}\n")

        if not summary.items:
            lines.append("*No statistical test reports (t, F, chi2, z, r) detected in text.*")
            return "\n".join(lines)

        lines.append("| Test | Stat Value | df | Reported p | Computed p | Status | Explanation | Source |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for it in summary.items:
            df_str = f"{it.df1:g}" if it.df2 is None and it.df1 is not None else (f"{it.df1:g}, {it.df2:g}" if it.df1 is not None else "-")
            status_icon = "Consistent" if it.is_consistent else ("DECISION ERROR" if it.is_decision_error else "Inconsistent")
            clean_expl = it.explanation.replace("|", "/")
            lines.append(
                f"| `{it.stat_type}` | {it.stat_value:.3g} | {df_str} | `p {it.p_operator} {it.p_reported_str}` | `{it.p_computed:.4f}` | {status_icon} | {clean_expl} | {it.source or '-'} |"
            )
        return "\n".join(lines)

    # Default: ASCII Terminal Table
    header = (
        f"Statistical Consistency Check Report\n"
        f"Total Tests: {summary.total_tests} | "
        f"Consistent: {summary.consistent_count} ({rate_str}) | "
        f"Inconsistent: {summary.inconsistent_count} | "
        f"Decision Errors: {summary.decision_error_count}\n"
        f"{'-' * 88}"
    )
    lines.append(header)
    if not summary.items:
        lines.append("No statistical test expressions detected.")
        return "\n".join(lines)

    row_fmt = "{:<6} {:<10} {:<10} {:<14} {:<12} {:<16} {:<14}"
    lines.append(row_fmt.format("Test", "Value", "df", "Reported p", "Computed p", "Status", "Source"))
    lines.append("-" * 88)

    for it in summary.items:
        df_str = f"{it.df1:g}" if it.df2 is None and it.df1 is not None else (f"{it.df1:g},{it.df2:g}" if it.df1 is not None else "-")
        status_lbl = "OK" if it.is_consistent else ("DECISION ERR" if it.is_decision_error else "INCONSISTENT")
        rep_p = f"p {it.p_operator} {it.p_reported_str}"
        lines.append(
            row_fmt.format(
                it.stat_type,
                f"{it.stat_value:.3g}",
                df_str,
                rep_p,
                f"{it.p_computed:.4f}",
                status_lbl,
                it.source or "-",
            )
        )
    lines.append("-" * 88)
    return "\n".join(lines)
