"""Theoretical proposition controversy and consensus matrix (pa consensus).

ROADMAP [P1-22] implementation:
Maps competing theoretical propositions and empirical hypotheses (H1 vs H2,
positive vs negative vs null findings) across corpus papers. Generates a structured
matrix of agreement vs contradiction, consensus scores, debate intensity levels,
and boundary conditions / heterogeneity explanations.

100% offline-first; pure local text/PDF parsing and SQLite adjacency relations.
Zero cloud infra or paid APIs.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


# ==============================================================================
# Common Academic Concept Keywords for Entity Grounding
# ==============================================================================

CANONICAL_CONCEPTS = [
    ("esg", "Corporate ESG Performance", re.compile(r"\b(?:ESG|environmental[\s,]+social[\s,]+and\s*governance)\b", re.IGNORECASE)),
    ("csr", "Corporate Social Responsibility", re.compile(r"\b(?:CSR|corporate\s*social\s*responsibility)\b", re.IGNORECASE)),
    ("digital_transformation", "Digital Transformation", re.compile(r"\b(?:digital\s*transformation|digitization|digitalization|数字化转型)\b", re.IGNORECASE)),
    ("financial_performance", "Firm Financial Performance", re.compile(r"\b(?:financial\s*performance|firm\s*performance|profitability|ROA|ROE|Tobin[\'s]*\s*Q|财务绩效|企业绩效)\b", re.IGNORECASE)),
    ("innovation", "Corporate Innovation Quality", re.compile(r"\b(?:innovation(?:\s*quality|\s*performance)?|R&D|patent[s]?|企业创新|创新绩效)\b", re.IGNORECASE)),
    ("debt_leverage", "Debt / Financial Leverage", re.compile(r"\b(?:debt\s*leverage|financial\s*leverage|leverage|debt\s*ratio|资本结构|杠杆率)\b", re.IGNORECASE)),
    ("environmental_regulation", "Environmental Regulation", re.compile(r"\b(?:environmental\s*regulation|carbon\s*tax|环境规制)\b", re.IGNORECASE)),
    ("green_innovation", "Green Innovation / Total Factor Productivity", re.compile(r"\b(?:green\s*innovation|green\s*total\s*factor\s*productivity|GTFP|绿色创新)\b", re.IGNORECASE)),
    ("ceo_duality", "CEO Duality / Board Structure", re.compile(r"\b(?:CEO\s*duality|board\s*structure|board\s*independence|两职合一|董事会结构)\b", re.IGNORECASE)),
    ("agency_cost", "Agency Costs", re.compile(r"\b(?:agency\s*cost[s]?|代理成本)\b", re.IGNORECASE)),
    ("cost_of_capital", "Cost of Capital", re.compile(r"\b(?:cost\s*of\s*capital|cost\s*of\s*debt|cost\s*of\s*equity|资本成本)\b", re.IGNORECASE)),
    ("firm_value", "Firm Value / Stock Returns", re.compile(r"\b(?:firm\s*value|stock\s*return[s]?|market\s*valuation|企业价值)\b", re.IGNORECASE)),
]


# ==============================================================================
# Data Structures
# ==============================================================================

@dataclass
class HypothesisItem:
    """Represents a single extracted hypothesis or propositional finding."""
    paper_id: str
    label: str  # "H1", "H2a", "Proposition 1", "Empirical Finding"
    statement: str
    variable_x: str
    variable_y: str
    relation_key: str  # "x -> y"
    direction: str  # "positive", "negative", "neutral", "inverted_u", "u_shaped", "unspecified"
    outcome: str  # "supported", "rejected", "partially_supported", "untested"
    effective_finding: str  # "positive", "negative", "neutral", "nonlinear"
    evidence_snippet: str = ""
    source: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RelationshipConsensus:
    """Synthesizes cross-paper agreement and debate on a specific proposition relationship."""
    relation_key: str
    label_x: str
    label_y: str
    total_papers: int
    positive_papers: list[str]
    negative_papers: list[str]
    null_papers: list[str]
    nonlinear_papers: list[str]
    consensus_score: float  # max(count) / total
    debate_level: str  # "Consensus Baseline", "Moderate Debate", "Intense Controversy"
    dominant_direction: str  # "positive", "negative", "null", "nonlinear"
    boundary_conditions: list[str]
    hypotheses: list[HypothesisItem]

    def to_dict(self) -> dict[str, Any]:
        return {
            "relation_key": self.relation_key,
            "label_x": self.label_x,
            "label_y": self.label_y,
            "total_papers": self.total_papers,
            "positive_papers": self.positive_papers,
            "negative_papers": self.negative_papers,
            "null_papers": self.null_papers,
            "nonlinear_papers": self.nonlinear_papers,
            "consensus_score": round(self.consensus_score, 4),
            "debate_level": self.debate_level,
            "dominant_direction": self.dominant_direction,
            "boundary_conditions": self.boundary_conditions,
            "hypotheses": [h.to_dict() for h in self.hypotheses],
        }


@dataclass
class ConsensusReport:
    """Full cross-paper consensus and controversy synthesis report."""
    total_papers: int
    total_hypotheses: int
    relationships: list[RelationshipConsensus]
    hypotheses_by_paper: dict[str, list[HypothesisItem]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_papers": self.total_papers,
            "total_hypotheses": self.total_hypotheses,
            "relationships": [r.to_dict() for r in self.relationships],
            "hypotheses_by_paper": {
                paper: [h.to_dict() for h in h_list]
                for paper, h_list in self.hypotheses_by_paper.items()
            },
        }


# ==============================================================================
# Direction and Variable Parsing
# ==============================================================================

DIR_POSITIVE = re.compile(
    r"\b(?:positive|positively|promotes?|enhances?|improves?|boosts?|increases?|higher|fosters?|stimulates?)\b|正向|促进|提升|显著增加",
    re.IGNORECASE,
)
DIR_NEGATIVE = re.compile(
    r"\b(?:negative|negatively|inhibits?|suppresses?|reduces?|decreases?|lower|lowers?|dampens?|impedes?)\b|负向|抑制|降低|显著减少",
    re.IGNORECASE,
)
DIR_NONLINEAR = re.compile(
    r"\b(?:inverted\s*u[- ]shaped|u[- ]shaped|nonlinear|non-linear|quadratic|threshold\s*effect)\b|倒U型|U型|非线性|门槛效应",
    re.IGNORECASE,
)
DIR_NULL = re.compile(
    r"\b(?:no\s*significant|not\s*significantly|insignificant|uncorrelated|fails?\s*to\s*affect)\b|无显著|不显著|无影响",
    re.IGNORECASE,
)

OUTCOME_SUPPORTED = re.compile(
    r"\b(?:(?:is\s*|was\s*|strongly\s*|empirically\s*)?supported|support(?:s|ing)?|confirmed|verified|validated|consistent\s*with)\b|得到支持|通过检验|验证了",
    re.IGNORECASE,
)
OUTCOME_REJECTED = re.compile(
    r"\b(?:(?:is\s*|was\s*)?rejected|not\s*supported|failed\s*to\s*support|fails\s*to\s*find\s*support|disconfirmed|reject(?:s|ing)?)\b|被拒绝|未通过|未能支持",
    re.IGNORECASE,
)
OUTCOME_PARTIAL = re.compile(
    r"\b(?:partially\s*supported|partly\s*supported)\b|部分支持",
    re.IGNORECASE,
)


def detect_direction(statement: str) -> str:
    """Classify the propositional direction of a hypothesis statement."""
    if DIR_NONLINEAR.search(statement):
        lower = statement.lower()
        return "inverted_u" if ("inverted" in lower or "倒" in statement) else "u_shaped"
    if DIR_NULL.search(statement):
        return "neutral"

    is_pos = bool(DIR_POSITIVE.search(statement))
    is_neg = bool(DIR_NEGATIVE.search(statement))

    if is_pos and not is_neg:
        return "positive"
    if is_neg and not is_pos:
        return "negative"
    return "unspecified"


def map_variables_from_text(statement: str) -> Tuple[str, str, str, str]:
    """Map canonical or heuristic Independent Variable (X) and Dependent Variable (Y)."""
    # 1. First attempt canonical taxonomy matching
    matched_concepts: list[Tuple[str, str, int]] = []
    for key, disp, pat in CANONICAL_CONCEPTS:
        m = pat.search(statement)
        if m:
            matched_concepts.append((key, disp, m.start()))

    if len(matched_concepts) >= 2:
        # Sort by occurrence order in sentence: first is typically X, second is Y
        matched_concepts.sort(key=lambda x: x[2])
        x_key, x_disp, _ = matched_concepts[0]
        y_key, y_disp, _ = matched_concepts[1]
        return x_key, x_disp, y_key, y_disp

    if len(matched_concepts) == 1:
        x_key, x_disp, _ = matched_concepts[0]
        return x_key, x_disp, "firm_performance", "Firm Performance"

    # 2. Heuristic extraction based on causal connectors
    causal_split = re.split(
        r"(?:has\s*a\s*(?:positive|negative)?\s*(?:impact|effect)\s*on|is\s*(?:positively|negatively)?\s*associated\s*with|significantly\s*(?:promotes|inhibits)|对|影响)",
        statement,
        maxsplit=1,
        flags=re.IGNORECASE,
    )
    if len(causal_split) == 2 and causal_split[0].strip() and causal_split[1].strip():
        raw_x = causal_split[0].strip()[:30]
        raw_y = causal_split[1].strip()[:30]
        clean_x = re.sub(r"^[A-Za-z0-9_]+\s*[:：]\s*", "", raw_x).strip()
        clean_y = re.sub(r"[\.;\n].*$", "", raw_y).strip()
        key_x = re.sub(r"\W+", "_", clean_x).lower().strip("_") or "variable_x"
        key_y = re.sub(r"\W+", "_", clean_y).lower().strip("_") or "variable_y"
        return key_x, clean_x, key_y, clean_y

    return "general_cause", "Independent Factor", "general_outcome", "Dependent Outcome"


# ==============================================================================
# Extraction Engine
# ==============================================================================

def extract_hypotheses_from_text(text: str, source_doc: str = "") -> list[HypothesisItem]:
    """Extract formalized hypotheses (H1, H2, etc.) and their validation outcomes."""
    items: list[HypothesisItem] = []

    # 1. Match hypothesis proposals
    # e.g. "Hypothesis 1 (H1): Corporate ESG ...", "H1a: ...", "假设 1: ...", "Proposition 1: ..."
    h_prop_pattern = re.compile(
        r"(?:(?:Hypothesis|Proposition|假说|假设|命题)\s*([0-9]+[a-zA-Z]?)|(?:H|P)([0-9]+[a-zA-Z]?))\s*[\(\[（]?(?:[hH][0-9]+[a-zA-Z]?)?[\)\]）]?\s*[:：\.-]?\s*([^\n\.\;]{15,280}[\.\;\n])",
        re.IGNORECASE,
    )

    # 2. Match outcome statements across the text
    # e.g. "Hypothesis 1 is supported", "H2 was rejected", "supporting H1", "假设1通过检验"
    h_outcomes: dict[str, Tuple[str, str]] = {}  # h_num -> (outcome, snippet)
    outcome_scan = re.compile(
        r"(?:(?:Hypothesis|Proposition|假说|假设|命题|[HP])\s*([0-9]+[a-zA-Z]?)[^.\n]{0,80}?(supported|rejected|not\s+supported|confirmed|failed\s+to\s+support|validated|verified|通过检验|未能支持|被拒绝|得到支持|验证了)|(supported|rejected|not\s+supported|confirmed|failed\s+to\s+support|validated|verified|通过检验|未能支持|被拒绝|得到支持|验证了|supporting|rejecting|confirming)\s+(?:Hypothesis|Proposition|假说|假设|命题|[HP])\s*([0-9]+[a-zA-Z]?))",
        re.IGNORECASE,
    )
    FUTURE_OR_CONDITIONAL = re.compile(
        r"\b(?:whether|if|future|plan(?:s|ned)?|will\s+test|to\s+test|remains?\s+to\s+be|yet\s+to\s+be|leaving|untested)\b|未来|计划|是否|待检验|留待",
        re.IGNORECASE,
    )
    for m in outcome_scan.finditer(text):
        h_num = (m.group(1) or m.group(4) or "").strip().upper()
        raw_out = (m.group(2) or m.group(3) or "").strip().lower()
        if not h_num or not raw_out:
            continue

        s_start = max(0, text.rfind("\n", 0, m.start()), text.rfind(".", 0, m.start()))
        s_end = text.find("\n", m.end())
        if s_end == -1:
            s_end = text.find(".", m.end())
        if s_end == -1:
            s_end = len(text)
        surrounding_sent = text[s_start:s_end]

        if FUTURE_OR_CONDITIONAL.search(surrounding_sent):
            status = "untested"
        elif OUTCOME_REJECTED.search(raw_out):
            status = "rejected"
        elif OUTCOME_PARTIAL.search(raw_out):
            status = "partially_supported"
        elif OUTCOME_SUPPORTED.search(raw_out):
            status = "supported"
        else:
            status = "untested"
        h_outcomes[h_num] = (status, m.group(0))

    # Parse each hypothesis proposal
    for m in h_prop_pattern.finditer(text):
        num = (m.group(1) or m.group(2) or "1").strip().upper()
        statement = m.group(3).strip()

        # Filter out if this match is merely an outcome sentence like "Hypothesis 1 is supported"
        if OUTCOME_SUPPORTED.search(statement) or OUTCOME_REJECTED.search(statement):
            continue

        direction = detect_direction(statement)
        x_key, x_disp, y_key, y_disp = map_variables_from_text(statement)
        relation_key = f"{x_key} -> {y_key}"

        # Associate outcome if found
        outcome, outcome_snip = h_outcomes.get(num, ("untested", ""))

        # Determine effective empirical finding direction:
        # If proposed positive and supported -> positive
        # If proposed positive and rejected -> neutral or negative
        # If proposed negative and supported -> negative
        # If untested -> untested
        if outcome == "supported":
            effective = direction
        elif outcome == "rejected":
            effective = "neutral" if direction != "neutral" else "unspecified"
        elif outcome == "partially_supported":
            effective = direction
        else:
            effective = "untested"

        items.append(
            HypothesisItem(
                paper_id=source_doc or "current_doc",
                label=f"H{num}",
                statement=statement,
                variable_x=x_disp,
                variable_y=y_disp,
                relation_key=relation_key,
                direction=direction,
                outcome=outcome,
                effective_finding=effective,
                evidence_snippet=outcome_snip or statement[:100],
                source=source_doc,
            )
        )

    # 3. If no formal H1/H2 found, scan for general empirical findings
    if not items:
        findings = extract_general_findings_from_text(text, source_doc=source_doc)
        items.extend(findings)

    return items


def extract_general_findings_from_text(text: str, source_doc: str = "") -> list[HypothesisItem]:
    """Fallback extractor for papers that state empirical findings directly without H1 labels."""
    findings: list[HypothesisItem] = []
    finding_pattern = re.compile(
        r"(?:we\s*find|results\s*indicate|empirical\s*results\s*show|evidence\s*suggests|发现|表明)\s*(?:that)?\s*([^\n\.\;]{20,250}[\.\;\n])",
        re.IGNORECASE,
    )

    for idx, m in enumerate(finding_pattern.finditer(text), 1):
        statement = m.group(1).strip()
        direction = detect_direction(statement)
        if direction == "unspecified":
            continue

        x_key, x_disp, y_key, y_disp = map_variables_from_text(statement)
        relation_key = f"{x_key} -> {y_key}"

        findings.append(
            HypothesisItem(
                paper_id=source_doc or "current_doc",
                label=f"Finding_{idx}",
                statement=statement,
                variable_x=x_disp,
                variable_y=y_disp,
                relation_key=relation_key,
                direction=direction,
                outcome="supported",
                effective_finding=direction,
                evidence_snippet=statement[:100],
                source=source_doc,
            )
        )
        if len(findings) >= 3:
            break

    return findings


def extract_boundary_conditions(text: str) -> list[str]:
    """Extract heterogeneity qualifiers explaining why empirical findings diverge."""
    boundary_patterns = [
        re.compile(r"(?:heterogeneity\s*analysis\s*shows\s*that|effect\s*is\s*more\s*pronounced\s*in|stronger\s*for|异质性分析表明)\s*([^\n\.\;]{15,180}[\.\;])", re.IGNORECASE),
        re.compile(r"(?:however[,\s]+for|in\s*contrast[,\s]+for|whereas\s*in)\s*([^\n\.\;]{15,180}[\.\;])", re.IGNORECASE),
        re.compile(r"(?:sample\s*period\s*from|developed\s*vs\s*emerging|state-owned\s*enterprises|SOEs)\b[^\n\.\;]{0,100}[\.\;]", re.IGNORECASE),
    ]
    conditions: list[str] = []
    for pat in boundary_patterns:
        for m in pat.finditer(text):
            clause = m.group(0).strip().replace("\n", " ")
            if len(clause) > 20 and clause not in conditions:
                conditions.append(clause)
            if len(conditions) >= 5:
                break
    return conditions


# ==============================================================================
# Matrix Synthesis & Report Assembly
# ==============================================================================

def build_consensus_matrix(hypotheses: list[HypothesisItem], boundary_conditions: Optional[list[str]] = None) -> ConsensusReport:
    """Group hypotheses across papers by relation key and calculate consensus metrics."""
    by_relation: dict[str, list[HypothesisItem]] = {}
    by_paper: dict[str, list[HypothesisItem]] = {}

    for h in hypotheses:
        if h.relation_key not in by_relation:
            by_relation[h.relation_key] = []
        by_relation[h.relation_key].append(h)

        p_id = h.paper_id or "default"
        if p_id not in by_paper:
            by_paper[p_id] = []
        by_paper[p_id].append(h)

    relationships: list[RelationshipConsensus] = []
    for rel_key, h_list in by_relation.items():
        pos_papers: set[str] = set()
        neg_papers: set[str] = set()
        null_papers: set[str] = set()
        nonlin_papers: set[str] = set()

        first_h = h_list[0]
        label_x = first_h.variable_x
        label_y = first_h.variable_y

        for h in h_list:
            doc_id = h.paper_id
            eff = h.effective_finding
            if eff == "positive":
                pos_papers.add(doc_id)
            elif eff == "negative":
                neg_papers.add(doc_id)
            elif eff == "neutral":
                null_papers.add(doc_id)
            elif eff in ("inverted_u", "u_shaped"):
                nonlin_papers.add(doc_id)

        all_papers = pos_papers | neg_papers | null_papers | nonlin_papers
        if not all_papers:
            dominant_dir = "untested"
            score = 0.0
            debate_level = "Insufficient Evidence"
            total_p = len({h.paper_id for h in h_list})
        else:
            total_p = len(all_papers)
            counts = {
                "positive": len(pos_papers),
                "negative": len(neg_papers),
                "null": len(null_papers),
                "nonlinear": len(nonlin_papers),
            }
            dominant_dir, max_count = max(counts.items(), key=lambda x: x[1])
            score = max_count / total_p

            # Debate classification
            if score >= 0.75:
                debate_level = "Consensus Baseline"
            elif score >= 0.50:
                debate_level = "Moderate Debate"
            else:
                debate_level = "Intense Controversy"

        relationships.append(
            RelationshipConsensus(
                relation_key=rel_key,
                label_x=label_x,
                label_y=label_y,
                total_papers=total_p,
                positive_papers=sorted(list(pos_papers)),
                negative_papers=sorted(list(neg_papers)),
                null_papers=sorted(list(null_papers)),
                nonlinear_papers=sorted(list(nonlin_papers)),
                consensus_score=score,
                debate_level=debate_level,
                dominant_direction=dominant_dir,
                boundary_conditions=boundary_conditions or [],
                hypotheses=h_list,
            )
        )

    # Sort relationships by total papers descending
    relationships.sort(key=lambda r: r.total_papers, reverse=True)

    total_unique_papers = len(by_paper)
    return ConsensusReport(
        total_papers=total_unique_papers,
        total_hypotheses=len(hypotheses),
        relationships=relationships,
        hypotheses_by_paper=by_paper,
    )


# ==============================================================================
# PDF & Corpus Extraction
# ==============================================================================

def extract_consensus_from_pdf(pdf_path: str | Path) -> list[HypothesisItem]:
    """Extract hypotheses and findings from an individual academic PDF."""
    p = Path(pdf_path)
    if not p.is_file():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    try:
        import fitz  # PyMuPDF
    except ImportError as e:
        raise RuntimeError("PyMuPDF is required for PDF parsing. Install via `pip install pymupdf`.") from e

    doc = fitz.open(str(p))
    full_text_pages: list[str] = []
    for page in doc:
        txt = page.get_text()
        if txt.strip():
            full_text_pages.append(txt)
    doc.close()

    full_text = "\n".join(full_text_pages)
    return extract_hypotheses_from_text(full_text, source_doc=p.name)


def extract_project_consensus(project_slug: str, root: Optional[Path] = None) -> ConsensusReport:
    """Scan all full-text PDFs in a project corpus and generate cross-paper consensus matrix."""
    from .project import DEFAULT_ROOT
    base_root = root or DEFAULT_ROOT
    proj_dir = base_root / project_slug
    if not proj_dir.is_dir():
        raise FileNotFoundError(f"Project directory not found: {proj_dir}")

    pdf_files = list(proj_dir.glob("*.pdf")) + list((proj_dir / "pdfs").glob("*.pdf"))
    all_hypotheses: list[HypothesisItem] = []
    all_boundaries: list[str] = []

    for pdf_path in sorted(pdf_files):
        try:
            hyps = extract_consensus_from_pdf(pdf_path)
            all_hypotheses.extend(hyps)
            # Extract boundaries
            import fitz
            doc = fitz.open(str(pdf_path))
            txt = "\n".join([page.get_text() for page in doc])
            doc.close()
            boundaries = extract_boundary_conditions(txt)
            all_boundaries.extend(boundaries)
        except Exception:
            continue

    return build_consensus_matrix(all_hypotheses, boundary_conditions=all_boundaries[:6])


# ==============================================================================
# Report Formatters
# ==============================================================================

def format_consensus_report(report: ConsensusReport, fmt: str = "table") -> str:
    """Format consensus report into terminal table, markdown, or json."""
    fmt = fmt.lower()
    if fmt == "json":
        return json.dumps(report.to_dict(), indent=2, ensure_ascii=False)

    if fmt == "markdown":
        lines: list[str] = [
            "# Academic Proposition Consensus & Controversy Matrix\n",
            f"- **Total Papers Analyzed**: {report.total_papers}",
            f"- **Total Hypotheses / Findings Extracted**: {report.total_hypotheses}",
            f"- **Unique Proposition Relationships**: {len(report.relationships)}\n",
            "### Cross-Paper Proposition Matrix\n",
            "| Relationship (X -> Y) | Dominant Finding | Consensus Score | Debate Level | Positive Papers | Negative Papers | Null / Insignificant |",
            "|---|---|---|---|---|---|---|",
        ]
        for r in report.relationships:
            pos_str = ", ".join(r.positive_papers) if r.positive_papers else "-"
            neg_str = ", ".join(r.negative_papers) if r.negative_papers else "-"
            null_str = ", ".join(r.null_papers) if r.null_papers else "-"
            dom_icon = r.dominant_direction.upper()
            lines.append(
                f"| **{r.label_x}** -> **{r.label_y}** | `{dom_icon}` | **{r.consensus_score * 100:.1f}%** | {r.debate_level} | {pos_str} | {neg_str} | {null_str} |"
            )

        if report.relationships and any(r.boundary_conditions for r in report.relationships):
            lines.append("\n### Key Controversy Drivers & Boundary Conditions\n")
            seen_bc: set[str] = set()
            for r in report.relationships:
                for bc in r.boundary_conditions:
                    if bc not in seen_bc:
                        seen_bc.add(bc)
                        lines.append(f"- *{bc}*")

        lines.append("\n### Detailed Hypotheses & Evidence Records\n")
        lines.append("| Paper | Label | Direction | Outcome | Statement | Snippet |")
        lines.append("|---|---|---|---|---|---|")
        for paper, h_list in report.hypotheses_by_paper.items():
            for h in h_list:
                clean_stmt = h.statement.replace("|", "/")[:120]
                clean_snip = h.evidence_snippet.replace("|", "/")[:80]
                lines.append(
                    f"| {paper} | `{h.label}` | {h.direction} | {h.outcome} | {clean_stmt} | {clean_snip} |"
                )

        return "\n".join(lines)

    # Default ASCII Terminal Table
    lines: list[str] = [
        f"Academic Proposition Consensus & Controversy Report\n"
        f"Total Papers: {report.total_papers} | Total Hypotheses: {report.total_hypotheses} | Relationships: {len(report.relationships)}\n"
        f"{'-' * 92}"
    ]
    if not report.relationships:
        lines.append("No explicit research propositions or hypotheses detected.")
        return "\n".join(lines)

    row_fmt = "{:<32} {:<10} {:<12} {:<20} {:<14}"
    lines.append(row_fmt.format("Relationship (X -> Y)", "Dominant", "Consensus", "Debate Level", "Papers (Pos/Neg)"))
    lines.append("-" * 92)

    for r in report.relationships:
        rel_disp = f"{r.label_x[:14]} -> {r.label_y[:14]}"
        counts_disp = f"+{len(r.positive_papers)} / -{len(r.negative_papers)} / 0:{len(r.null_papers)}"
        lines.append(
            row_fmt.format(
                rel_disp[:31],
                r.dominant_direction.upper()[:9],
                f"{r.consensus_score * 100:.1f}%",
                r.debate_level[:19],
                counts_disp,
            )
        )
    lines.append("-" * 92)
    return "\n".join(lines)
