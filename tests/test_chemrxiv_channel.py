import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pa_cli import chemrxiv_channel as channel


class ChemRxivChannelTests(unittest.TestCase):
    DOI = "10.26434/chemrxiv-2022-4brs3"

    def test_open_engage_asset_is_downloaded_and_saved(self):
        record = {
            "id": "item-1", "title": "Open Engage paper",
            "publishedDate": "2022-06-01T00:00:00Z",
            "asset": {"original": {"url": "https://assets.example/paper.pdf"}},
        }
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(channel, "_http_get_json", return_value=(200, record)), \
                 patch.object(channel, "_download_pdf", return_value=b"%PDF test") as download:
                result = channel.fetch_chemrxiv_doi(
                    self.DOI, str(Path(directory) / "paper.pdf"))
            self.assertEqual(result["source"], "chemrxiv_pdf")
            self.assertEqual(result["title"], "Open Engage paper")
            self.assertEqual(Path(result["path"]).read_bytes(), b"%PDF test")
            download.assert_called_once_with("https://assets.example/paper.pdf", timeout=60)

    def test_official_doi_pdf_fallback_survives_api_outage(self):
        with patch.object(channel, "_http_get_json", return_value=(503, {})), \
             patch.object(channel, "_download_pdf", return_value=b"%PDF fallback") as download:
            result = channel.fetch_chemrxiv_doi(self.DOI)
        self.assertEqual(result["source"], "chemrxiv_doi_pdf")
        self.assertIn("/doi/pdf/10.26434/chemrxiv-2022-4brs3", result["pdf_url"])
        self.assertEqual(download.call_count, 1)

    def test_rejects_non_chemrxiv_doi_without_network(self):
        result = channel.fetch_chemrxiv_doi("10.1000/example")
        self.assertEqual(result["error"], channel.E_NOT_CHEMRXIV)


if __name__ == "__main__":
    unittest.main()
