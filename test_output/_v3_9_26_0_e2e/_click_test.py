"""Test pa_cli.cli command invocation with CliRunner."""
import click
print('click version:', click.__version__)
import sys
sys.path.insert(0, r'G:\minimax - workspace\Paper agent')
from pa_cli import cli
print('cli imported')
from click.testing import CliRunner
runner = CliRunner()
# Test 1: fetch-batch --help
result = runner.invoke(cli.main, ['fetch-batch', '--help'])
print('fetch-batch Exit:', result.exit_code)
print('Output first 300:')
print(result.output[:300])
print('---')
# Test 2: cnki-guide --help
result2 = runner.invoke(cli.main, ['cnki-guide', '--help'])
print('cnki-guide Exit:', result2.exit_code)
print('Output first 300:')
print(result2.output[:300])
print('---')
# Test 3: Try fetch-batch with no args (should show error)
result3 = runner.invoke(cli.main, ['fetch-batch'])
print('fetch-batch (no args) Exit:', result3.exit_code)
print('Output first 500:')
print(result3.output[:500])
