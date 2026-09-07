import json, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pa_root import find_pa_root, get_install_instructions
def main():
    root=find_pa_root()
    if not root:
        print(json.dumps({"error":"pa_cli_not_found","hint":get_install_instructions().strip()}),file=sys.stderr); return 4
    try:
        result=subprocess.run([sys.executable,"-m","pa_cli.cli","fetch-stats","--json"],capture_output=True,text=True,timeout=30,cwd=str(root))
    except subprocess.TimeoutExpired:
        print(json.dumps({"error":"fetch_stats_timeout"}),file=sys.stderr); return 2
    if result.returncode:
        print(json.dumps({"error":"fetch_stats_failed","exit_code":result.returncode}),file=sys.stderr); return result.returncode
    try: print(json.dumps(json.loads(result.stdout)))
    except json.JSONDecodeError:
        print(json.dumps({"error":"fetch_stats_invalid_json"}),file=sys.stderr); return 1
    return 0
if __name__=="__main__": raise SystemExit(main())
