"""Publication identity and non-destructive metadata merging shared by workflows."""
import re


def canonical_doi(value):
    return re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)', '', str(value or '').strip(), flags=re.I).lower()


def record_aliases(paper):
    source=paper.get('source') or ''
    if source.startswith('clinicaltrials'):
        return ['registry:'+str(paper['nct_id']).strip()] if paper.get('nct_id') else []
    doi=canonical_doi(paper.get('doi'))
    aliases=['doi:'+doi] if doi else []
    for field in ('pmid','pmcid','arxiv_id','openalex_id'):
        if paper.get(field):aliases.append(field+':'+str(paper[field]).strip())
    if paper.get('europepmc_id') and paper.get('upstream_source'):
        aliases.append('epmc:'+str(paper['upstream_source'])+':'+str(paper['europepmc_id']))
    if not aliases and paper.get('title'):
        aliases=['title:'+paper['title'].strip().casefold()]
    return aliases


def merge_metadata(target, incoming):
    for name,value in incoming.items():
        if name in ('found_by','query_ids','reference_seed_dois'):
            target[name]=list(dict.fromkeys([*(target.get(name) or []),*(value or [])]))
        elif not target.get(name) and value not in ('',None,[]):
            target[name]=value
    return target


def deduplicate_records(papers):
    seen={};owners={}
    for paper in papers:
        if not isinstance(paper,dict) or 'error' in paper:continue
        aliases=record_aliases(paper)
        if not aliases:continue
        matches=list(dict.fromkeys(owners[a] for a in aliases if a in owners))
        key=matches[0] if matches else aliases[0]
        for other in matches[1:]:
            merge_metadata(seen[key],seen.pop(other))
            for alias,owner in list(owners.items()):
                if owner==other:owners[alias]=key
        if key not in seen:seen[key]=dict(paper)
        else:merge_metadata(seen[key],paper)
        for alias in aliases:owners[alias]=key
    return list(seen.values())
