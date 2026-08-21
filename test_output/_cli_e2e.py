"""Real CLI e2e test for v3.9.22.0 --prefer s2 (utf-8 output)."""
import json
import sys
from pathlib import Path
from click.testing import CliRunner

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pa_cli.cli import main

runner = CliRunner()

print("=" * 60)
print("CLI e2e: pa fetch --prefer s2 (10.1371/journal.pone.0000001)")
print("=" * 60)
print("Command: pa fetch 10.1371/journal.pone.0000001 --prefer s2 -o test_output")

result = runner.invoke(main, [
    "fetch", "10.1371/journal.pone.0000001",
    "--prefer", "s2",
    "-o", str(ROOT / "test_output"),
])
print(f"exit_code: {result.exit_code}")

# Write output to file (Windows console can't print emoji)
out_log = ROOT / "test_output" / "_cli_e2e_output.txt"
out_log.write_text(result.output, encoding="utf-8", errors="replace")
print(f"output written to: {out_log} ({len(result.output)} chars)")

# Look for the JSON part
if '"source":' in result.output or '"error":' in result.output:
    json_start = result.output.find("{")
    json_end = result.output.rfind("}") + 1
    if json_start >= 0 and json_end > json_start:
        try:
            data = json.loads(result.output[json_start:json_end])
            print("=== Parsed JSON ===")
            if "error" in data:
                print(f"  error: {data.get('error')}")
                print(f"  message: {data.get('message', '')[:120]}")
                if "channels" in data:
                    print(f"  channels: {data['channels']}")
            else:
                print(f"  source: {data.get('source')}")
                print(f"  saved_as: {data.get('saved_as')}")
                print(f"  elapsed_sec: {data.get('elapsed_sec')}")
                print(f"  final_status: {data.get('final_status')}")
        except json.JSONDecodeError as e:
            print(f"  JSON parse error: {e}")
            print(f"  raw JSON: {result.output[json_start:json_end][:500]}")

# Check if PDF saved
pdf_path = ROOT / "test_output" / "10_1371_journal_pone_0000001.pdf"
if pdf_path.exists():
    size = pdf_path.stat().st_size
    print(f"\n  PDF saved: {pdf_path}")
    print(f"  Size: {size:,} bytes")
    with open(pdf_path, "rb") as f:
        head = f.read(8)
    print(f"  Magic: {head}")
else:
    print(f"\n  No PDF saved at {pdf_path}")
