from pathlib import Path
from unittest.mock import patch
import json
import pytest
from click.testing import CliRunner
from pa_cli import jobs
from pa_cli.cli import main

def test_invalid_existing_pdf_is_not_success(tmp_path):
    from pa_cli.fetch_batch import _fetch_one_entry
    (tmp_path/'paper.pdf').write_bytes(b'%PDF-1.4 truncated actual download')
    with patch('pa_cli.fetch.fetch',return_value={'error':'unavailable'}) as fetch:
        result=_fetch_one_entry({'key':'paper','doi':'10.1234/actual'},tmp_path,skip_existing=True)
    assert not result.success and result.error!='skipped-existing'
    assert fetch.called

def test_sanitized_keys_cannot_reuse_another_paper(tmp_path):
    from pa_cli.fetch_batch import run_fetch_batch
    from pypdf import PdfWriter
    bib=tmp_path/'refs.bib';bib.write_text('@article{paper/x,doi={10.1234/a}}\n@article{paper:x,doi={10.1234/b}}')
    paths=[]
    def fake(**kw):
        path=Path(kw['out_path']);paths.append(path)
        writer=PdfWriter();writer.add_blank_page(width=100,height=100);writer.write(path)
        return {'path':str(path),'source':'fixture'}
    with patch('pa_cli.fetch.fetch',side_effect=fake):
        summary=run_fetch_batch(bib,tmp_path/'out',skip_existing=True)
    assert summary.n_success==2 and summary.n_skipped==0
    assert len(set(paths))==2

def test_job_manifest_stores_absolute_paths(tmp_path,monkeypatch):
    monkeypatch.setenv('PA_JOBS_DIR',str(tmp_path/'jobs'));monkeypatch.chdir(tmp_path)
    (tmp_path/'refs.bib').write_text('')
    with patch('pa_cli.jobs.subprocess.run') as worker:
        worker.return_value.returncode=0
        jobs.start_job('relative',Path('refs.bib'),Path('pdfs'))
    manifest=jobs.read_manifest('relative')
    assert Path(manifest.input_file).is_absolute() and Path(manifest.output_dir).is_absolute()

def test_jobs_resume_accepts_cli_budget(tmp_path,monkeypatch):
    monkeypatch.setenv('PA_JOBS_DIR',str(tmp_path/'jobs'))
    jobs.write_manifest(jobs.JobManifest('resume',str(tmp_path/'refs.bib'),str(tmp_path/'pdfs'),status='completed'))
    with patch('pa_cli.jobs.start_job',return_value=0) as start:
        result=CliRunner().invoke(main,['jobs','resume','resume','--max-total-sec','17'])
    assert result.exit_code==0,repr(result.exception)
    assert start.call_args.kwargs['max_total_sec']==17

def test_job_cli_accepts_public_pmc_source(tmp_path,monkeypatch):
    monkeypatch.setenv('PA_JOBS_DIR',str(tmp_path/'jobs'))
    bib=tmp_path/'refs.bib';bib.write_text('')
    with patch('pa_cli.jobs.start_job',return_value=0) as start:
        result=CliRunner().invoke(main,['jobs','start','--job-id','pmc','--input',str(bib),'--out',str(tmp_path/'out'),'--prefer','pmc'])
    assert result.exit_code==0,result.output
    assert start.call_args.kwargs['prefer']=='pmc'

def test_interrupted_job_cli_has_nonzero_status(tmp_path,monkeypatch):
    monkeypatch.setenv('PA_JOBS_DIR',str(tmp_path/'jobs'))
    bib=tmp_path/'refs.bib';bib.write_text('')
    with patch('pa_cli.jobs.start_job',return_value=-1):
        result=CliRunner().invoke(main,['jobs','start','--job-id','timeout','--input',str(bib),'--out',str(tmp_path/'out')])
    assert result.exit_code!=0

def test_saved_concept_remains_one_name():
    with patch('pa_cli.search_saved.get',return_value={'query':'sleep'}),patch('pa_cli.search_saved.to_pa_args',return_value={'query':'sleep','concept':'machine learning'}),patch('pa_cli.concepts.resolve_concept_ids',return_value=([],[])) as resolve,patch('pa_cli.search.run_search',return_value={'results':[]}):
        result=CliRunner().invoke(main,['search-saved','run','saved','--quiet'])
    assert result.exit_code==0,repr(result.exception)
    assert resolve.call_args.args[0]==['machine learning']

def test_explicit_aminer_mode_is_not_discarded():
    with patch('pa_cli.search.run_search',return_value={'results':[]}) as run:
        result=CliRunner().invoke(main,['search','multi word query','--engine','aminer','--aminer-mode','basic','--quiet'])
    assert result.exit_code==0,repr(result.exception)
    assert run.call_args.kwargs.get('aminer_mode')=='basic'

def test_scaffold_accepts_generated_topics_and_keeps_unassigned():
    from pa_cli.scaffold import _group_by_topic
    entries=[{'key':'a'},{'key':'b'},{'key':'c'}]
    result=_group_by_topic(entries,{'topics':[{'topic_id':1,'label':'Sleep','filenames':['a.pdf']},{'topic_id':2,'label':'Exercise','filenames':['b.txt']}]})
    assert [x[0] for x in result]==['Sleep','Exercise','Other / Unclustered']
    assert [p['key'] for _,papers in result for p in papers]==['a','b','c']

def test_screening_resolves_title_and_abstract_macros(tmp_path):
    from pa_cli.export_screening import build_screening_dict
    bib=tmp_path/'refs.bib';bib.write_text('@string{study={Accurate Study}}\n@article{a,title=study # { of care},abstract=study # { findings},journal=study}')
    row=build_screening_dict(bib)['a']
    assert row['title']=='Accurate Study of care' and row['abstract']=='Accurate Study findings'

def test_term_overlap_does_not_establish_claim_support(tmp_path):
    from pa_cli.mcp_fetch import _handle_pa_verify_claim
    pdf=tmp_path/'evidence.pdf';pdf.write_bytes(b'placeholder; extraction mocked')
    span={'text':'Treatment does not reduce mortality.','page':1,'section':'results','start':0,'end':35,'evidence_id':'e1'}
    with patch('pa_cli.evidence.build_index',return_value={}),patch('pa_cli.evidence.build_packet',return_value={'evidence':[span],'artifact_sha256':'a'}):
        result=_handle_pa_verify_claim({'pdf_path':str(pdf),'claim':'Treatment does reduce mortality'})
    assert result['verdict']=='insufficient_evidence'
    assert result['supporting_passages']==[]
    assert result['evidence_passages'][0]['verbatim_text']==span['text']
    assert result['verification_status']=='human_review_required'
