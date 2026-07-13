"""Debug: find where 'unknown url type: none' comes from."""
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pa_cli.fetch import fetch_doi

try:
    result = fetch_doi(
        '10.1186/s41239-021-00292-9',
        output_dir='C:/Users/DengN/.paper-agent/deep_rerank/debug',
        channels=['openalex'],
        max_total_sec=20,
    )
    print('result:', result)
except Exception as e:
    print('Exception type:', type(e).__name__)
    print('Exception message:', str(e))
    traceback.print_exc()
