"""Bounded structural PDF validation; exact content hashes memoize safe hot reads."""
from collections import OrderedDict
import hashlib
import io
import json
from pathlib import Path
import sys
import threading
import time
from .fetch_deadline import run_fetch

VALIDATION_SECONDS = 10
VALIDATION_MEMORY_MB = 512
VALIDATION_POLICY = 'pypdf-strict-pages-v1'
_slots = threading.BoundedSemaphore(2)
_memo = OrderedDict()
_lock = threading.Lock()

def structurally_valid(path: Path, sha256: str) -> bool:
    # Caller hashes its observed bytes on EVERY read; file names and sidecars
    # alone never authorize a cached validation. SHA256 collision resistance is
    # the same assumption used by the content-integrity cache itself.
    with _lock:
        if sha256 in _memo:
            _memo.move_to_end(sha256)
            return True
    checked = validate_pdf(path)
    if not checked.get('valid') or checked.get('sha256') != sha256:
        return False
    with _lock:
        _memo[sha256] = True
        if len(_memo) > 512:_memo.popitem(last=False)
    return True

def validate_pdf(path: Path) -> dict:
    started = time.monotonic()
    if not _slots.acquire(timeout=VALIDATION_SECONDS):return {'valid':False}
    try:
        remaining = VALIDATION_SECONDS - (time.monotonic()-started)
        if remaining <= 0:return {'valid':False}
        command=[sys.executable,'-c',
            'import sys,json; sys.path.insert(0,sys.argv[1]); '
            'from pa_cli.pdf_validation import validation_worker; '
            'r=json.load(sys.stdin); print(json.dumps(validation_worker(r["path"])))',
            str(Path(__file__).resolve().parent.parent)]
        result=run_fetch({'path':str(Path(path).resolve())},remaining,
                         _memory_mb=VALIDATION_MEMORY_MB,_command=command)
        return result if result.get('valid') is True else {'valid':False}
    finally:_slots.release()

def validation_worker(path: str) -> dict:
    with Path(path).open('rb') as stream:body=stream.read(256*1024*1024+1)
    valid=False
    if len(body)<=256*1024*1024 and body.startswith(b'%PDF-') and body.rstrip().endswith(b'%%EOF'):
        try:
            from pypdf import PdfReader
            from pypdf.generic import ArrayObject, NullObject, StreamObject
            reader=PdfReader(io.BytesIO(body),strict=True)
            valid=not reader.is_encrypted and bool(reader.pages)
            if valid:
                for page in reader.pages:
                    if page.get('/Type')!='/Page':valid=False;break
                    raw=page.get('/Contents')
                    if raw is not None:
                        raw=raw.get_object()
                        for item in (raw if isinstance(raw,ArrayObject) else [raw]):
                            if not isinstance(item.get_object(),(StreamObject,NullObject)):valid=False;break
                    if not valid:break
                    contents=page.get_contents()
                    if contents is not None:contents.get_data()
        except Exception:valid=False
    return {'valid':valid,'sha256':hashlib.sha256(body).hexdigest(),'size':len(body),'validation_policy':VALIDATION_POLICY}
