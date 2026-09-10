import json, sys, unittest
from pa_cli.fetch_deadline import run_fetch

class TraceTests(unittest.TestCase):
    def test_timeout_retains_inflight_stage_and_cleans_private_file(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory)/'path.txt'
            script = '''import json,sys,time
from pathlib import Path
from pa_cli.fetch_trace import configure,emit
request=json.load(sys.stdin)
Path(sys.argv[1]).write_text(request['_trace_path'])
configure(request['_trace_path']);emit('worker','started');emit('arxiv','started');emit('http','started')
time.sleep(30)
'''
            result=run_fetch({}, 1, _command=[sys.executable,'-c',script,str(marker)])
            self.assertEqual(result['error'],'fetch_timeout')
            self.assertEqual(result['retrieval_trace'][-1]['stage'],'http')
            self.assertEqual(result['retrieval_trace'][-1]['status'],'started')
            self.assertFalse(Path(marker.read_text()).exists())
            self.assertNotIn(str(marker),json.dumps(result))
    def test_private_fields_and_incomplete_events_not_exposed(self):
        script='''import json,sys
r=json.load(sys.stdin)
with open(r['_trace_path'],'w') as f:
 f.write(json.dumps(dict(stage='http',status='transport_error',elapsed_sec=0.1,url='secret',path='private'))+'\\n{')
print('{}')
'''
        result=run_fetch({},10,_command=[sys.executable,'-c',script])
        self.assertEqual(result['retrieval_trace'],[dict(stage='http',status='transport_error',elapsed_sec=0.1)])
    def test_http_transport_failure_is_classified(self):
        import tempfile
        from pathlib import Path
        from pa_cli.fetch_trace import configure, traced, read_trace
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'events';configure(str(path))
            try:
                self.assertEqual(traced('http')(lambda: (0,b''))(),(0,b''))
                self.assertEqual(read_trace(path)[-1]['status'],'transport_error')
            finally:
                configure(None)
def test_cli_timeout_does_not_blame_network():
 from click.testing import CliRunner
 from pa_cli.cli import main
 from unittest.mock import patch
 with patch('pa_cli.fetch.fetch_doi',return_value={'error':'fetch_timeout','final_status':'ALL_FAIL','retrieval_trace':[{'stage':'cache_write','status':'started','elapsed_sec':1}]}):
  result=CliRunner().invoke(main,['fetch','10.1000/test','--quiet'])
 assert 'Cloudflare' not in result.output
 assert 'all channels failed' not in result.output
 assert 'retrieval_trace' in result.output
def test_trace_keeps_latest_stage_after_many_attempts(tmp_path):
 from pa_cli.fetch_trace import configure,emit,read_trace
 path=tmp_path/'events';configure(str(path))
 try:
  for _ in range(70):emit('http','completed')
  emit('scihub','started')
  events=read_trace(path)
  assert len(events)<=64
  assert events[-1]['stage']=='scihub'
 finally:configure(None)
