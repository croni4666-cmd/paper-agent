import concurrent.futures as cf
import io
import threading
import time
from unittest.mock import patch

import pytest
from pypdf import PdfWriter
from pa_cli import cache, search, review

def pdf(pages=1):
    writer=PdfWriter()
    for _ in range(pages):writer.add_blank_page(width=100,height=100)
    out=io.BytesIO();writer.write(out);return out.getvalue()

def test_small_structural_pdf_accepted(tmp_path):
    cache.cache_put('10.1000/small',pdf(),root=tmp_path)
    assert cache.cache_get('10.1000/small',root=tmp_path)

def test_invalid_pdf_cannot_replace_good_index(tmp_path):
    old=cache.cache_put('10.1000/safe',pdf(650),root=tmp_path)
    with pytest.raises(ValueError):cache.cache_put('10.1000/safe',b'%PDF-1.7\n'+b'junk'*16000+b'\n%%EOF',root=tmp_path)
    assert cache.cache_get('10.1000/safe',root=tmp_path)['sha256']==old['sha256']

def test_legacy_bad_pdf_cannot_become_a_hit(tmp_path):
    import hashlib,json
    body=b'%PDF-1.7\n'+b'junk'*16000+b'\n%%EOF'
    path,meta=cache._paths('10.1000/legacy',tmp_path);path.write_bytes(body)
    meta.write_text(json.dumps({'doi':'10.1000/legacy','ts':time.time(),'sha256':hashlib.sha256(body).hexdigest()}))
    assert cache.cache_get('10.1000/legacy',root=tmp_path) is None

def test_pmid_only_is_valid_provider_identity():
    assert search._validated_engine_rows([{'pmid':'123','title':''}])==[{'pmid':'123','title':''}]

def test_pmid_survives_search_merge():
    with patch.object(search,'_run_search_engine',return_value=[{'pmid':'123','title':'','source':'pubmed'}]):
        result=search.run_search('sleep',engine='pubmed')
    assert result['engine_status']['pubmed']=='ok' and result['results'][0]['pmid']=='123'

def test_openalex_abstract_and_pmid_preserved():
    row=search._normalize_openalex({'id':'https://openalex.org/W1','title':'Study','ids':{'pmid':'https://pubmed.ncbi.nlm.nih.gov/123/'},
                                  'abstract_inverted_index':{'P':[0],'<':[1],'0.01':[2]}})
    assert row['abstract']=='P < 0.01' and row['pmid']=='123'

def test_generated_inventory_not_reingested(tmp_path):
    (tmp_path/'source.txt').write_text('Background material '*1500)
    text=review.synthesize(tmp_path)
    (tmp_path/'inventory.md').write_text(text,encoding='utf-8')
    assert len(review.build_corpus_index(tmp_path))==1
    assert '47%' not in text and 'FULL TEXT' not in text
    assert review.build_corpus_index(tmp_path)[0]['is_full_text'] is False

def test_pubmed_pacing_serializes_threads():
    barrier=threading.Barrier(8)
    def one(_):barrier.wait();search._pubmed_throttle(.05);return time.monotonic()
    with cf.ThreadPoolExecutor(8) as pool:starts=sorted(pool.map(one,range(8)))
    assert all(b-a>=.045 for a,b in zip(starts,starts[1:]))

def test_pubmed_xml_retains_comparisons():
    data=search._parse_pubmed_details(b'<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>123</PMID><Article><Abstract><AbstractText>P &lt; 0.01</AbstractText></Abstract></Article></MedlineCitation></PubmedArticle></PubmedArticleSet>')
    assert data['123']['abstract']=='P < 0.01'

def test_fetch_cannot_call_invalid_pdf_success_uncached(tmp_path,monkeypatch):
    from pa_cli import fetch
    path=tmp_path/'bad.pdf';path.write_bytes(b'%PDF-1.7\n'+b'junk'*16000+b'\n%%EOF')
    monkeypatch.setenv('PA_CACHE_DIR',str(tmp_path/'cache'))
    with patch.object(fetch,'_run_fetch_with_timeout',return_value={'pdf_path':str(path),'source':'fixture'}):
        result=fetch._fetch_doi_artifact('10.1000/bad',output_dir=str(tmp_path),use_cache=False)
    assert result['final_status']=='INVALID_ARTIFACT'
