import gzip
import io
import unittest
import urllib.error
import zlib
from unittest.mock import Mock, patch

from pa_cli import fetch


class Response(io.BytesIO):
    def __init__(self, body, encoding=''):
        super().__init__(body)
        self.status = 200
        self.headers = {'Content-Encoding': encoding}


class FetchHttpContracts(unittest.TestCase):
    def test_success_and_compression_close_response(self):
        for encoding, body in (('', b'data'), ('gzip', gzip.compress(b'data')),
                               ('deflate', zlib.compress(b'data'))):
            with self.subTest(encoding=encoding):
                response = Response(body, encoding)
                opener = Mock()
                opener.open.return_value = response
                with patch.object(fetch, '_build_opener', return_value=opener):
                    self.assertEqual(fetch._http_get_bytes('https://example.test'), (200, b'data'))
                self.assertTrue(response.closed)

    def test_http_error_closes_body(self):
        response = Response(gzip.compress(b'not found'), 'gzip')
        error = urllib.error.HTTPError('https://example.test', 404, 'missing',
                                       response.headers, response)
        opener = Mock()
        opener.open.side_effect = error
        with patch.object(fetch, '_build_opener', return_value=opener):
            self.assertEqual(fetch._http_get_bytes('https://example.test'), (404, b'not found'))
        self.assertTrue(response.closed)

    def test_read_and_decode_failures_close_and_hide_exception(self):
        for fail_read in (False, True):
            with self.subTest(fail_read=fail_read):
                response = Response(b'broken gzip', 'gzip')
                if fail_read:
                    response.read = Mock(side_effect=OSError('private-token=synthetic-secret'))
                opener = Mock()
                opener.open.return_value = response
                with patch.object(fetch, '_build_opener', return_value=opener):
                    self.assertEqual(fetch._http_get_bytes('https://example.test'), (0, b''))
                self.assertTrue(response.closed)

    def test_connection_failure_does_not_return_exception(self):
        opener = Mock()
        opener.open.side_effect = OSError('private-token=synthetic-secret')
        with patch.object(fetch, '_build_opener', return_value=opener):
            self.assertEqual(fetch._http_get_bytes('https://example.test'), (0, b''))
