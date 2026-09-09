from test_pdf_structure import make_pdf
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from click.testing import CliRunner
from pa_cli import cache, fetch
from pa_cli.cli import main
from pa_cli.fetch_deadline import run_fetch


class FetchDeadlineTests(unittest.TestCase):
    def test_public_worker_and_cli_return_real_cache_hit(self):
        entry = cache.cache_put('10.1000/deadline', make_pdf())
        result = fetch.fetch_doi('10.1000/deadline', max_total_sec=10)
        self.assertEqual(result['final_status'], 'SUCCESS_CACHE_HIT', result)
        self.assertEqual(result['saved_as'], entry['pdf_path'])
        self.assertTrue(result['_wrapper_notes']['max_total_sec_supported'])
        cli = CliRunner().invoke(main, ['fetch', '10.1000/deadline', '--max-total-sec', '10', '--quiet'])
        self.assertEqual(cli.exit_code, 0, cli.output)
        self.assertIn('SUCCESS_CACHE_HIT', cli.output)

    def test_invalid_budgets_do_not_launch_worker(self):
        for seconds in (0, -1, True, None, '10', float('nan'), float('inf'), 10 ** 400):
            with self.subTest(seconds=seconds), patch('pa_cli.fetch_deadline.subprocess.Popen') as launch:
                self.assertEqual(fetch.fetch_doi('10.1000/test', max_total_sec=seconds)['error'],
                                 'fetch_invalid_timeout')
                launch.assert_not_called()
        cli = CliRunner().invoke(main, ['fetch', '10.1000/test', '--max-total-sec', '0'])
        self.assertEqual(cli.exit_code, 2)

    def test_failed_worker_diagnostics_are_sanitized(self):
        script = "import sys; sys.stdin.read(); raise RuntimeError('private fixture detail')"
        result = run_fetch({}, 10, _command=[sys.executable, '-c', script])
        self.assertEqual(result['error'], 'fetch_worker_failed')
        self.assertNotIn('private fixture', json.dumps(result))

    def test_timeout_kills_descendants_and_prevents_late_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            ready = Path(temp) / 'ready'
            late = Path(temp) / 'late'
            # Descendant closes pipes, so a parent-only kill would return while
            # the child stays alive and writes the marker after the deadline.
            child = "import pathlib,time; time.sleep(2); pathlib.Path(%r).write_text('late')" % str(late)
            script = ("import sys,json,subprocess,time,pathlib; sys.stdin.read(); "
                      "p=subprocess.Popen([sys.executable,'-c',%r],stdin=subprocess.DEVNULL,"
                      "stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); "
                      "pathlib.Path(%r).write_text(str(p.pid)); time.sleep(30)") % (child, str(ready))
            started = time.monotonic()
            result = run_fetch({}, 1, _command=[sys.executable, '-c', script])
            self.assertEqual(result['error'], 'fetch_timeout', result)
            self.assertIsNone(result['saved_as'])
            self.assertLess(time.monotonic() - started, 5)
            self.assertTrue(ready.exists(), 'worker must have launched its descendant')
            time.sleep(2)
            self.assertFalse(late.exists(), 'descendant continued writing after timeout')

    def test_success_reaps_leftover_descendants(self):
        with tempfile.TemporaryDirectory() as temp:
            late = Path(temp) / 'late'
            child = "import pathlib,time; time.sleep(1); pathlib.Path(%r).write_text('late')" % str(late)
            script = ("import sys,subprocess; sys.stdin.read(); "
                      "subprocess.Popen([sys.executable,'-c',%r],stdin=subprocess.DEVNULL,"
                      "stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); print('{}')") % child
            result = run_fetch({}, 10, _command=[sys.executable, '-c', script])
            self.assertNotIn('error', result)
            time.sleep(1.5)
            self.assertFalse(late.exists())

    def test_worker_launch_failure_is_structured(self):
        with patch('pa_cli.fetch_deadline.subprocess.Popen', side_effect=OSError('private fixture')):
            result = fetch.fetch_doi('10.1000/test')
        self.assertEqual(result['error'], 'fetch_worker_failed')
        self.assertNotIn('private fixture', json.dumps(result))

    def test_real_http_wait_is_interrupted_inside_fetch_worker(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        import threading
        reached, release = threading.Event(), threading.Event()
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                reached.set()
                release.wait(5)
                self.send_response(503)
                self.end_headers()
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = 'http://127.0.0.1:%s/slow' % server.server_port
            script = """
from pa_cli import fetch
from pa_cli.fetch_worker import main

def slow(**kwargs):
    fetch._http_get_bytes(%r, timeout=30)
    return {'error': 'unexpected_completion'}
fetch.fetch = slow
main()
""" % url
            result = run_fetch({'doi': '10.1000/slow', 'use_cache': False}, 1,
                               _command=[sys.executable, '-c', script])
            self.assertTrue(reached.is_set(), result)
            self.assertEqual(result['error'], 'fetch_timeout', result)
        finally:
            release.set()
            server.shutdown()
            server.server_close()
            thread.join()

    @unittest.skipUnless(os.environ.get('PA_TEST_BROWSER') == '1', 'opt-in Chromium test')
    def test_real_chromium_is_terminated_on_timeout(self):
        import socket
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1', 0))
            port = reservation.getsockname()[1]
        with tempfile.TemporaryDirectory() as temp:
            ready = Path(temp) / 'browser-ready'
            script = """
import sys,time,pathlib
sys.stdin.read()
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=['--remote-debugging-port=%s'])
    page = browser.new_page()
    page.set_content('<h1>Local deadline fixture</h1>')
    pathlib.Path(%r).write_text('ready')
    time.sleep(30)
""" % (port, str(ready))
            result = run_fetch({}, 5, _command=[sys.executable, '-c', script])
            self.assertTrue(ready.exists(), 'real browser must start before timeout')
            self.assertEqual(result['error'], 'fetch_timeout', result)
            # The browser debug listener must disappear after tree termination.
            deadline = time.monotonic() + 2
            while True:
                with socket.socket() as probe:
                    probe.settimeout(.2)
                    alive = probe.connect_ex(('127.0.0.1', port)) == 0
                if not alive or time.monotonic() > deadline:
                    break
                time.sleep(.05)
            self.assertFalse(alive, 'Chromium survived worker timeout')

    def test_worker_uses_imported_package_after_changing_directory(self):
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as temp:
            try:
                os.chdir(temp)
                result = fetch.fetch_doi('10.1000/test', prefer='unsupported', max_total_sec=10)
                self.assertEqual(result['error'], 'fetch_invalid_preference', result)
            finally:
                os.chdir(previous)
