"""Installed wrappers must honor the configured runtime, not host Python."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / '.agents/skills/paper-agent/scripts'


@pytest.fixture
def backend(tmp_path):
    root = tmp_path / 'backend with spaces'
    package = root / 'pa_cli'
    package.mkdir(parents=True)
    (package / '__init__.py').write_text('__version__ = "9.8.7"', encoding='utf-8')
    (root / 'pyproject.toml').write_text('[project]\nname="fixture"\nversion="9.8.7"', encoding='utf-8')
    (package / 'citations.py').write_text(
        'def citation_walk(doi, direction, limit):\n'
        '    return {"results":[{"title":"追星 café 😀","year":2025}],"count":1,"direction":direction}\n', encoding='utf-8')
    (package / 'cli.py').write_text(
        'import json, sys\n'
        'from pathlib import Path\n'
        'if "citations" in sys.argv: raise SystemExit("No such command citations")\n'
        'data={"results":[{"title":"追星 café 😀","year":2025}],"count":1}\n'
        'if "--output" in sys.argv:\n'
        '    Path(sys.argv[sys.argv.index("--output")+1]).write_text(json.dumps(data),encoding="utf-8")\n'
        'else:\n'
        '    print(json.dumps(data,ensure_ascii=False))\n', encoding='utf-8')
    return root


def run_wrapper(name, args, backend, cwd, **env_updates):
    env = {**os.environ, 'PAPER_AGENT_ROOT': str(backend),
           'PAPER_AGENT_PYTHON': sys.executable, 'PYTHONUTF8': '0',
           'PYTHONIOENCODING': 'utf-8', **env_updates}
    # Simulate the minimal host interpreter without altering the selected child.
    launch = ('import runpy,sys; script=sys.argv[1]; sys.argv=sys.argv[1:]; '
              'sys.executable="missing-host-python"; runpy.run_path(script,run_name="__main__")')
    return subprocess.run([sys.executable, '-c', launch, str(SCRIPTS / name), *args],
                          cwd=cwd, env=env, capture_output=True, encoding='utf-8', timeout=30)


@pytest.mark.parametrize('name,args', [
    ('search.py', ['topic', '--engine', 'crossref']),
    ('fetch_stats.py', []), ('cache.py', ['stats']), ('keys.py', ['list']),
    ('citations.py', ['10.1000/test']),
])
def test_wrappers_use_selected_python_and_preserve_unicode(name, args, backend, tmp_path):
    result = run_wrapper(name, args, backend, tmp_path)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['results'][0]['title'] == '追星 café 😀'


def test_bootstrap_checks_selected_runtime(backend, tmp_path):
    result = run_wrapper('bootstrap.py', ['--check'], backend, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)['status'] == 'ok'


def test_invalid_explicit_repo_does_not_report_healthy(backend, tmp_path):
    result = run_wrapper('bootstrap.py', ['--repo', str(tmp_path/'missing'), '--check'], backend, tmp_path)
    assert result.returncode != 0
    assert json.loads(result.stdout)['status'] == 'repo_not_found'


def test_version_checks_selected_runtime(backend, tmp_path):
    (backend / 'fitz.py').write_text('print("optional library warning")', encoding='utf-8')
    result = run_wrapper('version.py', [], backend, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    data = json.loads(result.stdout)
    assert data['pa_cli_version'] == '9.8.7'
    assert data['runtime_python'] == sys.executable
    assert data['skill_version'] != '3.9.28.0'


def test_importable_playwright_without_browser_is_not_ready(backend, tmp_path):
    (backend / 'playwright').mkdir()
    (backend / 'playwright/__init__.py').write_text('', encoding='utf-8')
    result = run_wrapper('version.py', [], backend, tmp_path)
    data = json.loads(result.stdout)
    assert data['optional_deps']['playwright']['installed'] is True
    assert data['jats_to_pdf_available'] is False


def test_citations_output_is_relative_to_caller(backend, tmp_path):
    result = run_wrapper('citations.py', ['10.1000/test', '--output', 'citations.json'], backend, tmp_path)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / 'citations.json').is_file()
    assert not (backend / 'citations.json').exists()


def test_search_markdown_handles_backend_envelope(backend, tmp_path):
    result = run_wrapper('search.py', ['topic', '--output', 'markdown'], backend, tmp_path)
    assert result.returncode == 0, result.stderr
    assert '追星 café 😀' in result.stdout


@pytest.mark.parametrize('topics', [False, True])
def test_review_uses_real_backend_contract_and_caller_paths(tmp_path, topics):
    if topics:
        pytest.importorskip('sklearn', reason='optional topic-clustering dependency')
    corpus = tmp_path / 'corpus'
    corpus.mkdir()
    (corpus / 'sample.txt').write_text('Local test paper without a DOI. Family and media research.', encoding='utf-8')
    args = ['corpus', '--output', 'result.json' if topics else 'result.md']
    if topics:
        args.append('--topics')
    result = run_wrapper('review.py', args, SCRIPTS.parents[3], tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    data = json.loads(result.stdout)
    assert Path(data['output']).is_file()
    assert Path(data['output']).parent == tmp_path
    assert data['mode'] == ('clustering' if topics else 'draft')


def test_review_rejects_unsupported_llm_options(backend, tmp_path):
    result = run_wrapper('review.py', ['.', '--model', 'unused'], backend, tmp_path)
    assert result.returncode == 2
    assert json.loads(result.stderr)['error'] == 'unsupported_review_options'


def test_citations_backend_failure_does_not_write_output(backend, tmp_path):
    (backend / 'pa_cli/citations.py').write_text('def citation_walk(*args, **kwargs): return {"error":"doi_not_found"}', encoding='utf-8')
    result = run_wrapper('citations.py', ['10.1000/test', '--output', 'missing.json'], backend, tmp_path)
    assert result.returncode != 0
    assert not (tmp_path / 'missing.json').exists()
    assert json.loads(result.stderr)['error'] == 'citation_walk_failed'


@pytest.mark.parametrize('command', ['check', 'audit'])
def test_keys_commands_do_not_pass_unsupported_json_option(backend, tmp_path, command):
    (backend / 'pa_cli/cli.py').write_text('import sys\nassert "--json" not in sys.argv\nprint("{}")', encoding='utf-8')
    result = run_wrapper('keys.py', [command, 'openalex'] if command == 'check' else [command], backend, tmp_path)
    assert result.returncode == 0, result.stderr


def test_cache_clean_maps_backend_option_without_touching_user_cache(backend, tmp_path):
    (backend / 'pa_cli/cli.py').write_text('import sys\nassert "--older-than" in sys.argv\nassert "--older-than-days" not in sys.argv\nprint("{}")', encoding='utf-8')
    result = run_wrapper('cache.py', ['clean', '--older-than-days', '90'], backend, tmp_path)
    assert result.returncode == 0, result.stderr


def test_cache_clear_requires_confirmation_before_worker(backend, tmp_path):
    result = run_wrapper('cache.py', ['clear'], backend, tmp_path)
    assert result.returncode == 2
    assert json.loads(result.stderr)['error'] == 'cache_clear_confirmation_required'


def test_confirmed_cache_clear_uses_supported_backend_alias(backend, tmp_path):
    (backend / 'pa_cli/cli.py').write_text('import sys\nassert "clean" in sys.argv and "--all" in sys.argv\nassert "--confirm" not in sys.argv\nprint("{}")', encoding='utf-8')
    result = run_wrapper('cache.py', ['clear', '--confirm'], backend, tmp_path)
    assert result.returncode == 0, result.stderr
