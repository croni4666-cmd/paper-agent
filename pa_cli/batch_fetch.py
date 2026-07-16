"""pa_cli/batch_fetch.py — Semi-automated CNKI PDF download guide generator.

Why this exists (v3.9.8.3 honest finding):
  - xueshu789 /doDownload/ endpoint DOES work, but bar.cnki.net vLevel=5
    CAPTCHA blocks all non-real-browser automation (urllib/playwright/curl)
  - User's manual Edge workflow is the ONLY working path
  - Best we can do: make user's manual workflow FASTER by:
    1. Validating DOIs upfront (skip non-existent papers)
    2. Generating xueshu789 search URLs batch
    3. Including an Edge console snippet that auto-scrapes doDownload URLs

Usage:
  pa fetch-batch --input dois.txt --output guide.md
  pa fetch-batch --input dois.txt --output guide.md --copypath
"""
import json
import sys
import time
from pathlib import Path
from typing import List, Dict, Any
from urllib.parse import quote

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


# Edge console snippet to extract doDownload URLs from xueshu789 search result page.
# User pastes this into F12 Console after navigating to a search result page.
# It will:
#   1. Find all <a href> containing '/doDownload/'
#   2. Write to clipboard (one URL per line)
#   3. Display count and sample
# Note: this is a static snippet — works on any xueshu789 page with /doDownload/ links.
EDGE_CONSOLE_SNIPPET = """// 1. Find all doDownload links
const links = Array.from(document.querySelectorAll('a[href*="/doDownload/"]'))
                     .map(a => a.href)
                     .filter(href => !href.startsWith('javascript:'));

// 2. Display count and sample
console.log('Found ' + links.length + ' doDownload URLs');
links.slice(0, 3).forEach((url, i) => console.log('[' + (i+1) + '] ' + url.substring(0, 80) + '...'));

// 3. Copy to clipboard (one URL per line)
const text = links.join('\\n');
navigator.clipboard.writeText(text).then(() => {
  console.log('\\n[OK] Copied ' + links.length + ' URLs to clipboard. Paste into fetch_urls.txt');
});

// 4. Also open first 5 URLs in new tabs (for batch verification)
links.slice(0, 5).forEach((url, i) => {
  setTimeout(() => window.open(url, '_blank'), i * 300);
});
console.log('\\n[OK] Opened first 5 URLs in new tabs. Solve CAPTCHA per tab, PDFs download automatically.');
"""


def search_paper(query: str, year_min: int = None, year_max: int = None,
                 limit: int = 5) -> Dict[str, Any]:
    """Resolve a query (DOI or title) to paper metadata.

    Tries:
      1. If query looks like a DOI (10.xxxx/...): Crossref, then OpenAlex
      2. Else (treat as title): AMiner search (best for Chinese), then pa search

    Returns: {"status": "found|not_found|error", "paper": {...}, "input": original}
    """
    from urllib.parse import quote
    import urllib.request as ur
    import urllib.error
    import json

    query = query.strip()
    is_doi = query.startswith("10.") and "/" in query

    if is_doi:
        # 1) OpenAlex by DOI (best for English DOIs)
        try:
            url = f"https://api.openalex.org/works/doi:{quote(query, safe='/')}"
            req = ur.Request(url, headers={
                "User-Agent": "paper-agent/3.9.8.3 (mailto:dengn@gmail.com)",
                "Accept": "application/json",
            })
            with ur.urlopen(req, timeout=15) as r:
                data = json.loads(r.read().decode("utf-8", errors="ignore"))
            if data.get("id") and not data.get("error"):
                title = data.get("title") or data.get("display_name") or "—"
                authors = [a.get("author", {}).get("display_name", "")
                           for a in (data.get("authorships") or [])
                           if a.get("author", {}).get("display_name")]
                year = data.get("publication_year")
                venue = ""
                primary = data.get("primary_location") or {}
                source = primary.get("source") or {}
                if source.get("display_name"):
                    venue = source["display_name"]
                cited = data.get("cited_by_count", 0) or 0
                return {"status": "found",
                        "input": query, "input_type": "doi",
                        "paper": {"doi": query, "title": title,
                                  "authors": authors, "year": year,
                                  "venue": venue, "cited_by_count": cited,
                                  "source": "openalex"}}
        except Exception:
            pass

        # 2) Crossref fallback
        try:
            url = f"https://api.crossref.org/works/{quote(query, safe='/')}"
            req = ur.Request(url, headers={
                "User-Agent": "paper-agent/3.9.8.3 (mailto:dengn@gmail.com)",
                "Accept": "application/json",
            })
            with ur.urlopen(req, timeout=15) as r:
                data = json.loads(r.read().decode("utf-8", errors="ignore"))
            msg = data.get("message") or {}
            if msg.get("DOI"):
                title = (msg.get("title") or ["—"])[0]
                authors = []
                for a in msg.get("author", []) or []:
                    fam = a.get("family", "")
                    giv = a.get("given", "")
                    if fam or giv:
                        authors.append(f"{fam}, {giv}".strip(", "))
                issued = msg.get("issued", {}).get("date-parts", [[None]])[0]
                year = issued[0] if issued else None
                venue_list = msg.get("container-title") or []
                venue = venue_list[0] if venue_list else ""
                cited = msg.get("is-referenced-by-count", 0) or 0
                return {"status": "found",
                        "input": query, "input_type": "doi",
                        "paper": {"doi": query, "title": title,
                                  "authors": authors, "year": year,
                                  "venue": venue, "cited_by_count": cited,
                                  "source": "crossref"}}
        except Exception:
            pass

        return {"status": "not_found", "input": query, "input_type": "doi",
                "note": "DOI not in OpenAlex or Crossref. Try title as input."}

    else:
        # Title mode → AMiner search (best for Chinese)
        try:
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from pa_cli.aminer_channel import search_aminer
            results = search_aminer(query, limit=5)
            if results:
                # Take the first result (AMiner returns dicts)
                r = results[0]
                title = r.get("title", "—")
                # AMiner format: title_zh if query has CJK
                if not title and r.get("title_zh"):
                    title = r["title_zh"]
                return {"status": "found",
                        "input": query, "input_type": "title",
                        "paper": {
                            "doi": r.get("doi", ""),
                            "title": title or query,
                            "authors": [r.get("first_author", "")] if r.get("first_author") else [],
                            "year": r.get("year"),
                            "venue": r.get("venue_name", ""),
                            "cited_by_count": _aminer_cited_to_int(r.get("n_citation_bucket", "")),
                            "source": "aminer",
                        }}
        except Exception as e:
            return {"status": "error", "input": query, "input_type": "title",
                    "error": f"AMiner: {str(e)[:200]}"}
        return {"status": "not_found", "input": query, "input_type": "title",
                "note": "AMiner returned no results"}


def _aminer_cited_to_int(bucket: str) -> int:
    """Convert AMiner n_citation_bucket ('11-50', '5000+') to integer (midpoint or 5001)."""
    if not bucket:
        return 0
    try:
        if "+" in bucket:
            base = int(bucket.replace("+", ""))
            return base + 1
        if "-" in bucket:
            lo, hi = bucket.split("-")
            return (int(lo) + int(hi)) // 2
    except Exception:
        return 0
    return 0


def xueshu789_search_url(title: str) -> str:
    """Generate xueshu789 知网 search URL for a given paper title.

    Note: xueshu789 search uses POST + QueryJson, so this URL only works
    as a deep-link to the search form. User still needs to input the title.
    """
    return f"https://www.xueshu789.com/dbItem/2?keyValue={quote(title)}"


def make_doi_url(paper: Dict[str, Any]) -> str:
    """DOI canonical URL."""
    doi = paper.get("doi", "")
    if not doi:
        return ""
    return f"https://doi.org/{doi}"


def generate_guide(dois: List[str], output_path: Path,
                  year_min: int = None, year_max: int = None) -> Dict[str, Any]:
    """Main: read DOIs, search each, generate markdown guide."""
    print(f"Reading {len(dois)} DOIs from input...")
    results = []
    for i, doi in enumerate(dois, 1):
        if not doi.strip() or doi.startswith("#"):
            continue
        print(f"  [{i}/{len(dois)}] Searching {doi.strip()}...")
        r = search_paper(doi.strip(), year_min=year_min, year_max=year_max)
        r["input_doi"] = doi.strip()
        results.append(r)
        time.sleep(0.5)  # jitter to avoid rate limit

    # Generate markdown
    md_lines = [
        "# PDF 批量下载指南 (paper-agent v3.9.8.3 batch)",
        "",
        f"输入: {len(dois)} 个 DOI",
        f"成功搜索到 metadata: {sum(1 for r in results if r['status'] in ('found','partial'))} 篇",
        f"未找到: {sum(1 for r in results if r['status'] == 'not_found')} 篇",
        f"错误: {sum(1 for r in results if r['status'] == 'error')} 篇",
        "",
        "## 准备 (5 分钟一次性)",
        "",
        "1. 打开 Edge，访问 https://www.xueshu789.com/dbList/1",
        "2. 点 '**知网 [PDF格式 最好用]**' 按钮（'中文数据库' 区）",
        "3. 跳到知网搜索页后，按 **F12** → '**控制台**' tab",
        f"4. 把下面 JS 整个粘进去，按 Enter：",
        "",
        "```javascript",
        EDGE_CONSOLE_SNIPPET,
        "```",
        "",
        "JS 会自动打开搜索框（无）— 你需要**手动输入 query** 触发 search，",
        "然后 search result 页面出现后，**再跑一次** 这个 JS：",
        "JS 会：(a) 找所有 /doDownload/ 链接 (b) 复制到剪贴板 (c) 自动开 5 个新 tab",
        "",
        "## 论文列表",
        "",
        "| # | Title | DOI | Year | Status | xueshu789 Search |",
        "|---|-------|-----|------|--------|------------------|",
    ]
    for i, r in enumerate(results, 1):
        p = r.get("paper", {})
        title = p.get("title", "—")[:50]
        doi = p.get("doi", r.get("input_doi", "—"))
        year = p.get("year", "—")
        status = r["status"]
        search = xueshu789_search_url(title) if title != "—" else "—"
        md_lines.append(f"| {i} | {title} | {doi} | {year} | {status} | {search} |")

    md_lines.extend([
        "",
        "## 操作流程",
        "",
        "### A. 对每篇 paper，**手动走一次**这套流程：",
        "",
        "1. 在 xueshu789 知网搜索页 输入 **论文标题**（或 DOI）",
        "2. 找到 search result 列表页",
        "3. 在 Console 再跑一次上面的 JS",
        "4. JS 自动复制所有 doDownload URL 到剪贴板",
        "5. JS 自动开前 5 个 tab → 你**手动** verify CAPTCHA",
        "6. 每个 tab 的 PDF 自动下载到 Edge 的 `Downloads/` 目录",
        "7. 全部 verify 完成后，看 Downloads/ 找新下载的 PDF 文件",
        "",
        "### B. 或者**半批量**做法（10+ 篇一次）：",
        "",
        "1. 在 xueshu789 搜索一次（如 '数字普惠金融 家庭消费'）",
        "2. search result 列表有 10-20 篇相关 paper",
        "3. 在 Console 跑 JS，**所有 doDownload URL 都到剪贴板**",
        "4. 粘到 `fetch_urls.txt`",
        "5. 用这个命令打开全部：",
        "",
        "```powershell",
        "# PowerShell: 打开 fetch_urls.txt 里的所有 URL",
        "Get-Content fetch_urls.txt | ForEach-Object { Start-Process msedge $_ }",
        "```",
        "",
        "6. 每个 tab 手动 verify CAPTCHA",
        "7. Edge 自动下载所有 PDF",
        "",
        "## 限制",
        "",
        "- **xueshu789 cookies 4-8h 过期** — 超过需要重新 export",
        "- **bar.cnki.net vLevel=5 CAPTCHA** 必须人手动过（无 AI 绕过）",
        "- **proxy IP 不稳定** — xueshu789.com 偶尔换 IP，4 cookies 可能失效",
        "- **一次 verify 有效期短** — 同一 session 多次 verify 可能需要重新点",
        "",
        "## 失败时怎么办",
        "",
        "| 失败现象 | 原因 | 解决 |",
        "|----------|------|------|",
        "| console 没找 doDownload 链接 | xueshu789 search 用 POST，URL 不在 HTML | 触发 search 后 JS 才能找 |",
        "| verify 页面没出现 / 直接跳 PDF | cookies 还新鲜，bar.cnki.net 信任你 | 继续下 |",
        "| verify 一直过不去 | cookies 过期了 | 重跑 `pa fetch --export-cookies` |",
        "| '安全验证' / vLevel 跳 5 | bar.cnki.net 检测到异常 | 24h 后再试（IP 池刷新）|",
        "",
        "## 自动化的真正瓶颈",
        "",
        "paper-agent 在 v3.9.8.3 试过 4 种方法全失败（v3.9.8.3 commit bdaa9a6）：",
        "",
        "1. ❌ 直接 urllib 下载 — 触发 vLevel=5",
        "2. ❌ playwright + 4 cookies — 触发 vLevel=5",
        "3. ❌ playwright + user profile — 需要关 Edge + 弹窗",
        "4. ❌ playwright + browser fingerprint spoofing — TLS 指纹暴露",
        "",
        "**CAPTCHA vLevel=5 是 anti-bot 终极防御**，hobbyist 范围内无解。",
        "User 手动 Edge + JS 批量抓是**目前最快**的方案。",
    ])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(md_lines), encoding="utf-8")
    return {
        "results": results,
        "output": str(output_path),
        "n_total": len(dois),
        "n_found": sum(1 for r in results if r['status'] in ('found', 'partial')),
        "n_not_found": sum(1 for r in results if r['status'] == 'not_found'),
    }


if __name__ == "__main__":
    # Test: mix of DOIs and titles
    test_queries = [
        "10.3969/j.issn.1003-9031.2022.04.008",   # Chinese DOI
        "数字普惠金融对经济高质量发展的影响",  # Chinese title
        "10.1038/nature12373",                 # English DOI
        "Nanometre-scale thermometry in a living cell",  # English title
    ]
    out = Path("test_output/_batch_test_guide.md")
    summary = generate_guide(test_queries, out)
    print(f"\nGenerated: {summary['output']}")
    print(f"  found: {summary['n_found']}/{summary['n_total']}")
