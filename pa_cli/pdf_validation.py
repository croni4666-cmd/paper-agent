"""Bounded PDF parsing shared by fresh output and legacy cache reads."""
from pathlib import Path
from .fetch_deadline import run_fetch

VALIDATION_SECONDS = 10
VALIDATION_MEMORY_MB = 512
VALIDATION_POLICY = 'pypdf-strict-pages-v1'


from .fetch_trace import traced

@traced("pdf_validation")
def validate_pdf(path: Path) -> dict:
    result = run_fetch({'_operation': 'validate_pdf', 'path': str(Path(path).resolve())},
                       VALIDATION_SECONDS, _memory_mb=VALIDATION_MEMORY_MB)
    if result.get('valid') is not True:
        return {'valid': False}
    return result


def validation_worker(path: str) -> dict:
    import hashlib
    from .fetch_output import _parse_pdf_in_process
    path = Path(path)
    # Copy at most 256 MiB inside the memory-limited worker. Hash and parse
    # exactly these bytes, with no temporary files left after forced termination.
    import io
    with path.open('rb') as source:
        body = source.read(256 * 1024 * 1024 + 1)
    if len(body) > 256 * 1024 * 1024:
        return {'valid': False}
    return {'valid': _parse_pdf_in_process(io.BytesIO(body)),
            'sha256': hashlib.sha256(body).hexdigest(), 'size': len(body),
            'validation_policy': VALIDATION_POLICY}
