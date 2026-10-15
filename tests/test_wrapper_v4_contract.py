"""Check wrappers against the real v4 Click parser, without invoking providers."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from pa_cli.cli import main as cli

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / '.agents/skills/paper-agent/scripts'


class V4WrapperTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.corpus = Path(self.temp.name) / 'corpus'
        self.corpus.mkdir()

    def load(self, name):
        spec = importlib.util.spec_from_file_location('wrapper_' + name, SCRIPTS / (name + '.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def invoke(self, name, arguments, payload=None):
        module = self.load(name)
        commands = []

        def run(command, **kwargs):
            # Parse the actual commands/options; never invoke command callbacks.
            args = command[3:]
            group = cli
            ctx = None
            while True:
                command_name = args[0]
                group = group.commands[command_name]
                ctx = group.make_context(command_name, args[1:], parent=ctx)
                if not hasattr(group, 'commands'):
                    break
                args = [ctx.protected_args[0], *ctx.args]
            commands.append(command)
            if '--output' in command:
                Path(command[command.index('--output') + 1]).write_text('{}', encoding='utf-8')
            return subprocess.CompletedProcess(command, 0, json.dumps(payload or {'results': []}), '')

        output = io.StringIO()
        with patch.object(module, 'find_pa_root', return_value=ROOT), patch.object(
            module, 'run_pa', side_effect=run
        ), patch.object(sys, 'argv', [name, *arguments]), contextlib.redirect_stdout(output):
            code = module.main()
        self.assertEqual(code, 0, output.getvalue())
        self.assertTrue(commands)

    def test_review_and_clustering_use_v4_options(self):
        for extra in ([], ['--topics']):
            self.invoke('review', [str(self.corpus), '--output', str(self.corpus / 'out.json'), *extra])

    def test_citation_directions_match_cli(self):
        for extra in ([], ['--direction', 'backward']):
            self.invoke('citations', ['10.1000/example', *extra])

    def test_key_subcommands_have_valid_options(self):
        for arguments in (['list'], ['audit'], ['check', 'pubmed']):
            self.invoke('keys', arguments)

    def test_cache_subcommands_have_valid_options(self):
        for arguments in (['stats'], ['path'], ['clean', '--older-than-days', '30', '--dry-run']):
            self.invoke('cache', arguments)

    def test_search_controls_match_cli(self):
        self.invoke('search', ['topic', '--strategy', 'fast', '--source', 'openalex', '--quality-mode', 'off'])

    def test_unsupported_legacy_options_fail_before_child_process(self):
        for name, args in (
            ('review', [str(self.corpus), '--model', 'unsupported']),
            ('review', [str(self.corpus), '--top-k-clusters', '3']),
            ('citations', ['10.1000/example', '--direction', 'both']),
        ):
            module = self.load(name)
            with patch.object(sys, 'argv', [name, *args]), patch.object(module, 'run_pa') as child:
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    module.main()
                child.assert_not_called()

    def test_malformed_search_rows_fail_with_json_error(self):
        module = self.load('search')
        output = io.StringIO()
        with patch.object(module, 'find_pa_root', return_value=ROOT), patch.object(
            module, 'run_pa', return_value=subprocess.CompletedProcess([], 0, '{"results":[null]}', '')
        ), patch.object(sys, 'argv', ['search', 'topic']), contextlib.redirect_stderr(output):
            self.assertEqual(module.main(), 1)
        self.assertEqual(json.loads(output.getvalue())['error'], 'invalid_search_response')


if __name__ == '__main__':
    unittest.main()
