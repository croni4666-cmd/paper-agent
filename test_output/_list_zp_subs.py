"""Quick CLI introspection helper — list pa zotero project subcommands."""
import sys
sys.path.insert(0, '.')
from pa_cli import cli

zp = cli.main.commands['zotero'].commands['project']
print('pa zotero project subcommands:')
for name in sorted(zp.commands.keys()):
    cmd = zp.commands[name]
    h = (cmd.help or '').split('\n')[0]
    print(f'  - pa zotero project {name}  -- {h}')
