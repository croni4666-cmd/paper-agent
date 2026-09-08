"""Staged single-fetch output publication and shared PDF structure checks."""
from pathlib import Path
import math
import shutil
import tempfile
import time


def _complete_pdf(path: Path) -> bool:
    """Require readable unencrypted pages and content streams (not visual validation)."""
    try:
        with path.open('rb') as stream:
            if stream.read(5) != b'%PDF-':
                return False
            stream.seek(0, 2)
            size = stream.tell()
            stream.seek(max(0, size - 4096))
            if not stream.read().rstrip().endswith(b'%%EOF'):
                return False
            stream.seek(0)
            from pypdf import PdfReader
            reader = PdfReader(stream, strict=True)
            if reader.is_encrypted or not reader.pages:
                return False
            for page in reader.pages:
                if page.get('/Type') != '/Page':
                    return False
                from pypdf.generic import ArrayObject, NullObject, StreamObject
                raw = page.get('/Contents')
                if raw is not None:
                    raw = raw.get_object()
                    members = raw if isinstance(raw, ArrayObject) else [raw]
                    for member in members:
                        member = member.get_object()
                        if not isinstance(member, (StreamObject, NullObject)):
                            return False
                contents = page.get_contents()
                if contents is not None:
                    contents.get_data()
            return True
    except Exception:
        # Malformed documents can raise several parser/codec exceptions. Never
        # expose document content or parser details through fetch diagnostics.
        return False



def _publish(source: Path, target: Path):
    """Copy to a same-directory temporary file, then atomically replace target."""
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.pa-publish-', delete=False) as stream:
            temporary = Path(stream.name)
            with source.open('rb') as incoming:
                shutil.copyfileobj(incoming, stream)
        temporary.replace(target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def staged_fetch(request, seconds):
    from .fetch_deadline import run_fetch, _failure
    from .fetch import _doi_output_name, _is_jats_article
    started = time.monotonic()
    try:
        valid = (not isinstance(seconds, bool) and isinstance(seconds, (int, float))
                 and math.isfinite(seconds) and seconds > 0)
    except OverflowError:
        valid = False
    if not valid:
        return _failure('fetch_invalid_timeout', started)
    destination = Path(request['output_dir'])
    name = _doi_output_name(request['doi'])
    published_result = None
    try:
        # System temp keeps cache hits independent of output directory access.
        with tempfile.TemporaryDirectory(prefix='pa-single-') as directory:
            stage = Path(directory)
            worker_request = dict(request, output_dir=str(stage), _staged=True)
            remaining = seconds - (time.monotonic() - started)
            if remaining <= 0:
                return _failure('fetch_timeout', started)
            result = run_fetch(worker_request, remaining)
            if result.get('cache_hit'):
                return result
            pdf, xml = stage / name, (stage / name).with_suffix('.xml')
            if result.get('saved_as'):
                if Path(result['saved_as']).resolve() != pdf.resolve() or not _complete_pdf(pdf):
                    return _failure('fetch_invalid_pdf_output', started)
                _publish(pdf, destination / name)
                result['saved_as'] = str(destination / name)
                published_result = result
            # Do not return paths into a directory that is about to disappear.
            had_xml = result.pop('xml_path', None)
            result.pop('xml_size', None)
            if had_xml and result.get('error') not in ('fetch_timeout', 'fetch_worker_failed'):
                try:
                    if xml.is_file() and _is_jats_article(xml.read_bytes()):
                        xml_size = xml.stat().st_size
                        target_xml = (destination / name).with_suffix('.xml')
                        _publish(xml, target_xml)
                        result['xml_path'] = str(target_xml)
                        result['xml_size'] = xml_size
                        published_result = result
                except OSError:
                    result['xml_error'] = 'xml-publication-failed'
            return result
    except OSError:
        if published_result is not None:
            return {**published_result, 'cleanup_error': 'fetch-output-cleanup-failed'}
        return _failure('fetch_output_error', started)
