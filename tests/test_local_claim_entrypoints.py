import importlib.util
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch
import pytest

S=Path(__file__).resolve().parents[1]/'.agents/skills/paper-agent/scripts'
def load(name):
    sys.path.insert(0,str(S))
    spec=importlib.util.spec_from_file_location('local_'+name,S/(name+'.py'))
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod

def test_actual_claim_wrapper_does_not_infer_support(tmp_path):
    wrapper=load('verify_claim')
    span={'page':1,'start':0,'end':35,'text':'Treatment does not reduce mortality.','evidence_id':'e1','section':'results'}
    with patch('pa_cli.evidence.build_index',return_value={}),patch('pa_cli.evidence.build_packet',return_value={'evidence':[span]}):
        result=wrapper.verify(tmp_path/'paper.pdf','Treatment does reduce mortality')
    assert result['verdict']=='insufficient_evidence'
    assert result['supporting_passages']==[] and result['evidence_passages']

@pytest.mark.parametrize('name',['evidence','verify_claim'])
def test_evidence_entrypoints_use_selected_interpreter(tmp_path,name):
    wrapper=load(name);pdf=tmp_path/'test.pdf';pdf.write_bytes(b'%PDF mocked child')
    target=str(tmp_path/'selected_python.exe')
    argv=[name,str(pdf)] + (['--claim','sleep'] if name=='verify_claim' else ['--query','sleep'])
    with patch.object(wrapper,'find_pa_root',return_value=S.parents[3]),patch('_pa_runtime.find_pa_python',return_value=target),patch('subprocess.run',return_value=subprocess.CompletedProcess([],0)) as run,patch.object(sys,'argv',argv):
        result=wrapper.main()
    assert result==0 and run.called
    assert run.call_args.args[0][0]==target

@pytest.mark.parametrize('name',['evidence','verify_claim'])
def test_evidence_output_cannot_overwrite_source(tmp_path,name):
    wrapper=load(name);pdf=tmp_path/'test.pdf';before=b'%PDF original source';pdf.write_bytes(before)
    argv=[name,str(pdf),'--output',str(pdf)] + (['--claim','sleep'] if name=='verify_claim' else ['--index-only'])
    with patch.object(wrapper,'find_pa_root',return_value=S.parents[3]),patch('_pa_runtime.find_pa_python',return_value=sys.executable),patch('pa_cli.evidence.build_index',return_value={}),patch('pa_cli.evidence.build_packet',return_value={'evidence':[]}),patch.object(sys,'argv',argv):
        result=wrapper.main()
    assert result!=0 and pdf.read_bytes()==before
