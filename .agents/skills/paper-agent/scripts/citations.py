#!/usr/bin/env python3
"""Walk OpenAlex citations: forward = citing papers, backward = references."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pa_root import find_pa_python, find_pa_root, get_install_instructions

# No "pa citations" CLI exists. Use its library in the selected runtime.
# User inputs are separate argv values, never interpolated into code.
WORKER = '''import json, sys
from contextlib import redirect_stdout
with redirect_stdout(sys.stderr):
    from pa_cli.citations import citation_walk
    directions = ('forward', 'backward') if sys.argv[2] == 'both' else (sys.argv[2],)
    walks = {d: citation_walk(sys.argv[1], direction=d, limit=int(sys.argv[3])) for d in directions}
print(json.dumps(walks, ensure_ascii=False))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('doi')
    parser.add_argument('--direction', choices=['forward', 'backward', 'both'], default='both')
    parser.add_argument('--limit', type=int, default=50, help='Maximum records per direction')
    parser.add_argument('--output', help='JSON file, relative to caller directory')
    parser.add_argument('--quiet', action='store_true')
    args = parser.parse_args()
    if args.limit < 1:
        parser.error('--limit must be positive')
    root = find_pa_root()
    if not root:
        print(json.dumps({'error': 'pa_cli_not_found', 'hint': get_install_instructions()}), file=sys.stderr)
        return 4
    runtime = find_pa_python(root)
    try:
        result = subprocess.run([runtime, '-c', WORKER, args.doi, args.direction, str(args.limit)],
                                cwd=str(root), capture_output=True, text=True, encoding='utf-8', timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        print(json.dumps({'error': 'citation_worker_failed', 'message': str(exc)}), file=sys.stderr)
        return 2
    if result.returncode:
        print(json.dumps({'error': 'citation_worker_failed', 'exit_code': result.returncode,
                          'stderr_tail': result.stderr[-500:]}), file=sys.stderr)
        return 1
    try:
        walks = json.loads(result.stdout)
        if not isinstance(walks, dict) or not walks or any(
                not isinstance(w, dict) or (not isinstance(w.get('results'), list) and not w.get('error'))
                for w in walks.values()):
            print(json.dumps({'error': 'citation_walk_failed', 'walks': walks}), file=sys.stderr)
            return 1
        successful=[w for w in walks.values() if not w.get('error') and w.get('status','ok')!='error']
        if not successful:
            print(json.dumps({'error':'citation_walk_failed','walks':walks}),file=sys.stderr)
            return 1
        papers = [paper for walk in walks.values() for paper in walk.get('results',[])]
        status='partial' if any(w.get('error') or w.get('status')=='partial' for w in walks.values()) else 'ok'
        data = {'doi': args.doi, 'direction': args.direction, 'results': papers,
                'status':status,'count': len(papers), 'walks': walks}
        if result.stderr.strip():
            data['backend_warnings'] = result.stderr[-1000:]
        if args.output:
            output = Path(args.output).expanduser().resolve()
            output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps({'status': status, 'output_file': str(output), 'count': len(papers)}))
        else:
            print(json.dumps(data, ensure_ascii=False, indent=2))
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({'error': 'invalid_citations_output', 'message': str(exc)}), file=sys.stderr)
        return 1
    if result.stderr and not args.quiet:
        print(result.stderr, end='', file=sys.stderr)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
