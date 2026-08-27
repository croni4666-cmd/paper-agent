"""Patch the remaining 5 wrapper scripts to use _pa_root."""
import re
from pathlib import Path

SKILL_SCRIPTS = Path(r"G:\minimax - workspace\Paper agent\.agents\skills\paper-agent\scripts")
WRAPPERS = ["fetch_batch.py", "review.py", "citations.py", "keys.py", "cache.py"]

OLD_HEADER = """SKILL_ROOT = Path(__file__).resolve().parent.parent
PA_ROOT = SKILL_ROOT.parent.parent.parent
PYTHON = sys.executable"""

NEW_HEADER = """SKILL_ROOT = Path(__file__).resolve().parent.parent
PYTHON = sys.executable

# Add this script's directory to sys.path so we can import _pa_root
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pa_root import find_pa_root, get_install_instructions  # noqa: E402"""

for w in WRAPPERS:
    p = SKILL_SCRIPTS / w
    content = p.read_text(encoding="utf-8")
    if "from _pa_root import" in content:
        print(f"  {w}: already patched, skip")
        continue
    if OLD_HEADER in content:
        content = content.replace(OLD_HEADER, NEW_HEADER)
        print(f"  {w}: header patched")
    else:
        print(f"  {w}: header pattern NOT FOUND — need manual check")
        # Print first 30 lines
        for i, line in enumerate(content.split("\n")[:30], 1):
            print(f"    L{i}: {line}")
        continue

    # Now also replace `cwd=str(PA_ROOT)` with `cwd=str(pa_root)` + add pa_root check
    if 'cwd=str(PA_ROOT)' in content:
        content = content.replace('cwd=str(PA_ROOT)', 'cwd=str(pa_root)')
        print(f"  {w}: PA_ROOT -> pa_root")

    # Add pa_root check before the subprocess.run call
    # Find pattern: `args = parser.parse_args()` followed by build cmd
    # Insert pa_root check after parse_args
    parse_idx = content.find("args = parser.parse_args()")
    if parse_idx == -1:
        print(f"  {w}: parse_args not found")
        continue
    # Find the end of that line
    end_of_line = content.find("\n", parse_idx) + 1
    insertion = """
    # Find paper-agent root
    pa_root = find_pa_root()
    if not pa_root:
        print(json.dumps({
            "error": "pa_cli_not_found",
            "message": "paper-agent (pa_cli) is not installed in this Python environment.",
            "hint": get_install_instructions().strip(),
        }, indent=2), file=sys.stderr)
        return 4

"""
    # Check if already inserted
    if "pa_root = find_pa_root()" in content:
        print(f"  {w}: pa_root check already present, skip insertion")
    else:
        content = content[:end_of_line] + insertion + content[end_of_line:]
        print(f"  {w}: pa_root check inserted")

    p.write_text(content, encoding="utf-8")
    print(f"  {w}: saved")
    print()
