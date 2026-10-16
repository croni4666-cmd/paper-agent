import json
import pytest

from test_skill_runtime_health import backend, run_wrapper


def module_fixture(backend,name):
    (backend/f'pa_cli/{name}.py').write_text(
        'import json,sys,os\nprint(json.dumps({"argv":sys.argv[1:],"cwd":os.getcwd()}))',encoding='utf-8')


def test_research_wrapper_resolves_caller_paths_and_runtime(backend,tmp_path):
    module_fixture(backend,'research_search')
    (tmp_path/'profile.json').write_text('{}')
    result=run_wrapper('research_search.py',['profile.json','--output','result.json','--dry-run'],backend,tmp_path)
    assert result.returncode==0,result.stderr
    data=json.loads(result.stdout)
    assert data['argv'][0]==str(tmp_path/'profile.json')
    assert data['argv'][data['argv'].index('--output')+1]==str(tmp_path/'result.json')
    assert data['cwd']==str(backend)


def test_terminology_wrapper_resolves_import_paths(backend,tmp_path):
    module_fixture(backend,'mesh_lexicon')
    result=run_wrapper('terminology.py',['import','desc2026.gz','--output','mesh.sqlite',
                       '--source-url','https://example.test/mesh','--year','2026'],backend,tmp_path)
    assert result.returncode==0,result.stderr
    data=json.loads(result.stdout)
    assert data['argv'][1]==str(tmp_path/'desc2026.gz')
    assert data['argv'][data['argv'].index('--output')+1]==str(tmp_path/'mesh.sqlite')


def test_europepmc_engine_before_profile_is_not_treated_as_path(backend,tmp_path):
    module_fixture(backend,'research_search')
    result=run_wrapper('research_search.py',['--engine','europepmc','profile.json','--dry-run'],backend,tmp_path)
    assert result.returncode==0,result.stderr
    args=json.loads(result.stdout)['argv']
    assert args[args.index('--engine')+1]=='europepmc'
    assert str(tmp_path/'profile.json') in args


def test_wrapper_supports_options_before_profile_and_equals_paths(backend,tmp_path):
    module_fixture(backend,'research_search')
    default=backend/'cache/terminology/mesh-2026.sqlite'
    default.parent.mkdir(parents=True);default.touch()
    result=run_wrapper('research_search.py',['--max-queries','2','profile.json',
                       '--output=run.json','--mesh-index=custom.sqlite'],backend,tmp_path)
    assert result.returncode==0,result.stderr
    args=json.loads(result.stdout)['argv']
    assert str(tmp_path/'profile.json') in args
    assert '--output='+str(tmp_path/'run.json') in args
    assert '--mesh-index='+str(tmp_path/'custom.sqlite') in args
    assert '--mesh-index' not in args


def test_terminology_wrapper_supports_equals_paths(backend,tmp_path):
    module_fixture(backend,'mesh_lexicon')
    result=run_wrapper('terminology.py',['lookup','Menopause','--index=mesh.sqlite'],backend,tmp_path)
    assert result.returncode==0,result.stderr
    assert '--index='+str(tmp_path/'mesh.sqlite') in json.loads(result.stdout)['argv']
