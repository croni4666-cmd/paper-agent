import importlib.util,json,sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import pytest

SCRIPT=Path(__file__).resolve().parents[1]/'.agents/skills/paper-agent/scripts/fetch.py'
def load():
 spec=importlib.util.spec_from_file_location('fetch_wrapper_test',SCRIPT);m=importlib.util.module_from_spec(spec)
 with patch.dict(sys.modules,{'_pa_root':SimpleNamespace(find_pa_root=lambda:SCRIPT.parents[4],find_pa_python=lambda root:sys.executable,get_install_instructions=lambda:'install')}):spec.loader.exec_module(m)
 return m

def test_relative_output_uses_callers_directory(tmp_path,monkeypatch):
 m=load();monkeypatch.chdir(tmp_path)
 with patch.object(sys,'argv',['fetch.py','10.1000/test','--output-dir','papers']),patch.object(m.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout='{}',stderr='')) as run:
  assert m.main()==0
 args=run.call_args.args[0]
 assert Path(args[args.index('--output-dir')+1])==tmp_path/'papers'
 assert run.call_args.kwargs['encoding']=='utf-8'

def test_structured_failure_is_preserved(capsys):
 m=load();body={'handoff':{'user_action_required':'Provide accessible PDF'},'final_status':'ALL_FAIL'}
 with patch.object(sys,'argv',['fetch.py','10.1000/test']),patch.object(m.subprocess,'run',return_value=SimpleNamespace(returncode=2,stdout=json.dumps(body),stderr='failed')):
  assert m.main()==2
 assert json.loads(capsys.readouterr().out)==body

def test_invalid_doi_rejected_before_worker(capsys):
 m=load()
 with patch.object(sys,'argv',['fetch.py','not-a-doi']),patch.object(m.subprocess,'run') as run:
  assert m.main()==2
 run.assert_not_called()
 assert json.loads(capsys.readouterr().err)['error']=='invalid_doi'
@pytest.mark.parametrize('identifier',['https://doi.org/10.1000/test','doi:10.1000/test','arxiv:1706.03762','1706.03762','https://arxiv.org/abs/1706.03762/','arxiv: 1706.03762'])
def test_supported_identifier_forms(identifier):
 m=load()
 with patch.object(sys,'argv',['fetch.py',identifier]),patch.object(m.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout='{}',stderr='')) as run:
  assert m.main()==0
 assert run.call_args.args[0][4] in ('10.1000/test','10.48550/arXiv.1706.03762')

def test_runtime_override_is_preserved(tmp_path,monkeypatch):
 spec=importlib.util.spec_from_file_location('root_test',SCRIPT.with_name('_pa_root.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 python=tmp_path/'python.exe';python.touch();monkeypatch.setenv('PAPER_AGENT_PYTHON',str(python))
 assert m.find_pa_python(tmp_path)==str(python.resolve())
def test_local_runtime_config_resolves_outside_repo(tmp_path,monkeypatch):
 spec=importlib.util.spec_from_file_location('config_test',SCRIPT.with_name('_pa_root.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 skill=tmp_path/'skill';(skill/'scripts').mkdir(parents=True)
 root=tmp_path/'backend';(root/'pa_cli').mkdir(parents=True);(root/'pa_cli/__init__.py').touch()
 python=tmp_path/'python.exe';python.touch()
 (skill/'runtime.local.json').write_text(json.dumps({'root':str(root),'python':str(python)}),encoding='utf-8')
 monkeypatch.delenv('PAPER_AGENT_ROOT',raising=False);monkeypatch.delenv('PAPER_AGENT_PYTHON',raising=False)
 monkeypatch.setattr(m,'__file__',str(skill/'scripts/_pa_root.py'));monkeypatch.chdir(tmp_path)
 assert m.find_pa_root()==root.resolve()
 assert m.find_pa_python(root)==str(python.resolve())

@pytest.mark.parametrize('override',[True,False])
def test_interpreter_symlink_preserves_venv(tmp_path,monkeypatch,override):
 spec=importlib.util.spec_from_file_location('venv_test',SCRIPT.with_name('_pa_root.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 target=tmp_path/'base-python';target.touch();link=tmp_path/'.venv/bin/python';link.parent.mkdir(parents=True)
 try:link.symlink_to(target)
 except OSError:pytest.skip('symlink creation unavailable')
 monkeypatch.delenv('PAPER_AGENT_PYTHON',raising=False)
 if override:monkeypatch.setenv('PAPER_AGENT_PYTHON',str(link))
 assert m.find_pa_python(tmp_path)==str(link.absolute())
