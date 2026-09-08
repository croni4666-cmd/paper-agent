import base64
import io
import os
import tempfile
import threading
import unittest
import urllib.request
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from pa_cli import jats_to_pdf as jats

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jN1sAAAAASUVORK5CYII=')


@contextmanager
def figure_server():
    release = threading.Event()
    requested = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            requested.append(self.path)
            if self.path == '/slow':
                release.wait(5)
            try:
                self.send_response(200)
                self.send_header('Content-Type', 'image/png')
                self.send_header('Content-Length', str(len(PNG)))
                self.end_headers()
                self.wfile.write(PNG)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}', requested
    finally:
        release.set()
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)


@unittest.skipUnless(os.environ.get('PA_TEST_BROWSER') == '1', 'opt-in Chromium integration')
class JatsBrowserIntegration(unittest.TestCase):
    def test_http_figure_is_embedded_in_real_pdf(self):
        from pypdf import PdfReader
        with figure_server() as (base, requested):
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            html = f'<html><body><p>Figure contract</p><img src="{base}/figure?x=1&amp;y=2" alt="Visible figure"></body></html>'
            with patch.object(jats, '_build_figure_opener', return_value=opener):
                embedded = jats._embed_figures_as_data_uris(html)
            pdf = jats._html_to_pdf_via_playwright(embedded)
            self.assertEqual(requested, ['/figure?x=1&y=2'])
        reader = PdfReader(io.BytesIO(pdf))
        images = [obj.get_object() for page in reader.pages
                  for obj in page['/Resources'].get('/XObject', {}).values()
                  if obj.get_object().get('/Subtype') == '/Image']
        self.assertGreaterEqual(len(images), 1)
        self.assertIn('Figure contract', reader.pages[0].extract_text())

    def test_temp_path_with_spaces_hash_and_unicode(self):
        from pypdf import PdfReader
        factory = tempfile.NamedTemporaryFile
        with tempfile.TemporaryDirectory(prefix='paper # 中文 ') as folder, \
             patch.object(jats.tempfile, 'NamedTemporaryFile', side_effect=lambda **kw: factory(dir=folder, **kw)):
            pdf = jats._html_to_pdf_via_playwright('<p>Encoded path works</p>')
            self.assertEqual(list(Path(folder).iterdir()), [])
        self.assertIn('Encoded path works', PdfReader(io.BytesIO(pdf)).pages[0].extract_text())

    def test_real_timeout_closes_browser_and_removes_temp_file(self):
        from playwright.sync_api import sync_playwright, TimeoutError as BrowserTimeout
        factory = tempfile.NamedTemporaryFile
        browsers = []

        @contextmanager
        def tracking_playwright():
            with sync_playwright() as api:
                launch = api.chromium.launch
                def tracked_launch(*args, **kwargs):
                    browser = launch(*args, **kwargs)
                    browsers.append(browser)
                    return browser
                with patch.object(api.chromium, 'launch', side_effect=tracked_launch):
                    yield api

        with figure_server() as (base, requested), tempfile.TemporaryDirectory() as folder, \
             patch.object(jats.tempfile, 'NamedTemporaryFile', side_effect=lambda **kw: factory(dir=folder, **kw)), \
             patch('playwright.sync_api.sync_playwright', tracking_playwright):
            with self.assertRaises(BrowserTimeout):
                jats._html_to_pdf_via_playwright(f'<img src="{base}/slow">', timeout=1)
            self.assertIn('/slow', requested)
            self.assertEqual(list(Path(folder).iterdir()), [])
            self.assertTrue(browsers)
            self.assertTrue(all(not browser.is_connected() for browser in browsers))
