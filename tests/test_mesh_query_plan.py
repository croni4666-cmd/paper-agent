import gzip
import json
import sqlite3

import pytest

from pa_cli.mesh_lexicon import MeshIndex, import_mesh, download_mesh
from pa_cli.query_plan import build_plan


XML = b'''<DescriptorRecordSet>
<DescriptorRecord><DescriptorUI>D001</DescriptorUI><DescriptorName><String>Menopause</String></DescriptorName>
<TreeNumberList><TreeNumber>G01.1</TreeNumber></TreeNumberList><ConceptList>
<Concept PreferredConceptYN="Y"><ConceptUI>M001</ConceptUI><ScopeNote>A life stage.</ScopeNote><TermList>
<Term><String>Menopause</String></Term><Term><String>Climacteric</String></Term></TermList></Concept>
<Concept PreferredConceptYN="N"><ConceptUI>M002</ConceptUI><TermList><Term><String>Related state</String></Term></TermList></Concept>
</ConceptList></DescriptorRecord>
<DescriptorRecord><DescriptorUI>D002</DescriptorUI><DescriptorName><String>Insomnia</String></DescriptorName>
<ConceptList><Concept PreferredConceptYN="Y"><TermList><Term><String>Insomnia</String></Term><Term><String>Sleeplessness</String></Term></TermList></Concept></ConceptList></DescriptorRecord>
<DescriptorRecord><DescriptorUI>D003</DescriptorUI><DescriptorName><String>Other stage</String></DescriptorName>
<ConceptList><Concept PreferredConceptYN="Y"><TermList><Term><String>Climacteric</String></Term></TermList></Concept></ConceptList></DescriptorRecord>
</DescriptorRecordSet>'''


@pytest.fixture
def mesh(tmp_path):
    source = tmp_path / 'desc2026.gz'
    source.write_bytes(gzip.compress(XML))
    db = tmp_path / 'mesh.sqlite'
    manifest = import_mesh(source, db, source_url='https://nlmpubs.nlm.nih.gov/example', year=2026)
    return MeshIndex(db), manifest


def profile():
    return {'original_question': '更年期女性的互联网失眠干预', 'domain': 'medicine', 'topics': ['menopause','sleep'],
            'groups': [
                {'id': 'population','terms': ['menopause'], 'mesh': ['D001'], 'required': True},
                {'id': 'outcome','terms': ['insomnia'], 'mesh': ['D002'], 'required': True},
                {'id': 'delivery','terms': ['internet','digital'], 'required': False}]}


def test_import_preserves_source_and_preferred_concept_scope(mesh):
    index, manifest = mesh
    result = index.lookup('D001')[0]
    assert result['label'] == 'Menopause'
    assert 'Climacteric' in result['synonyms']
    assert 'Related state' not in result['synonyms']
    assert result['trees'] == ['G01.1']
    assert manifest['descriptor_count'] == 3
    assert len(manifest['source_sha256']) == 64
    assert manifest['year'] == 2026


def test_ambiguous_term_returns_all_candidates(mesh):
    index, _ = mesh
    assert {r['id'] for r in index.lookup('climacteric')} == {'D001','D003'}


def test_related_concept_is_visible_but_not_silently_equated(mesh):
    index, _ = mesh
    result = index.lookup('related state')[0]
    assert result['match_kind'] == 'related'


def test_missing_index_never_silently_creates_empty_database(tmp_path):
    path = tmp_path / 'missing.sqlite'
    with pytest.raises(FileNotFoundError):
        MeshIndex(path)
    assert not path.exists()


def test_malformed_import_preserves_existing_index(mesh, tmp_path):
    index, _ = mesh
    bad = tmp_path/'bad.xml'
    bad.write_text('<wrong/>')
    with pytest.raises(ValueError):
        import_mesh(bad, index.path, source_url='https://example.org',year=2026)
    assert index.lookup('D001')[0]['label'] == 'Menopause'


def test_generated_queries_keep_required_groups_and_original_question(mesh):
    index, _ = mesh
    plan = build_plan(profile(), index)
    assert plan['original_question'] == profile()['original_question']
    assert len(plan['queries']) >= 2
    for q in plan['queries']:
        assert {'population','outcome'} <= set(q['group_ids'])
        assert 'menopause' in q['query'].lower()
        assert 'insomnia' in q['query'].lower()
    assert any('[MeSH Terms]' in q['query'] for q in plan['queries'])
    assert any('delivery' not in q['group_ids'] for q in plan['queries'])
    assert 'Related state' not in json.dumps(plan['queries'])


def test_unresolved_and_ambiguous_mapping_are_not_forced(mesh):
    index, _ = mesh
    spec = profile()
    spec['groups'][0]['mesh'] = ['Climacteric','Unknown term']
    plan = build_plan(spec,index)
    assert {w['reason'] for w in plan['warnings']} >= {'ambiguous_mesh','unresolved_mesh'}
    assert all('Other stage' not in q['query'] for q in plan['queries'])


def test_terms_cannot_inject_pubmed_fields(mesh):
    index,_=mesh
    spec=profile();spec['groups'][0]['terms']=['menopause" OR cancer[tiab]']
    with pytest.raises(ValueError):build_plan(spec,index)


def test_group_ids_and_required_population_are_validated(mesh):
    index,_=mesh
    spec=profile();spec['groups'][1]['id']='population'
    with pytest.raises(ValueError):build_plan(spec,index)
    spec=profile();spec['groups'][0]['required']=False
    # No requirement that population always be required: the actual declared
    # required groups, rather than a medical-only schema, govern all queries.
    plan=build_plan(spec,index)
    assert all('outcome' in q['group_ids'] for q in plan['queries'])


def test_duplicate_queries_removed_deterministically(mesh):
    index,_=mesh
    spec=profile();spec['groups']=spec['groups'][:2]
    a=build_plan(spec,index);b=build_plan(spec,index)
    assert a==b
    assert len({q['query'] for q in a['queries']})==len(a['queries'])


def test_download_preserves_transport_gzip_instead_of_auto_decoding(tmp_path,monkeypatch):
    import requests
    from pa_cli import _http
    raw=gzip.compress(XML)
    class Raw:
        def stream(self,chunk_size,decode_content):
            assert decode_content is False
            yield raw
    class Response:
        headers={'Content-Encoding':'gzip'}
        def __init__(self):self.raw=Raw()
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def raise_for_status(self):pass
        def iter_content(self,*args):raise AssertionError('Do not auto-decode the .gz snapshot')
    monkeypatch.setattr(requests,'get',lambda *a,**k:Response())
    monkeypatch.setattr(_http,'get_proxy_dict',lambda:{})
    result=download_mesh(2026,tmp_path)
    assert (tmp_path/'desc2026.gz').read_bytes()==raw
    assert result['bytes']==len(raw)


def test_optional_branch_does_not_claim_present_group_was_relaxed(mesh):
    index,_=mesh
    plan=build_plan(profile(),index)
    for q in plan['queries']:
        assert not (set(q['group_ids']) & set(q['relaxed_optional_groups']))
