import base64
import io
import unittest
from html.parser import HTMLParser
from unittest.mock import Mock, patch

from pa_cli import jats_to_pdf as jats

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jN1sAAAAASUVORK5CYII=')


class ImageParser(HTMLParser):
    def handle_starttag(self, tag, attrs):
        if tag == 'img':
            self.attrs = attrs


class JatsFigureContracts(unittest.TestCase):
    def test_svg_query_url_keeps_svg_mime(self):
        svg = b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg"/>'
        html = '<img src="https://example.test/figure.svg?key=fixture" alt="Vector">'
        with patch.object(jats, '_build_figure_opener'), \
             patch.object(jats, '_download_figure', return_value=svg):
            result = jats._embed_figures_as_data_uris(html)
        self.assertEqual(result, '<img src="data:image/svg+xml;base64,' +
                         base64.b64encode(svg).decode() + '" alt="Vector">')

    def test_supported_image_mime_uses_content(self):
        for payload, expected in (
            (PNG, 'image/png'),
            (b'\xff\xd8\xff\xe0', 'image/jpeg'),
            (b'GIF89a', 'image/gif'),
            (b'RIFF\x04\x00\x00\x00WEBP', 'image/webp'),
            (b'<svg xmlns="http://www.w3.org/2000/svg"/>', 'image/svg+xml'),
            (b'<svg>', None),
            (b'<html/>', None),
        ):
            with self.subTest(expected=expected, payload=payload[:12]):
                self.assertEqual(jats._figure_mime(payload), expected)

    def test_failed_embedding_keeps_existing_remote_fallback(self):
        html = '<img src="https://example.test/image.svg" alt="Caption">'
        with patch.object(jats, '_build_figure_opener'), \
             patch.object(jats, '_download_figure', return_value=None):
            self.assertEqual(jats._embed_figures_as_data_uris(html), html)

    def test_embedding_preserves_attributes_and_payload_mime(self):
        html = '<img class="figure" src="https://example.test/download?format=png&amp;id=1" alt="Sample &amp; caption" width="200">'
        with patch.object(jats, '_build_figure_opener'), \
             patch.object(jats, '_download_figure', return_value=PNG) as download:
            result = jats._embed_figures_as_data_uris(html)
        parser = ImageParser()
        parser.feed(result)
        self.assertEqual(parser.attrs, [('class', 'figure'),
            ('src', 'data:image/png;base64,' + base64.b64encode(PNG).decode()),
            ('alt', 'Sample & caption'), ('width', '200')])
        self.assertEqual(download.call_args.args[0], 'https://example.test/download?format=png&id=1')

    def test_download_rejects_oversize_empty_and_non_image(self):
        for label, content, limit, expected in (
            ('exact_limit', PNG, len(PNG), PNG),
            ('oversize', PNG, len(PNG) - 1, None),
            ('html', b'<html>blocked</html>', 100, None),
            ('empty', b'', 100, None),
        ):
            with self.subTest(case=label):
                response = io.BytesIO(content)
                opener = Mock()
                opener.open.return_value = response
                with patch.object(jats, '_MAX_FIG_BYTES', limit):
                    self.assertEqual(jats._download_figure('https://example.test/image', opener), expected)
                self.assertTrue(response.closed)

    def test_connection_and_read_errors_are_safe(self):
        for during_read in (False, True):
            with self.subTest(during_read=during_read):
                response = io.BytesIO(PNG)
                opener = Mock()
                secret = 'synthetic-private-token'
                if during_read:
                    opener.open.return_value = response
                    response.read = Mock(side_effect=OSError(secret))
                else:
                    opener.open.side_effect = OSError(secret)
                with self.assertLogs(jats.logger, level='DEBUG') as logs:
                    self.assertIsNone(jats._download_figure('https://example.test/?key=' + secret, opener))
                self.assertNotIn(secret, '\n'.join(logs.output))
                if during_read:
                    self.assertTrue(response.closed)
