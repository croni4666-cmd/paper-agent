"""
pa_cli.build — pandoc wrapper for manuscript typesetting.

Per [P2-5] (ROADMAP "Writing pipeline"):
  - Prose = Mavis's job (user's chosen LLM)
  - Scaffold + typeset = paper-agent's job

This module provides the typeset half: takes a Bibtex + a markdown skeleton
(with [cite: key] placeholders) + a CSL style, and produces an output file
(HTML / DOCX / PDF) via pandoc.

Usage from CLI:
  pa build refs.bib --skeleton manuscript.md --out manuscript.html
  pa build refs.bib --skeleton manuscript.md --out manuscript.pdf --pdf-engine xelatex
  pa build refs.bib --skeleton manuscript.md --csl my-style.csl --out manuscript.docx
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Tuple

# ---------- Defaults ----------

# CSL bundled with paper-agent. Users can override via --csl.
DEFAULT_CSL = Path(__file__).parent / "data" / "chinese-gb7714-2005-numeric.csl"

# pandoc version when --citeproc was folded into core. We require this to
# avoid the legacy `--filter pandoc-citeproc` form.
PANDOC_MIN_VERSION = (2, 11)

# PDF engine preference order. First one that is found on PATH wins.
# xelatex is preferred for CJK (Chinese) because it handles Unicode natively.
# pdflatex works for English. weasyprint is a Python-based fallback that
# converts HTML → PDF without needing a TeX install.
PDF_ENGINES_PRIORITY = ["xelatex", "lualatex", "pdflatex", "weasyprint"]

# Minimum skeleton markdown sanity check (>= N headings, else warn).
MIN_SKELETON_HEADINGS = 3


# ---------- Pandoc availability ----------

class PandocError(RuntimeError):
    """Raised when pandoc is missing or too old."""


def find_pandoc() -> str:
    """Return absolute path to pandoc executable, or raise PandocError."""
    p = shutil.which("pandoc")
    if not p:
        raise PandocError(
            "pandoc not found on PATH. Install from https://pandoc.org/installing.html "
            "(Windows: choco install pandoc, or download MSI). Required for `pa build`."
        )
    return p


def pandoc_version(pandoc_path: str = None) -> Tuple[int, ...]:
    """Return pandoc version as a tuple of ints, e.g. (3, 6, 3)."""
    pandoc_path = pandoc_path or find_pandoc()
    out = subprocess.run(
        [pandoc_path, "--version"], capture_output=True, text=True, check=True
    )
    # First line: "pandoc.EXE 3.6.3" (Windows) or "pandoc 3.6.3" (Unix) etc.
    m = re.match(r"pandoc(?:\.exe)?\s+(\d+)\.(\d+)(?:\.(\d+))?", out.stdout, re.IGNORECASE)
    if not m:
        raise PandocError(f"Could not parse pandoc version from: {out.stdout!r}")
    return tuple(int(x) for x in m.groups() if x)


def check_pandoc() -> str:
    """Verify pandoc is installed and new enough. Returns path on success."""
    p = find_pandoc()
    v = pandoc_version(p)
    if v < PANDOC_MIN_VERSION:
        raise PandocError(
            f"pandoc { '.'.join(map(str, v)) } is too old; need >= "
            f"{'.'.join(map(str, PANDOC_MIN_VERSION))} (for built-in --citeproc)."
        )
    return p


# ---------- PDF engine detection ----------

def find_pdf_engine(prefer: Optional[str] = None) -> Optional[str]:
    """Return the first available PDF engine, or None.

    Args:
        prefer: If set and available, return this one even if not first in
                priority order. Lets user force e.g. xelatex.
    """
    if prefer:
        if shutil.which(prefer):
            return prefer
        # weasyprint is a Python module, not a binary on PATH; check via import
        if prefer == "weasyprint":
            try:
                import weasyprint  # noqa: F401
                return "weasyprint"
            except ImportError:
                return None
        return None
    for eng in PDF_ENGINES_PRIORITY:
        if shutil.which(eng):
            return eng
    # weasyprint fallback (Python module, not a binary)
    try:
        import weasyprint  # noqa: F401
        return "weasyprint"
    except ImportError:
        pass
    return None


# ---------- Skeleton validation ----------

def validate_skeleton(skeleton_path: Path) -> int:
    """Quick sanity check on a markdown skeleton. Returns heading count.

    Warns (via stderr) if there are too few headings — usually means the user
    forgot to write the structure.
    """
    text = skeleton_path.read_text(encoding="utf-8")
    # Markdown ATX headings (# / ## / ### etc.) at start of line
    headings = re.findall(r"^#{1,6}\s+\S", text, flags=re.MULTILINE)
    if len(headings) < MIN_SKELETON_HEADINGS:
        import sys
        print(
            f"[pa build] WARNING: skeleton has only {len(headings)} heading(s); "
            f"a lit-review skeleton usually has >= {MIN_SKELETON_HEADINGS}. "
            f"Consider running `pa scaffold <bib> > skeleton.md` first.",
            file=sys.stderr,
        )
    return len(headings)


# ---------- Build ----------

def build(
    bibtex_path: Path,
    skeleton_path: Path,
    output_path: Path,
    csl_path: Optional[Path] = None,
    output_format: Optional[str] = None,  # auto-detect from output_path suffix
    pdf_engine: Optional[str] = None,    # auto-detect; user can force
    extra_args: Optional[list] = None,    # passthrough to pandoc (advanced)
    quiet: bool = False,
) -> Path:
    """Build a manuscript from bibtex + markdown skeleton via pandoc.

    Args:
        bibtex_path: Path to .bib file (from `pa search --format bibtex`).
        skeleton_path: Path to .md file with [#cite: key] or [@key] placeholders.
        output_path: Where to write the result. Suffix determines format.
        csl_path: Citation style. Defaults to bundled GB/T 7714 numeric.
        output_format: Override format detection (html/docx/pdf/tex/md).
        pdf_engine: Force a specific PDF engine.
        extra_args: Additional pandoc CLI args (advanced; for power users).
        quiet: Suppress progress output.

    Returns:
        The output_path (for chaining).
    """
    # --- Validate inputs ---
    bibtex_path = Path(bibtex_path)
    if not bibtex_path.is_file():
        raise FileNotFoundError(f"Bibtex not found: {bibtex_path}")
    skeleton_path = Path(skeleton_path)
    if not skeleton_path.is_file():
        raise FileNotFoundError(f"Skeleton markdown not found: {skeleton_path}")
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if csl_path is None:
        csl_path = DEFAULT_CSL
    else:
        csl_path = Path(csl_path)
    if not csl_path.is_file():
        raise FileNotFoundError(
            f"CSL file not found: {csl_path}\n"
            f"  Hint: download from https://github.com/citation-style-language/styles "
            f"or omit --csl to use the bundled GB/T 7714 numeric."
        )

    # --- Detect format ---
    if output_format is None:
        suffix = output_path.suffix.lower().lstrip(".")
        suffix_map = {
            "html": "html", "htm": "html",
            "docx": "docx",
            "pdf": "pdf",
            "tex": "latex", "latex": "latex",
            "md": "gfm", "markdown": "gfm",
            "epub": "epub",
            "odt": "odt",
            "rtf": "rtf",
        }
        if suffix not in suffix_map:
            raise ValueError(
                f"Cannot infer output format from suffix '{output_path.suffix}'. "
                f"Use --format {{html,docx,pdf,tex,md,epub,odt,rtf}} or a recognized "
                f"file extension."
            )
        output_format = suffix_map[suffix]

    # --- Sanity check skeleton ---
    validate_skeleton(skeleton_path)

    # --- Resolve PDF engine if needed ---
    if output_format == "pdf":
        engine = find_pdf_engine(pdf_engine)
        if engine is None:
            raise RuntimeError(
                "No PDF engine found. Options:\n"
                "  1. Install MiKTeX (https://miktex.org/) for xelatex (best for CJK)\n"
                "  2. Install TeX Live (https://tug.org/texlive/) for xelatex\n"
                "  3. `pip install weasyprint` for a Python-only fallback (lower fidelity)\n"
                "Then re-run `pa build ...`. For non-PDF output, use --out manuscript.html "
                "or --out manuscript.docx (no engine needed)."
            )
        if not quiet:
            import sys
            print(f"[pa build] PDF engine: {engine}", file=sys.stderr)
    else:
        engine = None

    # --- Run pandoc ---
    pandoc_path = check_pandoc()
    cmd = [
        pandoc_path,
        str(skeleton_path),
        f"--citeproc",
        f"--bibliography={bibtex_path}",
        f"--csl={csl_path}",
        f"-o", str(output_path),
        f"-t", output_format,
    ]
    if engine:
        cmd.append(f"--pdf-engine={engine}")
    if extra_args:
        cmd.extend(extra_args)

    if not quiet:
        import sys
        print(f"[pa build] pandoc {output_format}: {skeleton_path.name} + {bibtex_path.name}", file=sys.stderr)
        print(f"[pa build] -> {output_path}", file=sys.stderr)

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"pandoc failed (exit {proc.returncode}):\n"
            f"  stdout: {proc.stdout[:500]}\n"
            f"  stderr: {proc.stderr[:500]}"
        )
    if not quiet:
        size = output_path.stat().st_size
        import sys
        print(f"[pa build] OK {size:,} bytes", file=sys.stderr)

    return output_path
