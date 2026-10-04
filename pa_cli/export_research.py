"""
pa_cli.export_research — Structured research metadata export for downstream modeling & typesetting.

Supports target formats:
  - jupyter: Pandas DataFrame-ready records JSON or complete starter analysis notebook (.ipynb).
  - typst: Modern Typst project scaffolding (main.typ + refs.bib) ready for `typst compile`.
  - bib / bibtex: Curated, clean BibTeX references file.
  - markdown: Comprehensive literature digest markdown report.
  - json: Full machine-readable metadata and papers export.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .bibtex import format_bibtex_entry
from .project import DEFAULT_ROOT, load_meta, project_files
from .scaffold import load_bibtex


def _extract_paper_records(
    entries: List[Dict[str, Any]],
    pdf_map: Optional[Dict[str, str]] = None,
    topics_data: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Transform raw BibTeX/screening dicts into clean, normalized tabular records."""
    pdf_map = pdf_map or {}
    records: List[Dict[str, Any]] = []

    # Build topic mapping by paper key/stem
    topic_mapping: Dict[str, List[str]] = {}
    if topics_data and "topics" in topics_data:
        for t in topics_data["topics"]:
            lbl = t.get("label", f"Topic {t.get('topic_id', '')}").strip()
            for fn in t.get("filenames", []):
                stem = Path(fn).stem.lower()
                topic_mapping.setdefault(stem, []).append(lbl)

    for e in entries:
        key = e.get("key") or e.get("ID") or e.get("id") or ""
        stem_lower = key.lower()
        title = e.get("title", "Untitled").strip()
        author = e.get("author", "Unknown").strip()
        year_str = str(e.get("year", "")).strip()
        try:
            year = int(year_str) if year_str and year_str.isdigit() else None
        except Exception:
            year = None

        venue = (
            e.get("journal")
            or e.get("booktitle")
            or e.get("publisher")
            or e.get("venue")
            or ""
        ).strip()
        doi = e.get("doi", "").strip()
        arxiv_id = e.get("arxiv_id", "").strip()
        url = e.get("url", "").strip()
        if not url and doi:
            url = f"https://doi.org/{doi}"
        elif not url and arxiv_id:
            url = f"https://arxiv.org/abs/{arxiv_id}"

        abstract = e.get("abstract", "").strip()

        pdf_path = pdf_map.get(key) or pdf_map.get(key.lower()) or None
        has_pdf = bool(pdf_path)

        topics = topic_mapping.get(stem_lower, [])

        records.append({
            "key": key,
            "title": title,
            "author": author,
            "year": year,
            "venue": venue,
            "doi": doi,
            "arxiv_id": arxiv_id,
            "url": url,
            "abstract": abstract,
            "has_pdf": has_pdf,
            "pdf_path": pdf_path,
            "topics": topics,
        })
    return records


def export_to_jupyter_notebook(
    records: List[Dict[str, Any]],
    meta: Optional[Dict[str, Any]] = None,
) -> str:
    """Generate a clean, valid Jupyter Notebook (.ipynb v4) starter analysis."""
    meta = meta or {}
    title = meta.get("title", "Literature Corpus Analysis")
    slug = meta.get("slug", "corpus")
    n_papers = len(records)
    n_pdfs = sum(1 for r in records if r.get("has_pdf"))

    cells = [
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                f"# Literature Analysis: {title}\n",
                "\n",
                "> Generated automatically by **Paper Agent** (Literature & Evidence Intelligence Subsystem)  \n",
                f"> **Project**: `{slug}` | **Total Papers**: {n_papers} | **Downloaded PDFs**: {n_pdfs}  \n",
                f"> **Generated at**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
                "\n",
                "This starter notebook loads the catalogued research papers into a Pandas DataFrame\n",
                "for publication distribution modeling, bibliographic analysis, and evidence exploration.",
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# 1. Load literature records into Pandas DataFrame\n",
                "import json\n",
                "import pandas as pd\n",
                "\n",
                f"raw_records = {json.dumps(records, ensure_ascii=False, indent=2)}\n",
                "\n",
                "df = pd.DataFrame(raw_records)\n",
                'print(f"Loaded {len(df)} papers into DataFrame. Shape: {df.shape}")\n',
                "df.head()",
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# 2. Bibliographic distributions: Years & Top Venues\n",
                'if "year" in df.columns and df["year"].notna().any():\n',
                '    print("--- Publication Year Distribution ---")\n',
                '    print(df["year"].value_counts().sort_index(ascending=False))\n',
                "\n",
                'if "venue" in df.columns and (df["venue"] != "").any():\n',
                '    print("\\n--- Top 10 Publication Venues ---")\n',
                '    print(df[df["venue"] != ""]["venue"].value_counts().head(10))\n',
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# 3. Full-text PDF and DOI Availability\n",
                'pdf_coverage = df["has_pdf"].sum() if "has_pdf" in df.columns else 0\n',
                'doi_coverage = (df["doi"] != "").sum() if "doi" in df.columns else 0\n',
                'print(f"Full-text PDFs available: {pdf_coverage} / {len(df)} ({pdf_coverage/max(len(df),1):.1%})")\n',
                'print(f"Registered DOIs: {doi_coverage} / {len(df)} ({doi_coverage/max(len(df),1):.1%})")\n',
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# 4. Keyword search helper across Title and Abstract\n",
                "def search_corpus(query: str, require_pdf: bool = False):\n",
                '    q = query.lower()\n',
                '    mask = df["title"].str.lower().str.contains(q, na=False) | df["abstract"].str.lower().str.contains(q, na=False)\n',
                "    if require_pdf:\n",
                '        mask = mask & df["has_pdf"]\n',
                '    return df[mask][["key", "title", "year", "venue", "has_pdf"]]\n',
                "\n",
                "# Example search (uncomment and run):\n",
                '# search_corpus("model")\n',
            ],
        },
    ]

    notebook_dict = {
        "cells": cells,
        "metadata": {
            "language_info": {
                "name": "python",
                "version": "3",
            },
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    return json.dumps(notebook_dict, ensure_ascii=False, indent=2)


def export_to_typst(
    records: List[Dict[str, Any]],
    raw_entries: List[Dict[str, Any]],
    meta: Optional[Dict[str, Any]] = None,
    bib_rel_name: str = "refs.bib",
) -> Dict[str, str]:
    """Generate Typst document template and clean BibTeX companion file."""
    meta = meta or {}
    title = meta.get("title", "Literature Review & Evidence Digest")
    desc = meta.get("description", "")
    n_papers = len(records)
    n_pdfs = sum(1 for r in records if r.get("has_pdf"))

    # Generate companion clean BibTeX
    bib_lines = []
    for e in raw_entries:
        try:
            bib_lines.append(format_bibtex_entry(e))
        except Exception:
            pass
    bib_content = "\n\n".join(bib_lines) + "\n"

    # Generate main.typ
    typ_lines = [
        "// Typst Literature Digest Template generated by Paper Agent",
        '#set page(',
        '  paper: "a4",',
        '  margin: (x: 2.2cm, top: 2.5cm, bottom: 2.5cm),',
        '  header: align(right)[#text(8pt, fill: luma(120))[Paper Agent Evidence Digest]],',
        '  numbering: "1",',
        ')',
        '#set text(font: "Libertinus Serif", size: 10.5pt, lang: "en")',
        '#set par(justify: true, leading: 0.65em)',
        "",
        "#align(center)[",
        '  #v(0.8em)',
        f'  #text(size: 17pt, weight: "bold")[{title}]',
        '  #v(0.4em)',
        '  #text(size: 11pt, style: "italic")[Academic Literature & Evidence Intelligence Subsystem]',
        '  #v(0.4em)',
        f'  #text(size: 8.5pt, fill: luma(110))[Generated: {datetime.now().strftime("%Y-%m-%d")} | {n_papers} Papers Catalogued | {n_pdfs} Full-Text PDFs]',
        '  #v(1.2em)',
        "]",
        "",
    ]

    if desc:
        typ_lines.extend([
            "== Overview",
            "",
            desc,
            "",
        ])

    typ_lines.extend([
        "== Catalogued Literature Digest",
        "",
    ])

    for i, r in enumerate(records, 1):
        k = r["key"]
        t = r["title"].replace('"', '\\"')
        a = r["author"]
        y = r["year"] or "n.d."
        v = r["venue"]
        doi = r["doi"]
        has_pdf = " [Full-Text PDF Available]" if r["has_pdf"] else ""

        typ_lines.append(f'=== {i}. {t} @{k}{has_pdf}')
        typ_lines.append(f'- *Authors*: {a}')
        if v:
            typ_lines.append(f'- *Venue*: {v} ({y})')
        else:
            typ_lines.append(f'- *Year*: {y}')
        if doi:
            typ_lines.append(f'- *DOI*: #link("https://doi.org/{doi}")[{doi}]')
        elif r["arxiv_id"]:
            typ_lines.append(f'- *arXiv*: #link("https://arxiv.org/abs/{r["arxiv_id"]}")[{r["arxiv_id"]}]')

        if r["abstract"]:
            abs_text = r["abstract"][:600].replace('"', '\\"').replace("\n", " ")
            typ_lines.append(
                '#block(inset: (left: 8pt), stroke: (left: 2pt + luma(180)))[\n'
                f'  #text(size: 9pt, style: "italic")[{abs_text}...]\n'
                ']'
            )
        typ_lines.append("")

    typ_lines.extend([
        "== References",
        "",
        f'#bibliography("{bib_rel_name}", title: none, style: "ieee")',
        "",
    ])

    typ_content = "\n".join(typ_lines)
    return {
        "main.typ": typ_content,
        "refs.bib": bib_content,
    }


def export_research(
    source: Any,
    target: str = "jupyter",
    out_file: Optional[Union[str, Path]] = None,
    root: Path = DEFAULT_ROOT,
) -> Dict[str, Any]:
    """Export literature corpus to Jupyter/Pandas, Typst, BibTeX, Markdown, or JSON.

    Parameters:
      source: Project slug, Path to .bib/.json, or list of dict entries.
      target: One of ['jupyter', 'typst', 'bib', 'bibtex', 'markdown', 'json'].
      out_file: Destination file or directory path.
      root: Default project storage root.
    """
    target_lower = target.lower().strip()
    if target_lower in ("bibtex", "bib"):
        target_norm = "bib"
    else:
        target_norm = target_lower

    allowed_targets = {"jupyter", "typst", "bib", "markdown", "json"}
    if target_norm not in allowed_targets:
        raise ValueError(
            f"Unsupported target {target!r}. Must be one of: {sorted(allowed_targets)}"
        )

    # 1. Resolve source into raw_entries, meta, pdf_map, topics_data
    meta: Dict[str, Any] = {}
    pdf_map: Dict[str, str] = {}
    topics_data: Optional[Dict[str, Any]] = None
    raw_entries: List[Dict[str, Any]] = []
    slug: Optional[str] = None

    if isinstance(source, (str, Path)):
        src_path = Path(source)
        # Check if source is an existing project slug
        proj_dir = root / str(source)
        if proj_dir.is_dir() and (proj_dir / "meta.json").exists():
            slug = str(source)
            files = project_files(slug, root)
            meta = load_meta(slug, root)
            raw_entries = load_bibtex(files["refs"])
            if files["pdfs"].exists():
                for p in files["pdfs"].glob("*.pdf"):
                    pdf_map[p.stem] = str(p)
                    pdf_map[p.stem.lower()] = str(p)
            topics_file = files["dir"] / "topics.json"
            if topics_file.exists():
                try:
                    topics_data = json.loads(topics_file.read_text(encoding="utf-8"))
                except Exception:
                    pass
        elif src_path.is_file():
            if src_path.suffix.lower() == ".bib":
                raw_entries = load_bibtex(src_path)
                meta = {"title": src_path.stem}
            elif src_path.suffix.lower() == ".json":
                try:
                    data = json.loads(src_path.read_text(encoding="utf-8"))
                    if isinstance(data, dict):
                        raw_entries = data.get("papers") or data.get("entries") or []
                        meta = data.get("meta") or {"title": src_path.stem}
                    elif isinstance(data, list):
                        raw_entries = data
                        meta = {"title": src_path.stem}
                except Exception as e:
                    raise ValueError(f"Failed to load JSON from {src_path}: {e}")
            else:
                raw_entries = load_bibtex(src_path)
                meta = {"title": src_path.stem}
        else:
            raise FileNotFoundError(
                f"Source {source!r} is neither an existing project slug under {root} nor an existing file."
            )
    elif isinstance(source, list):
        raw_entries = source
        meta = {"title": "Exported Corpus"}
    elif isinstance(source, dict):
        raw_entries = source.get("papers") or source.get("entries") or []
        meta = source.get("meta") or {"title": "Exported Corpus"}
    else:
        raise ValueError(f"Unsupported source type: {type(source)}")

    records = _extract_paper_records(raw_entries, pdf_map, topics_data)

    files_written: List[str] = []
    content: Optional[str] = None
    extra_data: Dict[str, Any] = {}

    # 2. Render target
    if target_norm == "jupyter":
        # Check if destination specifies .json vs .ipynb
        is_json_records = out_file and str(out_file).lower().endswith(".json")
        if is_json_records:
            content = json.dumps(records, ensure_ascii=False, indent=2)
        else:
            content = export_to_jupyter_notebook(records, meta)

        if out_file:
            out_p = Path(out_file)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            out_p.write_text(content, encoding="utf-8")
            files_written.append(str(out_p))

    elif target_norm == "typst":
        bib_filename = "refs.bib"
        if out_file:
            out_p = Path(out_file)
            if out_p.is_dir() or str(out_file).endswith(("/", "\\")):
                typ_file = out_p / "main.typ"
                bib_file = out_p / "refs.bib"
            elif out_p.suffix.lower() == ".typ":
                typ_file = out_p
                bib_file = out_p.with_suffix(".bib")
                bib_filename = bib_file.name
            else:
                out_p.mkdir(parents=True, exist_ok=True)
                typ_file = out_p / "main.typ"
                bib_file = out_p / "refs.bib"

            typst_artifacts = export_to_typst(
                records, raw_entries, meta, bib_rel_name=bib_filename
            )
            typ_file.parent.mkdir(parents=True, exist_ok=True)
            typ_file.write_text(typst_artifacts["main.typ"], encoding="utf-8")
            bib_file.write_text(typst_artifacts["refs.bib"], encoding="utf-8")
            files_written.extend([str(typ_file), str(bib_file)])
            content = typst_artifacts["main.typ"]
            extra_data["typst_file"] = str(typ_file)
            extra_data["bib_file"] = str(bib_file)
        else:
            typst_artifacts = export_to_typst(
                records, raw_entries, meta, bib_rel_name=bib_filename
            )
            content = typst_artifacts["main.typ"]
            extra_data["refs_bib"] = typst_artifacts["refs.bib"]

    elif target_norm == "bib":
        bib_lines = []
        for e in raw_entries:
            try:
                bib_lines.append(format_bibtex_entry(e))
            except Exception:
                pass
        content = "\n\n".join(bib_lines) + "\n"
        if out_file:
            out_p = Path(out_file)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            out_p.write_text(content, encoding="utf-8")
            files_written.append(str(out_p))

    elif target_norm == "markdown":
        from .project import project_export as proj_exp
        if slug:
            res = proj_exp(slug, format="markdown", out_file=out_file, root=root)
            return res
        else:
            lines = [
                f"# Literature Digest: {meta.get('title', 'Corpus')}",
                "",
                f"> Total Papers: {len(records)} | PDFs: {len(pdf_map)}",
                "",
            ]
            for i, r in enumerate(records, 1):
                lines.append(f"### {i}. [{r['key']}] {r['title']} ({r['year'] or 'n.d.'})")
                lines.append(f"- **Authors**: {r['author']}")
                if r['venue']:
                    lines.append(f"- **Venue**: {r['venue']}")
                if r['doi']:
                    lines.append(f"- **DOI**: [{r['doi']}](https://doi.org/{r['doi']})")
                if r['abstract']:
                    lines.append(f"- **Abstract**: {r['abstract'][:300]}...")
                lines.append("")
            content = "\n".join(lines)
            if out_file:
                out_p = Path(out_file)
                out_p.parent.mkdir(parents=True, exist_ok=True)
                out_p.write_text(content, encoding="utf-8")
                files_written.append(str(out_p))

    elif target_norm == "json":
        export_dict = {
            "meta": meta,
            "n_papers": len(records),
            "n_pdfs": sum(1 for r in records if r.get("has_pdf")),
            "papers": records,
        }
        content = json.dumps(export_dict, ensure_ascii=False, indent=2)
        if out_file:
            out_p = Path(out_file)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            out_p.write_text(content, encoding="utf-8")
            files_written.append(str(out_p))

    res_dict = {
        "target": target_norm,
        "format": target_norm,
        "n_papers": len(records),
        "n_pdfs": sum(1 for r in records if r.get("has_pdf")),
        "files_written": files_written,
        "out_file": files_written[0] if files_written else None,
        "content_length": len(content) if content else 0,
        "content": content if not files_written else None,
    }
    if slug:
        res_dict["slug"] = slug
    res_dict.update(extra_data)
    return res_dict
