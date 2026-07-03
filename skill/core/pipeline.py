"""
Paper Agent Skill - 通用 Pipeline 接口 (Topic-Agnostic, Full Implementation)

4 phase + run_full_pipeline — **全部真正执行**, 不再是 placeholder
"""
import datetime
import json
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any

SKILL_ROOT = Path(__file__).parent.parent
WORKSPACE = SKILL_ROOT.parent

sys.path.insert(0, str(SKILL_ROOT))
sys.path.insert(0, str(WORKSPACE))

from skill.config import Config, get_config, reload_config

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


# ============================================================
# 主题配置
# ============================================================
def load_topic_config(topic: str) -> Dict[str, Any]:
    if not HAS_YAML:
        raise ImportError('❌ 需要 PyYAML: pip install pyyaml')
    path = SKILL_ROOT / 'topics' / f'{topic}.yaml'
    if not path.exists():
        available = list_example_topics()
        raise FileNotFoundError(
            f'❌ 主题配置不存在: {path}\n'
            f'   可用 example: {available}\n'
            f'   创建新主题: from skill.core import create_topic_template'
        )
    with open(path, encoding='utf-8') as f:
        return yaml.safe_load(f)


def list_example_topics() -> List[str]:
    topics_dir = SKILL_ROOT / 'topics'
    return sorted([p.stem for p in topics_dir.glob('_example_*.yaml')]) if topics_dir.exists() else []


def list_all_topics() -> List[str]:
    topics_dir = SKILL_ROOT / 'topics'
    return sorted([p.stem for p in topics_dir.glob('*.yaml')]) if topics_dir.exists() else []


def create_topic_template(name: str, description: str = '') -> Path:
    target = SKILL_ROOT / 'topics' / f'{name}.yaml'
    if target.exists():
        raise FileExistsError(f'主题已存在: {target}')
    template = SKILL_ROOT / 'topics' / 'template.yaml'
    if not template.exists():
        raise FileNotFoundError(f'template.yaml 不存在: {template}')
    content = template.read_text(encoding='utf-8')
    import datetime
    today = datetime.date.today().isoformat()
    content = content.replace('name: ""', f'name: "{name}"')
    content = content.replace('short_name: ""', f'short_name: "{name}"')
    content = content.replace('description: ""', f'description: "{description}"')
    content = content.replace('last_updated: "2026-06-28"', f'last_updated: "{today}"')
    target.write_text(content, encoding='utf-8')
    print(f'✓ 创建主题: {target}')
    return target


# ============================================================
# 4 Phase 真正执行
# ============================================================
def phase_a_download(
    topic: str,
    dois: List[str],
    workspace_dir: Optional[str] = None,
    max_weapons: int = 4,
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Phase A: 批量下载 PDF (真正执行)"""
    from skill.tools.downloader_inline import download_paper
    
    cfg = get_config(topic=topic, workspace_dir=workspace_dir)
    cfg.ensure_dirs()
    out_dir = Path(output_dir) if output_dir else cfg.pdf_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    
    print(f'[Phase A] {topic}: 下载 {len(dois)} 篇')
    
    results = {'topic': topic, 'success': [], 'failed': [], 'skipped': [], 'total_attempted': 0}
    
    for doi in dois:
        safe = doi.replace('/', '_').replace(':', '_')
        out_path = out_dir / f'{safe}.pdf'
        
        if out_path.exists() and out_path.stat().st_size > 10000:
            results['success'].append({'doi': doi, 'path': str(out_path), 'weapon': 'cached', 'host': 'local'})
            results['total_attempted'] += 1
            continue
        
        ok, weapon, host = download_paper(doi, str(out_path), max_weapons=max_weapons, verbose=False)
        results['total_attempted'] += 1
        if ok:
            results['success'].append({'doi': doi, 'path': str(out_path), 'weapon': weapon, 'host': host})
        else:
            results['failed'].append({'doi': doi, 'weapon': None})
    
    results['hit_rate'] = (
        len(results['success']) / results['total_attempted']
        if results['total_attempted'] > 0 else 0
    )
    print(f'  ✓ {len(results["success"])}/{results["total_attempted"]} = {results["hit_rate"]:.1%}')
    return results


def phase_b_extract(
    topic: str,
    papers: Optional[List[Dict]] = None,
    workspace_dir: Optional[str] = None,
    use_v31_enhance: bool = True,
) -> Dict[str, Any]:
    """Phase B: 8 字段抽取 (真正执行)
    
    Args:
        papers: paper 列表 (含 doi, title, abstract)。None 时从 pool_dir/pool.json 读
    """
    from skill.core.field_extractor import extract_from_paper
    
    cfg = get_config(topic=topic, workspace_dir=workspace_dir)
    
    # 加载 papers
    if papers is None:
        pool_path = cfg.pool_dir / 'pool.json'
        if not pool_path.exists():
            return {'status': 'no_pool', 'note': f'pool.json 不存在: {pool_path}'}
        pool_data = json.loads(pool_path.read_text(encoding='utf-8'))
        papers = pool_data.get('papers', [])
    
    print(f'[Phase B] {topic}: 抽 {len(papers)} 篇 8 字段')
    
    results = []
    for p in papers:
        fields = extract_from_paper(p, pdf_dir=cfg.pdf_dir)
        results.append({**p, **fields})
    
    # 保存
    out_path = cfg.report_dir / ('extraction_v31.json' if use_v31_enhance else 'extraction_v2.json')
    out_path.write_text(json.dumps({
        'metadata': {
            'topic': topic,
            'method': 'v3.1' if use_v31_enhance else 'v2.1',
            'total': len(results),
        },
        'papers': results,
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    
    # 统计字段命中率
    field_stats = {}
    for field in ['methodology', 'sample_size', 'effect_size', 'intervention', 'outcome', 'key_finding', 'country', 'positive_or_negative']:
        if field == 'positive_or_negative':
            hits = sum(1 for r in results if r.get(field) and r.get(field) != 'mixed')
        elif field == 'country':
            hits = sum(1 for r in results if r.get(field))
        else:
            hits = sum(1 for r in results if r.get(field))
        field_stats[field] = hits
    
    print(f'  ✓ 字段命中率:')
    for f, h in field_stats.items():
        print(f'    {f}: {h}/{len(results)} ({h/len(results)*100:.0f}%)')
    
    return {
        'status': 'success',
        'topic': topic,
        'total': len(results),
        'output_path': str(out_path),
        'field_stats': field_stats,
        'papers': results,
    }


def phase_c_topic_model(
    topic: str,
    papers: Optional[List[Dict]] = None,
    n_topics: Optional[int] = None,
    workspace_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Phase C: 主题建模 (TF-IDF + NMF)"""
    from skill.core.topic_modeler import run_nmf
    
    cfg = get_config(topic=topic, workspace_dir=workspace_dir)
    
    # 加载 papers
    if papers is None:
        # 优先从 extraction 读, fallback 到 pool
        extract_path = cfg.report_dir / 'extraction_v31.json'
        if extract_path.exists():
            extract_data = json.loads(extract_path.read_text(encoding='utf-8'))
            papers = extract_data.get('papers', [])
        else:
            pool_path = cfg.pool_dir / 'pool.json'
            if pool_path.exists():
                pool_data = json.loads(pool_path.read_text(encoding='utf-8'))
                papers = pool_data.get('papers', [])
    
    topic_cfg = load_topic_config(topic)
    if n_topics is None:
        n_topics = topic_cfg.get('topic_modeling', {}).get('n_topics', 8)
    
    print(f'[Phase C] {topic}: TF-IDF + NMF, {n_topics} 主题, {len(papers)} 篇')
    
    result = run_nmf(papers, n_topics=n_topics)
    
    # 保存
    out_path = cfg.report_dir / 'topic_modeling.json'
    out_path.write_text(json.dumps({
        'metadata': {
            'topic': topic,
            'method': 'TF-IDF + NMF',
            'n_topics': n_topics,
            'n_papers': len(papers),
        },
        **result,
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    
    print(f'  ✓ {len(result["topics"])} 主题, 保存到 {out_path.name}')
    return {
        'status': 'success',
        'topic': topic,
        'n_topics': n_topics,
        'topics': result['topics'],
        'output_path': str(out_path),
    }


def phase_d_quality_prisma(
    topic: str,
    extraction: Optional[Dict] = None,
    prisma_counts: Optional[Dict] = None,
    workspace_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Phase D: 质量评分 + PRISMA 流程图
    
    Args:
        extraction: extraction dict (含 papers)。None 时从 report_dir/extraction_v31.json 读
        prisma_counts: {identified, screened, eligible, included, pdf, abstract, by_source}
    """
    from skill.core.quality_scorer import score_all
    from skill.core.prisma import generate_markdown
    
    cfg = get_config(topic=topic, workspace_dir=workspace_dir)
    
    # 加载 extraction
    if extraction is None:
        extract_path = cfg.report_dir / 'extraction_v31.json'
        if not extract_path.exists():
            return {'status': 'no_extraction', 'note': f'extraction_v31.json 不存在'}
        extraction = json.loads(extract_path.read_text(encoding='utf-8'))
    
    papers = extraction.get('papers', [])
    print(f'[Phase D] {topic}: 质量评分 + PRISMA, {len(papers)} 篇')
    
    # 1. 质量评分
    quality = score_all(papers)
    quality_path = cfg.report_dir / 'quality_scoring.json'
    quality_path.write_text(json.dumps({
        'metadata': {
            'topic': topic,
            'method': 'SIGN-50 改编',
            **quality,
        },
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    
    print(f'  ✓ 质量评分: avg={quality["avg_total"]:.1f}/16, {quality["grade_dist"]}')
    
    # 2. PRISMA (需要 prisma_counts)
    if prisma_counts:
        prisma_md = generate_markdown(**prisma_counts)
        prisma_path = cfg.report_dir / 'PRISMA.md'
        prisma_path.write_text(prisma_md, encoding='utf-8')
        print(f'  ✓ PRISMA: saved to {prisma_path.name}')
    
    return {
        'status': 'success',
        'topic': topic,
        'quality_avg': quality['avg_total'],
        'grade_dist': quality['grade_dist'],
        'output_paths': {
            'quality': str(quality_path),
            'prisma': str(cfg.report_dir / 'PRISMA.md') if prisma_counts else None,
        },
    }


# ============================================================
# 一键 4 phase
# ============================================================
def run_full_pipeline(
    topic: str,
    dois: Optional[List[str]] = None,
    workspace_dir: Optional[str] = None,
    n_topics: int = 8,
) -> Dict[str, Any]:
    """一键跑 4 phase (需要 doi 列表 + prisma_counts)"""
    print(f'\n{"=" * 70}')
    print(f'=== {topic} 全 pipeline ===')
    print(f'{"=" * 70}\n')
    
    results = {}
    
    if dois:
        results['A'] = phase_a_download(topic=topic, dois=dois, workspace_dir=workspace_dir)
    
    results['B'] = phase_b_extract(topic=topic, workspace_dir=workspace_dir)
    
    results['C'] = phase_c_topic_model(topic=topic, workspace_dir=workspace_dir, n_topics=n_topics)
    
    # PRISMA 需要 counts (用户提供)
    results['D'] = phase_d_quality_prisma(topic=topic, workspace_dir=workspace_dir)
    
    return results


# ============================================================
# 完整 7 阶段 (含 search + screen + select)
# ============================================================
def run_search_screen_pipeline(
    topic: str,
    query: str,
    channels: Optional[List[str]] = None,
    max_per_channel: int = 50,
    workspace_dir: Optional[str] = None,
    n_topics: int = 8,
    **kwargs: Any,
) -> Dict[str, Any]:
    """完整 7 阶段: search → dedup → 3-stage screen → topic select → 4 phase
    
    Args:
        topic: 主题名
        query: 检索词
        channels: 6 通道 (默认全跑)
        max_per_channel: 每通道上限
    """
    from skill.core.paper_fetcher import (
        search_with_searchpool,
        fetch_all_channels,
        dedup_papers,
    )
    from skill.core.screening import screen_3stage, topic_select
    from skill.core.relevance import rank_papers

    cfg = get_config(topic=topic, workspace_dir=workspace_dir)
    topic_cfg = load_topic_config(topic)

    print(f'\n{"=" * 70}')
    print(f'=== {topic} 完整 7 阶段 (Phase 4: SearchPool backend) ===')
    print(f'{"=" * 70}\n')

    # Stage 1: multi-searcher retrieval (Phase 4: SearchPool wraps habanero / pyalex / arxiv.py)
    print(f'[1] 多 searcher 检索 "{query}" (Phase 4 SearchPool: Crossref / S2 / arxiv / OpenAlex)')
    try:
        channel_results = search_with_searchpool(
            query,
            max_per_channel=max_per_channel,
        )
        backend = 'SearchPool (habanero+pyalex+arxiv.py)'
    except Exception as e:
        # Fall back to legacy if api_pool isn't importable
        print(f'  ⚠ SearchPool init failed ({e}), falling back to legacy urllib')
        api_keys = {'core': cfg.get_api_key('CORE_API_KEY')}
        channel_results = fetch_all_channels(
            query,
            channels=channels,
            max_per_channel=max_per_channel,
            api_keys=api_keys,
        )
        backend = 'legacy (urllib hand-roll)'
    print(f'  backend: {backend}')
    all_papers = []
    for ch, ps in channel_results.items():
        all_papers.extend(ps)
    print(f'  原始: {len(all_papers)} 篇, 来源: {dict((k, len(v)) for k, v in channel_results.items())}')
    
    # Stage 2: 去重
    print(f'\n[2] 去重')
    unique = dedup_papers(all_papers, by='doi_or_title')
    print(f'  去重后: {len(unique)} 篇')
    
    # Stage 3: 3-stage 筛选
    print(f'\n[3] 3-stage 筛选')
    screen_result = screen_3stage(unique)
    final_pool = screen_result['stage3_passed']

    # Stage 3.5: relevance ranking (Phase 5, 2026-07-03)
    # Inspired by LGAR (Jaumann et al. ACL Findings 2025, arXiv:2505.24757):
    # graded relevance + dense rerank beats binary classification by 5-10pp MAP.
    # We implement a lightweight version: TF-IDF cosine by default, optional
    # LLM 0-10 grader if --ranker=llm is passed (requires MiniMax API key).
    print(f'\n[3.5] relevance ranking (paper-agent Phase 5)')
    use_llm = kwargs.get('ranker') == 'llm'
    llm_max = kwargs.get('llm_max', 30)
    ranked_pool = rank_papers(
        final_pool,
        query=query,
        use_llm=use_llm,
        llm_max=llm_max,
    )
    # Show top-10 for inspection
    print(f'  total ranked: {len(ranked_pool)} papers')
    if ranked_pool:
        print(f'  top-10 by relevance:')
        for p in ranked_pool[:10]:
            title = (p.get('title') or '')[:60]
            rel = p.get('_relevance', 0)
            cit = p.get('cited_by_count', 0) or 0
            print(f'    rank {p.get("_rank"):3d}  rel={rel:.3f}  cit={cit:5d}  {title}')

    # Stage 4: 主题精选 — use ranked_pool (sorted by relevance desc) as the
    # input ordering. Within each theme bucket, topic_select still falls back
    # to cited_by_count as secondary sort. So relevance + citation together
    # pick the strongest papers.
    print(f'\n[4] 主题精选')
    themes_dict = topic_cfg.get('themes', {})
    selected = topic_select(ranked_pool, themes_dict, top_n_per_theme=8)
    
    # 保存 pool
    pool_path = cfg.pool_dir / 'pool.json'
    pool_path.parent.mkdir(parents=True, exist_ok=True)
    pool_path.write_text(json.dumps({
        'metadata': {
            'topic': topic,
            'query': query,
            'identified': len(all_papers),
            'after_dedup': len(unique),
            'after_screening': len(final_pool),
            'after_topic_select': len(selected),
            'channels': {k: len(v) for k, v in channel_results.items()},
        },
        'papers': selected,
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'  ✓ pool saved: {pool_path.name}')
    
    # Stage 5-7: 4 phase
    print(f'\n[5-7] 跑 4 phase')
    
    # 5: 下载
    dois = [p.get('doi') for p in selected if p.get('doi')]
    arxiv_dois = [p.get('arxiv_id', '').replace('http://arxiv.org/abs/', '') for p in selected if p.get('arxiv_id')]
    all_dois = [d for d in dois if d] + [f'arXiv:{d}' for d in arxiv_dois if d]
    
    a_result = phase_a_download(topic=topic, dois=dois, workspace_dir=workspace_dir) if dois else {'success': []}
    
    # 6: 抽取
    b_result = phase_b_extract(topic=topic, papers=selected, workspace_dir=workspace_dir)
    
    # 7: 主题 + 质量
    c_result = phase_c_topic_model(topic=topic, workspace_dir=workspace_dir, n_topics=n_topics)
    
    prisma_counts = {
        'identified_count': len(all_papers),
        'after_screening_count': len(final_pool),
        'after_eligibility_count': len(selected),
        'included_count': len(selected),
        'by_source': {k: len(v) for k, v in channel_results.items()},
        'pdf_count': a_result.get('total_attempted', 0) and len(a_result.get('success', [])),
        'abstract_count': len(selected) - len(a_result.get('success', [])),
    }
    
    d_result = phase_d_quality_prisma(topic=topic, workspace_dir=workspace_dir, prisma_counts=prisma_counts)
    
    print(f'\n{"=" * 70}')
    print(f'✅ {topic} pipeline 完成')
    print(f'{"=" * 70}')
    
    return {
        'search': channel_results,
        'pool_size': len(selected),
        'A': a_result,
        'B': b_result,
        'C': c_result,
        'D': d_result,
    }


# ============================================================
# Phase E (v3.3 新增): Role Reflection + Prompt Improvement Loop
# ============================================================
def phase_e_role_reflection(
    topic: str,
    lit_review_md: Optional[str] = None,
    lit_review_path: Optional[Path] = None,
    framework_extraction_path: Optional[Path] = None,
    workspace_dir: Optional[str] = None,
    audience: str = "researcher",
) -> Dict[str, Any]:
    """Phase E.1: Role Reflection (4 角色反思)

    Args:
        topic: 主题名
        lit_review_md: Lit Review 的 Markdown 内容 (str)
        lit_review_path: 或 Lit Review 文件路径 (Path)
        framework_extraction_path: v3.2 framework 抽取 JSON 路径
        workspace_dir: workspace 目录

    Returns:
        {
            'status': 'success',
            'output_path': 'Role_Reflection_<date>.md',
            'roles': [researcher, teacher, policy_maker, student],
            'reflection_dimensions': 5,
        }

    v3.3 实现:
      - 调用 skill.core.role_reflector.generate_role_reflection()
      - heuristic 简化版, 不依赖 LLM
      - 5 维度结构由代码保证
    """
    print(f'[Phase E.1] {topic}: 4 角色反思 (audience: {audience})')

    from skill.core.role_reflector import generate_role_reflection

    # 默认输出路径
    cfg = get_config(topic=topic, workspace_dir=workspace_dir)
    output_path = cfg.report_dir / f"Role_Reflection_{datetime.date.today().isoformat()}.md"

    # 默认 lit_review_path: 从 report_dir 找 Lit_Review_*.md
    if lit_review_path is None and lit_review_md is None:
        candidates = list(cfg.report_dir.glob("Lit_Review_*.md"))
        if candidates:
            lit_review_path = max(candidates, key=lambda p: p.stat().st_mtime)

    # 默认 framework_extraction_path: 从 report_dir 找 *framework*.json
    if framework_extraction_path is None:
        candidates = list(cfg.report_dir.glob("*framework*.json")) + list(cfg.report_dir.glob("*v3_2*.json"))
        if candidates:
            framework_extraction_path = max(candidates, key=lambda p: p.stat().st_mtime)

    result = generate_role_reflection(
        lit_review_md=lit_review_md,
        lit_review_path=lit_review_path,
        framework_extraction_path=framework_extraction_path,
        output_path=output_path,
    )

    print(f'  ✓ Role Reflection: {output_path.name}')
    print(f'  ✓ 4 角色: {result["roles"]}')
    print(f'  ✓ 5 维度: Identity/Praises/Concerns/Unmet Needs/Suggestions')

    return result


def phase_f_prompt_improvement(
    topic: str,
    role_reflection_path: Optional[Path] = None,
    current_prompts: Optional[Dict[str, Any]] = None,
    workspace_dir: Optional[str] = None,
    auto_apply: bool = False,
) -> Dict[str, Any]:
    """Phase E.2: Prompt Improvement Suggestions (把反思转化为下次 prompt 优化)

    Args:
        topic: 主题名
        role_reflection_path: Role_Reflection_<date>.md 路径
        current_prompts: 当前 paper agent 的 prompt 模板 (从 yaml 读取)
        workspace_dir: workspace 目录
        auto_apply: 是否自动合并到 yaml (默认 False, 需用户 review)

    Returns:
        {
            'status': 'success',
            'output_path': 'Prompt_Improvement_Suggestions_<date>.md',
            'improvements': [...],
        }

    v3.3 实现:
      - 调用 skill.core.prompt_improver.generate_prompt_improvement()
      - heuristic 简化版, 不依赖 LLM
      - 5 类改进 (content_addition / methodology / framework / config / audience)
    """
    print(f'[Phase E.2] {topic}: Prompt Improvement Suggestions (auto_apply={auto_apply})')

    from skill.core.prompt_improver import generate_prompt_improvement

    # 默认 role_reflection_path: 从 report_dir 找 Role_Reflection_*.md
    cfg = get_config(topic=topic, workspace_dir=workspace_dir)
    if role_reflection_path is None:
        candidates = list(cfg.report_dir.glob("Role_Reflection_*.md"))
        if candidates:
            role_reflection_path = max(candidates, key=lambda p: p.stat().st_mtime)

    output_path = cfg.report_dir / f"Prompt_Improvement_Suggestions_{datetime.date.today().isoformat()}.md"

    result = generate_prompt_improvement(
        role_reflection_path=role_reflection_path,
        output_path=output_path,
        auto_apply=auto_apply,
    )

    print(f'  ✓ Prompt Improvement: {output_path.name}')
    print(f'  ✓ {len(result["improvements"])} 项改进, 5 类')

    return result


def run_full_pipeline_v33(
    topic: str,
    dois: Optional[List[str]] = None,
    workspace_dir: Optional[str] = None,
    n_topics: int = 8,
    enable_phase_e: bool = True,
    audience: str = "researcher",
) -> Dict[str, Any]:
    """v3.3 一键跑 6 phase: A → B → C → D → E → F

    与 v3.2 run_full_pipeline 的差异:
      - 多了 phase_e (Role Reflection) + phase_f (Prompt Improvement)
      - 形成自我进化闭环
    """
    print(f'\n{"=" * 70}')
    print(f'=== {topic} v3.3 全 pipeline (含 Phase E) ===')
    print(f'{"=" * 70}\n')

    # Phase A-D: 复用 v3.2
    results = run_full_pipeline(topic=topic, dois=dois, workspace_dir=workspace_dir, n_topics=n_topics)

    # Phase E.1: Role Reflection
    if enable_phase_e:
        results['E'] = phase_e_role_reflection(
            topic=topic,
            workspace_dir=workspace_dir,
            audience=audience,
        )
        print(f'  ✓ Phase E.1: Role Reflection ({audience})')

        # Phase E.2: Prompt Improvement
        results['F'] = phase_f_prompt_improvement(
            topic=topic,
            workspace_dir=workspace_dir,
            auto_apply=False,  # 需用户 review
        )
        print(f'  ✓ Phase E.2: Prompt Improvement')

    print(f'\n{"=" * 70}')
    print(f'✅ {topic} v3.3 pipeline 完成 (含 Phase E 闭环)')
    print(f'{"=" * 70}')

    return results


# ============================================================
# CLI
# ============================================================
if __name__ == '__main__':
    print('Paper Agent Skill — Topic-Agnostic Pipeline (Full)')
    print('=' * 60)
    print(f'Example topics: {list_example_topics()}')
    print(f'All topics: {list_all_topics()}')
    print()
    print('Quick start:')
    print('  from skill.core import run_search_screen_pipeline')
    print('  run_search_screen_pipeline(topic="your_topic", query="your query")')
    print()
    print('v3.3 Phase E (Role Reflection + Prompt Improvement):')
    print('  from skill.core import run_full_pipeline_v33')
    print('  run_full_pipeline_v33(topic="your_topic", enable_phase_e=True)')
    print()
    print('详见: skill/PHASE_E_DESIGN.md')