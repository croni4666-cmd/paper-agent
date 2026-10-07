"""Evolutionary citation and methodology lineage engine (pa lineage).

ROADMAP [P1-23] implementation:
Traces methodology evolution (Baseline model -> Critique -> Extension -> Paradigm shift)
by joining citation graphs / BibTeX metadata with methodology section fingerprints.

Supports:
- Econometric & causal inference lineages (OLS -> TWFE -> Staggered DID -> SDID)
- Macro & structural modeling lineages (RBC -> DSGE -> HANK)
- Machine learning & AI lineages (Linear -> Trees -> Neural -> Transformers -> LLM)
- Visual Mermaid diagrams, terminal ASCII lineage trees, academic markdown digests, and JSON DAGs.

100% offline-first; pure local citation graphs, BibTeX, and PDF parsing.
Zero cloud infra or paid APIs.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


# ==============================================================================
# Canonical Methodology Signatures & Taxonomies
# ==============================================================================

METHOD_TAXONOMY = [
    # 1. Causal Econometrics
    {
        "key": "staggered_did",
        "name": "Staggered Difference-in-Differences",
        "family": "causal_inference",
        "rank": 4,
        "pattern": re.compile(r"\b(?:staggered\s*(?:difference-in-differences|DID)|Callaway\s*and\s*Sant\'?Anna|Sun\s*and\s*Abraham|Goodman-Bacon|de\s*Chaisemartin|多期DID|交错DID)\b", re.IGNORECASE),
    },
    {
        "key": "synthetic_control",
        "name": "Synthetic Control / SDID",
        "family": "causal_inference",
        "rank": 4,
        "pattern": re.compile(r"\b(?:synthetic\s*control|SDID|synthetic\s*difference-in-differences|Abadie|合成控制法)\b", re.IGNORECASE),
    },
    {
        "key": "rdd",
        "name": "Regression Discontinuity Design (RDD)",
        "family": "causal_inference",
        "rank": 3,
        "pattern": re.compile(r"\b(?:regression\s*discontinuity|fuzzy\s*RDD|sharp\s*RDD|\bRDD\b|断点回归)\b", re.IGNORECASE),
    },
    {
        "key": "iv_2sls",
        "name": "Instrumental Variables (IV / 2SLS)",
        "family": "causal_inference",
        "rank": 2,
        "pattern": re.compile(r"\b(?:instrumental\s*variable[s]?|2SLS|two-stage\s*least\s*squares|\bIV\b|工具变量法)\b", re.IGNORECASE),
    },
    {
        "key": "twfe",
        "name": "Two-Way Fixed Effects (TWFE)",
        "family": "causal_inference",
        "rank": 2,
        "pattern": re.compile(r"\b(?:two-way\s*fixed\s*effects|TWFE|fixed\s*effects\s*model|双向固定效应)\b", re.IGNORECASE),
    },
    {
        "key": "ols",
        "name": "Ordinary Least Squares (OLS)",
        "family": "causal_inference",
        "rank": 1,
        "pattern": re.compile(r"\b(?:ordinary\s*least\s*squares|\bOLS\b|pooled\s*OLS|普通最小二乘)\b", re.IGNORECASE),
    },

    # 2. Macro & Structural Estimation
    {
        "key": "hank",
        "name": "Heterogeneous Agent New Keynesian (HANK)",
        "family": "macro_structural",
        "rank": 4,
        "pattern": re.compile(r"\b(?:HANK|heterogeneous\s*agent\s*new\s*keynesian|Kaplan-Moll-Violante)\b", re.IGNORECASE),
    },
    {
        "key": "dsge",
        "name": "DSGE Model (Smets-Wouters)",
        "family": "macro_structural",
        "rank": 3,
        "pattern": re.compile(r"\b(?:DSGE|dynamic\s*stochastic\s*general\s*equilibrium|Smets-Wouters)\b", re.IGNORECASE),
    },
    {
        "key": "rbc",
        "name": "Real Business Cycle (RBC)",
        "family": "macro_structural",
        "rank": 2,
        "pattern": re.compile(r"\b(?:RBC|real\s*business\s*cycle|Kydland-Prescott)\b", re.IGNORECASE),
    },

    # 3. Machine Learning & Natural Language Processing
    {
        "key": "llm",
        "name": "Large Language Model / Transformer",
        "family": "machine_learning",
        "rank": 4,
        "pattern": re.compile(r"\b(?:large\s*language\s*model|LLM|transformer|GPT|BERT|attention\s*mechanism)\b", re.IGNORECASE),
    },
    {
        "key": "deep_learning",
        "name": "Deep Neural Network (DNN / CNN / LSTM)",
        "family": "machine_learning",
        "rank": 3,
        "pattern": re.compile(r"\b(?:neural\s*network|deep\s*learning|\bCNN\b|\bLSTM\b|\bMLP\b)\b", re.IGNORECASE),
    },
    {
        "key": "tree_models",
        "name": "Tree-based Ensemble (Random Forest / XGBoost)",
        "family": "machine_learning",
        "rank": 2,
        "pattern": re.compile(r"\b(?:random\s*forest|XGBoost|gradient\s*boosting|LightGBM)\b", re.IGNORECASE),
    },
]


# ==============================================================================
# Data Structures
# ==============================================================================

@dataclass
class LineageNode:
    """Represents an academic paper and its detected methodology fingerprint."""
    paper_id: str
    title: str
    authors: str
    year: int
    methods: list[str]  # e.g. ["twfe", "staggered_did"]
    method_names: list[str]
    primary_family: str
    paradigm_role: str  # "foundational", "critique", "extension", "application"
    citations_count: int = 0
    parents: list[str] = None  # ancestor paper_ids
    children: list[str] = None  # successor paper_ids

    def __post_init__(self):
        if self.parents is None:
            self.parents = []
        if self.children is None:
            self.children = []

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LineageEdge:
    """Directed evolutionary relationship between two methodology papers."""
    source: str
    target: str
    relation_type: str  # "evolves_to", "critiques", "extends", "applies"
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MethodologyLineage:
    """Full methodology lineage graph and chronological transition paths."""
    total_papers: int
    nodes: dict[str, LineageNode]
    edges: list[LineageEdge]
    families_detected: list[str]
    evolution_paths: list[list[str]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_papers": self.total_papers,
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "edges": [e.to_dict() for e in self.edges],
            "families_detected": self.families_detected,
            "evolution_paths": self.evolution_paths,
        }


# ==============================================================================
# Methodology Detection & Fingerprinting
# ==============================================================================

def detect_methodologies(text: str) -> Tuple[list[str], list[str], str]:
    """Detect methodology tags, human-readable names, and primary family."""
    found_keys: list[str] = []
    found_names: list[str] = []
    family_counts: dict[str, int] = {}

    for spec in METHOD_TAXONOMY:
        if spec["pattern"].search(text):
            found_keys.append(spec["key"])
            found_names.append(spec["name"])
            fam = spec["family"]
            family_counts[fam] = family_counts.get(fam, 0) + 1

    primary_family = (
        max(family_counts.items(), key=lambda x: x[1])[0]
        if family_counts
        else "general_empirical"
    )

    return found_keys, found_names, primary_family


def detect_paradigm_role(text: str, methods: list[str], year: int) -> str:
    """Classify the paper's role in methodology lineage."""
    lower = text.lower()
    # Check if critique
    if re.search(r"\b(?:critique|bias\s*in|failure\s*of|flaws\s*in|negative\s*weights|fallacy)\b", lower):
        return "critique"
    # Check if foundational / seminal
    if re.search(r"\b(?:propose\s*a\s*(?:new|novel)|introduce\s*a\s*(?:new|novel)|seminal|foundational|groundbreaking)\b", lower):
        return "foundational"
    # Check if extension
    if re.search(r"\b(?:extend|extension|generalize|relaxing\s*the\s*assumption|robust\s*to)\b", lower):
        return "extension"
    # Default: application
    return "application"


# ==============================================================================
# Graph Construction & Evolution Paths
# ==============================================================================

def build_lineage_graph(papers: list[dict[str, Any]]) -> MethodologyLineage:
    """Construct chronological DAG joining citations and methodology ranks."""
    nodes: dict[str, LineageNode] = {}
    edges: list[LineageEdge] = []
    families: set[str] = set()

    # 1. Instantiate LineageNode for each paper
    for p in papers:
        pid = p.get("paper_id") or p.get("id") or p.get("key") or "paper"
        title = p.get("title") or "Untitled Paper"
        authors = p.get("authors") or "Unknown"
        year = int(p.get("year") or 2020)
        full_text = f"{title}\n{p.get('abstract', '')}\n{p.get('content', '')}"

        keys, names, fam = detect_methodologies(full_text)
        role = p.get("role") or detect_paradigm_role(full_text, keys, year)
        if fam != "general_empirical":
            families.add(fam)

        nodes[pid] = LineageNode(
            paper_id=pid,
            title=title,
            authors=authors,
            year=year,
            methods=keys,
            method_names=names,
            primary_family=fam,
            paradigm_role=role,
            citations_count=int(p.get("citations_count", 0)),
        )

    # 2. Infer Evolutionary Edges (Parent -> Child)
    # Sort chronologically
    sorted_pids = sorted(nodes.keys(), key=lambda k: nodes[k].year)

    for i, p_early_id in enumerate(sorted_pids):
        node_early = nodes[p_early_id]
        early_methods = set(node_early.methods)

        for p_late_id in sorted_pids[i + 1:]:
            node_late = nodes[p_late_id]
            late_methods = set(node_late.methods)

            # Check if papers share methodology family or methods
            # Generic 'general_empirical' or empty methods must not fabricate evolution edges
            has_substantive_methods = bool(early_methods and late_methods)
            substantive_family = (node_early.primary_family != "general_empirical" and
                                  node_early.primary_family == node_late.primary_family)
            shares_methods = bool(early_methods & late_methods)

            # Connect only if they share specific methods or a specialized family
            if (shares_methods or (substantive_family and has_substantive_methods)) and node_early.year < node_late.year:
                # Determine relationship type
                if node_late.paradigm_role == "critique":
                    rel = "critiques"
                    expl = f"Evaluates limitations or biases in {node_early.title[:40]}"
                elif node_late.paradigm_role == "extension":
                    rel = "extends"
                    expl = f"Extends methodological specification of {node_early.title[:40]}"
                else:
                    rel = "evolves_to"
                    expl = f"Methodological progression ({node_early.year} -> {node_late.year})"

                # Add directed edge
                edges.append(LineageEdge(source=p_early_id, target=p_late_id, relation_type=rel, explanation=expl))
                node_early.children.append(p_late_id)
                node_late.parents.append(p_early_id)

    # 3. Compute distinct evolution paths (longest paths in DAG)
    paths: list[list[str]] = []
    roots = [pid for pid, n in nodes.items() if not n.parents]
    for r in roots:
        # Simple DFS up to length 5
        def dfs(curr: str, curr_path: list[str]):
            curr_node = nodes[curr]
            if not curr_node.children:
                if len(curr_path) > 1:
                    paths.append(curr_path[:])
                return
            for child in curr_node.children:
                if child not in curr_path and len(curr_path) < 5:
                    dfs(child, curr_path + [child])

        dfs(r, [r])

    return MethodologyLineage(
        total_papers=len(nodes),
        nodes=nodes,
        edges=edges,
        families_detected=sorted(list(families)),
        evolution_paths=paths,
    )


# ==============================================================================
# PDF & Corpus Extraction
# ==============================================================================

def extract_project_lineage(project_slug: str, root: Optional[Path] = None) -> MethodologyLineage:
    """Extract papers and citation metadata from a project corpus and build lineage."""
    from .project import DEFAULT_ROOT
    base_root = root or DEFAULT_ROOT
    proj_dir = base_root / project_slug
    if not proj_dir.is_dir():
        raise FileNotFoundError(f"Project directory not found: {proj_dir}")

    # Read project meta.json or bibtex
    papers: list[dict[str, Any]] = []
    meta_path = proj_dir / "meta.json"
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            for p_dict in meta.get("papers", []):
                papers.append(p_dict)
        except Exception:
            pass

    # Read PDF text files if meta is sparse
    pdf_files = list(proj_dir.glob("*.pdf")) + list((proj_dir / "pdfs").glob("*.pdf"))
    if not papers:
        import fitz
        for pdf_path in sorted(pdf_files):
            try:
                doc = fitz.open(str(pdf_path))
                text = "\n".join([page.get_text() for page in doc[:3]])
                doc.close()
                # Extract year heuristic
                m_year = re.search(r"\b(19\d\d|20\d\d)\b", text)
                year = int(m_year.group(1)) if m_year else 2020
                papers.append({
                    "paper_id": pdf_path.stem,
                    "title": pdf_path.stem.replace("_", " ").title(),
                    "authors": "Literature Corpus",
                    "year": year,
                    "content": text,
                })
            except Exception:
                continue

    return build_lineage_graph(papers)


# ==============================================================================
# Report Formatters
# ==============================================================================

def format_lineage_tree(lineage: MethodologyLineage) -> str:
    """Format lineage as a clean terminal ASCII tree diagram."""
    lines: list[str] = [
        f"Methodology Evolution Lineage Tree\n"
        f"Total Papers: {lineage.total_papers} | Families: {', '.join(lineage.families_detected) or 'empirical'}\n"
        f"{'-' * 88}"
    ]
    if not lineage.nodes:
        lines.append("No papers available to construct lineage.")
        return "\n".join(lines)

    # Roots (nodes with no parents)
    roots = sorted(
        [n for n in lineage.nodes.values() if not n.parents],
        key=lambda n: n.year,
    )
    if not roots:
        roots = sorted(list(lineage.nodes.values()), key=lambda n: n.year)[:1]

    visited: set[str] = set()

    def print_node(node: LineageNode, prefix: str = "", is_last: bool = True):
        visited.add(node.paper_id)
        connector = "\\-- " if is_last else "+-- "
        methods_str = f" [{', '.join(node.method_names)}]" if node.method_names else ""
        lines.append(f"{prefix}{connector}[{node.year}] {node.authors} - \"{node.title[:45]}\" ({node.paradigm_role.upper()}){methods_str}")

        child_prefix = prefix + ("    " if is_last else "|   ")
        children = [lineage.nodes[cid] for cid in node.children if cid in lineage.nodes]
        for idx, child in enumerate(children):
            if child.paper_id not in visited:
                print_node(child, child_prefix, is_last=(idx == len(children) - 1))

    for idx, r in enumerate(roots):
        print_node(r, is_last=(idx == len(roots) - 1))

    # Print remaining unvisited nodes
    unvisited = [n for n in lineage.nodes.values() if n.paper_id not in visited]
    if unvisited:
        lines.append("\nAdditional Related Studies:")
        for u in sorted(unvisited, key=lambda n: n.year):
            methods_str = f" [{', '.join(u.method_names)}]" if u.method_names else ""
            lines.append(f"  * [{u.year}] {u.authors}: {u.title[:45]} ({u.paradigm_role}){methods_str}")

    lines.append("-" * 88)
    return "\n".join(lines)


def format_lineage_mermaid(lineage: MethodologyLineage) -> str:
    """Generate Mermaid directed flowchart diagram."""
    lines: list[str] = ["```mermaid", "graph TD"]

    # Add node definitions
    for pid, n in lineage.nodes.items():
        clean_id = re.sub(r"\W+", "_", pid).strip("_")
        clean_title = n.title.replace('"', "'")[:30]
        role_label = n.paradigm_role.upper()
        lines.append(f'    {clean_id}["[{n.year}] {clean_title}<br/><i>{role_label}</i>"]')

    # Add edges
    for e in lineage.edges:
        src = re.sub(r"\W+", "_", e.source).strip("_")
        tgt = re.sub(r"\W+", "_", e.target).strip("_")
        lines.append(f"    {src} -->|{e.relation_type}| {tgt}")

    lines.append("```")
    return "\n".join(lines)


def format_lineage_markdown(lineage: MethodologyLineage) -> str:
    """Format academic Markdown methodology evolution narrative."""
    lines: list[str] = [
        "# Methodology Lineage & Evolution Digest\n",
        f"- **Total Papers in Lineage**: {lineage.total_papers}",
        f"- **Methodology Domains**: {', '.join(lineage.families_detected) or 'Empirical Social Science'}\n",
        "### Evolutionary Timeline\n",
        "| Year | Paper / Authors | Primary Methods | Paradigm Role | Key Innovation / Extension |",
        "|---|---|---|---|---|",
    ]
    for n in sorted(lineage.nodes.values(), key=lambda x: x.year):
        meth_str = ", ".join(n.method_names) if n.method_names else "Empirical Standard"
        clean_title = n.title.replace("|", "/")
        lines.append(
            f"| **{n.year}** | {n.authors} (*{clean_title[:35]}*) | `{meth_str}` | {n.paradigm_role.upper()} | {n.primary_family} |"
        )

    if lineage.edges:
        lines.append("\n### Methodology Evolution Graph (Mermaid)\n")
        lines.append(format_lineage_mermaid(lineage))

    return "\n".join(lines)


def format_lineage_json(lineage: MethodologyLineage) -> str:
    """Export complete lineage DAG as JSON."""
    return json.dumps(lineage.to_dict(), indent=2, ensure_ascii=False)
