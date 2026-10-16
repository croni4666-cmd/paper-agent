#!/usr/bin/env python3
"""Download/import/lookup MeSH using the configured paper-agent runtime."""
from pathlib import Path
import json
import subprocess
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
from _pa_root import find_pa_python, find_pa_root


def main():
    root=find_pa_root()
    if not root:
        print(json.dumps({'error':'pa_cli_not_found'}),file=sys.stderr)
        return 4
    args=list(sys.argv[1:])
    if len(args)>1 and args[0]=='import' and not args[1].startswith('-'):
        args[1]=str(Path(args[1]).resolve())
    for flag in ('--output','--index','--directory'):
        if flag in args and args.index(flag)+1<len(args):
            i=args.index(flag)+1
            args[i]=str(Path(args[i]).resolve())
        for i,arg in enumerate(args):
            if arg.startswith(flag+'='):
                args[i]=flag+'='+str(Path(arg.split('=',1)[1]).resolve())
    try:
        result=subprocess.run([find_pa_python(root),'-m','pa_cli.mesh_lexicon',*args],
                               cwd=str(root),capture_output=True,text=True,encoding='utf-8',timeout=180)
    except subprocess.TimeoutExpired:
        print(json.dumps({'error':'terminology_operation_timeout'}),file=sys.stderr)
        return 2
    if result.stdout:print(result.stdout,end='')
    if result.stderr:print(result.stderr,end='',file=sys.stderr)
    return result.returncode


if __name__=='__main__':
    raise SystemExit(main())
