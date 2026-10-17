from unittest.mock import patch
from click.testing import CliRunner
from pa_cli import jobs
from pa_cli.cli import main
from pa_cli.fetch_batch import FetchSummary


def test_automatic_noise_suggestions_do_not_erase_specialist_topics(tmp_path):
    from pa_cli.topics import cluster_topics
    for number, text in enumerate(['melanoma oncology tumor']*3+['asthma allergy inhaler']*3):
        # Distinct source bytes prevent the real corpus index from correctly
        # collapsing identical fixture copies; digits do not add TF-IDF terms.
        (tmp_path/f'paper_{number}.txt').write_text((text+'\n')*20+f'\n{number}\n',encoding='utf-8')
    with patch('pa_cli.topics._build_concept_index',return_value=({},[])):
        result=cluster_topics(tmp_path,tmp_path/'topics.json',label_method='handroll',word_count_min=1)
    assert result['n_papers']==6 and result['k']==2
    assert all(t['keywords'] for t in result['topics'])
    assert result['domain_stopwords_applied_count']==0


def test_handroll_stopwords_remove_features_and_keywords():
    from pa_cli.topics import _build_tfidf_matrix, _cluster_with_handroll
    papers=[{'filename':'a.txt','title':'','text':'noise noise beta'}]
    matrix,names=_build_tfidf_matrix(papers,extra_stopwords=['noise'])
    assert names==['a.txt'] and matrix.shape==(1,1)
    topics,_=_cluster_with_handroll(papers,{},[],extra_stopwords=['noise'])
    assert topics[0]['keywords']==['beta']
    assert topics[0]['paper_count']==1


def test_stopwords_cannot_erase_source_identity():
    from pa_cli.topics import _cluster_with_handroll
    papers=[{'filename':'a.txt','title':'noise','text':''}]
    topics,_=_cluster_with_handroll(papers,{},[],extra_stopwords=['noise'])
    assert len(topics)==1 and topics[0]['filenames']==['a.txt']
    assert topics[0]['keywords']==[]


def test_jobs_reads_current_batch_counts():
    line = '[pa fetch-batch] total=4 success=2 failure=1 skipped=1 size=10 KB time=0.5s'
    assert jobs.parse_log_counts(line) == {'n_total':4,'n_success':2,'n_failed':1,'n_skipped':1}


def test_batch_cli_forwards_preferred_public_source(tmp_path):
    bib=tmp_path/'refs.bib';bib.write_text('@article{a,title={Example}}',encoding='utf-8')
    with patch('pa_cli.fetch_batch.run_fetch_batch',return_value=FetchSummary()) as worker:
        result=CliRunner().invoke(main,['fetch-batch',str(bib),'--out-dir',str(tmp_path/'out'),'--prefer','pmc'])
    assert result.exit_code==0,result.output
    assert worker.call_args.kwargs['prefer']=='pmc'
