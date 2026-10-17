from pathlib import Path
from unittest.mock import patch
from pa_cli.fetch_batch import _fetch_one_entry,run_fetch_batch
from pa_cli import jobs

def test_new_invalid_download_is_not_success(tmp_path):
    def broken(**kwargs):
        out=Path(kwargs['out_path']);out.write_bytes(b'%PDF-1.4 truncated upstream content')
        return {'path':str(out),'source':'upstream','size':out.stat().st_size}
    with patch('pa_cli.fetch.fetch',side_effect=broken):
        result=_fetch_one_entry({'key':'new','doi':'10.1234/broken'},tmp_path)
    assert not result.success

def test_ambiguous_duplicate_keys_do_not_skip_another_doi(tmp_path):
    from pypdf import PdfWriter
    bib=tmp_path/'refs.bib';bib.write_text('@article{same,doi={10.1234/a}}\n@article{same,doi={10.1234/b}}')
    def fake(**kwargs):
        out=Path(kwargs['out_path']);writer=PdfWriter();writer.add_blank_page(width=100,height=100);writer.write(out)
        return {'path':str(out)}
    with patch('pa_cli.fetch.fetch',side_effect=fake):
        result=run_fetch_batch(bib,tmp_path/'out',skip_existing=True)
    assert result.n_failure==2 and result.n_success==0 and result.n_skipped==0
    assert all('duplicate' in r.error for r in result.results)

def test_partial_job_has_failure_exit_and_manifest(tmp_path,monkeypatch):
    monkeypatch.setenv('PA_JOBS_DIR',str(tmp_path/'jobs'))
    def child(cmd,stdout,**kwargs):
        stdout.write('[pa fetch-batch] total=2 success=1 failure=1 skipped=0\n')
        return type('Result',(),{'returncode':0})()
    with patch('pa_cli.jobs.subprocess.run',side_effect=child):
        code=jobs.start_job('partial',tmp_path/'refs.bib',tmp_path/'out')
    assert jobs.read_manifest('partial').status=='failed'
    assert code!=0

def test_windows_case_key_conflict_is_reported(tmp_path):
    bib=tmp_path/'refs.bib';bib.write_text('@article{Paper,doi={10.1234/a}}\n@article{paper,doi={10.1234/b}}')
    with patch('pa_cli.fetch.fetch',return_value={'error':'not expected'}) as fetch:
        result=run_fetch_batch(bib,tmp_path/'out',skip_existing=True)
    assert result.n_failure==2 and not fetch.called
    assert all('duplicate' in r.error for r in result.results)

def test_reserved_device_basename_is_removed(tmp_path):
    with patch('pa_cli.fetch.fetch',return_value={'error':'probe'}) as fetch:
        _fetch_one_entry({'key':'CON.txt','doi':'10.1234/a'},tmp_path)
    assert Path(fetch.call_args.kwargs['out_path']).name.split('.')[0].upper()!='CON'

def test_scaffold_does_not_guess_ambiguous_file_stems():
    from pa_cli.scaffold import _group_by_topic
    entries=[{'key':'a'}]
    topics=[{'label':'Sleep','filenames':['a.pdf']},{'label':'Exercise','filenames':['a.txt']}]
    for order in (topics,topics[::-1]):
        assert _group_by_topic(entries,{'topics':order})==[('Other / Unclustered',entries)]

def test_resume_cli_default_uses_original_timeout(tmp_path,monkeypatch):
    from click.testing import CliRunner
    from pa_cli.cli import main
    monkeypatch.setenv('PA_JOBS_DIR',str(tmp_path/'jobs'))
    jobs.write_manifest(jobs.JobManifest('budget',str(tmp_path/'r.bib'),str(tmp_path/'pdf'),status='completed',max_total_sec=17))
    with patch('pa_cli.jobs.start_job',return_value=0) as start:
        r=CliRunner().invoke(main,['jobs','resume','budget'])
    assert r.exit_code==0
    assert start.call_args.kwargs['max_total_sec']==17

def test_no_match_claim_keeps_response_schema(tmp_path):
    from pa_cli.mcp_fetch import _handle_pa_verify_claim
    pdf=tmp_path/'a.pdf';pdf.write_bytes(b'mocked extraction')
    with patch('pa_cli.evidence.build_index',return_value={}),patch('pa_cli.evidence.build_packet',return_value={'evidence':[]}):
        result=_handle_pa_verify_claim({'pdf_path':str(pdf),'claim':'sleep'})
    assert result['evidence_passages']==[] and result['verification_status']=='human_review_required'
