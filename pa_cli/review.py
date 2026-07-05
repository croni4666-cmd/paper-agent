"""
pa_cli.review — synthesize lit review section from a corpus of papers.

Pipeline:
  1. Walk corpus_dir for *.pdf / *.md / *.txt (DOCX NOT supported — 2026-07-05)
  2. Extract text:
       - PDF: PyMuPDF
       - MD / TXT: read as UTF-8 (with BOM / encoding-error fallback)
  3. Classify each paper (full-text vs abstract-only based on word count)
  4. Build standardized metadata block (authors, year, DOI, venue)
  5. Generate lit review markdown following the v3.2 template

Output is a markdown file structured for direct use in academic lit review.

[ P1-4 FORMAT-EXPANSION ] (2026-07-05): added MD + TXT readers per user request
  (real corpus is 95% MD; previously only PDF was supported, which silently ignored
  most files).
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False


# Supported file extensions for build_corpus_index
SUPPORTED_EXTENSIONS = {".pdf", ".md", ".txt"}


def extract_text(path: Path) -> Dict[str, Any]:
    """Extract text from a paper file. Dispatches by extension.

    Returns dict with: text (str), pages (int), error (str|None).
    - .pdf → PyMuPDF
    - .md / .txt → read as UTF-8 with fallback
    - other → returns error="unsupported_extension"
    """
    ext = path.suffix.lower()
    if ext == ".pdf":
        return _extract_text_pdf(path)
    if ext in (".md", ".txt"):
        return _extract_text_plain(path)
    return {"text": "", "pages": 0, "error": f"unsupported_extension:{ext}"}


def _extract_text_pdf(pdf_path: Path) -> Dict[str, Any]:
    """Extract text from a PDF using PyMuPDF."""
    if not HAS_PYMUPDF:
        return {"text": "", "pages": 0, "error": "pymupdf-not-installed"}
    try:
        doc = fitz.open(str(pdf_path))
        all_text = []
        for i, page in enumerate(doc):
            all_text.append(page.get_text("text"))
        doc.close()
        return {"text": "\n".join(all_text), "pages": len(all_text), "error": None}
    except Exception as e:
        return {"text": "", "pages": 0, "error": str(e)[:200]}


def _extract_text_plain(path: Path) -> Dict[str, Any]:
    """Read a plain-text file (MD or TXT) as UTF-8 with fallback.

    - Tries UTF-8 first
    - Falls back to UTF-8 with BOM
    - Falls back to GBK (Chinese Windows files often saved as GBK)
    - On total failure returns error message
    """
    encodings = ["utf-8-sig", "utf-8", "gbk", "latin-1"]
    for enc in encodings:
        try:
            text = path.read_text(encoding=enc)
            return {"text": text, "pages": 1, "error": None}
        except (UnicodeDecodeError, UnicodeError):
            continue
        except Exception as e:
            return {"text": "", "pages": 0, "error": f"read_error:{type(e).__name__}:{str(e)[:200]}"}
    return {"text": "", "pages": 0, "error": "decode_failed_all_encodings"}


def parse_pdf_metadata(pdf_path: Path) -> Dict[str, str]:
    """Extract Title/Author/Subject from PDF metadata block."""
    if pdf_path.suffix.lower() != ".pdf" or not HAS_PYMUPDF:
        return {}
    try:
        doc = fitz.open(str(pdf_path))
        meta = doc.metadata or {}
        doc.close()
        return {
            "title": meta.get("title", "") or "",
            "author": meta.get("author", "") or "",
            "subject": meta.get("subject", "") or "",
            "keywords": meta.get("keywords", "") or "",
            "creator": meta.get("creator", "") or "",
        }
    except Exception:
        return {}


def build_corpus_index(corpus_dir: Path, word_count_min: int = 1000) -> List[Dict[str, Any]]:
    """Walk corpus_dir, extract text from each paper file (PDF / MD / TXT).

    DOCX is NOT supported (user explicitly opted out 2026-07-05 to keep deps minimal).
    """
    papers = []
    # Glob all supported extensions, dedupe by filename
    seen: set = set()
    files: List[Path] = []
    for ext in SUPPORTED_EXTENSIONS:
        for f in sorted(corpus_dir.glob(f"*{ext}")):
            if f.name not in seen:
                seen.add(f.name)
                files.append(f)
    files.sort()  # stable order across extensions

    for f in files:
        ext = f.suffix.lower()
        meta = parse_pdf_metadata(f) if ext == ".pdf" else {}
        text_data = extract_text(f)
        word_count = len(text_data["text"].split()) if text_data["text"] else 0
        # Extract DOI from filename or text
        doi = ""
        m = re.search(r'10\.\d{4,9}/[^\s"]+', f.name)
        if m:
            doi = m.group(0).rstrip("._-")
        elif text_data["text"]:
            m2 = re.search(r'(10\.\d{4,9}/[^\s,;]+)', text_data["text"][:5000])
            if m2:
                doi = m2.group(1).rstrip(".,;)")
        # For MD/TXT: try to extract title from first H1 (# ...)
        title = meta.get("title", "")
        if not title and ext in (".md", ".txt"):
            first_lines = text_data["text"].splitlines()[:5]
            for line in first_lines:
                line = line.strip()
                if line.startswith("# "):
                    title = line[2:].strip()
                    break
            if not title:
                title = f.stem.replace("_", " ").replace("-", " ")
        elif not title:
            title = f.stem.replace("_", " ")
        papers.append({
            "path": str(f),
            "filename": f.name,
            "extension": ext,
            "title": title,
            "author": meta.get("author", ""),
            "subject": meta.get("subject", ""),
            "doi": doi,
            "word_count": word_count,
            "pages": text_data["pages"],
            "is_full_text": word_count >= word_count_min,
            "error": text_data.get("error"),
        })
    return papers


def synthesize(corpus_dir: Path, template: str = "v32",
               word_count_min: int = 1000) -> str:
    """Generate lit review markdown from corpus."""
    corpus = build_corpus_index(corpus_dir, word_count_min)
    if not corpus:
        return f"# Lit Review\n\n(empty corpus: {corpus_dir})\n"
    full_text = [p for p in corpus if p["is_full_text"]]
    abstract_only = [p for p in corpus if not p["is_full_text"]]
    date_str = datetime.now().strftime("%Y-%m-%d")

    md = []
    md.append(f"# Lit Review (auto-synthesized from corpus, {date_str})\n")
    md.append(f"\n**Corpus**: {corpus_dir}\n")
    md.append(f"**Total papers**: {len(corpus)} ({len(full_text)} full-text, {len(abstract_only)} abstract-only)\n")
    md.append(f"**Template**: {template}\n")
    md.append(f"**Total word count**: {sum(p['word_count'] for p in corpus):,}\n")
    md.append("\n---\n\n## Papers (in extraction order)\n\n")

    for i, p in enumerate(corpus, 1):
        status = "✅ FULL TEXT" if p["is_full_text"] else "⚠ abstract-only"
        md.append(f"### {i}. {p['title']} {status}\n\n")
        md.append(f"- **File**: `{p['filename']}`\n")
        if p["author"]:
            md.append(f"- **Author(s)**: {p['author']}\n")
        if p["subject"]:
            md.append(f"- **Venue / Year**: {p['subject']}\n")
        if p["doi"]:
            md.append(f"- **DOI**: {p['doi']}\n")
        md.append(f"- **Pages**: {p['pages']} | **Words**: {p['word_count']:,}\n")
        if p.get("error"):
            md.append(f"- **Error**: {p['error']}\n")
        md.append("\n")

    # Citation impact ranking
    md.append("\n---\n\n## Corpus summary\n\n")
    md.append(f"- **Full-text coverage**: {len(full_text)}/{len(corpus)} ({100*len(full_text)//max(len(corpus),1)}%)\n")
    md.append(f"- **Total words extracted**: {sum(p['word_count'] for p in corpus):,}\n")
    md.append(f"- **DOIs identified**: {sum(1 for p in corpus if p['doi'])}\n")

    # Open issues
    if abstract_only:
        md.append(f"\n### Open issues ({len(abstract_only)} abstract-only papers)\n\n")
        md.append("Per paper-agent v4 principle, after 5 minutes of Cloudflare challenge failure, "
                  "the CLI surfaces these as handoff to user browser action:\n\n")
        for p in abstract_only:
            md.append(f"- `{p['filename']}` ({p['word_count']} words) — {p['title'][:80]}\n")

    md.append("\n---\n*Generated by pa-cli v3.2 review command. For richer synthesis, use the llm-driven review template with explicit full-text quotes per paper.*\n")
    return "".join(md)