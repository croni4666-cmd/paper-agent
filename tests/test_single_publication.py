from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from pa_cli import cache, fetch
from pa_cli.fetch_deadline import run_fetch
from pa_cli.fetch_output import _publish

from test_pdf_structure import make_pdf
PDF = make_pdf()
DOI = '10.1000/publication'


class SinglePublicationTests(unittest.TestCase):
    def worker(self, body, delay=0):
        script = '''
from pathlib import Path
import time
from pa_cli import fetch
from pa_cli.fetch_worker import main

def download(**kwargs):
    Path(kwargs['out_path']).write_bytes(%r)
    time.sleep(%r)
    return {'path': kwargs['out_path'], 'source': 'fixture'}
fetch.fetch = download
from pa_cli import channel_stats
channel_stats.record_event = lambda *args, **kwargs: None
main()
''' % (body, delay)
        return lambda request, seconds: run_fetch(request, seconds, _command=[sys.executable, '-c', script])

    def test_real_worker_timeout_preserves_old_output(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / fetch._doi_output_name(DOI)
            target.write_bytes(PDF)
            with patch('pa_cli.fetch_deadline.run_fetch', side_effect=self.worker(b'%PDF-partial', 30)):
                result = fetch.fetch_doi(DOI, temp, max_total_sec=1, use_cache=False)
            self.assertEqual(result['error'], 'fetch_timeout')
            self.assertEqual(target.read_bytes(), PDF)
            self.assertEqual(list(Path(temp).iterdir()), [target])

    def test_real_worker_success_publishes_and_caches_complete_pdf(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch('pa_cli.fetch_deadline.run_fetch', side_effect=self.worker(PDF)):
                result = fetch.fetch_doi(DOI, temp, max_total_sec=10, use_cache=False)
            target = Path(temp) / fetch._doi_output_name(DOI)
            self.assertEqual(result['saved_as'], str(target))
            self.assertEqual(target.read_bytes(), PDF)
            self.assertTrue(result['cache_written'])
            self.assertIsNotNone(cache.cache_get(DOI))
            self.assertEqual(list(Path(temp).iterdir()), [target])

    def test_partial_pdf_success_is_not_published_or_cached(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / fetch._doi_output_name(DOI)
            target.write_bytes(PDF)
            with patch('pa_cli.fetch_deadline.run_fetch', side_effect=self.worker(b'%PDF-1.7 partial')):
                result = fetch.fetch_doi(DOI, temp, max_total_sec=10, use_cache=False)
            self.assertEqual(result['error'], 'fetch_invalid_pdf_output')
            self.assertEqual(target.read_bytes(), PDF)
            self.assertIsNone(cache.cache_get(DOI))

    def test_copy_failure_preserves_existing_destination(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, target = root / 'new.pdf', root / 'existing.pdf'
            source.write_bytes(PDF)
            target.write_bytes(b'previous')
            def partial(source, destination):
                destination.write(b'partial')
                raise OSError('fixture')
            with patch('pa_cli.fetch_output.shutil.copyfileobj', side_effect=partial), self.assertRaises(OSError):
                _publish(source, target)
            self.assertEqual(target.read_bytes(), b'previous')
            self.assertEqual(len(list(root.iterdir())), 2)

    def test_valid_xml_only_is_published_and_partial_xml_preserves_previous(self):
        for body in (b'<article><body>full text</body></article>', b'<article>partial'):
            with self.subTest(body=body), tempfile.TemporaryDirectory() as temp:
                target = (Path(temp) / fetch._doi_output_name(DOI)).with_suffix('.xml')
                target.write_bytes(b'previous')
                def worker(request, seconds):
                    xml = (Path(request['output_dir']) / fetch._doi_output_name(DOI)).with_suffix('.xml')
                    xml.write_bytes(body)
                    return {'error': 'pmc_pdf_unavailable', 'saved_as': None, 'xml_path': str(xml), 'xml_size': len(body)}
                with patch('pa_cli.fetch_deadline.run_fetch', side_effect=worker):
                    result = fetch.fetch_doi(DOI, temp, use_cache=False)
                if body.endswith(b'</article>'):
                    self.assertEqual(target.read_bytes(), body)
                    self.assertEqual(result['xml_path'], str(target))
                else:
                    self.assertEqual(target.read_bytes(), b'previous')
                    self.assertNotIn('xml_path', result)

    def test_cache_hit_does_not_require_output_directory(self):
        cache.cache_put(DOI, PDF)
        with tempfile.TemporaryDirectory() as temp:
            not_directory = Path(temp) / 'file'
            not_directory.write_text('existing')
            result = fetch.fetch_doi(DOI, str(not_directory / 'child'), max_total_sec=10)
            self.assertTrue(result['cache_hit'], result)
            self.assertEqual(not_directory.read_text(), 'existing')

    def test_real_worker_preserves_successful_pdf_and_xml(self):
        script = """
from pathlib import Path
from pa_cli import fetch, channel_stats
from pa_cli.fetch_worker import main

def download(**kwargs):
    pdf = Path(kwargs['out_path'])
    xml = pdf.with_suffix('.xml')
    pdf.write_bytes(%r)
    xml.write_bytes(b'<article><body>Full text</body></article>')
    return {'path': str(pdf), 'xml_path': str(xml), 'xml_size': xml.stat().st_size}
fetch.fetch = download
channel_stats.record_event = lambda *args, **kwargs: None
main()
""" % PDF
        with tempfile.TemporaryDirectory() as temp:
            def worker(request, seconds):
                return run_fetch(request, seconds, _command=[sys.executable, '-c', script])
            with patch('pa_cli.fetch_deadline.run_fetch', side_effect=worker):
                result = fetch.fetch_doi(DOI, temp, use_cache=False)
            self.assertEqual(Path(result['saved_as']).read_bytes(), PDF)
            self.assertTrue(Path(result['xml_path']).read_bytes().endswith(b'</article>'))
            self.assertEqual(Path(result['xml_path']).parent, Path(temp))

    def test_xml_read_failure_does_not_mask_published_pdf(self):
        with tempfile.TemporaryDirectory() as temp:
            def worker(request, seconds):
                pdf = Path(request['output_dir']) / fetch._doi_output_name(DOI)
                pdf.write_bytes(PDF)
                xml = pdf.with_suffix('.xml')
                xml.write_bytes(b'<article/>')
                return {'saved_as': str(pdf), 'final_status': 'SUCCESS', 'xml_path': str(xml)}
            original = Path.read_bytes
            def read(path):
                if path.suffix == '.xml':
                    raise OSError('fixture XML read failure')
                return original(path)
            with patch('pa_cli.fetch_deadline.run_fetch', side_effect=worker), patch.object(Path, 'read_bytes', read):
                result = fetch.fetch_doi(DOI, temp, use_cache=False)
            self.assertEqual(result['final_status'], 'SUCCESS')
            self.assertEqual(Path(result['saved_as']).read_bytes(), PDF)
            self.assertEqual(result['xml_error'], 'xml-publication-failed')

    def test_stage_cleanup_failure_preserves_published_success(self):
        original = tempfile.TemporaryDirectory
        class CleanupFailure:
            def __init__(self, **kwargs):
                self.directory = original(**kwargs)
            def __enter__(self):
                return self.directory.__enter__()
            def __exit__(self, *args):
                self.directory.__exit__(*args)
                raise OSError('fixture cleanup failure')
        with original() as temp:
            def worker(request, seconds):
                pdf = Path(request['output_dir']) / fetch._doi_output_name(DOI)
                pdf.write_bytes(PDF)
                return {'saved_as': str(pdf), 'final_status': 'SUCCESS'}
            with patch('pa_cli.fetch_output.tempfile.TemporaryDirectory', CleanupFailure), \
                 patch('pa_cli.fetch_deadline.run_fetch', side_effect=worker):
                result = fetch.fetch_doi(DOI, temp, use_cache=False)
            self.assertEqual(result['final_status'], 'SUCCESS')
            self.assertEqual(Path(result['saved_as']).read_bytes(), PDF)
            self.assertEqual(result['cleanup_error'], 'fetch-output-cleanup-failed')
    def test_slow_optional_cache_cannot_discard_download(self):
        script = '''
from pathlib import Path
import sys,time
from pa_cli import fetch,cache,fetch_deadline,channel_stats
from pa_cli.fetch_worker import main

def slow(*args,**kwargs):
    time.sleep(30)
cache.cache_put=slow
channel_stats.record_event=lambda *a,**k:None
supervise=fetch_deadline.run_fetch
slow_child="from pa_cli import cache; import time; cache.cache_put=lambda *a,**k:time.sleep(30); from pa_cli.fetch_worker import main; main()"
def nested(request, seconds, **kwargs):
    if request.get('_operation')=='cache_write':
        kwargs['_command']=[sys.executable,'-c',slow_child]
    return supervise(request,seconds,**kwargs)
fetch_deadline.run_fetch=nested
def download(**kwargs):
    Path(kwargs['out_path']).write_bytes(%r)
    return {'path':kwargs['out_path'],'source':'fixture'}
fetch.fetch=download
main()
''' % PDF
        script = script.replace('\nmain()\n', '\ntime.sleep(1.5)\nmain()\n')
        with tempfile.TemporaryDirectory() as temp:
            request=dict(doi=DOI,output_dir=temp,use_cache=False,_staged=True)
            result=run_fetch(request,4,_command=[sys.executable,'-c',script])
            self.assertEqual(result.get('final_status'),'SUCCESS',result)
            self.assertFalse(result['cache_written'])
            self.assertEqual(result['cache_status'],'fetch_timeout')
            self.assertEqual(Path(result['saved_as']).read_bytes(),PDF)
