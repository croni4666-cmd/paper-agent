"""
pa_cli.empirical_design — Extract empirical design, variables, data sources, and sample rules from academic PDFs.

Implements ROADMAP [P0-18]:
  1. Data sources & time coverage (CSMAR, Wind, Compustat, CRSP, FRED, EDGAR, etc.)
  2. Sample selection & filtering criteria (exclude financial/ST firms, winsorization levels)
  3. Dependent, independent, and control variables with measurement proxies
  4. Econometric identification strategy (DID, Fixed Effects, 2SLS, RDD, GMM, Event Study)
  5. Multi-paper cross-study comparative matrix export
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .evidence import build_index
from .project import DEFAULT_ROOT, project_files


# ──────────────────────────────────────────────────────────────────────
# Dictionary of Known Academic & Industry Databases
# ──────────────────────────────────────────────────────────────────────

KNOWN_DATA_SOURCES = [
    # Chinese databases
    {"id": "csmar", "name": "CSMAR", "patterns": [r"\bcsmar\b", r"国泰安"]},
    {"id": "wind", "name": "Wind", "patterns": [r"\bwind\b", r"万得信息", r"万得数据库"]},
    {"id": "choice", "name": "Choice", "patterns": [r"\beastmoney\b", r"东方财富", r"同花顺choice", r"\bchoice数据库\b"]},
    {"id": "cnrds", "name": "CNRDS", "patterns": [r"\bcnrds\b", r"中国研究数据服务平台"]},
    {"id": "resset", "name": "RESSET", "patterns": [r"\bresset\b", r"锐思数据"]},
    {"id": "cfps", "name": "CFPS", "patterns": [r"\bcfps\b", r"中国家庭追踪调查"]},
    {"id": "chfs", "name": "CHFS", "patterns": [r"\bchfs\b", r"中国家庭金融调查"]},
    {"id": "charls", "name": "CHARLS", "patterns": [r"\bcharls\b", r"中国健康与养老追踪调查"]},
    {"id": "ceps", "name": "CEPS", "patterns": [r"\bceps\b", r"中国教育追踪调查"]},
    {"id": "nbs_china", "name": "National Bureau of Statistics (China)", "patterns": [r"国家统计局", r"中国统计年鉴", r"城市统计年鉴", r"工业企业数据库"]},
    {"id": "customs_china", "name": "China Customs", "patterns": [r"中国海关数据库", r"海关进出口数据库", r"customs\s+data"]},

    # International databases
    {"id": "compustat", "name": "Compustat", "patterns": [r"\bcompustat\b", r"\bcapital\s+iq\b"]},
    {"id": "crsp", "name": "CRSP", "patterns": [r"\bcrsp\b", r"center\s+for\s+research\s+in\s+security\s+prices"]},
    {"id": "wrds", "name": "WRDS", "patterns": [r"\bwrds\b", r"wharton\s+research\s+data\s+services"]},
    {"id": "execucomp", "name": "Execucomp", "patterns": [r"\bexecucomp\b"]},
    {"id": "audit_analytics", "name": "Audit Analytics", "patterns": [r"audit\s+analytics"]},
    {"id": "optionmetrics", "name": "OptionMetrics", "patterns": [r"optionmetrics"]},
    {"id": "factset", "name": "FactSet", "patterns": [r"\bfactset\b"]},
    {"id": "refinitiv", "name": "Refinitiv / Thomson Reuters", "patterns": [r"refinitiv", r"thomson\s+reuters", r"datastream", r"worldscope", r"sdc\s+platinum"]},
    {"id": "bloomberg", "name": "Bloomberg", "patterns": [r"bloomberg\s+terminal", r"bloomberg\s+database", r"\bbloomberg\b"]},
    {"id": "sec_edgar", "name": "SEC EDGAR", "patterns": [r"\bsec\s+edgar\b", r"\bedgar\b", r"10-[kq]\s+filings?"]},
    {"id": "fred", "name": "FRED", "patterns": [r"\bfred\b", r"federal\s+reserve\s+economic\s+data"]},
    {"id": "world_bank", "name": "World Bank", "patterns": [r"world\s+bank", r"\bwdi\b", r"world\s+development\s+indicators"]},
    {"id": "imf", "name": "IMF", "patterns": [r"international\s+monetary\s+fund", r"\bimf\b", r"world\s+economic\s+outlook"]},
    {"id": "uspto", "name": "USPTO / Patent Office", "patterns": [r"\buspto\b", r"patent\s+and\s+trademark\s+office", r"国家知识产权局", r"cnipa"]},
]

# ──────────────────────────────────────────────────────────────────────
# Econometric Identification Strategies
# ──────────────────────────────────────────────────────────────────────

IDENTIFICATION_PATTERNS = [
    {"name": "Difference-in-Differences (DID)", "patterns": [
        r"\bdifference-in-differences\b", r"\bdid\b", r"双重差分", r"多期did", r"渐进双重差分",
        r"staggered\s+did", r"staggered\s+difference-in-differences", r"twoway\s+did"
    ]},
    {"name": "Fixed Effects (FE / TWFE)", "patterns": [
        r"fixed\s+effects?", r"two-way\s+fixed\s+effects?", r"\btwfe\b", r"双向固定效应", r"固定效应模型"
    ]},
    {"name": "Instrumental Variables (IV / 2SLS)", "patterns": [
        r"instrumental\s+variables?", r"\b2sls\b", r"two-stage\s+least\s+squares?", r"工具变量", r"两阶段最小二乘"
    ]},
    {"name": "Regression Discontinuity (RDD)", "patterns": [
        r"regression\s+discontinuity", r"\brdd\b", r"\brd\s+design\b", r"断点回归"
    ]},
    {"name": "Propensity Score Matching (PSM)", "patterns": [
        r"propensity\s+score\s+matching", r"\bpsm\b", r"倾向得分匹配", r"psm-did"
    ]},
    {"name": "Event Study", "patterns": [
        r"event\s+study", r"事件研究法", r"平行趋势检验", r"parallel\s+trends?\s+test"
    ]},
    {"name": "GMM (Generalized Method of Moments)", "patterns": [
        r"generalized\s+method\s+of\s+moments", r"\bgmm\b", r"系统gmm", r"差分gmm"
    ]},
    {"name": "Ordinary Least Squares (OLS)", "patterns": [
        r"ordinary\s+least\s+squares", r"\bols\s+regression\b", r"\bols\b", r"最小二乘法"
    ]},
]

# ──────────────────────────────────────────────────────────────────────
# Common Standard Control Variables
# ──────────────────────────────────────────────────────────────────────

STANDARD_CONTROLS = [
    {"label": "Firm Size (Size)", "patterns": [r"\bsize\b", r"\blnsize\b", r"firm\s+size", r"企业规模", r"公司规模", r"资产规模", r"ln\(asset\w*\)"]},
    {"label": "Leverage (Lev)", "patterns": [r"\blev\b", r"\bleverage\b", r"financial\s+leverage", r"资产负债率", r"资本结构"]},
    {"label": "Return on Assets (ROA)", "patterns": [r"\broa\b", r"return\s+on\s+assets", r"总资产净利润率", r"总资产收益率", r"总资产报酬率"]},
    {"label": "Return on Equity (ROE)", "patterns": [r"\broe\b", r"return\s+on\s+equity", r"净资产收益率"]},
    {"label": "Tobin's Q (TobinQ)", "patterns": [r"tobin'?s?\s*q", r"托宾q", r"市值账面比"]},
    {"label": "Cash Holdings (Cash)", "patterns": [r"\bcash\b", r"cash\s+ratio", r"cash\s+holdings", r"现金持有", r"现金比率"]},
    {"label": "Firm Age (Age)", "patterns": [r"\bage\b", r"\blnage\b", r"firm\s+age", r"企业年龄", r"成立年限"]},
    {"label": "Revenue Growth (Growth)", "patterns": [r"\bgrowth\b", r"sales\s+growth", r"revenue\s+growth", r"营业收入增长率", r"成长性"]},
    {"label": "Board Size (Board)", "patterns": [r"\bboard\b", r"board\s+size", r"董事会规模", r"董事人数"]},
    {"label": "Independent Directors (Indep)", "patterns": [r"\bindep\b", r"independent\s+directors?", r"独立董事比例", r"独董比例"]},
    {"label": "CEO Duality (Dual)", "patterns": [r"\bdual\b", r"ceo\s+duality", r"两职合一", r"董事长与总经理"]},
    {"label": "Largest Shareholder (Top1)", "patterns": [r"\btop1\b", r"first\s+largest\s+shareholder", r"第一大股东持股比例", r"股权集中度"]},
    {"label": "State Ownership (SOE)", "patterns": [r"\bsoe\b", r"state-owned", r"state\s+ownership", r"国有企业", r"产权性质"]},
    {"label": "Book-to-Market (BM)", "patterns": [r"\bbm\b", r"book-to-market", r"账面市值比"]},
    {"label": "Institutional Ownership (Inst)", "patterns": [r"\binst\b", r"institutional\s+investors?", r"机构投资者持股", r"机构持股比例"]},
]


# ──────────────────────────────────────────────────────────────────────
# Extraction Logic
# ──────────────────────────────────────────────────────────────────────

def _extract_sample_period(text: str) -> Optional[str]:
    """Scan text for sample time coverage (e.g. '2010 to 2020', '2005-2019')."""
    patterns = [
        # English: from 2010 to 2020 / sample period spans 2005 through 2018
        r"(?:sample\s+(?:period|covers?|spans?|from|range)|data\s+(?:from|period)|time\s+period(?:\s+is)?|study\s+period)\s*(?:from|spans|covers)?\s*([12][90]\d{2})\s*(?:to|through|-|–|—|until|and)\s*([12][90]\d{2})",
        # English: between 2010 and 2020
        r"between\s+([12][90]\d{2})\s+and\s+([12][90]\d{2})",
        # Chinese: 2010—2020年 / 2010年至2020年
        r"([12][90]\d{2})\s*(?:年)?\s*[-–—至到]\s*([12][90]\d{2})\s*年",
        # Contextual year range: during/for/spanning the period 2010-2022
        r"(?:during|for|covering|spanning)\s+(?:the\s+period\s+)?([12][90]\d{2})\s*[-–—]\s*([12][90]\d{2})",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            y1, y2 = int(m.group(1)), int(m.group(2))
            if 1950 <= y1 <= 2035 and 1950 <= y2 <= 2035 and y1 <= y2:
                return f"{y1}–{y2}"
    return None


def _extract_sample_filtering(text: str) -> List[str]:
    """Extract sample filtering and data cleaning rules."""
    rules = []
    # Financial industry filter
    if re.search(r"exclude[d]?\s+[^.\n]{0,80}(?:financial\s+(?:institutions|firms|companies|industry|sector)|firms\s+in\s+the\s+financial)", text, re.I) or \
       re.search(r"剔除金融(?:业|类)?上市公司", text):
        rules.append("Excludes financial institutions and firms")

    # ST / *ST filter
    if re.search(r"\b(?:st|\*st|special\s+treatment)\s+(?:firms|companies|stocks|listed)\b", text, re.I) or \
       re.search(r"exclude[d]?\s+[^.\n]{0,80}\b(?:st|\*st|special\s+treatment)\b", text, re.I) or \
       re.search(r"剔除(?:st|\*st|退市|pt)公司", text, re.I):
        rules.append("Excludes ST and *ST (special treatment) listed firms")

    # Negative net assets / insolvency
    if re.search(r"exclude[d]?\s+(?:firms\s+with\s+negative\s+(?:equity|net\s+assets)|insolvent\s+firms)", text, re.I) or \
       re.search(r"剔除资产负债率大于1|净资产为负|资不抵债", text):
        rules.append("Excludes firms with negative net assets or insolvency")

    # Missing variables filter
    if re.search(r"exclude[d]?\s+(?:observations|firms|sample)\s+with\s+missing\s+(?:values|data|variables)", text, re.I) or \
       re.search(r"剔除数据缺失|主要变量缺失", text):
        rules.append("Excludes observations with missing key variables")

    # Winsorization
    w_match = re.search(r"(?:winsoriz\w*|缩尾)\s*(?:at\s+(?:the\s+)?)?(\d+%\s*(?:and|to|-)\s*\d+%|\d+%\s*(?:level|分位数)?|\d+%\s*水平)", text, re.I)
    if w_match:
        rules.append(f"Winsorized continuous variables ({w_match.group(0).strip()})")
    elif re.search(r"winsoriz\w*", text, re.I) or re.search(r"双侧缩尾|缩尾处理", text):
        rules.append("Winsorized continuous variables to mitigate outlier effects")

    return rules


def _extract_data_sources(text: str) -> List[str]:
    """Identify data sources and databases mentioned in text."""
    found = []
    for src in KNOWN_DATA_SOURCES:
        for pat in src["patterns"]:
            if re.search(pat, text, re.IGNORECASE):
                found.append(src["name"])
                break
    return found


def _extract_identifications(text: str) -> List[str]:
    """Identify econometric estimation and identification strategies."""
    strategies = []
    for s in IDENTIFICATION_PATTERNS:
        for pat in s["patterns"]:
            if re.search(pat, text, re.IGNORECASE):
                strategies.append(s["name"])
                break
    return strategies


def _extract_control_variables(text: str) -> List[str]:
    """Identify standard control variables present in the text."""
    controls = []
    for c in STANDARD_CONTROLS:
        for pat in c["patterns"]:
            if re.search(pat, text, re.IGNORECASE):
                controls.append(c["label"])
                break
    return controls


def _extract_fe_and_clustering(text: str) -> List[str]:
    """Identify fixed effects and standard error clustering."""
    results = []
    if re.search(r"firm\s+(?:and|&)\s+year\s+fixed\s+effects?|公司(?:和|与)年份固定效应|行业(?:和|与)年份固定效应", text, re.I):
        results.append("Firm and Year Two-way Fixed Effects")
    elif re.search(r"industry\s+(?:and|&)\s+year\s+fixed\s+effects?", text, re.I):
        results.append("Industry and Year Fixed Effects")
    elif re.search(r"province\s+(?:and|&)\s+year\s+fixed\s+effects?|省份固定效应", text, re.I):
        results.append("Province and Year Fixed Effects")

    cluster_match = re.search(r"cluster(?:ed)?\s+(?:at\s+(?:the\s+)?([a-z]+)\s+level|standard\s+errors\s+by\s+([a-z]+))|在\s*([^\s]+)\s*层面聚类", text, re.I)
    if cluster_match:
        lvl = cluster_match.group(1) or cluster_match.group(2) or cluster_match.group(3) or "firm"
        results.append(f"Standard errors clustered at {lvl.strip()} level")
    elif re.search(r"robust\s+standard\s+errors?|稳健标准误", text, re.I):
        results.append("Robust standard errors")

    return results


def _extract_variables(text: str) -> Dict[str, List[Dict[str, str]]]:
    """Extract explicit dependent and key independent variable descriptions."""
    dvs: List[Dict[str, str]] = []
    ivs: List[Dict[str, str]] = []

    # Dependent variable patterns
    dv_patterns = [
        r"(?:dependent\s+variable(?:s)?\s*(?:is|are|as|denoted\s+as)?\s*[:\s]*)([A-Za-z0-9_\(\)\s]{2,40})",
        r"we\s+use\s+([A-Za-z0-9_\s]{2,35})\s+as\s+the\s+dependent\s+variable",
        r"被解释变量\s*[为是：:]\s*([^\n，。]{2,30})",
        r"因变量\s*[为是：:]\s*([^\n，。]{2,30})",
    ]
    for pat in dv_patterns:
        for m in re.finditer(pat, text, re.I):
            var_name = m.group(1).strip()
            if var_name and len(var_name) < 40 and not any(d["name"].lower() == var_name.lower() for d in dvs):
                dvs.append({"name": var_name, "type": "dependent"})

    # Independent variable patterns
    iv_patterns = [
        r"(?:(?:key\s+|main\s+)?explanatory\s+variable(?:s)?|(?:key\s+|main\s+)?independent\s+variable(?:s)?)\s*(?:is|are|as|denoted\s+as)?\s*[:\s]*([A-Za-z0-9_\(\)\s]{2,40})",
        r"we\s+use\s+([A-Za-z0-9_\s]{2,35})\s+as\s+the\s+(?:key\s+|main\s+)?(?:explanatory|independent)\s+variable",
        r"核心解释变量\s*[为是：:]\s*([^\n，。]{2,30})",
        r"解释变量\s*[为是：:]\s*([^\n，。]{2,30})",
    ]
    for pat in iv_patterns:
        for m in re.finditer(pat, text, re.I):
            var_name = m.group(1).strip()
            if var_name and len(var_name) < 40 and not any(i["name"].lower() == var_name.lower() for i in ivs):
                ivs.append({"name": var_name, "type": "independent"})

    return {"dependent": dvs, "independent": ivs}


# ──────────────────────────────────────────────────────────────────────
# Public Core Function: extract_empirical_design
# ──────────────────────────────────────────────────────────────────────

def extract_empirical_design(pdf_path: Union[str, Path]) -> Dict[str, Any]:
    """Parse a single PDF file and extract its empirical research design specifications.

    Uses section-aware indexing (evidence.py) to target Data and Methodology sections,
    extracting data sources, sample coverage, variables, and econometric identification.
    """
    path = Path(pdf_path)
    if not path.is_file():
        raise FileNotFoundError(f"PDF file does not exist: {path}")

    # Index document via evidence module
    idx = build_index(path)
    pages = idx.get("pages", [])

    # Gather full text, giving priority focus to methods and data sections, excluding references
    full_text_list = []
    methods_text_list = []

    for p in pages:
        txt = p.get("text", "")
        # Cut off once references section begins
        if re.search(r"^\s*(?:references|bibliography|works\s+cited|参考文献)\s*$", txt, re.IGNORECASE | re.MULTILINE):
            pre_ref = re.split(r"^\s*(?:references|bibliography|works\s+cited|参考文献)\s*$", txt, flags=re.IGNORECASE | re.MULTILINE)[0]
            if pre_ref.strip():
                full_text_list.append(pre_ref)
            break
        full_text_list.append(txt)
        # Check if page has methods or data
        if any(w in txt.lower() for w in ["data", "method", "empirical", "sample", "variable", "model", "estimation", "数据", "变量", "模型"]):
            methods_text_list.append(txt)

    combined_text = "\n".join(full_text_list)
    methods_text = "\n".join(methods_text_list) if methods_text_list else combined_text

    # 1. Data sources
    sources = _extract_data_sources(methods_text)
    if not sources:
        sources = _extract_data_sources(combined_text)

    # 2. Sample period
    period = _extract_sample_period(methods_text) or _extract_sample_period(combined_text)

    # 3. Sample filtering
    filtering = _extract_sample_filtering(methods_text)
    if not filtering:
        filtering = _extract_sample_filtering(combined_text)

    # 4. Identification strategies
    strategies = _extract_identifications(methods_text)
    if not strategies:
        strategies = _extract_identifications(combined_text)

    # 5. Fixed effects & clustering
    fe_clustering = _extract_fe_and_clustering(methods_text)

    # 6. Controls
    controls = _extract_control_variables(methods_text)

    # 7. Variables (DV & IV)
    var_dict = _extract_variables(methods_text)

    return {
        "file_name": path.name,
        "file_path": str(path.resolve()),
        "data_sources": sources,
        "sample_period": period,
        "sample_filtering": filtering,
        "identification_strategies": strategies,
        "fixed_effects_and_clustering": fe_clustering,
        "dependent_variables": var_dict["dependent"],
        "independent_variables": var_dict["independent"],
        "control_variables": controls,
    }


def extract_project_empirical_designs(
    slug: str,
    root: Path = DEFAULT_ROOT,
) -> Dict[str, Any]:
    """Extract empirical designs for all full-text PDFs in a project corpus."""
    files = project_files(slug, root)
    if not files["dir"].exists():
        raise FileNotFoundError(f"Project {slug!r} does not exist at {root}")

    pdf_dir = files["pdfs"]
    if not pdf_dir.exists():
        return {
            "slug": slug,
            "n_pdfs": 0,
            "designs": [],
        }

    pdf_files = list(pdf_dir.glob("*.pdf"))
    designs = []
    for p in pdf_files:
        try:
            d = extract_empirical_design(p)
            designs.append(d)
        except Exception as e:
            designs.append({
                "file_name": p.name,
                "file_path": str(p),
                "error": str(e),
            })

    return {
        "slug": slug,
        "n_pdfs": len(pdf_files),
        "designs": designs,
    }


def render_design_markdown(designs_data: Union[Dict[str, Any], List[Dict[str, Any]]]) -> str:
    """Render extracted empirical designs into a structured Markdown comparative specification."""
    if isinstance(designs_data, dict) and "designs" in designs_data:
        items = designs_data["designs"]
        header_title = f"# Empirical Design Specifications: `{designs_data.get('slug', 'Corpus')}`"
    elif isinstance(designs_data, list):
        items = designs_data
        header_title = "# Empirical Design Specifications"
    else:
        items = [designs_data]
        header_title = f"# Empirical Design Specification: `{designs_data.get('file_name', 'Paper')}`"

    lines = [
        header_title,
        "",
        "> Extracted automatically by **Paper Agent** (Literature & Evidence Intelligence Subsystem).  ",
        "> Designed for guiding downstream data crawlers, database extraction (CSMAR, Wind, Compustat), and econometric modeling.",
        "",
    ]

    # Summary table
    lines.extend([
        "## Cross-Paper Comparative Matrix",
        "",
        "| Paper | Data Sources | Sample Period | Identification | Key Explanatory | Sample Filters |",
        "|---|---|---|---|---|---|",
    ])

    for it in items:
        if "error" in it:
            lines.append(f"| {it.get('file_name', '?')} | *Extraction error* | - | - | - | {it['error'][:40]} |")
            continue
        fname = it.get("file_name", "?")
        srcs = ", ".join(it.get("data_sources", [])) or "Not detected"
        period = it.get("sample_period") or "n.d."
        ident = ", ".join(it.get("identification_strategies", [])) or "OLS / General"
        ivs = ", ".join([v["name"] for v in it.get("independent_variables", [])]) or "General"
        filters = "; ".join(it.get("sample_filtering", [])) or "None explicit"
        lines.append(f"| `{fname}` | {srcs} | {period} | {ident} | {ivs} | {filters} |")

    lines.append("")

    # Detailed sections per paper
    lines.append("## Detailed Empirical Design per Paper\n")
    for i, it in enumerate(items, 1):
        if "error" in it:
            continue
        lines.append(f"### {i}. `{it.get('file_name', 'Paper')}`\n")

        # 1. Data Sources
        srcs = it.get("data_sources", [])
        lines.append(f"- **Data Sources & Databases**: {', '.join(srcs) if srcs else 'Not explicitly detected'}")

        # 2. Sample Period
        lines.append(f"- **Sample Time Horizon**: {it.get('sample_period') or 'Unspecified / cross-sectional'}")

        # 3. Sample Filtering
        flt = it.get("sample_filtering", [])
        if flt:
            lines.append("- **Sample Selection & Cleaning Rules**:")
            for rule in flt:
                lines.append(f"  - {rule}")
        else:
            lines.append("- **Sample Selection & Cleaning Rules**: None detected")

        # 4. Identification Strategy
        strat = it.get("identification_strategies", [])
        lines.append(f"- **Econometric Identification Strategy**: {', '.join(strat) if strat else 'General Regression'}")

        fe = it.get("fixed_effects_and_clustering", [])
        if fe:
            lines.append(f"- **Fixed Effects & Standard Errors**: {', '.join(fe)}")

        # 5. Variables
        dvs = it.get("dependent_variables", [])
        if dvs:
            lines.append(f"- **Dependent Variables**: {', '.join([d['name'] for d in dvs])}")
        ivs = it.get("independent_variables", [])
        if ivs:
            lines.append(f"- **Key Explanatory Variables**: {', '.join([d['name'] for d in ivs])}")

        cvs = it.get("control_variables", [])
        if cvs:
            lines.append(f"- **Baseline Control Variables Detected**: {', '.join(cvs)}")

        lines.append("")

    return "\n".join(lines)
