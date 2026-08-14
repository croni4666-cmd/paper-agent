#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
读 3 篇 PDF 提取关键内容 (abstract + intro + conclusion)
"""
import sys
import re
from pathlib import Path

PDF_DIR = Path(r"G:\minimax - workspace\Paper agent\search_results\pdfs")
OUT = Path(r"G:\minimax - workspace\Paper agent\search_results\pdf_extracted.txt")

# 尝试 pdfplumber -> pypdf -> PyPDF2 -> fitz
def get_reader():
    try:
        import pdfplumber
        return ("pdfplumber", pdfplumber)
    except ImportError:
        pass
    try:
        from pypdf import PdfReader
        return ("pypdf", PdfReader)
    except ImportError:
        pass
    try:
        from PyPDF2 import PdfReader
        return ("PyPDF2", PdfReader)
    except ImportError:
        pass
    try:
        import fitz
        return ("fitz", fitz)
    except ImportError:
        pass
    return (None, None)

def extract_text(reader_lib, path):
    name, mod = reader_lib
    if name == "pdfplumber":
        text = []
        with mod.open(path) as pdf:
            for p in pdf.pages:
                t = p.extract_text() or ""
                text.append(t)
        return "\n".join(text)
    elif name in ("pypdf", "PyPDF2"):
        r = mod(str(path))
        text = []
        for p in r.pages:
            try:
                t = p.extract_text() or ""
            except Exception:
                t = ""
            text.append(t)
        return "\n".join(text)
    elif name == "fitz":
        doc = mod.open(str(path))
        text = []
        for p in doc:
            text.append(p.get_text())
        doc.close()
        return "\n".join(text)
    return ""

def find_section(text, *names, max_chars=2500):
    """找指定 section (Abstract / Introduction / Conclusion)"""
    for name in names:
        # 匹配 "Abstract" "ABSTRACT" "1. Introduction" 等
        for pat in [name, name.upper(), name.title()]:
            idx = text.find(pat)
            if idx >= 0:
                # 找下一个 section
                chunk = text[idx:idx+max_chars]
                # 找下一个数字+点+大写 或 "References" 等
                next_section = re.search(r"\n\s*\d+\.?\s+[A-Z][A-Za-z ]{2,30}\n|\nReferences\n|\nREFERENCES\n|\nDiscussion\n", chunk[100:])
                if next_section:
                    chunk = chunk[:100 + next_section.start()]
                return chunk
    return ""

def main():
    lib = get_reader()
    if not lib[0]:
        print("No PDF library found. Need pdfplumber/pypdf/PyPDF2/fitz")
        sys.exit(1)
    print(f"Using: {lib[0]}")
    print(f"=" * 60)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out_lines = []
    for pdf in sorted(PDF_DIR.glob("*.pdf")):
        out_lines.append(f"\n{'='*70}\n# FILE: {pdf.name}\n{'='*70}\n")
        try:
            text = extract_text(lib, pdf)
        except Exception as e:
            out_lines.append(f"ERROR: {e}\n")
            continue
        # 提取关键 section
        abstract = find_section(text, "Abstract", "ABSTRACT")
        intro = find_section(text, "Introduction", "INTRODUCTION", "1. Introduction")
        conclusion = find_section(text, "Conclusion", "CONCLUSIONS", "Conclusions", "Discussion", "DISCUSSION")
        # fallback：前 3000 字符
        head = text[:3000] if text else "(no text)"
        out_lines.append(f"\n## ABSTRACT\n{abstract if abstract else '(not found)'}\n")
        out_lines.append(f"\n## INTRODUCTION (first 1500 chars)\n{intro[:1500] if intro else '(not found)'}\n")
        out_lines.append(f"\n## CONCLUSION / DISCUSSION (first 2000 chars)\n{conclusion[:2000] if conclusion else '(not found)'}\n")
        # 也存 head 兜底
        out_lines.append(f"\n## FULL HEAD (first 3000 chars - 兜底)\n{head}\n")
        # 输出进度
        print(f"[ok] {pdf.name}: text len={len(text)}")
    OUT.write_text("\n".join(out_lines), encoding="utf-8")
    print(f"\n[save] -> {OUT}")
    print(f"Total chars: {sum(len(x) for x in out_lines)}")

if __name__ == "__main__":
    main()
