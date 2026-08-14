#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""地中海饮食 5 轮 search 聚合 + 聚类 + 抽 top"""
import json
from pathlib import Path
from collections import defaultdict

SR_DIR = Path(r"G:\minimax - workspace\Paper agent\search_results")
FILES = [
    "med_components.json",
    "med_predimed.json",
    "med_microbiota.json",
    "med_mortality.json",
    "med_cn.json",
]

KW_PREDIMED = ["predimed"]
KW_REVIEW = ["review", "systematic", "meta-analysis", "narrative review", "\u7efc\u8ff0", "\u5143\u5206\u6790"]
KW_RCT = ["randomized", "rct", "controlled trial", "\u968f\u673a\u5bf9\u7167"]
KW_COMP = ["components", "pattern", "pyramid", "score", "adherence", "\u7ec4\u6210", "\u7279\u5f81", "\u91d1\u5b57\u5854", "\u6a21\u5f0f"]
KW_MICRO = ["microbiota", "microbiome", "scfa", "short-chain", "gut", "\u80a0\u9053", "\u83cc\u7fa4", "\u83cc"]
KW_MORT = ["mortality", "death", "all-cause", "cardiovascular", "cancer", "survival", "\u6b7b\u4ea1", "\u5168\u56e0"]
KW_CV = ["cardiovascular", "cvd", "coronary", "stroke", "heart", "\u5fc3\u8840\u7ba1"]
KW_COG = ["cognition", "cognitive", "alzheimer", "dementia", "brain", "\u8ba4\u77e5", "\u8111"]
KW_METAB = ["metabolic", "diabetes", "obesity", "insulin", "\u4ee3\u8c22", "\u7cd6\u5c3f"]
KW_INFLAM = ["inflammation", "inflammatory", "crp", "il-6", "tnf", "\u70ce\u75c7", "\u708e\u75c7"]

def load_all():
    papers = []
    for fn in FILES:
        p = SR_DIR / fn
        if not p.exists(): continue
        data = json.loads(p.read_text(encoding="utf-8"))
        items = data if isinstance(data, list) else data.get("results", data.get("papers", []))
        for it in items:
            paper = {
                "title": (it.get("title") or it.get("display_name") or "").strip(),
                "authors": it.get("authors") or [],
                "year": it.get("year") or it.get("publication_year"),
                "doi": it.get("doi") or "",
                "cited_by": it.get("cited_by_count") or it.get("citations") or 0,
                "venue": (it.get("venue") or it.get("host_venue") or it.get("journal") or "").strip(),
                "source_file": fn,
                "abstract": (it.get("abstract") or "")[:400],
            }
            if paper["authors"] and isinstance(paper["authors"][0], dict):
                paper["authors"] = [a.get("name", "") for a in paper["authors"]]
            papers.append(paper)
    return papers

def dedup(papers):
    seen = set()
    out = []
    for p in papers:
        doi = (p.get("doi") or "").lower().strip()
        title = (p.get("title") or "").lower().strip()[:60]
        if doi and doi in seen: continue
        if title and title in seen: continue
        if doi: seen.add(doi)
        if title: seen.add(title)
        out.append(p)
    return out

def score(p):
    text = (p["title"] + " " + p["abstract"] + " " + p["venue"]).lower()
    s = 0
    for kw in KW_PREDIMED: 
        if kw in text: s += 80
    for kw in KW_REVIEW:
        if kw in text: s += 30
    for kw in KW_RCT:
        if kw in text: s += 25
    for kw in KW_COMP:
        if kw in text: s += 20
    for kw in KW_MICRO:
        if kw in text: s += 15
    for kw in KW_MORT:
        if kw in text: s += 20
    for kw in KW_CV:
        if kw in text: s += 15
    for kw in KW_COG:
        if kw in text: s += 10
    for kw in KW_METAB:
        if kw in text: s += 10
    for kw in KW_INFLAM:
        if kw in text: s += 10
    cites = p["cited_by"] or 0
    if cites > 1000: s += 30
    elif cites > 500: s += 25
    elif cites > 200: s += 20
    elif cites > 100: s += 15
    elif cites > 50: s += 10
    elif cites > 20: s += 5
    if "mediterranean" in text or "\u5730\u4e2d\u6d77" in text: s += 10
    return s

def fmt_authors(a, n=3):
    a = [x for x in a if x]
    if len(a) <= n: return ", ".join(a) if a else "?"
    return ", ".join(a[:n]) + " et al."

def main():
    papers = load_all()
    print(f"[load] {len(papers)} raw")
    papers = dedup(papers)
    print(f"[dedup] {len(papers)} unique")
    for p in papers: p["score"] = score(p)
    papers.sort(key=lambda x: (x["score"], x["cited_by"] or 0), reverse=True)

    # 找 PREDIMED
    predimed = [p for p in papers if "predimed" in p["title"].lower() or any("predimed" in (p.get("abstract") or "").lower() for _ in [0])]
    predimed_kept = []
    seen = set()
    for p in papers:
        if "predimed" in p["title"].lower() or "predimed" in p.get("abstract", "").lower()[:200].lower():
            if p["doi"] and p["doi"] not in seen:
                predimed_kept.append(p)
                seen.add(p["doi"])

    # 按主题聚类
    by_cat = defaultdict(list)
    for p in papers:
        text = (p["title"] + " " + p["abstract"]).lower()
        if any(k in text for k in KW_PREDIMED) or "predimed" in text:
            by_cat["PREDIMED/RCT"].append(p)
        if any(k in text for k in KW_REVIEW):
            by_cat["REVIEW/SR"].append(p)
        if any(k in text for k in KW_COMP):
            by_cat["COMPONENTS/PATTERN"].append(p)
        if any(k in text for k in KW_MICRO):
            by_cat["MICROBIOTA"].append(p)
        if any(k in text for k in KW_MORT):
            by_cat["MORTALITY/CV"].append(p)
        if any(k in text for k in KW_COG):
            by_cat["COGNITION"].append(p)
        if any(k in text for k in KW_INFLAM):
            by_cat["INFLAMMATION"].append(p)

    print(f"\n=== TOP 25 overall ===\n")
    for i, p in enumerate(papers[:25], 1):
        cites = p["cited_by"] or 0
        year = p["year"] or "?"
        venue = (p["venue"] or "?").replace("\n", " ")[:50]
        print(f"{i:2d}. [{p['score']:3d}|c={cites:4d}|{year}] {p['title'][:100]}")
        print(f"     {fmt_authors(p['authors'])} | {venue}")
        if p["doi"]: print(f"     DOI: {p['doi']}")
        print()

    print(f"\n=== PREDIMED 专属论文 (n={len(predimed_kept)}) ===\n")
    for i, p in enumerate(predimed_kept[:10], 1):
        cites = p["cited_by"] or 0
        year = p["year"] or "?"
        print(f"{i}. [c={cites}|{year}] {p['title'][:110]}")
        if p["doi"]: print(f"   DOI: {p['doi']}")
        print()

    print(f"\n=== 主题分布 ===")
    for cat, ps in sorted(by_cat.items(), key=lambda x: -len(x[1])):
        print(f"  {cat}: {len(ps)} papers")

    # 各主题 top 3
    for cat, ps in sorted(by_cat.items(), key=lambda x: -len(x[1])):
        if not ps: continue
        ps.sort(key=lambda x: (x["score"], x["cited_by"] or 0), reverse=True)
        print(f"\n=== TOP 3 in {cat} ===")
        for i, p in enumerate(ps[:3], 1):
            cites = p["cited_by"] or 0
            year = p["year"] or "?"
            print(f"  {i}. [c={cites}|{year}] {p['title'][:90]}")
            if p["doi"]: print(f"     DOI: {p['doi']}")

    # 保存 top 50
    (SR_DIR / "med_consolidated.json").write_text(json.dumps(papers[:50], ensure_ascii=False, indent=2), encoding="utf-8")
    (SR_DIR / "med_predimed.json").write_text(json.dumps(predimed_kept, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[save] top 50 -> med_consolidated.json, PREDIMED {len(predimed_kept)} -> med_predimed.json")

if __name__ == "__main__":
    main()
