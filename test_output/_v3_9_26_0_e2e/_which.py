"""Check which pa_cli.cli is loaded."""
import sys
sys.path.insert(0, r"G:\minimax - workspace\Paper agent")
import pa_cli.cli
print("pa_cli.cli loaded from:", pa_cli.cli.__file__)
print("pa_cli version:", pa_cli.__version__)
# Check if fetch-batch is registered
main = pa_cli.cli.main
print("Commands:", sorted(main.list_commands(None)))
