import json
import unittest
from unittest.mock import patch

from pa_cli import biorxiv_channel, chemrxiv_channel, core_channel, jats_to_pdf, osf_channel


class _Response:
    status = 200

    def read(self, *_args):
        return json.dumps({"ok": True}).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class _Opener:
    def __init__(self):
        self.request = None

    def open(self, request, timeout):
        self.request = request
        return _Response()


class NetworkRoutingTests(unittest.TestCase):
    def test_channel_metadata_uses_validated_opener(self):
        for channel in (biorxiv_channel, chemrxiv_channel, core_channel, osf_channel):
            opener = _Opener()
            with self.subTest(channel=channel.__name__), \
                 patch.object(channel, "build_opener", return_value=opener):
                status, payload = channel._http_get_json(
                    "https://example.test/api", require_auth=False
                ) if channel is core_channel else channel._http_get_json(
                    "https://example.test/api"
                )

                self.assertEqual(status, 200)
                self.assertEqual(payload, {"ok": True})
                self.assertIsNotNone(opener.request)

    def test_jats_figure_embedding_does_not_install_global_opener(self):
        opener = _Opener()
        html = '<img src="https://example.test/figure.png" alt="figure">'
        with patch.object(jats_to_pdf, "_build_figure_opener", return_value=opener), patch.object(jats_to_pdf, "_download_figure", return_value=b"image"), patch.object(jats_to_pdf.urllib.request, "install_opener") as install:
            jats_to_pdf._embed_figures_as_data_uris(html, proxy="http://127.0.0.1:7890")

        install.assert_not_called()


if __name__ == "__main__":
    unittest.main()
