"""
pa_cli.review — auditable source inventory from a corpus of papers.

Pipeline:
  1. Walk corpus_dir for *.pdf / *.md / *.txt (DOCX NOT supported — 2026-07-05)
  2. Extract text:
       - PDF: PyMuPDF
       - MD / TXT: read as UTF-8 (with BOM / encoding-error fallback)
  3. Record extracted text and unverified completeness; deduplicate exact conversions
  4. Build standardized metadata block (authors, year, DOI, venue)
  5. Generate lit review markdown following the v3.2 template

Output is a source inventory. Scientific synthesis and completeness need review.

[ P1-4 FORMAT-EXPANSION ] (2026-07-05): added MD + TXT readers per user request
  (real corpus is 95% MD; previously only PDF was supported, which silently ignored
  most files).
"""

import hashlib
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
        # Bind extraction, metadata and provenance to the same immutable bytes.
        meta = {}
        raw = b''
        try:
            raw = f.read_bytes()
            if ext == '.pdf':
                if not HAS_PYMUPDF:
                    raise RuntimeError('pymupdf-not-installed')
                with fitz.open(stream=raw, filetype='pdf') as doc:
                    metadata = doc.metadata or {}
                    meta = {'title':metadata.get('title',''), 'author':metadata.get('author',''),
                            'subject':metadata.get('subject','')}
                    text_data = {'text':'\n'.join(page.get_text('text') for page in doc),
                                 'pages':len(doc), 'error':None}
            else:
                for encoding in ['utf-8-sig','utf-8','gbk','latin-1']:
                    try:
                        content = raw.decode(encoding);break
                    except UnicodeDecodeError:
                        continue
                text_data = {'text':content,'pages':1,'error':None}
        except Exception as exc:
            text_data = {'text':'','pages':0,'error':type(exc).__name__}
        if ext in ('.md','.txt') and text_data['text'].splitlines()[:1] == ['# Corpus inventory — not scientific synthesis']:
            continue  # Do not ingest this tool's own generated output on the next run.
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
        normalized = re.sub(r'---\s*PDF PAGE\s+\d+\s*---', ' ', text_data['text'], flags=re.I)
        tokens = re.findall(r'\w+', normalized.casefold())
        canonical_text = re.sub(r'\s+', ' ', normalized).strip()
        source = {'path':str(f),'sha256':hashlib.sha256(raw).hexdigest(),
                  'bytes':len(raw),'extension':ext,'extraction_error':text_data.get('error')}
        # Only collapse exact extracted text after known conversion page
        # markers/whitespace. Preserve negation, punctuation and scientific
        # comparisons; an unverified DOI/name/similarity is insufficient.
        duplicate = None
        for previous in papers:
            exact = bool(canonical_text) and canonical_text == previous['_canonical']
            if not text_data.get('error') and exact:
                duplicate = previous;break
        if duplicate is not None:
            duplicate['source_files'].append(source)
            duplicate['duplicate_match'] = 'exact_extracted_text_except_page_markers_and_whitespace'
            continue
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
            "is_full_text": False,
            "completeness": "unverified",
            "text_available": bool(text_data['text']),
            "long_text": word_count >= word_count_min,
            "evidence_basis": "extracted_text" if text_data['text'] else "unavailable",
            "source_files": [source],
            "evidence_id": 'E-'+hashlib.sha256((canonical_text if canonical_text else
                            'unavailable:'+source['sha256']+':'+str(f.resolve())).encode('utf-8')).hexdigest()[:16],
            "_canonical": canonical_text,
            "error": text_data.get("error"),
        })
    for paper in papers:
        paper.pop('_canonical',None)
    return papers


def synthesize(corpus_dir: Path, template: str = "v32",
               word_count_min: int = 1000) -> str:
    """Generate an auditable inventory, never an automatic scientific verdict."""
    corpus = build_corpus_index(corpus_dir, word_count_min)
    return _inventory_markdown(corpus_dir, corpus)


def _inventory_markdown(corpus_dir: Path, corpus: List[Dict[str, Any]]) -> str:
    files = sum(len(p['source_files']) for p in corpus)
    lines = ['# Corpus inventory — not scientific synthesis', '',
             f'**Corpus**: {corpus_dir}', f'**Input files**: {files}',
             f'**Unique sources**: {len(corpus)}', '',
             'Text extraction does not verify article completeness, eligibility or scientific claims.',
             'Support/refute decisions and cross-study conflict interpretation require separate evidence appraisal.', '']
    for i,p in enumerate(corpus,1):
        lines += [f"## {i}. [{p['evidence_id']}] {p['title']}",
                  '- Basis: '+p['evidence_basis']+'; completeness unverified',
                  f"- Words: {p['word_count']}; pages: {p['pages']}",
                  '- DOI candidate (not identity-verified): '+(p['doi'] or 'unresolved')]
        for s in p['source_files']:
            lines.append(f"- Source: {s['path']} | SHA256: {s['sha256']}")
        if p.get('duplicate_match'):
            lines.append('- Conversion grouping heuristic: '+p['duplicate_match'])
        if p.get('error'):
            lines.append('- Extraction error: '+p['error'])
        lines.append('')
    return '\n'.join(lines)+'\n'
