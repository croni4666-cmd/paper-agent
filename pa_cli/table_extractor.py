"""
pa_cli.table_extractor — Local offline PDF tabular data extractor.

Implements ROADMAP [P0-17]:
  1. High-fidelity offline table extraction using PyMuPDF cell geometry and text-flow heuristics.
  2. Native support for grid tables, LaTeX three-line tables (\\toprule/\\midrule/\\bottomrule),
     and whitespace-aligned academic empirical tables.
  3. Automatic association of table titles (e.g. Table 1, 表 1) and footnotes/notes.
  4. Table semantic classification:
     - descriptive_statistics
     - baseline_regression
     - correlation_matrix
     - robustness_checks
     - mechanism_analysis
     - heterogeneity
     - general
  5. Multi-format export: Markdown, JSON, and CSV.
  6. Project corpus batch extraction across all catalogued PDFs.
"""

from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    import pymupdf as fitz
except ImportError:
    import fitz

from .project import DEFAULT_ROOT, project_files


# ──────────────────────────────────────────────────────────────────────
# Table Classification Patterns
# ──────────────────────────────────────────────────────────────────────

TABLE_CLASSIFICATION_RULES = [
    {
        "type": "descriptive_statistics",
        "patterns": [
            r"descriptive\s+statistics?",
            r"summary\s+statistics?",
            r"sample\s+statistics?",
            r"描述性统计",
            r"变量描述",
            r"\bmean\b.*\bstd(?:\.|\s+dev)?\b",
        ],
    },
    {
        "type": "baseline_regression",
        "patterns": [
            r"baseline\s+regressions?",
            r"benchmark\s+regressions?",
            r"main\s+results?",
            r"ols\s+regressions?",
            r"fixed\s+effects?\s+regressions?",
            r"基准回归",
            r"主回归",
            r"实证结果",
        ],
    },
    {
        "type": "correlation_matrix",
        "patterns": [
            r"correlation\s+matrix",
            r"correlations?",
            r"pearson\s+correlation",
            r"相关系数矩阵",
            r"相关性分析",
        ],
    },
    {
        "type": "robustness_checks",
        "patterns": [
            r"\brobustness\b",
            r"\bplacebo\b",
            r"alternative\s+measures?",
            r"alternative\s+samples?",
            r"稳健性",
            r"替换变量",
            r"安慰剂",
        ],
    },
    {
        "type": "mechanism_analysis",
        "patterns": [
            r"\bmechanisms?\b",
            r"\bchannels?\b",
            r"\bmediat(?:ion|ing)\b",
            r"机制检验",
            r"中介效应",
            r"作用机制",
        ],
    },
    {
        "type": "heterogeneity",
        "patterns": [
            r"\bheterogeneity\b",
            r"\bsubsample\b",
            r"group\s+regressions?",
            r"异质性",
            r"分组回归",
        ],
    },
]


def classify_table(title: str, text: str) -> str:
    """Classify the empirical type of a table based on its title and text."""
    combined = f"{title} {text}".lower()
    for rule in TABLE_CLASSIFICATION_RULES:
        for pat in rule["patterns"]:
            if re.search(pat, combined, re.IGNORECASE):
                return rule["type"]
    return "general"


def _format_markdown_table(headers: List[str], rows: List[List[str]]) -> str:
    """Generate clean Markdown table syntax from headers and data rows."""
    if not headers and not rows:
        return ""
    if not headers and rows:
        headers = [f"Col {i+1}" for i in range(len(rows[0]))]

    num_cols = len(headers)
    normalized_rows = []
    for r in rows:
        if len(r) < num_cols:
            r = r + [""] * (num_cols - len(r))
        elif len(r) > num_cols:
            r = r[:num_cols]
        normalized_rows.append([c.strip().replace("\n", " ").replace("|", "\\|") for c in r])

    norm_headers = [h.strip().replace("\n", " ").replace("|", "\\|") for h in headers]

    lines = [
        "| " + " | ".join(norm_headers) + " |",
        "| " + " | ".join(["---"] * num_cols) + " |",
    ]
    for r in normalized_rows:
        lines.append("| " + " | ".join(r) + " |")

    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────
# Heuristic Text-Aligned Table Parser
# ──────────────────────────────────────────────────────────────────────

def _extract_text_aligned_table(
    lines: List[str],
) -> Optional[Tuple[str, List[str], List[List[str]], str]]:
    """Heuristic extractor for academic tables formatted with whitespace or rules."""
    title = ""
    notes = ""
    header_line_idx = -1
    table_lines: List[str] = []

    # 1. Look for table title (e.g. Table 1, 表 1)
    for idx, line in enumerate(lines):
        clean = line.strip()
        if re.match(r"^(?:Table\s+\d+|表\s*\d+)[.:\s]", clean, re.IGNORECASE):
            title = clean
            header_line_idx = idx + 1
            break

    if header_line_idx == -1:
        return None

    # 2. Collect candidate rows until notes or empty line sequence
    for line in lines[header_line_idx:]:
        clean = line.strip()
        if not clean:
            continue
        # Check if line is Notes/Footnotes
        if re.match(r"^(?:Notes?|Note|注[：:]|\*|Standard\s+errors)", clean, re.IGNORECASE):
            notes = clean
            break
        table_lines.append(clean)

    if len(table_lines) < 2:
        return None

    # 3. Parse headers and rows
    # Split using 2 or more spaces or tabs
    header_tokens = re.split(r"\s{2,}|\t", table_lines[0].strip())
    if len(header_tokens) < 2:
        # Fallback to whitespace split if header line doesn't have double space
        header_tokens = table_lines[0].split()

    if len(header_tokens) < 2:
        return None

    rows: List[List[str]] = []
    for row_line in table_lines[1:]:
        tokens = re.split(r"\s{2,}|\t", row_line.strip())
        if len(tokens) < 2:
            tokens = row_line.split()
        if tokens:
            rows.append(tokens)

    if not rows:
        return None

    return title, header_tokens, rows, notes


# ──────────────────────────────────────────────────────────────────────
# Page-Level Extraction
# ──────────────────────────────────────────────────────────────────────

def extract_tables_from_page(page: fitz.Page, page_number: int) -> List[Dict[str, Any]]:
    """Extract all tabular structures on a single PDF page."""
    extracted_tables: List[Dict[str, Any]] = []

    # 1. Native PyMuPDF TableFinder
    native_tables = []
    try:
        tabs = page.find_tables()
        if tabs and tabs.tables:
            native_tables = tabs.tables
    except Exception:
        native_tables = []

    # Extract all text blocks on the page for title/note association
    page_text = page.get_text("text") or ""
    page_lines = page_text.splitlines()

    if native_tables:
        for idx, tab in enumerate(native_tables, 1):
            raw_matrix = tab.extract()
            if not raw_matrix or len(raw_matrix) < 2:
                continue

            headers = [str(c or "") for c in raw_matrix[0]]
            data_rows = [[str(c or "") for c in row] for row in raw_matrix[1:]]

            # Try to associate Table title from text preceding table bbox
            bbox = tab.bbox
            title = f"Table on Page {page_number}"
            notes = ""

            for line in page_lines:
                clean = line.strip()
                if re.match(r"^(?:Table\s+\d+|表\s*\d+)[.:\s]", clean, re.IGNORECASE):
                    title = clean
                    break

            for line in page_lines:
                clean = line.strip()
                if re.match(r"^(?:Notes?|Note|注[：:]|\*|Standard\s+errors)", clean, re.IGNORECASE):
                    notes = clean
                    break

            md_content = _format_markdown_table(headers, data_rows)
            table_type = classify_table(title, md_content)

            extracted_tables.append({
                "table_id": idx,
                "page": page_number,
                "title": title,
                "type": table_type,
                "bbox": list(bbox),
                "row_count": len(raw_matrix),
                "col_count": len(headers),
                "headers": headers,
                "rows": data_rows,
                "notes": notes,
                "markdown": md_content,
            })

    # 2. Heuristic fallback for text-aligned academic tables (if native didn't find any)
    if not extracted_tables:
        parsed = _extract_text_aligned_table(page_lines)
        if parsed:
            title, headers, rows, notes = parsed
            md_content = _format_markdown_table(headers, rows)
            table_type = classify_table(title, md_content)
            extracted_tables.append({
                "table_id": 1,
                "page": page_number,
                "title": title or f"Table on Page {page_number}",
                "type": table_type,
                "bbox": [0.0, 0.0, float(page.rect.width), float(page.rect.height)],
                "row_count": len(rows) + 1,
                "col_count": len(headers),
                "headers": headers,
                "rows": rows,
                "notes": notes,
                "markdown": md_content,
            })

    return extracted_tables


# ──────────────────────────────────────────────────────────────────────
# Full-PDF and Project Extraction
# ──────────────────────────────────────────────────────────────────────

def extract_tables(pdf_path: Union[str, Path]) -> Dict[str, Any]:
    """Extract all empirical tables across an entire PDF file."""
    path = Path(pdf_path)
    if not path.is_file():
        raise FileNotFoundError(f"PDF file does not exist: {path}")

    doc = fitz.open(str(path))
    all_tables: List[Dict[str, Any]] = []
    global_counter = 1

    for page_num in range(len(doc)):
        page = doc[page_num]
        page_tables = extract_tables_from_page(page, page_num + 1)
        for t in page_tables:
            t["global_id"] = global_counter
            all_tables.append(t)
            global_counter += 1

    doc.close()

    return {
        "file_name": path.name,
        "file_path": str(path.resolve()),
        "total_tables": len(all_tables),
        "tables": all_tables,
    }


def extract_project_tables(slug: str, root: Path = DEFAULT_ROOT) -> Dict[str, Any]:
    """Batch extract all tables across all full-text PDFs in a project corpus."""
    files = project_files(slug, root)
    if not files["dir"].exists():
        raise FileNotFoundError(f"Project {slug!r} does not exist at {root}")

    pdf_dir = files["pdfs"]
    if not pdf_dir.exists():
        return {
            "slug": slug,
            "n_pdfs": 0,
            "total_tables": 0,
            "papers": [],
        }

    pdf_files = list(pdf_dir.glob("*.pdf"))
    papers_results = []
    total_tables_count = 0

    for p in pdf_files:
        try:
            res = extract_tables(p)
            papers_results.append(res)
            total_tables_count += res["total_tables"]
        except Exception as e:
            papers_results.append({
                "file_name": p.name,
                "file_path": str(p),
                "total_tables": 0,
                "tables": [],
                "error": str(e),
            })

    return {
        "slug": slug,
        "n_pdfs": len(pdf_files),
        "total_tables": total_tables_count,
        "papers": papers_results,
    }


def render_tables_markdown(data: Dict[str, Any]) -> str:
    """Format extracted tables into a clean Markdown document."""
    lines = []
    if "papers" in data:
        slug = data.get("slug", "Corpus")
        lines.append(f"# Catalogued Empirical Tables: Project `{slug}`\n")
        lines.append(f"> Total PDFs scanned: {data.get('n_pdfs', 0)} | Total tables extracted: {data.get('total_tables', 0)}\n")

        for p in data.get("papers", []):
            fname = p.get("file_name", "?")
            lines.append(f"## Paper: `{fname}`\n")
            if "error" in p:
                lines.append(f"> *Extraction error: {p['error']}*\n")
                continue
            tables = p.get("tables", [])
            if not tables:
                lines.append("> *No empirical tables detected in document.*\n")
                continue
            for t in tables:
                lines.append(f"### {t.get('title', 'Table')} (Page {t.get('page')})\n")
                lines.append(f"- **Type**: `{t.get('type')}` ({t.get('row_count')} rows × {t.get('col_count')} columns)\n")
                lines.append(t.get("markdown", ""))
                lines.append("")
                if t.get("notes"):
                    lines.append(f"*{t['notes']}*\n")
                lines.append("")
    else:
        fname = data.get("file_name", "Paper")
        lines.append(f"# Empirical Tables Extracted: `{fname}`\n")
        lines.append(f"> Total tables extracted: {data.get('total_tables', 0)}\n")

        tables = data.get("tables", [])
        if not tables:
            lines.append("> *No empirical tables detected in document.*\n")
        for t in tables:
            lines.append(f"## {t.get('title', 'Table')} (Page {t.get('page')})\n")
            lines.append(f"- **Type**: `{t.get('type')}` ({t.get('row_count')} rows × {t.get('col_count')} columns)\n")
            lines.append(t.get("markdown", ""))
            lines.append("")
            if t.get("notes"):
                lines.append(f"*{t['notes']}*\n")
            lines.append("")

    return "\n".join(lines)


def export_tables_to_csv(tables_data: Dict[str, Any], out_dir: Union[str, Path]) -> List[str]:
    """Export each extracted table as a standalone CSV file into destination directory."""
    dest = Path(out_dir)
    dest.mkdir(parents=True, exist_ok=True)
    saved_files: List[str] = []

    all_tables = []
    if "papers" in tables_data:
        for p in tables_data.get("papers", []):
            stem = Path(p.get("file_name", "paper")).stem
            for t in p.get("tables", []):
                all_tables.append((f"{stem}_table_{t.get('global_id', t.get('table_id', 1))}.csv", t))
    else:
        stem = Path(tables_data.get("file_name", "paper")).stem
        for t in tables_data.get("tables", []):
            all_tables.append((f"{stem}_table_{t.get('global_id', t.get('table_id', 1))}.csv", t))

    for filename, t in all_tables:
        csv_path = dest / filename
        with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            if t.get("headers"):
                writer.writerow(t["headers"])
            for row in t.get("rows", []):
                writer.writerow(row)
        saved_files.append(str(csv_path))

    return saved_files
