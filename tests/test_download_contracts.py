import io
import unittest
from unittest.mock import patch, Mock
from pa_cli import biorxiv_channel, core_channel, osf_channel, chemrxiv_channel

CHANNELS = (biorxiv_channel, core_channel, osf_channel, chemrxiv_channel)
PDF = b'%PDF-1.7\nexample\n%%EOF'

class DownloadContracts(unittest.TestCase):
    def test_download_matrix(self):
        for channel in CHANNELS:
            for label, data, cap, expected in (
                ('success', PDF, len(PDF), PDF),
                ('html', b'<html>challenge</html>', 100, None),
                ('oversize', PDF, len(PDF)-1, None),
                ('empty', b'', 100, None),
            ):
                with self.subTest(channel=channel.__name__, case=label):
                    response=io.BytesIO(data)
                    opener=Mock()
                    opener.open.return_value=response
                    with patch.object(channel, 'build_opener', return_value=opener):
                        result=channel._download_pdf('https://example.test/paper.pdf',max_bytes=cap)
                    self.assertEqual(result,expected)
                    self.assertTrue(response.closed)

    def test_connection_and_mid_read_failures(self):
        for channel in CHANNELS:
            for during_read in (False, True):
                with self.subTest(channel=channel.__name__, during_read=during_read):
                    opener=Mock()
                    response=Mock()
                    response.__enter__=Mock(return_value=response)
                    response.__exit__=Mock(return_value=False)
                    if during_read:
                        opener.open.return_value=response
                        response.read.side_effect=OSError('stream interrupted')
                    else:
                        opener.open.side_effect=OSError('connection failed')
                    with patch.object(channel,'build_opener',return_value=opener):
                        self.assertIsNone(channel._download_pdf('https://example.test/paper.pdf'))
                    if during_read:
                        self.assertTrue(response.__exit__.called)
