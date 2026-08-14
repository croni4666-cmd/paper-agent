#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
合并 5 个 search 结果,按被引数 + 相关性聚类,挑出真正的 meta-analysis / RCT。
"""
import json
import os
from pathlib import Path
from collections import defaultdict

SR_DIR = Path(r"G:\minimax - workspace\Paper agent\search_results")
FILES = [
    "meta_analysis.json",
    "fermented_dairy.json",
    "cn_meta.json",
    "dose_response.json",
    "persistence.json",
]

# 主题关键词 (粗筛)
KEYWORDS_META = ["meta-analysis", "systematic review", "meta analysis", "\u7efc\u8ff0", "\u5143\u5206\u6790", "\u7cfb\u7edf\u8bc4\u4ef7"]
KEYWORDS_RCT = ["randomized", "rct", "controlled trial", "\u968f\u673a\u5bf9\u7167", "\u4e34\u5e8a\u8bd5\u9a8c"]
KEYWORDS_DOSE = ["dose", "dosage", "cfu", "colony forming", "\u5242\u91cf", "\u6d3b\u83cc\u6570", "\u6d3b\u83cc\u91cf"]
KEYWORDS_PERSIST = ["colonization", "persistence", "transient", "gut microbiota", "intestinal microbiota", "\u5b9a\u690d", "\u6301\u4e45", "\u9057\u7559"]
KEYWORDS_FERMENT = ["fermented", "yogurt", "dairy", "\u9178\u5976", "\u53d1\u9175"]
KEYWORDS_MULTI = ["multi-strain", "multistrain", "combination", "blend", "\u591a\u83cc\u80a1", "\u590d\u5408\u83cc\u673a"]

def load_all():
    papers = []
    for fn in FILES:
        p = SR_DIR / fn
        if not p.exists():
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        # JSON 结构: {"results": [...], "by_engine": ..., ...} 或直接 list
        if isinstance(data, dict):
            items = data.get("results", data.get("papers", []))
        else:
            items = data
        for it in items:
            # 标准化字段
            paper = {
                "title": (it.get("title") or it.get("display_name") or "").strip(),
                "authors": it.get("authors") or [],
                "year": it.get("year") or it.get("publication_year"),
                "doi": it.get("doi") or "",
                "cited_by": it.get("cited_by_count") or it.get("citations") or 0,
                "venue": (it.get("venue") or it.get("host_venue") or it.get("journal") or "").strip(),
                "source_file": fn,
                "url": it.get("url") or it.get("doi_url") or "",
                "abstract": (it.get("abstract") or it.get("abstract_inverted_index") or "")[:300],
            }
            # 作者展平
            if paper["authors"] and isinstance(paper["authors"][0], dict):
                paper["authors"] = [a.get("name", a.get("author", "")) for a in paper["authors"]]
            papers.append(paper)
    return papers

def dedup(papers):
    """按 DOI + title fuzzy 去重"""
    seen_doi = set()
    seen_title = set()
    out = []
    for p in papers:
        doi = (p.get("doi") or "").lower().strip()
        title = (p.get("title") or "").lower().strip()
        # title 前 60 字符 fuzzy
        title_key = title[:60]
        if doi and doi in seen_doi:
            continue
        if title_key and title_key in seen_title:
            continue
        if doi:
            seen_doi.add(doi)
        if title_key:
            seen_title.add(title_key)
        out.append(p)
    return out

def score_relevance(p):
    """计算相关性分数"""
    text = (p["title"] + " " + p["abstract"] + " " + p["venue"]).lower()
    score = 0
    # meta 优先
    for kw in KEYWORDS_META:
        if kw in text:
            score += 50
    for kw in KEYWORDS_RCT:
        if kw in text:
            score += 30
    for kw in KEYWORDS_MULTI:
        if kw in text:
            score += 25
    for kw in KEYWORDS_FERMENT:
        if kw in text:
            score += 15
    for kw in KEYWORDS_DOSE:
        if kw in text:
            score += 20
    for kw in KEYWORDS_PERSIST:
        if kw in text:
            score += 20
    # 高被引加分
    cites = p["cited_by"] or 0
    if cites > 500:
        score += 30
    elif cites > 200:
        score += 20
    elif cites > 100:
        score += 10
    elif cites > 30:
        score += 5
    # 主题词出现次数
    if "probiotic" in text or "\u76ca\u751f\u83cc" in text:
        score += 5
    if "gut" in text or "\u80a0" in text:
        score += 5
    if "health" in text or "\u5065\u5eb7" in text:
        score += 3
    return score

def fmt_authors(authors, n=3):
    if not authors:
        return "?"
    a = [x for x in authors if x]
    if len(a) <= n:
        return ", ".join(a)
    return ", ".join(a[:n]) + " et al."

def main():
    papers = load_all()
    print(f"[load] {len(papers)} papers (raw)")
    papers = dedup(papers)
    print(f"[dedup] {len(papers)} papers (unique)")

    # 计算分数
    for p in papers:
        p["score"] = score_relevance(p)

    # 按分数排序
    papers.sort(key=lambda x: (x["score"], x["cited_by"] or 0), reverse=True)

    # 输出 top 30
    print(f"\n=== TOP 30 by relevance (score + cites) ===\n")
    for i, p in enumerate(papers[:30], 1):
        cites = p["cited_by"] or 0
        year = p["year"] or "?"
        venue = (p["venue"] or "?").replace("\n", " ")[:50]
        title = p["title"][:100]
        authors = fmt_authors(p["authors"])
        print(f"{i:2d}. [{p['score']:3d}|c={cites:4d}|{year}] {title}")
        print(f"     {authors} | {venue}")
        if p["doi"]:
            print(f"     DOI: {p['doi']}")
        print()

    # 分类统计
    by_cat = defaultdict(list)
    for p in papers:
        text = (p["title"] + " " + p["abstract"]).lower()
        if any(kw in text for kw in KEYWORDS_META) or "\u7efc\u8ff0" in text or "\u5143\u5206\u6790" in text:
            by_cat["META/SR"].append(p)
        if any(kw in text for kw in KEYWORDS_RCT) and p not in by_cat["META/SR"]:
            by_cat["RCT"].append(p)
        if any(kw in text for kw in KEYWORDS_DOSE):
            by_cat["DOSE"].append(p)
        if any(kw in text for kw in KEYWORDS_PERSIST):
            by_cat["PERSISTENCE"].append(p)
        if any(kw in text for kw in KEYWORDS_FERMENT):
            by_cat["FERMENTED_DAIRY"].append(p)
        if any(kw in text for kw in KEYWORDS_MULTI):
            by_cat["MULTI-STRAIN"].append(p)

    print(f"\n=== 主题分布 ===")
    for cat, ps in sorted(by_cat.items(), key=lambda x: -len(x[1])):
        print(f"  {cat}: {len(ps)} papers")

    # 主题各自 top 3
    for cat, ps in sorted(by_cat.items(), key=lambda x: -len(x[1])):
        if not ps:
            continue
        ps.sort(key=lambda x: (x["score"], x["cited_by"] or 0), reverse=True)
        print(f"\n=== TOP 3 in {cat} ===")
        for i, p in enumerate(ps[:3], 1):
            cites = p["cited_by"] or 0
            year = p["year"] or "?"
            print(f"  {i}. [c={cites}|{year}] {p['title'][:90]}")
            if p["doi"]:
                print(f"     DOI: {p['doi']}")

    # 输出 JSON 供后续 review
    out_json = SR_DIR / "consolidated.json"
    out_json.write_text(json.dumps(papers[:50], ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[save] top 50 -> {out_json}")

if __name__ == "__main__":
    main()
