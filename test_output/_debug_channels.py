"""Find which channel throws 'unknown url type: none'."""
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pa_cli.fetch import fetch_doi

# Test each channel in isolation
channels_to_test = [
    ["openalex"],
    ["arxiv"],
    ["unpaywall"],
    ["doi_redirect"],
    ["scihub"],
    ["playwright"],
]

for chs in channels_to_test:
    print(f"\n=== Testing channels={chs} ===")
    try:
        result = fetch_doi(
            '10.1186/s41239-021-00292-9',
            output_dir='C:/Users/DengN/.paper-agent/deep_rerank/debug',
            channels=chs,
            max_total_sec=15,
        )
        print(f"  status: {result.get('final_status')}")
        if result.get("saved_as"):
            print(f"  saved: {result.get('saved_as')}")
    except Exception as e:
        print(f"  EXCEPTION: {type(e).__name__}: {e}")
        traceback.print_exc()
