"""JATS XML → HTML → real PDF.

Converts PubMed Central's JATS (Journal Article Tag Suite) XML to a
real PDF with embedded figures. The output replaces the `.xml` bytes
returned by PMC's EFetch API (currently saved with `.pdf` extension
in paper-agent v3.9.20.1) with a true PDF that users can read.

Pipeline:
  JATS XML bytes
    → lxml parse → element walker
    → HTML string (with inline figure URLs)
    → Playwright Chromium → page.pdf()
    → real PDF bytes

Design:
- Pure stdlib + lxml (already a dep) for XML→HTML
- Playwright (already a dep) for HTML→PDF
- No new external deps
- Optional figure embedding (off by default; downloads to temp dir)
- CSS for journal-style layout (A4, 11pt, 1.5 line spacing)
- Defensive against missing tags / publisher restrictions

Usage:
    from pa_cli.jats_to_pdf import jats_xml_to_pdf
    pdf_bytes = jats_xml_to_pdf(xml_bytes, doi="10.xxxx/yyyy", pmcid="PMC12345")
    # Save to file
    with open("out.pdf", "wb") as f:
        f.write(pdf_bytes)

Limitations:
- Some JATS tags (e.g., media objects, inline math) are simplified
- Publisher-restricted figures (K-Dense hazard) are skipped silently
- Tables are rendered as text rows; complex multi-page tables may overflow
- Citations rendered as numbered list, not formatted as in journal
"""
from __future__ import annotations

import base64
import html as html_mod
import io
import logging
import re
import sys
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from xml.etree.ElementTree import Element

logger = logging.getLogger(__name__)

# Maximum size for downloaded figure (skip huge images to avoid timeout)
_MAX_FIG_BYTES = 5 * 1024 * 1024  # 5 MB

# Inline element whitelist (JATS uses these; everything else is dropped)
_INLINE_TAGS = {
    "bold", "italic", "sub", "sup", "sc", "underline", "monospace",
    "email", "ext-link", "uri", "inline-graphic", "inline-formula",
    "break", "named-content", "styled-content", "target",
}

# Block element whitelist
_BLOCK_TAGS = {
    "p", "sec", "title", "list", "list-item", "disp-formula",
    "fig", "fig-group", "table-wrap", "caption", "attrib",
    "alternatives", "graphic", "media", "supplementary-material",
    "ack", "disp-quote", "speech", "statement", "verse-group",
    "def-list", "def-item", "term", "def", "address", "array",
    "p", "hr",
}


# ---------------------------------------------------------------------------
# XML → HTML
# ---------------------------------------------------------------------------

def _local(tag: str) -> str:
    """Strip namespace from JATS tag like '{ns}article-title' → 'article-title'."""
    return tag.split("}", 1)[1] if "}" in tag else tag


def _child_text(elem: Element, tag: str) -> Optional[str]:
    """Return text content of first child matching `tag` (with namespace stripped)."""
    for c in elem:
        if _local(c.tag) == tag:
            return "".join(t.strip() for t in c.itertext()).strip() or None
    return None


def _all_children(elem: Element, tag: str) -> List[Element]:
    return [c for c in elem if _local(c.tag) == tag]


def _render_inline(elem: Element) -> str:
    """Render inline-only content (bold, italic, sub, sup, etc.) as HTML."""
    out = []
    for node in elem.iter():
        # Skip the element itself (we want descendants only)
        if node is elem:
            continue
        local = _local(node.tag)
        text = node.text or ""
        tail = node.tail or ""
        if node.tag is elem.tag and elem.text:
            out.append(html_mod.escape(elem.text))
        if local == "bold":
            out.append(f"<strong>{html_mod.escape(text)}</strong>")
        elif local == "italic":
            out.append(f"<em>{html_mod.escape(text)}</em>")
        elif local == "sub":
            out.append(f"<sub>{html_mod.escape(text)}</sub>")
        elif local == "sup":
            out.append(f"<sup>{html_mod.escape(text)}</sup>")
        elif local == "underline":
            out.append(f"<u>{html_mod.escape(text)}</u>")
        elif local == "monospace":
            out.append(f"<code>{html_mod.escape(text)}</code>")
        elif local in {"ext-link", "uri", "email"}:
            href = node.get("{http://www.w3.org/1999/xlink}href") or node.get("href") or text
            out.append(f'<a href="{html_mod.escape(href)}">{html_mod.escape(text or href)}</a>')
        elif local == "inline-graphic":
            # Inline figure - skip for now (too small to be useful)
            pass
        elif local == "break":
            out.append("<br>")
        elif local == "xref":
            ref = node.get("rid", "")
            text_xref = text or "?"
            out.append(f'<a href="#{html_mod.escape(ref)}">[{html_mod.escape(text_xref)}]</a>')
        else:
            # Unknown inline tag: just render its text
            if text and not tail:
                out.append(html_mod.escape(text))
        # Append tail (whitespace between this node and next sibling)
        if tail.strip():
            out.append(html_mod.escape(tail))
    # Combine element.text (start) + collected descendants + element.tail
    head = html_mod.escape(elem.text) if elem.text else ""
    return head + "".join(out)


def _render_block(elem: Element, depth: int = 0, pmcid: str = "") -> str:
    """Render a block element recursively."""
    local = _local(elem.tag)
    if local == "sec":
        title = _child_text(elem, "title") or ""
        sec_type = elem.get("sec-type", "")
        inner = "".join(_render_block(c, depth + 1, pmcid=pmcid) for c in elem)
        if depth == 0:
            return f'<h2 class="sec-title">{html_mod.escape(title)}</h2>{inner}'
        elif depth == 1:
            return f'<h3 class="sec-title">{html_mod.escape(title)}</h3>{inner}'
        else:
            return f'<h4 class="sec-title">{html_mod.escape(title)}</h4>{inner}'
    elif local == "title":
        # title is wrapped in sec/fg/abstract — skip (sec handler does it)
        return ""
    elif local == "p":
        return f'<p>{_render_inline(elem).strip()}</p>'
    elif local == "fig":
        return _render_figure(elem, depth, pmcid=pmcid)
    elif local == "table-wrap":
        return _render_table(elem, depth)
    elif local == "list":
        list_type = elem.get("list-type", "bullet")
        tag = "ol" if list_type == "order" else "ul"
        items = "".join(_render_block(c, depth + 1, pmcid=pmcid) for c in elem if _local(c.tag) == "list-item")
        return f"<{tag}>{items}</{tag}>"
    elif local == "list-item":
        return f"<li>{_render_inline(elem).strip()}</li>"
    elif local == "disp-formula":
        # Use MathJax-style inline math (browser will render)
        math_text = "".join(elem.itertext()).strip()
        if math_text:
            return f'<div class="math">\\({html_mod.escape(math_text)}\\)</div>'
        return ""
    elif local == "ack":
        title = _child_text(elem, "title") or "Acknowledgments"
        inner = "".join(_render_block(c, depth + 1, pmcid=pmcid) for c in elem if _local(c.tag) != "title")
        return f'<div class="ack"><h3>{html_mod.escape(title)}</h3>{inner}</div>'
    elif local == "supplementary-material":
        return ""  # skip in body output
    elif local == "attrib":
        return f'<div class="attrib">{_render_inline(elem).strip()}</div>'
    elif local == "caption":
        title = _child_text(elem, "title") or ""
        body_paras = "".join(_render_block(c, depth + 1, pmcid=pmcid) for c in elem if _local(c.tag) != "title")
        return f'<div class="caption"><strong>{html_mod.escape(title)}</strong>{body_paras}</div>'
    elif local in {"disp-quote", "speech", "statement"}:
        return f'<blockquote>{_render_inline(elem).strip()}</blockquote>'
    elif local == "address":
        return f'<address>{_render_inline(elem).strip()}</address>'
    elif local == "hr":
        return "<hr>"
    else:
        # Unknown block: recurse into children if any, else inline
        if list(elem):
            return "".join(_render_block(c, depth + 1, pmcid=pmcid) for c in elem)
        return _render_inline(elem)


def _render_figure(fig: Element, depth: int, pmcid: str = "") -> str:
    """Render a <fig> element: graphic (image), caption, optional alt-text."""
    fig_id = fig.get("id", "")
    caption = ""
    for c in fig:
        if _local(c.tag) == "caption":
            cap_text = "".join(c.itertext()).strip()
            if cap_text:
                caption = html_mod.escape(cap_text)
            break
    # Find <graphic> xlink:href
    graphic = next((c for c in fig if _local(c.tag) in {"graphic", "alternatives"}), None)
    img_html = ""
    if graphic is not None:
        href = graphic.get("{http://www.w3.org/1999}xlink}href") or graphic.get("href") or graphic.get("{http://www.w3.org/1999/xlink}href")
        if not href:
            # Check <alternatives> > <graphic>
            if _local(graphic.tag) == "alternatives":
                for sub in graphic:
                    if _local(sub.tag) == "graphic":
                        href = sub.get("{http://www.w3.org/1999/xlink}href") or sub.get("href")
                        if href:
                            break
        if href:
            # PMC EFetch returns RELATIVE xlink:href like
            # "fendo-17-1798827-g001.jpg" (just the basename). The real
            # URL is https://www.ncbi.nlm.nih.gov/pmc/articles/instance/{id}/bin/<basename>
            # If href is already absolute (rare in JATS), keep as-is.
            if not href.startswith("http"):
                if pmcid:
                    href = f"https://www.ncbi.nlm.nih.gov/pmc/articles/instance/{pmcid}/bin/{href}"
                else:
                    logger.debug(f"<graphic> xlink:href is relative but no PMCID provided: {href}")
            # Caller (_embed_figures_as_data_uris) downloads and converts to data URI.
            img_html = f'<img src="{html_mod.escape(href)}" alt="{caption[:100]}" loading="lazy">'
    return (
        f'<figure id="{html_mod.escape(fig_id)}" class="jats-fig">'
        f'{img_html}'
        f'<figcaption>{caption}</figcaption>'
        f'</figure>'
    )


def _render_table(tw: Element, depth: int) -> str:
    """Render a <table-wrap> as an HTML table."""
    cap = ""
    rows = []
    for c in tw:
        local = _local(c.tag)
        if local == "caption":
            cap = "".join(c.itertext()).strip()
        elif local == "table":
            # <table> contains <thead>/<tbody> with <tr>/<th>/<td>
            for tr in c.iter():
                if _local(tr.tag) == "tr":
                    cells = []
                    for cell in tr:
                        ct = _local(cell.tag)
                        if ct in {"th", "td"}:
                            cell_text = "".join(cell.itertext()).strip()
                            tag = "th" if ct == "th" else "td"
                            cells.append(f"<{tag}>{html_mod.escape(cell_text)}</{tag}>")
                    if cells:
                        rows.append("<tr>" + "".join(cells) + "</tr>")
    if not rows:
        return ""
    caption_html = f"<caption>{html_mod.escape(cap)}</caption>" if cap else ""
    return (
        f'<table class="jats-table">{caption_html}<tbody>'
        + "".join(rows)
        + "</tbody></table>"
    )


def _render_metadata(front: Element) -> Dict[str, str]:
    """Extract title, authors, journal, year from <front>."""
    meta = {}
    title = ""
    for t in front.iter():
        if _local(t.tag) == "article-title":
            title += "".join(t.itertext()).strip()
    meta["title"] = title
    # Authors
    authors = []
    for contrib in front.iter():
        if _local(contrib.tag) == "contrib" and contrib.get("contrib-type") == "author":
            surname = _child_text(contrib, "surname") or ""
            given = _child_text(contrib, "given-names") or ""
            if surname:
                authors.append(f"{given} {surname}".strip())
    meta["authors"] = ", ".join(authors)
    # Journal + year
    for j in front.iter():
        if _local(j.tag) == "journal-title":
            meta["journal"] = "".join(j.itertext()).strip()
            break
    pub_date = ""
    for pd in front.iter():
        if _local(pd.tag) == "pub-date":
            year = _child_text(pd, "year")
            if year:
                pub_date = year
                break
    meta["year"] = pub_date
    return meta


def _render_abstract(front: Element) -> str:
    """Render <abstract> as HTML (if present)."""
    abs_elem = None
    for c in front.iter():
        if _local(c.tag) == "abstract":
            abs_elem = c
            break
    if abs_elem is None:
        return ""
    inner = "".join(_render_block(c, 1) for c in abs_elem if _local(c.tag) != "title")
    if not inner.strip():
        return ""
    return f'<div class="abstract"><h2>Abstract</h2>{inner}</div>'


def _render_references(back: Element) -> str:
    """Render <ref-list> as a numbered list."""
    ref_list = None
    for c in back:
        if _local(c.tag) == "ref-list":
            ref_list = c
            break
    if ref_list is None:
        return ""
    items = []
    for ref in ref_list:
        if _local(ref.tag) != "ref":
            continue
        ref_id = ref.get("id", "")
        # Get citation text (mixed-citation or element-citation)
        text = "".join(ref.itertext()).strip()
        # Compress whitespace
        text = re.sub(r"\s+", " ", text)
        # Trim very long citations
        if len(text) > 600:
            text = text[:600] + "..."
        if text:
            items.append(
                f'<li id="{html_mod.escape(ref_id)}" class="ref">'
                f'{html_mod.escape(text)}</li>'
            )
    if not items:
        return ""
    return f'<div class="references"><h2>References</h2><ol>{"".join(items)}</ol></div>'


# ---------------------------------------------------------------------------
# HTML page
# ---------------------------------------------------------------------------

_PDF_CSS = """
@page {
    size: A4;
    margin: 2.5cm 2cm 2.5cm 2cm;
    @bottom-center {
        content: counter(page);
        font-size: 9pt;
        color: #666;
    }
}
body {
    font-family: "Charter", "Bitstream Charter", "Cambria", "Georgia", serif;
    font-size: 11pt;
    line-height: 1.5;
    color: #222;
    max-width: 100%;
    margin: 0;
    padding: 0;
}
.title {
    font-size: 18pt;
    font-weight: bold;
    line-height: 1.3;
    margin: 0 0 12pt 0;
    text-align: left;
}
.metadata {
    font-size: 10pt;
    color: #555;
    margin: 0 0 24pt 0;
    border-bottom: 1px solid #ddd;
    padding-bottom: 12pt;
}
.metadata .journal {
    font-style: italic;
}
.metadata .authors {
    margin: 6pt 0 6pt 0;
}
.abstract {
    background: #f7f8fa;
    border-left: 3px solid #4a90e2;
    padding: 10pt 14pt;
    margin: 16pt 0;
    font-size: 10pt;
    line-height: 1.4;
}
.abstract h2 {
    font-size: 11pt;
    margin: 0 0 6pt 0;
    color: #4a90e2;
}
.sec-title {
    font-size: 14pt;
    color: #222;
    margin: 22pt 0 8pt 0;
    font-weight: bold;
    border-bottom: 1px solid #eee;
    padding-bottom: 4pt;
}
h3.sec-title { font-size: 12pt; }
h4.sec-title { font-size: 11pt; }
p {
    margin: 0 0 8pt 0;
    text-align: justify;
}
.jats-fig {
    margin: 16pt 0;
    page-break-inside: avoid;
}
.jats-fig img {
    max-width: 100%;
    height: auto;
    border: 1px solid #ddd;
    background: #fff;
}
.jats-fig figcaption {
    font-size: 9.5pt;
    color: #444;
    margin-top: 4pt;
    line-height: 1.35;
    text-align: left;
}
.jats-table {
    border-collapse: collapse;
    width: 100%;
    margin: 14pt 0;
    font-size: 9.5pt;
    page-break-inside: avoid;
}
.jats-table caption {
    text-align: left;
    font-weight: bold;
    margin-bottom: 4pt;
    font-size: 10pt;
    caption-side: top;
}
.jats-table th, .jats-table td {
    border: 1px solid #ccc;
    padding: 4pt 6pt;
    text-align: left;
    vertical-align: top;
}
.jats-table th {
    background: #f0f0f0;
    font-weight: bold;
}
.references {
    margin-top: 32pt;
    font-size: 9pt;
    line-height: 1.4;
    border-top: 1px solid #ddd;
    padding-top: 12pt;
}
.references h2 {
    font-size: 12pt;
    margin: 0 0 8pt 0;
}
.references ol {
    padding-left: 18pt;
    margin: 0;
}
.references li {
    margin: 0 0 4pt 0;
    word-break: break-word;
}
.ack {
    margin-top: 16pt;
    font-size: 10pt;
    color: #444;
    border-top: 1px dashed #ddd;
    padding-top: 8pt;
}
.ack h3 {
    font-size: 11pt;
    color: #555;
    margin: 0 0 4pt 0;
}
.attrib {
    font-size: 9pt;
    color: #666;
    font-style: italic;
    margin: 4pt 0;
}
.math {
    font-family: "STIX", "Latin Modern Math", serif;
    text-align: center;
    margin: 8pt 0;
    font-style: italic;
}
code {
    font-family: "Cascadia Code", "Consolas", monospace;
    font-size: 9.5pt;
    background: #f5f5f5;
    padding: 0 2pt;
    border-radius: 2pt;
}
a { color: #4a90e2; text-decoration: none; }
a:hover { text-decoration: underline; }
hr { border: 0; border-top: 1px solid #ddd; margin: 16pt 0; }
"""


def jats_xml_to_html(xml_bytes: bytes, doi: str = "", pmcid: str = "") -> str:
    """Convert JATS XML bytes to a styled HTML page.

    Args:
        xml_bytes: Raw JATS XML (e.g. from PMC EFetch).
        doi: Optional DOI for the <title> metadata.
        pmcid: Optional PMCID for the <title> metadata.

    Returns:
        A complete HTML document string.
    """
    # Parse with stdlib (handles the typical PMC EFetch output without
    # needing lxml; lxml would also work but stdlib is more portable).
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        logger.error(f"JATS parse error: {e}")
        raise ValueError(f"Could not parse JATS XML: {e}") from e

    # Find <front> and <body> at the top of <article>
    article = None
    front = None
    body = None
    back = None
    for c in root:
        local = _local(c.tag)
        if local == "article":
            article = c
            for sub in c:
                slocal = _local(sub.tag)
                if slocal == "front":
                    front = sub
                elif slocal == "body":
                    body = sub
                elif slocal == "back":
                    back = sub
            break

    if body is None:
        raise ValueError("JATS XML has no <body>")

    # Build title section
    meta = _render_metadata(front) if front is not None else {}
    title = meta.get("title") or "Untitled article"
    authors = meta.get("authors", "")
    journal = meta.get("journal", "")
    year = meta.get("year", "")

    title_html = (
        f'<h1 class="title">{html_mod.escape(title)}</h1>'
        f'<div class="metadata">'
        f'<div class="journal">{html_mod.escape(journal)}'
        + (f' ({html_mod.escape(year)})' if year else '')
        + '</div>'
        + (f'<div class="authors">{html_mod.escape(authors)}</div>' if authors else '')
        + (f'<div>DOI: {html_mod.escape(doi)}</div>' if doi else '')
        + (f'<div>PMCID: {html_mod.escape(pmcid)}</div>' if pmcid else '')
        + '</div>'
    )

    # Abstract
    abstract_html = _render_abstract(front) if front is not None else ""

    # Body (pass pmcid so figure URLs can be resolved to full PMC URLs)
    body_html = "".join(_render_block(c, 0, pmcid=pmcid) for c in body)

    # References
    refs_html = _render_references(back) if back is not None else ""

    page = (
        '<!DOCTYPE html>\n<html lang="en">\n<head>\n'
        '<meta charset="utf-8">\n'
        f'<title>{html_mod.escape(title)}</title>\n'
        f'<style>{_PDF_CSS}</style>\n'
        '</head>\n<body>\n'
        + title_html
        + abstract_html
        + body_html
        + refs_html
        + '\n</body>\n</html>'
    )
    return page


# ---------------------------------------------------------------------------
# HTML → PDF (Playwright)
# ---------------------------------------------------------------------------

def _html_to_pdf_via_playwright(html_str: str, timeout: int = 60) -> bytes:
    """Render an HTML string to PDF bytes using Playwright Chromium.

    Args:
        html_str: HTML document.
        timeout: Page load timeout in seconds.

    Returns:
        PDF bytes.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise RuntimeError(
            "playwright not installed; cannot render HTML→PDF"
        ) from e

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            context = browser.new_context()
            page = context.new_page()
            # Use file:// to render the HTML; avoids http://localhost overhead
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".html", delete=False, encoding="utf-8"
            ) as tmp:
                tmp.write(html_str)
                tmp_path = tmp.name
            try:
                page.goto(f"file://{tmp_path}", wait_until="load", timeout=timeout * 1000)
                # Give images time to load
                page.wait_for_load_state("networkidle", timeout=timeout * 1000)
                pdf_bytes = page.pdf(
                    format="A4",
                    print_background=True,
                    prefer_css_page_size=True,
                    margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
                )
            finally:
                Path(tmp_path).unlink(missing_ok=True)
            return pdf_bytes
        finally:
            browser.close()


# ---------------------------------------------------------------------------
# Optional: download figures and embed as data URIs
# ---------------------------------------------------------------------------

def _download_figure(url: str, timeout: int = 10) -> Optional[bytes]:
    """Download a figure URL; return None on failure."""
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "paper-agent-jats2pdf/1.0"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            content = r.read(_MAX_FIG_BYTES)
            return content
    except Exception as e:
        logger.debug(f"figure download failed: {url}: {e}")
        return None


def _embed_figures_as_data_uris(html_str: str, doi: str = "", proxy: str = None) -> str:
    """Replace <img src="https://..."> with embedded data URIs.

    Best-effort: download each figure and convert to base64. Failures
    are silently skipped (URL stays as remote, browser may still load).
    """
    if proxy:
        # Set proxy for urllib
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy, "https": proxy})
        )
        urllib.request.install_opener(opener)

    def replace_img(m: re.Match) -> str:
        prefix, url, alt = m.group(1), m.group(2), m.group(3)
        if url.startswith("data:") or not url.startswith("http"):
            return m.group(0)
        data = _download_figure(url)
        if not data:
            return m.group(0)
        # Guess MIME from URL
        ext = Path(url).suffix.lower().lstrip(".")
        mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif", "svg": "svg+xml"}.get(ext, "jpeg")
        b64 = base64.b64encode(data).decode("ascii")
        return f'{prefix}data:image/{mime};base64,{b64}" alt="{alt}'

    # Match <img src="..."> with any attribute order
    return re.sub(
        r'(<img[^>]*\ssrc=")(https?://[^"]+)(["][^>]*>)',
        lambda m: replace_img(m),
        html_str,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def jats_xml_to_pdf(
    xml_bytes: bytes,
    doi: str = "",
    pmcid: str = "",
    embed_figures: bool = True,
    proxy: str = None,
) -> bytes:
    """Convert JATS XML bytes to a real PDF (full pipeline).

    Args:
        xml_bytes: Raw JATS XML (e.g. from PMC EFetch).
        doi: Optional DOI (for metadata + filename).
        pmcid: Optional PMCID.
        embed_figures: If True, download and base64-embed figures.
            Falls back to remote URLs on download failure.
        proxy: HTTP proxy URL (e.g., for GFW bypass).

    Returns:
        Real PDF bytes.
    """
    html_str = jats_xml_to_html(xml_bytes, doi=doi, pmcid=pmcid)
    if embed_figures:
        html_str = _embed_figures_as_data_uris(html_str, doi=doi, proxy=proxy)
    return _html_to_pdf_via_playwright(html_str)


if __name__ == "__main__":
    # CLI test: pa-jats2pdf <xml-file> [-o output.pdf]
    if len(sys.argv) < 2:
        print("Usage: python -m pa_cli.jats_to_pdf <xml-file> [-o out.pdf]")
        sys.exit(1)
    src = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2] == "-o" and len(sys.argv) > 3 else src.with_suffix(".pdf")
    if not out.exists() and len(sys.argv) >= 4:
        out = Path(sys.argv[3])
    print(f"Reading {src}...")
    xml = src.read_bytes()
    print(f"Converting to PDF...")
    pdf = jats_xml_to_pdf(xml, doi=src.stem, pmcid="")
    out.write_bytes(pdf)
    print(f"Wrote {out} ({len(pdf)} bytes)")
