"""Compile declared concept groups into auditable PubMed query variants."""
from __future__ import annotations

from .mesh_lexicon import MeshIndex, normalize


def _phrase(text: str) -> str:
    if not isinstance(text,str) or not text.strip() or any(c in text for c in '\"[]\n\r\x00'):
        raise ValueError('Terms must be plain nonempty phrases without quotes, fields, or control characters')
    return ' '.join(text.split())


def _unique(terms):
    seen, result = set(), []
    for t in terms:
        key = normalize(t)
        if key not in seen:
            seen.add(key)
            result.append(t)
    return result


def build_plan(spec: dict, index: MeshIndex | None = None, *, expansion: str = 'full', engine: str = 'pubmed') -> dict:
    if engine not in ('pubmed', 'europepmc'):
        raise ValueError('engine must be pubmed or europepmc')
    if engine == 'europepmc' and expansion != 'none':
        raise ValueError('Europe PMC currently supports expansion=none only')
    if expansion not in ('none','headings','full'):
        raise ValueError('expansion must be none, headings, or full')
    if not isinstance(spec,dict) or not isinstance(spec.get('original_question'),str) or not spec['original_question'].strip():
        raise ValueError('An original_question is required')
    if not isinstance(spec.get('groups'),list) or not spec['groups']:
        raise ValueError('At least one declared concept group is required')
    groups, warnings, seen_ids = [], [], set()
    for raw in spec['groups']:
        gid = raw.get('id')
        if not isinstance(gid,str) or not gid.strip() or gid in seen_ids:
            raise ValueError('Group IDs must be nonempty and unique')
        seen_ids.add(gid)
        if not isinstance(raw.get('required',True),bool):
            raise ValueError('required must be a boolean')
        terms, seeds = raw.get('terms',[]), raw.get('mesh',[])
        if not isinstance(terms,list) or not isinstance(seeds,list):
            raise ValueError('terms and mesh must be lists')
        free = [_phrase(t) for t in terms]
        mapped = []
        for seed in seeds:
            seed = _phrase(seed)
            if index is None:
                warnings.append({'group':gid,'input':seed,'reason':'mesh_index_missing'})
                continue
            found = index.lookup(seed)
            reason = 'unresolved_mesh' if not found else 'ambiguous_mesh' if len(found)>1 else 'related_mesh' if found[0]['match_kind']=='related' else None
            if reason:
                warnings.append({'group':gid,'input':seed,'reason':reason,'candidate_ids':[f['id'] for f in found]})
                continue
            concept = found[0]
            mapped.append(concept)
            # A descriptor's related concepts may be narrower, broader or
            # otherwise related; only preferred-concept terms enter this block.
            if expansion == 'full':
                free.extend(_phrase(t) for t in concept['synonyms'])
        if not free and not (mapped and expansion=='headings'):
            raise ValueError(f'Group {gid} has no usable free-text or mapped terms')
        groups.append({'id':gid,'required':raw.get('required',True),
                       'terms':_unique(free),'mesh_concepts':mapped,
                       'original_terms':terms})
    required = [g for g in groups if g['required']]
    if not required:
        raise ValueError('At least one group must be required')
    queries, seen_queries = [], {}

    def add(kind, selected, use_mesh, title_group=None):
        blocks=[]
        for g in selected:
            field='Title' if g['id']==title_group else 'Title/Abstract'
            terms=([f'{"TITLE" if field=="Title" else "TITLE_ABS"}:"{t}"' for t in g['terms']]
                   if engine=='europepmc' else [f'"{t}"[{field}]' for t in g['terms']])
            if use_mesh and expansion!='none' and field!='Title':
                terms += [f'"{c["label"]}"[MeSH Terms]' for c in g['mesh_concepts']]
            if not terms:
                return None
            blocks.append('('+' OR '.join(terms)+')')
        query=' AND '.join(blocks)
        if query not in seen_queries:
            seen_queries[query]=f'q{len(queries)+1:03}'
            queries.append({'id':f'q{len(queries)+1:03}','kind':kind,'query':query,
                            'engine':engine,'group_ids':[g['id'] for g in selected],
                            'relaxed_optional_groups':[g['id'] for g in groups if g['id'] not in {s['id'] for s in selected}]})
        return seen_queries[query]
    add('all_groups_free_text',groups,False)
    add('all_groups_mesh_and_free',groups,True)
    primary=add('required_groups_mesh_and_free',required,True)
    add('required_groups_free_text',required,False)
    # One optional block at a time; never a Cartesian product of tokens.
    for optional in (g for g in groups if not g['required']):
        for term in optional['original_terms']:
            branch={**optional,'terms':[_phrase(term)],'mesh_concepts':[]}
            add('optional_phrase_branch',[*required,branch],True)
    order={'required_groups_mesh_and_free':0,'all_groups_mesh_and_free':1,
           'all_groups_free_text':2,'required_groups_free_text':3,'optional_phrase_branch':4}
    legacy=[q['id'] for q in sorted(queries,key=lambda q:(order.get(q['kind'],9),q['id']))]
    priority=['intervention','vasomotor','delivery','outcome','population']
    focused=sorted(required,key=lambda g:priority.index(g['id']) if g['id'] in priority else len(priority))[:3]
    portfolio=[primary]
    for group in focused:
        qid=add('title_focus_'+group['id'],required,True,title_group=group['id'])
        if qid is not None:portfolio.append(qid)
    context=add('adaptive_context',groups,True)
    followup=context if context and context!=primary else next((qid for qid in portfolio if qid!=primary),None)
    adaptive=[primary]+([followup] if followup else [])
    return {'schema_version':1,'original_question':spec['original_question'],
            'expansion':expansion,
            'domain':spec.get('domain','medicine'),'topics':spec.get('topics',[]),
            'groups':groups,'queries':queries,'warnings':warnings,
            'query_strategies':{'single':[primary], 'portfolio':list(dict.fromkeys(portfolio)),
                                'legacy':legacy,'adaptive':adaptive},
            'vocabulary':index.manifest if index else None,
            'limitations':['Structured groups are explicit assistant/user mappings, not an automatic validated translator.',
                           'Queries retrieve candidates; they do not establish clinical efficacy or answer equivalence.']}
