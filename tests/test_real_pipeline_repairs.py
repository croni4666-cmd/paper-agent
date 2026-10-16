"""Portable synthetic regressions for mechanisms found in real pipeline audits."""
from pathlib import Path
from unittest.mock import patch
import json
import pytest
from pa_cli.fetch import _is_jats_article
from pa_cli.search import _normalize_openalex,run_search
from pa_cli.review import build_corpus_index,synthesize

@pytest.fixture
def conversion_corpus(tmp_path):
    import fitz
    for i in range(6):
        doc=fitz.open()
        page=doc.new_page()
        page.insert_text((72,72),f'Synthetic study {i}. Sleep intervention comparison P < 0.01.')
        text=page.get_text()
        doc.save(tmp_path/f'study_{i}.pdf')
        doc.close()
        (tmp_path/f'study_{i}.txt').write_text(text,encoding='utf-8')
    return tmp_path

def test_pmc_wrapper_is_valid_but_error_page_is_not():
    body=b'<pmc-articleset><article><body><p>Synthetic study.</p></body></article></pmc-articleset>'
    assert _is_jats_article(body)
    assert not _is_jats_article(b'<html><body>Error</body></html>')
    assert not _is_jats_article(b'<pmc-articleset><ERROR>no article</ERROR></pmc-articleset>')

def test_openalex_keeps_available_abstracts_and_pmids():
    data={'response':{'results':[{'id':'https://openalex.org/W100', 'title':'Synthetic study',
          'ids':{'pmid':'https://pubmed.ncbi.nlm.nih.gov/12345/'},
          'abstract_inverted_index':{'Sleep':[0], 'comparison':[1]}}]}}
    for raw in data['response']['results']:
        out=_normalize_openalex(raw)
        if raw.get('abstract_inverted_index'):
            pairs=sorted((pos,word) for word,positions in raw['abstract_inverted_index'].items() for pos in positions)
            assert out['abstract']==' '.join(word for pos,word in pairs)
        if (raw.get('ids') or {}).get('pmid'):
            assert out['pmid']==raw['ids']['pmid'].rstrip('/').split('/')[-1]

def test_provider_error_and_partial_rows_keep_nested_status_contract():
    with patch('pa_cli.aminer_channel._aminer_token',return_value='test'),patch('pa_cli.aminer_channel.search_aminer',return_value=[{'error':'offline_fixture'}]):
        r=run_search('offline',engine='aminer')
    assert r['engine_status']['aminer']['status']=='error'
    assert r['engine_status']['aminer']['count']==0 and r['by_engine']['aminer']==0
    with patch('pa_cli.search.search_crossref',return_value=[{'title':'Real row','doi':'10.1000/x'},{'error':'partial_fixture'}]):
        r=run_search('offline',engine='crossref')
    assert r['engine_status']['crossref']['status']=='partial'
    assert r['engine_status']['crossref']['count']==1 and len(r['results'])==1

def test_malformed_provider_rows_are_errors():
    with patch('pa_cli.search.search_crossref',return_value=['bad']):
        r=run_search('offline',engine='crossref')
    assert r['engine_status']['crossref']['status']=='error' and r['results']==[]

def test_six_pdf_text_pairs_are_six_sources(conversion_corpus):
    rows=build_corpus_index(conversion_corpus)
    assert len(rows)==6
    assert sum(len(r['source_files']) for r in rows)==12
    assert all(r['completeness']=='unverified' and not r['is_full_text'] for r in rows)
    assert all(all(f['sha256'] for f in r['source_files']) for r in rows)

def test_different_content_same_stem_is_not_merged(tmp_path):
    (tmp_path/'same.md').write_text('# Intervention A\n'+'exercise improves sleep '*400)
    (tmp_path/'same.txt').write_text('# Intervention B\n'+'exercise does not improve sleep '*400)
    assert len(build_corpus_index(tmp_path))==2

def test_review_is_honest_inventory_not_scientific_verdict(conversion_corpus):
    text=synthesize(conversion_corpus)
    assert 'not scientific synthesis' in text
    assert 'Unique sources**: 6' in text
    assert '~47%' not in text and '✅ FULL TEXT' not in text
    assert 'completeness unverified' in text

def test_single_negation_change_in_long_same_stem_is_not_a_conversion(tmp_path):
    body='background scientific context '*500
    (tmp_path/'study.md').write_text(body+'exercise improves sleep')
    (tmp_path/'study.txt').write_text(body+'exercise does not improve sleep')
    assert len(build_corpus_index(tmp_path))==2

def test_unreadable_or_empty_sources_do_not_share_evidence_identity(tmp_path):
    (tmp_path/'empty_a.txt').write_text('')
    (tmp_path/'empty_b.txt').write_text('')
    rows=build_corpus_index(tmp_path)
    assert len({r['evidence_id'] for r in rows})==2

def test_partial_success_records_are_retained_by_research_flow():
    from pa_cli.research_search import run_research
    response={'results':[{'pmid':'123','title':'Sleep','abstract':'Sleep'}],
              'engine_status':{'pubmed':{'status':'partial','count':1}}}
    r=run_research({'original_question':'Sleep','groups':[{'id':'sleep','terms':['sleep']}]},
        searcher=lambda *a,**k:response,max_sources=0,max_queries=1)
    assert len(r['records'])==1 and r['query_runs'][0]['status']=='partial'
    assert r['research_verified'] is False

def test_cli_does_not_infer_prisma_eligibility_from_inventory(tmp_path):
    from click.testing import CliRunner
    from pa_cli.cli import main
    (tmp_path/'paper.txt').write_text('sleep '*1500)
    result=CliRunner().invoke(main,['review',str(tmp_path),'--with-prisma','--quiet'])
    assert result.exit_code==2
    assert 'eligibility' in result.output.lower()

def test_pubmed_identifier_only_record_is_not_a_provider_schema_error():
    with patch('pa_cli.search.search_pubmed',return_value=[{'pmid':'123','title':'','source':'pubmed'}]):
        r=run_search('offline',engine='pubmed')
    assert r['engine_status']['pubmed']['status']=='ok'
    assert len(r['results'])==1 and r['results'][0]['pmid']=='123'

def test_partial_metadata_is_insufficient_evidence_not_total_retrieval_failure():
    from pa_cli.research_search import run_research
    response={'results':[{'pmid':'123','title':'Sleep'}],
              'engine_status':{'pubmed':{'status':'partial','count':1}}}
    r=run_research({'original_question':'Sleep','groups':[{'id':'sleep','terms':['sleep']}]},
        searcher=lambda *a,**k:response,max_sources=0,max_queries=1)
    assert r['status']=='insufficient_candidates'
    assert len(r['records'])==1

def test_openalex_pmid_survives_cross_engine_doi_merge():
    doi='10.1000/same'
    with patch('pa_cli.search.search_crossref',return_value=[{'doi':doi,'title':'Same'}]), \
         patch('pa_cli.search.search_openalex',return_value=[{'doi':doi,'title':'Same','pmid':'12345','abstract':'Same abstract'}]):
        r=run_search('offline',engine='crossref,openalex')
    assert len(r['results'])==1 and r['results'][0]['pmid']=='12345'
