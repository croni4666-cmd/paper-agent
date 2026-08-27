"""Check if pa_cli.cli imports and what commands are registered."""
import sys
sys.path.insert(0, r"G:\minimax - workspace\Paper agent")
try:
    from pa_cli import cli
    print("pa_cli.cli imports OK")
    # List all click commands
    if hasattr(cli, "main"):
        main = cli.main
        print(f"main group: {main}")
        # Click 8: commands attribute, Click 9: get_command
        try:
            commands = main.list_commands(None) if hasattr(main, "list_commands") else []
            print(f"Registered commands ({len(commands)}):")
            for cmd in sorted(commands):
                print(f"  - {cmd}")
        except Exception as e:
            print(f"Error listing commands: {e}")
except Exception as e:
    import traceback
    traceback.print_exc()
    print(f"IMPORT ERROR: {e}")
