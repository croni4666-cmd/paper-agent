import concurrent.futures
import threading
import time

import pytest

from pa_cli import cache, search, pdf_validation
from test_pdf_structure import make_pdf


def test_corrupt_pdf_write_cannot_replace_good_cache(tmp_path):
    doi = '10.1000/pressure-preserve'
    old = cache.cache_put(doi, make_pdf(), root=tmp_path)
    with pytest.raises(ValueError):
        cache.cache_put(doi, b'%PDF-1.7\nnot a document\n%%EOF', root=tmp_path)
    assert cache.cache_get(doi, root=tmp_path)['sha256'] == old['sha256']


def test_pubmed_throttle_spaces_concurrent_reservations():
    barrier = threading.Barrier(8)
    def reserve(_):
        barrier.wait()
        search._pubmed_throttle(0.04)
        return time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        starts = sorted(pool.map(reserve, range(8)))
    assert all(b-a >= 0.035 for a,b in zip(starts, starts[1:]))


def test_pdf_validation_bounds_concurrent_parser_workers(monkeypatch, tmp_path):
    lock = threading.Lock()
    active = 0
    peak = 0
    def worker(*args, **kwargs):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(.06)
        with lock:active -= 1
        return {'valid':True}
    monkeypatch.setattr(pdf_validation, 'run_fetch', worker)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _:pdf_validation.validate_pdf(tmp_path/'x.pdf'),range(8)))
    assert all(r['valid'] for r in results)
    assert peak <= 2
