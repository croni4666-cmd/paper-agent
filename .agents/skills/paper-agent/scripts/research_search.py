#!/usr/bin/env python3
"""Run opt-in concept search in the configured paper-agent runtime."""
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
    path_flags={'--mesh-index','--registry','--output','--query-cache'}
    value_flags=path_flags|{'--engine','--max-queries','--limit','--patience','--min-new','--max-sources','--time-budget','--expansion','--strategy','--cache-ttl','--reference-seeds','--reference-limit','--max-result-slots'}
    i=0;profile_seen=False
    while i<len(args):
        flag,equals,value=args[i].partition('=')
        if equals and flag in path_flags:
            args[i]=flag+'='+str(Path(value).resolve())
        elif args[i] in value_flags:
            if i+1<len(args) and args[i] in path_flags:
                args[i+1]=str(Path(args[i+1]).resolve())
            i+=1
        elif not args[i].startswith('-') and not profile_seen:
            args[i]=str(Path(args[i]).resolve());profile_seen=True
        i+=1
    index=Path(root)/'cache/terminology/mesh-2026.sqlite'
    if not any(a=='--mesh-index' or a.startswith('--mesh-index=') for a in args) and index.is_file() and '--sources-only' not in args:
        args=['--mesh-index',str(index),*args]
    try:
        result=subprocess.run([find_pa_python(root),'-m','pa_cli.research_search',*args],
                               cwd=str(root),capture_output=True,text=True,encoding='utf-8',timeout=300)
    except subprocess.TimeoutExpired:
        print(json.dumps({'error':'research_search_timeout'}),file=sys.stderr)
        return 2
    if result.stdout:print(result.stdout,end='')
    if result.stderr:print(result.stderr,end='',file=sys.stderr)
    return result.returncode


if __name__=='__main__':
    raise SystemExit(main())
