import sys
import os
import unittest
import tempfile
import time
from pathlib import Path
from unittest.mock import patch
from pa_cli import pdf_validation
from test_pdf_structure import make_pdf
from pa_cli.fetch_deadline import run_fetch


class ValidationResourceTests(unittest.TestCase):
    def test_worker_cannot_allocate_beyond_memory_budget(self):
        script = "import sys,json; sys.stdin.read(); data=bytearray(1024*1024*1024); print('{}')"
        result = run_fetch({}, 5, _command=[sys.executable, '-c', script], _memory_mb=256)
        self.assertEqual(result.get('error'), 'fetch_worker_failed')

    def test_stalled_parser_is_terminated_and_rejected(self):
        script = (
            "import json,sys,time; from pathlib import Path; "
            "from pa_cli import fetch_output; "
            "from pa_cli.pdf_validation import validation_worker; "
            "request=json.load(sys.stdin); "
            "fetch_output._parse_pdf_in_process=lambda stream: (Path(request['path']+'.started').touch(), time.sleep(60)); "
            "print(json.dumps(validation_worker(request['path'])))"
        )
        def supervised(request, seconds, **kwargs):
            return run_fetch(request, seconds, _command=[sys.executable, '-c', script], **kwargs)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'valid.pdf'
            path.write_bytes(make_pdf())
            started = time.monotonic()
            with patch.object(pdf_validation, 'VALIDATION_SECONDS', 1), patch.object(
                    pdf_validation, 'run_fetch', side_effect=supervised):
                self.assertEqual(pdf_validation.validate_pdf(path), {'valid': False})
            self.assertLess(time.monotonic() - started, 5)
            self.assertTrue(Path(str(path) + '.started').exists())
            self.assertEqual(len(list(Path(directory).iterdir())), 2)

    @unittest.skipIf(os.name == 'nt', 'POSIX process-group regression')
    def test_outer_timeout_also_stops_nested_validator(self):
        child = (
            "import json,sys,time; from pathlib import Path; "
            "r=json.load(sys.stdin); Path(r['started']).touch(); "
            "time.sleep(2); Path(r['escaped']).touch(); print('{}')"
        )
        outer = (
            "import json,sys; from pa_cli import fetch_deadline; "
            "r=json.load(sys.stdin); fetch_deadline._IN_FETCH_WORKER=True; "
            "fetch_deadline.run_fetch(r, 10, "
            "_command=[sys.executable,'-c',r['child']], _memory_mb=256)"
        )
        with tempfile.TemporaryDirectory() as directory:
            started = Path(directory) / 'started'
            escaped = Path(directory) / 'escaped'
            result = run_fetch({'started': str(started), 'escaped': str(escaped), 'child': child},
                               1, _command=[sys.executable, '-c', outer])
            self.assertEqual(result.get('error'), 'fetch_timeout')
            self.assertTrue(started.exists(), 'Nested parser did not start')
            time.sleep(2)
            self.assertFalse(escaped.exists(), 'Nested parser survived outer timeout')
