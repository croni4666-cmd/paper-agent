"""The installed wrapper must preserve both structured errors and warnings."""
import json

from test_skill_runtime_health import backend, run_wrapper


def test_search_wrapper_preserves_failure_json_and_stderr(backend, tmp_path):
    (backend / 'pa_cli/cli.py').write_text(
        'import json,sys\n'
        'print(json.dumps({"engine_status":{"pubmed":{"status":"error","count":0}},"results":[]}))\n'
        'print("runtime warning",file=sys.stderr)\n'
        'raise SystemExit(2)\n', encoding='utf-8')
    result = run_wrapper('search.py', ['insomnia'], backend, tmp_path)
    assert result.returncode == 2
    assert json.loads(result.stdout)['engine_status']['pubmed']['status'] == 'error'
    assert 'runtime warning' in result.stderr
