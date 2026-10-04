"""Simulation calibration parameters and effect-size prior harvester (pa extract-parameters).

ROADMAP [P1-24 / P1-25] implementation:
Harvests numerical parameter priors, elasticities, discount factors, depreciation rates,
risk aversion coefficients, shock persistences, effect sizes, standard errors, and confidence
intervals from empirical and structural academic papers.

Outputs structured representations for downstream numerical simulations:
- Terminal ASCII tables
- Markdown calibration tables for academic manuscripts
- Machine-readable JSON
- Executable Python calibration dictionaries for SciPy, PyMC, and DSGE simulation pipelines.

100% offline-first; pure regex and local M2 evidence scanning. Zero external API cost.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ==============================================================================
# Parameter Taxonomy and Canonical Mapping
# ==============================================================================

CANONICAL_PARAMETERS = [
    {
        "name": "discount_factor",
        "display_name": "Discount Factor",
        "symbol": "beta",
        "category": "macro",
        "pattern": (
            r"(?:\b(?:discount\s*factor|time\s*preference|discount\s*rate)\b[^=:\d\n]{0,35}(?:=|is\s*set\s*to|calibrated\s*to|equal\s*to)?\s*(?:beta|β)?\s*=?\s*([0-9]+\.[0-9]+))|"
            r"(?:\b(?:calibrated|calibrate|set|benchmark)\b[^=:\d\n]{0,25}\b(?:beta|β)\s*=?\s*([0-9]+\.[0-9]+))"
        ),
    },
    {
        "name": "risk_aversion",
        "display_name": "Relative Risk Aversion (CRRA)",
        "symbol": "gamma",
        "category": "macro",
        "pattern": (
            r"\b(?:risk\s*aversion|\bCRRA\b|coefficient\s*of\s*relative\s*risk\s*aversion|\bgamma\b|γ)\b"
            r"[^=:\d\n]{0,35}(?:=|is\s*set\s*to|calibrated\s*to|equal\s*to)?\s*=?\s*([0-9]+\.[0-9]+)"
        ),
    },
    {
        "name": "capital_share",
        "display_name": "Capital Share",
        "symbol": "alpha",
        "category": "macro",
        "pattern": r"\b(?:capital\s*share|output\s*elasticity\s*of\s*capital|\balpha\b|α)\b[^=:\d\n]{0,35}(?:=|is\s*set\s*to|calibrated\s*to|equal\s*to)?\s*=?\s*([0-9]+\.[0-9]+)",
    },
    {
        "name": "depreciation_rate",
        "display_name": "Capital Depreciation Rate",
        "symbol": "delta",
        "category": "macro",
        "pattern": r"\b(?:depreciation\s*rate|capital\s*depreciation|\bdelta\b|δ)\b[^=:\d\n]{0,35}(?:=|is\s*set\s*to|calibrated\s*to|equal\s*to)?\s*=?\s*([0-9]+\.[0-9]+)",
    },
    {
        "name": "frisch_elasticity",
        "display_name": "Frisch Elasticity of Labor Supply",
        "symbol": "eta",
        "category": "macro",
        "pattern": r"\b(?:Frisch\s*elasticity(?:\s*of\s*labor\s*supply)?|labor\s*supply\s*elasticity|\beta\b|η)\b[^=:\d\n]{0,35}(?:=|is\s*set\s*to|calibrated\s*to|equal\s*to)?\s*=?\s*([0-9]+\.[0-9]+)",
    },
    {
        "name": "intertemporal_substitution",
        "display_name": "Intertemporal Elasticity of Substitution (IES)",
        "symbol": "psi",
        "category": "macro",
        "pattern": r"\b(?:intertemporal\s*elasticity\s*of\s*substitution|\bIES\b|\bEIS\b|\bpsi\b|ψ)\b[^=:\d\n]{0,35}(?:=|is\s*set\s*to|calibrated\s*to|equal\s*to)?\s*=?\s*([0-9]+\.[0-9]+)",
    },
    {
        "name": "shock_persistence",
        "display_name": "Shock Persistence / AR(1) Autocorrelation",
        "symbol": "rho",
        "category": "macro",
        "pattern": r"\b(?:(?:AR\(1\)\s*)?persistence(?:\s*parameter)?|autocorrelation\s*of\s*(?:the\s*)?(?:technology|productivity)\s*shock|\brho\b|ρ)\b[^=:\d\n]{0,35}(?:=|is\s*set\s*to|calibrated\s*to|equal\s*to)?\s*=?\s*([0-9]+\.[0-9]+)",
    },
    {
        "name": "shock_volatility",
        "display_name": "Shock Innovation Volatility (Std. Dev.)",
        "symbol": "sigma",
        "category": "macro",
        "pattern": r"\b(?:(?:innovation|shock)\s*(?:volatility|standard\s*deviation)|sigma_e|sigma_ε|\bsigma\b|σ)\b[^=:\d\n]{0,35}(?:=|is\s*set\s*to|calibrated\s*to|equal\s*to)?\s*=?\s*([0-9]+\.[0-9]+)",
    },
    {
        "name": "price_elasticity",
        "display_name": "Price Elasticity of Demand / Substitution",
        "symbol": "theta",
        "category": "micro",
        "pattern": r"\b(?:price\s*elasticity(?:\s*of\s*demand)?|elasticity\s*of\s*substitution\s*across\s*goods|\btheta\b|θ|\bepsilon\b|ε)\b[^=:\d\n]{0,35}(?:=|is\s*set\s*to|calibrated\s*to|equal\s*to)?\s*=?\s*([0-9]+\.[0-9]+)",
    },
    {
        "name": "treatment_effect",
        "display_name": "Empirical Baseline Treatment Effect",
        "symbol": "beta_treat",
        "category": "empirical",
        "pattern": r"\b(?:treatment\s*effect|average\s*treatment\s*effect|\bATE\b|\bATT\b|DID\s*estimate|baseline\s*(?:treatment\s*)?effect)\b[^=:\d\n]{0,35}(?:=|is|was|estimated\s*at|equal\s*to)?\s*(?:beta|β)?\s*=?\s*([−–—\-]?\d+\.[0-9]+)",
    },
    {
        "name": "marginal_propensity_consume",
        "display_name": "Marginal Propensity to Consume (MPC)",
        "symbol": "MPC",
        "category": "macro",
        "pattern": r"\b(?:marginal\s*propensity\s*to\s*consume|\bMPC\b)\b[^=:\d\n]{0,35}(?:=|is|was|estimated\s*at|calibrated\s*to|equal\s*to)?\s*=?\s*([0-9]+\.[0-9]+)",
    },
]


# ==============================================================================
# Data Structures
# ==============================================================================

@dataclass
class CalibrationParameter:
    """Represents a single extracted parameter prior or calibration value."""
    name: str
    display_name: str
    symbol: str
    value: float
    std_err: Optional[float] = None
    ci_lower: Optional[float] = None
    ci_upper: Optional[float] = None
    unit_frequency: Optional[str] = None
    category: str = "general"
    source_snippet: str = ""
    source_doc: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CalibrationSummary:
    """Collection and cross-paper distribution of harvested parameters."""
    total_parameters: int
    parameters: list[CalibrationParameter]
    by_category: dict[str, list[dict[str, Any]]]
    distributions: dict[str, dict[str, float]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_parameters": self.total_parameters,
            "parameters": [p.to_dict() for p in self.parameters],
            "by_category": self.by_category,
            "distributions": self.distributions,
        }


# ==============================================================================
# Auxiliary Extractors (Confidence Intervals, SE, Frequency)
# ==============================================================================

CI_PATTERN = re.compile(
    r"(?:95%?\s*CI|confidence\s*interval)\s*[:=\s]*[\[\(]?\s*([−–—\-]?\d+\.?\d*)\s*(?:,\s*|to\s*|\s*;\s*)\s*([−–—\-]?\d+\.?\d*)\s*[\]\)]?",
    re.IGNORECASE,
)

SE_PATTERN = re.compile(
    r"(?:SE|std\.?\s*err\.?)\s*[:=\s]\s*([0-9]+\.[0-9]+)",
    re.IGNORECASE,
)

FREQUENCY_KEYWORDS = [
    ("quarterly", re.compile(r"\bquarterly\b", re.IGNORECASE)),
    ("annual", re.compile(r"\b(?:annual|annually|annualized|per\s*year)\b", re.IGNORECASE)),
    ("monthly", re.compile(r"\b(?:monthly|per\s*month)\b", re.IGNORECASE)),
    ("daily", re.compile(r"\b(?:daily|per\s*day)\b", re.IGNORECASE)),
    ("percent", re.compile(r"\b(?:percent|percentage|%)\b", re.IGNORECASE)),
]


def extract_contextual_metadata(snippet: str) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[str]]:
    """Extract standard error, 95% confidence interval, and frequency from context."""
    std_err: Optional[float] = None
    ci_lower: Optional[float] = None
    ci_upper: Optional[float] = None
    freq: Optional[str] = None

    # Check SE
    m_se = SE_PATTERN.search(snippet)
    if m_se:
        try:
            std_err = float(m_se.group(1))
        except ValueError:
            pass

    # Check CI
    m_ci = CI_PATTERN.search(snippet)
    if m_ci:
        try:
            low_str = m_ci.group(1).replace("−", "-").replace("–", "-").replace("—", "-")
            high_str = m_ci.group(2).replace("−", "-").replace("–", "-").replace("—", "-")
            ci_lower = float(low_str)
            ci_upper = float(high_str)
        except ValueError:
            pass

    # Check frequency
    for label, pat in FREQUENCY_KEYWORDS:
        if pat.search(snippet):
            freq = label
            break

    return std_err, ci_lower, ci_upper, freq


def get_sentence_clause(text: str, match_start: int, match_end: int) -> str:
    """Extract the specific sentence containing the match to prevent metadata bleeding."""
    left = max(
        text.rfind(". ", 0, match_start),
        text.rfind(".\n", 0, match_start),
        text.rfind("\n", 0, match_start),
    )
    left = 0 if left == -1 else left + 1

    right1 = text.find(". ", match_end)
    right2 = text.find(".\n", match_end)
    right3 = text.find("\n", match_end)
    right_cands = [pos for pos in (right1, right2, right3) if pos != -1]
    right = min(right_cands) if right_cands else len(text)
    return text[left:right].strip()


# ==============================================================================
# Text Harvesting Engine
# ==============================================================================

def harvest_parameters_from_text(
    text: str,
    source_doc: str = "",
    category_filter: Optional[str] = None,
) -> list[CalibrationParameter]:
    """Scan text and extract calibration parameter priors."""
    results: list[CalibrationParameter] = []
    seen_keys: set[Tuple[str, float]] = set()

    for spec in CANONICAL_PARAMETERS:
        if category_filter and category_filter.lower() != "all":
            if spec["category"].lower() != category_filter.lower():
                continue

        pattern = re.compile(spec["pattern"], re.IGNORECASE)
        for m in pattern.finditer(text):
            matched_val = next((g for g in m.groups() if g is not None), None)
            if not matched_val:
                continue
            val_str = matched_val.replace("−", "-").replace("–", "-").replace("—", "-")
            try:
                val = float(val_str)
            except ValueError:
                continue

            # Deduplicate multiple hits for same parameter and identical value
            key = (spec["name"], val)
            if key in seen_keys:
                continue
            seen_keys.add(key)

            # Precise sentence clause isolation
            clause = get_sentence_clause(text, m.start(), m.end())
            std_err, ci_low, ci_high, freq = extract_contextual_metadata(clause)

            results.append(
                CalibrationParameter(
                    name=spec["name"],
                    display_name=spec["display_name"],
                    symbol=spec["symbol"],
                    value=val,
                    std_err=std_err,
                    ci_lower=ci_low,
                    ci_upper=ci_high,
                    unit_frequency=freq,
                    category=spec["category"],
                    source_snippet=clause,
                    source_doc=source_doc,
                )
            )

    return results


def summarize_parameters(params: list[CalibrationParameter]) -> CalibrationSummary:
    """Compute cross-parameter summary metrics and distribution bounds."""
    by_cat: dict[str, list[dict[str, Any]]] = {}
    vals_by_name: dict[str, list[float]] = {}

    for p in params:
        cat = p.category
        if cat not in by_cat:
            by_cat[cat] = []
        by_cat[cat].append(p.to_dict())

        if p.name not in vals_by_name:
            vals_by_name[p.name] = []
        vals_by_name[p.name].append(p.value)

    dists: dict[str, dict[str, float]] = {}
    for name, v_list in vals_by_name.items():
        if v_list:
            dists[name] = {
                "count": len(v_list),
                "min": round(min(v_list), 4),
                "mean": round(sum(v_list) / len(v_list), 4),
                "max": round(max(v_list), 4),
            }

    return CalibrationSummary(
        total_parameters=len(params),
        parameters=params,
        by_category=by_cat,
        distributions=dists,
    )


# ==============================================================================
# PDF & Corpus Extraction
# ==============================================================================

def harvest_parameters_from_pdf(
    pdf_path: str | Path,
    category_filter: Optional[str] = None,
) -> CalibrationSummary:
    """Extract calibration parameters from all pages of a PDF document."""
    p = Path(pdf_path)
    if not p.is_file():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    try:
        import fitz  # PyMuPDF
    except ImportError as e:
        raise RuntimeError("PyMuPDF is required for PDF parsing. Install via `pip install pymupdf`.") from e

    doc = fitz.open(str(p))
    all_params: list[CalibrationParameter] = []

    for page_idx, page in enumerate(doc):
        text = page.get_text()
        if not text.strip():
            continue
        page_source = f"{p.name}:p{page_idx + 1}"
        page_params = harvest_parameters_from_text(
            text,
            source_doc=page_source,
            category_filter=category_filter,
        )
        all_params.extend(page_params)

    doc.close()
    return summarize_parameters(all_params)


def harvest_parameters_from_project(
    project_slug: str,
    root: Optional[Path] = None,
    category_filter: Optional[str] = None,
) -> dict[str, Any]:
    """Scan all full-text PDFs in a project corpus and harvest calibration priors."""
    from .project import DEFAULT_ROOT
    base_root = root or DEFAULT_ROOT
    proj_dir = base_root / project_slug
    if not proj_dir.is_dir():
        raise FileNotFoundError(f"Project directory not found: {proj_dir}")

    pdf_files = list(proj_dir.glob("*.pdf")) + list((proj_dir / "pdfs").glob("*.pdf"))
    per_paper: dict[str, dict[str, Any]] = {}
    all_params: list[CalibrationParameter] = []

    for pdf_path in sorted(pdf_files):
        summary = harvest_parameters_from_pdf(pdf_path, category_filter=category_filter)
        all_params.extend(summary.parameters)
        per_paper[pdf_path.name] = summary.to_dict()

    overall = summarize_parameters(all_params)
    return {
        "project": project_slug,
        "total_papers_analyzed": len(pdf_files),
        "overall_summary": overall.to_dict(),
        "papers": per_paper,
    }


# ==============================================================================
# Report Formatters
# ==============================================================================

def format_parameters_report(summary: CalibrationSummary, fmt: str = "table") -> str:
    """Format calibration summary into table, markdown, json, or python code."""
    fmt = fmt.lower()

    if fmt == "json":
        return json.dumps(summary.to_dict(), indent=2, ensure_ascii=False)

    if fmt == "python":
        lines: list[str] = [
            '"""Simulation calibration priors harvested by Paper Agent."""',
            "",
            "CALIBRATION_PRIORS = {",
        ]
        for p in summary.parameters:
            ci_val = f"[{p.ci_lower}, {p.ci_upper}]" if p.ci_lower is not None else "None"
            se_val = f"{p.std_err}" if p.std_err is not None else "None"
            lines.append(f'    "{p.name}": {{')
            lines.append(f'        "symbol": "{p.symbol}",')
            lines.append(f'        "value": {p.value},')
            lines.append(f'        "std_err": {se_val},')
            lines.append(f'        "ci_95": {ci_val},')
            lines.append(f'        "frequency": "{p.unit_frequency or ""}",')
            lines.append(f'        "category": "{p.category}",')
            lines.append(f'        "source": "{p.source_doc}",')
            lines.append("    },")
        lines.append("}")
        return "\n".join(lines)

    if fmt == "markdown":
        lines: list[str] = [
            "# Simulation Calibration Parameters & Effect-Size Priors\n",
            f"- **Total Parameters Harvested**: {summary.total_parameters}",
        ]
        if summary.distributions:
            lines.append("\n### Parameter Prior Distributions (Empirical Range)\n")
            lines.append("| Parameter | Symbol | Min | Mean | Max | Sample Count |")
            lines.append("|---|---|---|---|---|---|")
            for name, d in summary.distributions.items():
                p_spec = next((sp for sp in CANONICAL_PARAMETERS if sp["name"] == name), None)
                sym = p_spec["symbol"] if p_spec else name
                disp = p_spec["display_name"] if p_spec else name
                lines.append(f"| {disp} | `{sym}` | {d['min']} | {d['mean']} | {d['max']} | {d['count']} |")

        lines.append("\n### Harvested Calibration Priors\n")
        lines.append("| Parameter | Symbol | Value | Std Err | 95% CI | Frequency | Source |")
        lines.append("|---|---|---|---|---|---|---|")
        for p in summary.parameters:
            se_str = f"{p.std_err:.4g}" if p.std_err is not None else "-"
            ci_str = f"[{p.ci_lower:g}, {p.ci_upper:g}]" if p.ci_lower is not None else "-"
            freq_str = p.unit_frequency or "-"
            lines.append(
                f"| {p.display_name} | `{p.symbol}` | **{p.value}** | {se_str} | {ci_str} | {freq_str} | {p.source_doc or '-'} |"
            )
        return "\n".join(lines)

    # Default ASCII Terminal Table
    lines: list[str] = [
        f"Simulation Calibration Parameters & Effect-Size Priors\n"
        f"Total Parameters: {summary.total_parameters}\n"
        f"{'-' * 88}"
    ]
    if not summary.parameters:
        lines.append("No calibration parameters detected.")
        return "\n".join(lines)

    row_fmt = "{:<26} {:<10} {:<10} {:<10} {:<16} {:<12}"
    lines.append(row_fmt.format("Parameter", "Symbol", "Value", "Std Err", "95% CI", "Frequency"))
    lines.append("-" * 88)

    for p in summary.parameters:
        se_str = f"{p.std_err:.4g}" if p.std_err is not None else "-"
        ci_str = f"[{p.ci_lower:g},{p.ci_upper:g}]" if p.ci_lower is not None else "-"
        freq_str = p.unit_frequency or "-"
        lines.append(
            row_fmt.format(
                p.display_name[:25],
                p.symbol,
                f"{p.value:g}",
                se_str,
                ci_str,
                freq_str,
            )
        )
    lines.append("-" * 88)
    return "\n".join(lines)
