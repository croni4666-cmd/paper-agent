"""Bounded synthetic capacity checks, never scientific/model evaluation."""
from decimal import Decimal
import hashlib
import json
import multiprocessing as mp
from pathlib import Path

from pa_cli.gateway_store import GatewayStore
from pa_cli.ris import render_ris
from pa_cli.run_report import build_report


def _reserve(path, number, ready, go, output):
    with_store = GatewayStore(path)
    ready.put(number)
    if not go.wait(25):
        raise RuntimeError("fixture barrier timeout")
    request = f"request-{number}"
    receipt = dict(request_id=request, run_id="stress", estimated_tokens=1000,
                   estimated_cost_usd="0.001", gateway_decision="AUTHORIZED", total_candidates=1,
                   receipt_id="receipt-" + request, payload_sha256="a" * 64)
    accepted = with_store.reserve(request, "stress", 1000, "0.001", 4000, "0.004",
                                  {"pid": 123, "birth": str(number)}, receipt)
    if accepted:
        with_store.finalize(request, receipt)
        with_store.finalize(request, dict(receipt))
    output.put(accepted)
    with_store.close()


def test_eight_processes_respect_caps_and_idempotent_finalization(tmp_path):
    path = tmp_path / "journal.db"
    GatewayStore(path).close()
    context = mp.get_context("spawn")
    ready, output, go = context.Queue(), context.Queue(), context.Event()
    workers = [context.Process(target=_reserve, args=(str(path), n, ready, go, output)) for n in range(8)]
    try:
        for worker in workers:
            worker.start()
        assert {ready.get(timeout=30) for _ in workers} == set(range(8))
        go.set()
        assert sum(output.get(timeout=30) for _ in workers) == 4
        for worker in workers:
            worker.join(15)
            assert worker.exitcode == 0
        store = GatewayStore(path)
        try:
            assert store.totals("stress") == (4000, Decimal("0.004"))
            assert len(store.receipts()) == 4
            assert store.status()["pending"] == []
        finally:
            store.close()
    finally:
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
                worker.join(5)
        for queue in (ready, output):
            queue.cancel_join_thread()
            queue.close()


def test_large_export_and_partial_batch_snapshot(tmp_path):
    entries = [dict(type="article", title=f"Fixture {n}\nER  - injection", authors=["甲", "Beta"], doi=f"10.1234/{n}") for n in range(3000)]
    content = render_ris(entries)
    assert content.count("TY  - JOUR\n") == 3000
    assert content.count("\nER  - \n") == 3000
    count = 8000
    rows = [dict(success=n % 2 == 0, error="" if n % 2 == 0 else "global-timeout") for n in range(count)]
    path = tmp_path / "batch.json"
    raw = json.dumps(dict(n_total=count, n_success=count//2, n_failure=0, n_skipped=count//2, results=rows)).encode()
    path.write_bytes(raw)
    report = build_report({"fetch": path})
    assert report["overall_status"] == "partial"
    assert report["stages"][0]["snapshot_sha256"] == hashlib.sha256(raw).hexdigest()
    assert report["stages"][0]["counts"]["reported_available"] == 4000


def test_generated_pdf_index_and_packet_bounds(tmp_path):
    import pymupdf
    from pa_cli.evidence import build_index, build_packet, _validate
    for number in range(20):
        path = tmp_path / f"fixture-{number}.pdf"
        with pymupdf.open() as document:
            for page in range(4):
                document.new_page().insert_text((72, 72), f"Methods\nGenerated workflow fixture {number}.\nResults\nBounded software result page {page}.")
            document.save(path)
        index = build_index(path)
        _validate(index)
        packet = build_packet(index, "workflow result", max_bytes=4000, max_spans=3)
        assert packet["external_upload_allowed"] is False
        assert index["spans"]
