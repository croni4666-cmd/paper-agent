import json
import math
import unittest
from unittest.mock import Mock, patch
from click.testing import CliRunner
from pa_cli.engine_probe import probe_search_engines

class ProbeValidationTests(unittest.TestCase):
    def test_invalid_configuration_never_calls_provider(self):
        for options in ({'engines': []}, {'engines': ['typo']}, {'limit': 0},
                        {'limit': 6}, {'engine_timeout': math.nan},
                        {'engine_timeout': math.inf}, {'engine_timeout': 0}):
            with self.subTest(options=options):
                runner = Mock()
                with self.assertRaises(ValueError):
                    probe_search_engines('test', runner=runner, **options)
                runner.assert_not_called()

    def test_duplicate_engine_runs_once(self):
        runner = Mock(return_value={'by_engine': {'crossref': 1},
            'engine_status': {'crossref': {'status': 'ok'}}})
        report = probe_search_engines('test', engines=['crossref', 'crossref'], runner=runner)
        self.assertEqual(len(report['engines']), 1)
        self.assertEqual(runner.call_count, 1)

    def test_errors_do_not_copy_provider_secrets(self):
        for message in ('https://api.test/?api_key=secret', 'Authorization: Bearer secret',
                        'socks5://user:secret@proxy.test', 'timed out secret'):
            with self.subTest(message=message):
                report = probe_search_engines('test', engines=['crossref'],
                    runner=Mock(side_effect=RuntimeError(message)))
                self.assertNotIn('secret', json.dumps(report))

    def test_cli_rejects_invalid_selection(self):
        from pa_cli.cli import main
        with patch('pa_cli.search.run_search') as runner:
            result = CliRunner().invoke(main, ['engine-probe', '--engine', ','])
        self.assertEqual(result.exit_code, 2)
        runner.assert_not_called()
