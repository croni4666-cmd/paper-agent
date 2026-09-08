import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from pa_cli import channel_stats


class ChannelStatsTests(unittest.TestCase):
    def test_record_and_summarize_by_channel(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "events.jsonl"
            channel_stats.record_event("10.1/example", "pmc_jats_pdf", True, 2.5, path=path)
            channel_stats.record_event("10.2/example", "pmc_jats_pdf", False, 1.0,
                                       error="not_found", path=path)
            channel_stats.record_event("10.3/example", "biorxiv", True, 3.0, path=path)

            summary = channel_stats.summarize(path=path)

        self.assertEqual(summary["total_attempts"], 3)
        self.assertEqual(summary["channels"]["pmc_jats_pdf"]["successes"], 1)
        self.assertEqual(summary["channels"]["pmc_jats_pdf"]["failures"], 1)
        self.assertEqual(summary["channels"]["pmc_jats_pdf"]["success_rate"], 0.5)
        self.assertEqual(summary["channels"]["biorxiv"]["avg_elapsed_sec"], 3.0)

    def test_invalid_json_line_is_ignored(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "events.jsonl"
            path.write_text('not json\n' + json.dumps({
                "timestamp": "2026-09-07T00:00:00",
                "channel": "pmc",
                "success": True,
                "elapsed_sec": 1,
            }) + "\n", encoding="utf-8")

            summary = channel_stats.summarize(path=path)

        self.assertEqual(summary["total_attempts"], 1)
        self.assertEqual(summary["invalid_records"], 1)


    @patch("pa_cli.channel_stats.record_event")
    @patch("pa_cli.fetch.fetch")
    def test_fetch_wrapper_records_final_source(self, mock_fetch, mock_record):
        from pa_cli.fetch import fetch_doi
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "paper.pdf"
            path.write_bytes(b"%PDF test")
            mock_fetch.return_value = {
                "source": "pmc_jats_pdf", "path": str(path),
                "size": path.stat().st_size, "pdf_url": None,
            }
            result = fetch_doi("10.1000/example", output_dir=temp, use_cache=False)

        self.assertEqual(result["final_status"], "SUCCESS")
        args, _ = mock_record.call_args
        self.assertEqual(args[0], "10.1000/example")
        self.assertEqual(args[1], "pmc_jats_pdf")
        self.assertTrue(args[2])
if __name__ == "__main__":
    unittest.main()
