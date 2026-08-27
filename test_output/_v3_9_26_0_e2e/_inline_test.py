
import click, sys, json
print("click version:", click.__version__)
sys.path.insert(0, r"G:\minimax - workspace\Paper agent")
from pa_cli import cli
print("cli imported")
print("commands:", sorted(cli.main.list_commands(None)))
print("---")
from click.testing import CliRunner
runner = CliRunner()
r1 = runner.invoke(cli.main, ["fetch-batch", "--help"])
print("fetch-batch Exit:", r1.exit_code, "len:", len(r1.output))
print("Output first 500:")
print(r1.output[:500])
print("---")
r2 = runner.invoke(cli.main, ["cnki-guide", "--help"])
print("cnki-guide Exit:", r2.exit_code, "len:", len(r2.output))
print("Output first 500:")
print(r2.output[:500])
