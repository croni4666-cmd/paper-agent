import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from pa_cli import jats_to_pdf as jats


class JatsBrowserLifecycle(unittest.TestCase):
    def _browser_api(self):
        api = types.ModuleType('playwright.sync_api')
        api.sync_playwright = MagicMock()
        browser = api.sync_playwright.return_value.__enter__.return_value.chromium.launch.return_value
        return api, browser

    def test_browser_and_temp_cleanup_on_all_render_stages(self):
        for stage in ('success', 'new_context', 'goto', 'wait_for_load_state', 'pdf'):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as folder:
                api, browser = self._browser_api()
                page = browser.new_context.return_value.new_page.return_value
                page.pdf.return_value = b'%PDF-test'
                if stage == 'new_context':
                    browser.new_context.side_effect = RuntimeError('context failed')
                elif stage != 'success':
                    getattr(page, stage).side_effect = RuntimeError('render failed')
                factory = tempfile.NamedTemporaryFile
                with patch.dict(sys.modules, {'playwright': types.ModuleType('playwright'), 'playwright.sync_api': api}), \
                     patch.object(jats.tempfile, 'NamedTemporaryFile', side_effect=lambda **kw: factory(dir=folder, **kw)):
                    if stage == 'success':
                        self.assertEqual(jats._html_to_pdf_via_playwright('<p>Text</p>'), b'%PDF-test')
                    else:
                        with self.assertRaises(RuntimeError):
                            jats._html_to_pdf_via_playwright('<p>Text</p>')
                browser.close.assert_called_once()
                self.assertEqual(list(Path(folder).iterdir()), [])

    def test_temp_cleanup_when_writing_html_fails(self):
        api, browser = self._browser_api()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'partial.html'
            path.write_text('partial')
            tmp = MagicMock()
            tmp.__enter__.return_value = tmp
            tmp.name = str(path)
            tmp.write.side_effect = OSError('disk full')
            with patch.dict(sys.modules, {'playwright': types.ModuleType('playwright'), 'playwright.sync_api': api}), \
                 patch.object(jats.tempfile, 'NamedTemporaryFile', return_value=tmp):
                with self.assertRaises(OSError):
                    jats._html_to_pdf_via_playwright('<p>Text</p>')
            browser.close.assert_called_once()
            self.assertFalse(path.exists())
