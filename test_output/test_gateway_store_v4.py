"""Generated-only tests for the canonical local journal; no network or papers."""
import importlib
import json
import multiprocessing
import sqlite3
from decimal import Decimal
from decimal import localcontext

import pytest


def store_type():
    try:
        return importlib.import_module("pa_cli.gateway_store").GatewayStore
    except ModuleNotFoundError:
        pytest.fail("The canonical GatewayStore implementation is missing")


def receipt(request_id="req", run_id="run", tokens=10, cost="0.001", decision="AUTHORIZED"):
    return {"request_id": request_id, "run_id": run_id, "estimated_tokens": tokens,
            "estimated_cost_usd": cost, "gateway_decision": decision,
            "receipt_id": "receipt_" + request_id, "payload_sha256": "a" * 64}


def reserve(store, request_id="req", tokens=10, cost="0.001", owner=None, **kwargs):
    rec = receipt(request_id, tokens=tokens, cost=cost)
    return store.reserve(request_id, "run", tokens, cost, kwargs.pop("max_tokens", 100000),
                         kwargs.pop("max_cost", "0.01"), owner or {"pid": 123, "birth": "old"}, rec)


def test_authorization_moves_pending_to_committed_exactly_once(tmp_path):
    store = store_type()(tmp_path / "journal.db")
    assert reserve(store)
    assert store.totals("run") == (10, Decimal("0.001"))
    assert store.receipts() == []
    rec = receipt()
    assert store.finalize("req", rec) == rec
    assert store.finalize("req", dict(rec)) == rec
    assert store.totals("run") == (10, Decimal("0.001"))
    assert store.status()["pending"] == []
    assert store.status()["runs"][0]["committed_tokens"] == 10
    assert store.receipts() == [rec]
    store.close()
    reopened = store_type()(tmp_path / "journal.db")
    assert reopened.totals("run") == (10, Decimal("0.001"))
    reopened.close()


def test_rejection_atomically_releases_only_its_reservation(tmp_path):
    store = store_type()(tmp_path / "journal.db")
    assert reserve(store)
    assert reserve(store, "other")
    rec = receipt(decision="REJECTED")
    store.finalize("req", rec)
    assert store.totals("run") == (10, Decimal("0.001"))
    assert store.receipts() == [rec]
    with pytest.raises(ValueError):
        store.finalize("req", receipt())
    store.close()


def test_caps_and_request_identity_cannot_change(tmp_path):
    store = store_type()(tmp_path / "journal.db")
    assert reserve(store, max_tokens=20, max_cost="0.002")
    assert reserve(store, max_tokens=20, max_cost="0.002")
    with pytest.raises(ValueError):
        reserve(store, tokens=11, max_tokens=20, max_cost="0.002")
    with pytest.raises(ValueError):
        reserve(store, "second", max_tokens=100, max_cost="0.002")
    with pytest.raises(ValueError):
        reserve(store, "second", max_tokens=20, max_cost="0.003")
    assert reserve(store, "second", max_tokens=20, max_cost="0.002")
    assert not reserve(store, "third", max_tokens=20, max_cost="0.002")
    with pytest.raises(ValueError):
        store.finalize("req", receipt(tokens=11))
    assert store.totals("run") == (20, Decimal("0.002"))
    store.close()


@pytest.mark.parametrize("cost", ["NaN", "Infinity", "-0.001", None, True, "invalid"])
def test_invalid_cost_never_creates_quota(tmp_path, cost):
    store = store_type()(tmp_path / "journal.db")
    with pytest.raises(ValueError):
        reserve(store, cost=cost)
    assert store.status()["runs"] == []
    store.close()


def _race_reserve(path, request_id, ready, go, result):
    store = store_type()(path)
    ready.put(request_id)
    go.wait(20)
    result.put(store.reserve(request_id, "run", 60000, "0.006", 100000, "0.01",
                             {"pid": 123, "birth": request_id},
                             receipt(request_id, tokens=60000, cost="0.006")))
    store.close()


def test_real_processes_cannot_both_reserve_over_limit(tmp_path):
    path = tmp_path / "journal.db"
    store_type()(path).close()
    ctx = multiprocessing.get_context("spawn")
    ready, result, go = ctx.Queue(), ctx.Queue(), ctx.Event()
    processes = [ctx.Process(target=_race_reserve, args=(str(path), str(i), ready, go, result))
                 for i in range(2)]
    try:
        for process in processes:
            process.start()
        assert {ready.get(timeout=20), ready.get(timeout=20)} == {"0", "1"}
        go.set()
        assert sorted([result.get(timeout=20), result.get(timeout=20)]) == [False, True]
        for process in processes:
            process.join(20)
            assert process.exitcode == 0
        store = store_type()(path)
        assert store.totals("run") == (60000, Decimal("0.006"))
        assert len(store.status()["pending"]) == 1
        store.close()
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(10)


def test_commit_failure_retains_quota_and_receipt_absence(tmp_path, monkeypatch):
    module = importlib.import_module("pa_cli.gateway_store") if store_type() else None
    connect = sqlite3.connect
    class FailCommit(sqlite3.Connection):
        fail = False
        def execute(self, sql, *args, **kwargs):
            if self.fail and sql == "COMMIT":
                raise sqlite3.OperationalError("injected commit failure")
            return super().execute(sql, *args, **kwargs)
    monkeypatch.setattr(module.sqlite3, "connect", lambda *a, **k: connect(*a, factory=FailCommit, **k))
    store = module.GatewayStore(tmp_path / "journal.db")
    reserve(store)
    store._conn.fail = True
    with pytest.raises(Exception, match="injected commit failure"):
        store.finalize("req", receipt())
    store._conn.fail = False
    assert store.totals("run") == (10, Decimal("0.001"))
    assert store.receipts() == []
    assert len(store.status()["pending"]) == 1
    store.close()


@pytest.mark.parametrize("kind", ["foreign", "future", "corrupt", "empty", "altered"])
def test_unrecognized_database_rejected_without_byte_changes(tmp_path, kind):
    path = tmp_path / "journal.db"
    cls = store_type()
    if kind == "foreign":
        with sqlite3.connect(path) as conn:
            conn.execute("CREATE TABLE private_data (value TEXT)")
            conn.execute("INSERT INTO private_data VALUES ('keep')")
    elif kind in {"future", "altered"}:
        cls(path).close()
        with sqlite3.connect(path) as conn:
            if kind == "future":
                conn.execute("PRAGMA user_version=999")
            else:
                conn.execute("CREATE TABLE unexpected (value TEXT)")
    else:
        path.write_bytes(b"" if kind == "empty" else b"invalid sqlite bytes")
    original = path.read_bytes()
    with pytest.raises(ValueError):
        cls(path)
    assert path.read_bytes() == original


@pytest.mark.parametrize("state", ["alive", "unknown"])
def test_recovery_refuses_releasing_unconfirmed_dead_owner(tmp_path, monkeypatch, state):
    store = store_type()(tmp_path / "journal.db")
    reserve(store)
    monkeypatch.setattr("pa_cli.process_identity.owner_status", lambda owner: state)
    with pytest.raises(ValueError):
        store.recover("req", "abort", "operator", "evidence.txt")
    assert store.totals("run") == (10, Decimal("0.001"))
    assert store.status()["events"] == []
    store.close()


@pytest.mark.parametrize("resolution, expected", [("abort", 0), ("commit", 10)])
def test_dead_owner_recovery_records_immutable_event(tmp_path, monkeypatch, resolution, expected):
    store = store_type()(tmp_path / "journal.db")
    reserve(store, max_tokens=10, max_cost="0.001")
    monkeypatch.setattr("pa_cli.process_identity.owner_status", lambda owner: "dead")
    event = store.recover("req", resolution, "operator", "evidence.txt")
    assert event["resolution"] == resolution
    assert event["operator"] == "operator"
    assert event["evidence"] == "evidence.txt"
    assert store.totals("run")[0] == expected
    assert store.status()["runs"][0]["max_tokens"] == 10
    assert store.status()["pending"] == []
    assert store.status()["events"] == [event]
    with pytest.raises(ValueError):
        store.recover("req", "abort", "operator", "again.txt")
    if resolution == "commit":
        assert store.receipts()[0]["estimated_tokens"] == 10
    store.close()


def legacy_files(tmp_path, pending=None, records=None):
    audit = tmp_path / "legacy.jsonl"
    sidecar = tmp_path / ".legacy.jsonl.reservations.json"
    audit.write_text("\n".join(json.dumps(r) for r in (records or [receipt()])) + "\n", encoding="utf-8")
    sidecar.write_text(json.dumps(pending or {}), encoding="utf-8")
    return audit, sidecar


def test_migration_atomic_idempotent_and_preserves_sources(tmp_path):
    audit, sidecar = legacy_files(tmp_path, records=[receipt(), receipt("reject", decision="REJECTED")])
    original = [p.read_bytes() for p in (audit, sidecar)]
    store = store_type()(tmp_path / "journal.db")
    report = store.migrate(audit, sidecar, "operator")
    assert report["imported_receipts"] == 2
    assert report["already_imported"] is False
    assert store.totals("run") == (10, Decimal("0.001"))
    repeated = store.migrate(audit, sidecar, "operator")
    assert repeated["already_imported"] is True
    assert len(store.receipts()) == 2
    assert [p.read_bytes() for p in (audit, sidecar)] == original
    assert len(report["source_digests"]["audit"]) == 64
    store.close()


@pytest.mark.parametrize("bad", ["audit", "pending", "unknown", "live", "excess"])
def test_migration_rejects_bad_or_unsafe_sources_without_partial_import(tmp_path, monkeypatch, bad):
    pending = {"run": {"pending": {"tokens": 10, "cost": "0.001", "pid": 123,
                                    "birth": "legacy", "timestamp": 1}}}
    audit, sidecar = legacy_files(tmp_path, pending=pending)
    if bad == "audit":
        audit.write_text(json.dumps(receipt()) + "\n{broken", encoding="utf-8")
    elif bad == "pending":
        sidecar.write_text('{"run": {"pending": {"tokens": -1}}}', encoding="utf-8")
    elif bad == "excess":
        audit.write_text(json.dumps(receipt(tokens=100001)) + "\n", encoding="utf-8")
    state = "alive" if bad == "live" else "unknown" if bad == "unknown" else "dead"
    monkeypatch.setattr("pa_cli.process_identity.owner_status", lambda owner: state)
    before = [p.read_bytes() for p in (audit, sidecar)]
    store = store_type()(tmp_path / "journal.db")
    with pytest.raises(ValueError):
        store.migrate(audit, sidecar, "operator")
    assert store.totals("run") == (0, Decimal("0"))
    assert store.receipts() == []
    assert store.status()["runs"] == []
    assert [p.read_bytes() for p in (audit, sidecar)] == before
    store.close()


def test_dead_legacy_pending_remains_held_until_explicit_recovery(tmp_path, monkeypatch):
    audit, sidecar = legacy_files(tmp_path, pending={"run": {"pending": {
        "tokens": 20, "cost": "0.002", "pid": 123, "birth": "legacy", "timestamp": 1}}})
    monkeypatch.setattr("pa_cli.process_identity.owner_status", lambda owner: "dead")
    store = store_type()(tmp_path / "journal.db")
    assert store.migrate(audit, sidecar, "operator")["imported_reservations"] == 1
    assert store.totals("run") == (30, Decimal("0.003"))
    assert store.status()["pending"][0]["request_id"] == "pending"
    store.recover("pending", "abort", "operator", "dead-process.txt")
    assert store.totals("run") == (10, Decimal("0.001"))
    store.close()


def test_unreserved_rejection_is_durable_without_allocating_caps(tmp_path):
    store = store_type()(tmp_path / "journal.db")
    rec = receipt(decision="REJECTED")
    assert store.record_rejection(rec) == rec
    assert store.record_rejection(dict(rec)) == rec
    assert store.status()["runs"] == []
    assert store.totals("run") == (0, Decimal("0"))
    with pytest.raises(ValueError):
        store.record_rejection(dict(rec, payload_sha256="b" * 64))
    with pytest.raises(ValueError):
        reserve(store)
    store.close()
    reopened = store_type()(tmp_path / "journal.db", read_only=True, create=False)
    assert reopened.receipts() == [rec]
    with pytest.raises(ValueError):
        reopened.record_rejection(receipt("another", decision="REJECTED"))
    reopened.close()


def test_read_only_diagnostics_do_not_create_or_change_database(tmp_path):
    path = tmp_path / "journal.db"
    cls = store_type()
    with pytest.raises(ValueError):
        cls(path, read_only=True, create=False)
    assert not path.exists()
    store = cls(path)
    reserve(store)
    store.close()
    original = path.read_bytes()
    reader = cls(path, read_only=True, create=False)
    assert reader.status()["integrity"] == "ok"
    assert reader.totals("run") == (10, Decimal("0.001"))
    reader.receipts()
    reader.close()
    assert path.read_bytes() == original


def test_decimal_accounting_does_not_round_away_tiny_pending_cost(tmp_path):
    store = store_type()(tmp_path / "journal.db")
    with localcontext() as context:
        context.prec = 3
        assert reserve(store, "first", tokens=1, cost="0.009999999999999999999999999999")
        assert reserve(store, "tiny", tokens=1, cost="0.000000000000000000000000000001")
        assert store.totals("run") == (2, Decimal("0.010000000000000000000000000000"))
        assert not reserve(store, "excess", tokens=1, cost="0.000000000000000000000000000001")
    store.close()


@pytest.mark.parametrize("phase", ["reserve", "finalize", "recover", "migrate"])
def test_each_write_failure_rolls_back_all_of_its_transaction(tmp_path, monkeypatch, phase):
    cls = store_type()
    module = importlib.import_module("pa_cli.gateway_store")
    connect = sqlite3.connect
    class FailCommit(sqlite3.Connection):
        fail = False
        def execute(self, sql, *args, **kwargs):
            if self.fail and sql == "COMMIT":
                raise sqlite3.OperationalError("injected commit failure")
            return super().execute(sql, *args, **kwargs)
    monkeypatch.setattr(module.sqlite3, "connect", lambda *a, **k: connect(*a, factory=FailCommit, **k))
    store = cls(tmp_path / "journal.db")
    if phase in {"finalize", "recover"}:
        reserve(store)
    before = store.status()
    store._conn.fail = True
    sources = None
    with pytest.raises(ValueError, match="injected commit failure"):
        if phase == "reserve":
            reserve(store)
        elif phase == "finalize":
            store.finalize("req", receipt())
        elif phase == "recover":
            monkeypatch.setattr("pa_cli.process_identity.owner_status", lambda owner: "dead")
            store.recover("req", "commit", "operator", "evidence.txt")
        else:
            sources = legacy_files(tmp_path)
            source_bytes = [p.read_bytes() for p in sources]
            store.migrate(*sources, "operator")
    store._conn.fail = False
    after = store.status()
    assert after["runs"] == before["runs"]
    assert len(after["pending"]) == len(before["pending"])
    assert after["events"] == before["events"]
    assert store.receipts() == []
    if sources:
        assert [p.read_bytes() for p in sources] == source_bytes
    store.close()


def test_append_only_history_and_caps_reject_direct_mutation(tmp_path):
    path = tmp_path / "journal.db"
    store = store_type()(path)
    reserve(store)
    store.finalize("req", receipt())
    store.close()
    with sqlite3.connect(path) as conn:
        for sql in ["UPDATE runs SET max_tokens=1", "DELETE FROM runs",
                    "DELETE FROM requests", "UPDATE requests SET state='reserved'",
                    "UPDATE receipts SET content='{}'", "DELETE FROM receipts"]:
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(sql)
    reopened = store_type()(path)
    assert reopened.totals("run") == (10, Decimal("0.001"))
    assert reopened.receipts() == [receipt()]
    reopened.close()


def test_receipt_identity_and_missing_request_fail_closed(tmp_path):
    store = store_type()(tmp_path / "journal.db")
    reserve(store)
    for rec in [dict(receipt(), request_id="other"), dict(receipt(), run_id="other"),
                dict(receipt(), estimated_cost_usd="0.002")]:
        with pytest.raises(ValueError):
            store.finalize("req", rec)
    with pytest.raises(ValueError):
        store.finalize("missing", receipt("missing"))
    assert store.totals("run") == (10, Decimal("0.001"))
    assert store.receipts() == []
    store.close()


def test_migration_detects_source_changes_and_rolls_back(tmp_path, monkeypatch):
    cls = store_type()
    audit, sidecar = legacy_files(tmp_path)
    original_import = cls._import_sources
    def concurrent_writer(self, *args):
        result = original_import(self, *args)
        audit.write_text(json.dumps(receipt("changed")) + "\n", encoding="utf-8")
        return result
    monkeypatch.setattr(cls, "_import_sources", concurrent_writer)
    store = cls(tmp_path / "journal.db")
    with pytest.raises(ValueError, match="source changed"):
        store.migrate(audit, sidecar, "operator")
    assert store.status()["runs"] == []
    assert store.receipts() == []
    assert store.status()["events"] == []
    store.close()


def test_migration_rejects_changed_sources_and_nonempty_target(tmp_path):
    cls = store_type()
    audit, sidecar = legacy_files(tmp_path)
    store = cls(tmp_path / "journal.db")
    store.migrate(audit, sidecar, "operator")
    audit.write_text(json.dumps(receipt("changed")) + "\n", encoding="utf-8")
    with pytest.raises(ValueError):
        store.migrate(audit, sidecar, "operator")
    assert store.totals("run") == (10, Decimal("0.001"))
    assert store.receipts() == [receipt()]
    store.close()


def test_schema_change_after_open_is_rejected_before_mutation(tmp_path):
    path = tmp_path / "journal.db"
    store = store_type()(path)
    reserve(store)
    with sqlite3.connect(path) as conn:
        conn.execute("DROP TRIGGER receipts_no_delete")
    before = path.read_bytes()
    with pytest.raises(ValueError):
        store.finalize("req", receipt())
    store.close()
    assert path.read_bytes() == before


def test_commit_recovery_of_unknown_owner_keeps_reserved_amounts(tmp_path, monkeypatch):
    store = store_type()(tmp_path / "journal.db")
    reserve(store)
    monkeypatch.setattr("pa_cli.process_identity.owner_status", lambda owner: "unknown")
    event = store.recover("req", "commit", "operator", "usage-confirmation.txt")
    assert event["owner_status"] == "unknown"
    assert store.totals("run") == (10, Decimal("0.001"))
    assert store.status()["runs"][0]["committed_tokens"] == 10
    with pytest.raises(ValueError):
        store.recover("req", "abort", "operator", "release.txt")
    store.close()


def test_receipt_limit_and_status_filter_are_consistent(tmp_path):
    store = store_type()(tmp_path / "journal.db")
    for request_id in ("a", "b", "c"):
        store.record_rejection(receipt(request_id, decision="REJECTED"))
    assert [r["request_id"] for r in store.receipts(limit=2)] == ["b", "c"]
    assert store.receipts(limit=0) == []
    with pytest.raises(ValueError):
        store.receipts(limit=-1)
    reserve(store)
    assert store.status("missing")["pending"] == []
    assert len(store.status("run")["pending"]) == 1
    store.close()


def test_migration_persists_operator_reconciled_cap_and_rejects_repeat_changes(tmp_path):
    audit, sidecar = legacy_files(tmp_path)
    store = store_type()(tmp_path / "journal.db")
    report = store.migrate(audit, sidecar, "operator", max_cost="0.002")
    assert report["legacy_max_cost"] == "0.002"
    assert store.status()["runs"][0]["max_cost"] == "0.002"
    assert store.migrate(audit, sidecar, "operator", max_cost="0.0020")["already_imported"]
    with pytest.raises(ValueError):
        store.migrate(audit, sidecar, "operator", max_cost="0.003")
    assert reserve(store, "remaining", max_cost="0.002")
    assert not reserve(store, "excess", max_cost="0.002")
    store.close()


def test_migration_chooses_minimum_recorded_and_operator_cap_for_entire_run(tmp_path):
    audit, sidecar = legacy_files(tmp_path, records=[dict(receipt(), max_cost="0.003"),
                                                   dict(receipt("second"), max_cost="0.002")])
    store = store_type()(tmp_path / "journal.db")
    store.migrate(audit, sidecar, "operator", max_cost="0.004")
    assert store.status()["runs"][0]["max_cost"] == "0.002"
    assert store.totals("run") == (20, Decimal("0.002"))
    store.close()


def test_migration_rejects_usage_above_reconciled_cap_without_partial_import(tmp_path):
    audit, sidecar = legacy_files(tmp_path)
    store = store_type()(tmp_path / "journal.db")
    with pytest.raises(ValueError):
        store.migrate(audit, sidecar, "operator", max_cost="0.0005")
    assert store.status()["runs"] == []
    assert store.receipts() == []
    store.close()


def _delayed_first_creation(path, ready, proceed, result):
    module = importlib.import_module("pa_cli.gateway_store")
    original_connect = sqlite3.connect
    class DelayedBegin(sqlite3.Connection):
        def execute(self, sql, *args, **kwargs):
            if sql == "BEGIN IMMEDIATE":
                ready.set()
                proceed.wait(20)
            return super().execute(sql, *args, **kwargs)
    module.sqlite3.connect = lambda *a, **k: original_connect(*a, factory=DelayedBegin, **k)
    store = module.GatewayStore(path)
    result.put(store.status()["integrity"])
    store.close()


def test_simultaneous_creation_waits_for_the_initializing_process(tmp_path, monkeypatch):
    path = tmp_path / "journal.db"
    cls = store_type()
    ctx = multiprocessing.get_context("spawn")
    ready, proceed, result = ctx.Event(), ctx.Event(), ctx.Queue()
    first = ctx.Process(target=_delayed_first_creation, args=(str(path), ready, proceed, result))
    first.start()
    try:
        assert ready.wait(20)
        assert path.exists()
        original_connect = sqlite3.connect
        class ReleaseFirst(sqlite3.Connection):
            def execute(self, sql, *args, **kwargs):
                if sql == "PRAGMA application_id":
                    proceed.set()  # First creator now waits on this transaction.
                return super().execute(sql, *args, **kwargs)
        monkeypatch.setattr(sqlite3, "connect", lambda *a, **k: original_connect(*a, factory=ReleaseFirst, **k))
        second = cls(path)
        assert second.status()["integrity"] == "ok"
        second.close()
        assert result.get(timeout=20) == "ok"
        first.join(20)
        assert first.exitcode == 0
    finally:
        proceed.set()
        if first.is_alive():
            first.terminate()
            first.join(10)


def test_status_does_not_disclose_extra_owner_or_receipt_payload(tmp_path):
    store = store_type()(tmp_path / "journal.db")
    reserve(store, owner={"pid": 123, "birth": "birth", "credential": "SECRET",
                          "passage": "full generated passage"})
    result = json.dumps(store.status())
    assert "SECRET" not in result
    assert "full generated passage" not in result
    store.close()


@pytest.mark.parametrize("duplicate", ["receipt", "pending", "json_key"])
def test_migration_duplicate_identity_is_rejected_atomically(tmp_path, duplicate, monkeypatch):
    audit, sidecar = legacy_files(tmp_path)
    if duplicate == "receipt":
        audit.write_text(json.dumps(receipt()) + "\n" + json.dumps(receipt()) + "\n", encoding="utf-8")
    elif duplicate == "pending":
        sidecar.write_text(json.dumps({"run": {"req": {"pid": 123, "birth": "birth", "timestamp": 1,
                                                         "tokens": 1, "cost": "0.001"}}}), encoding="utf-8")
    else:
        sidecar.write_text('{"run": {}, "run": {}}', encoding="utf-8")
    monkeypatch.setattr("pa_cli.process_identity.owner_status", lambda owner: "dead")
    sources = [p.read_bytes() for p in (audit, sidecar)]
    store = store_type()(tmp_path / "journal.db")
    with pytest.raises(ValueError):
        store.migrate(audit, sidecar, "operator")
    assert store.status()["runs"] == []
    assert store.receipts() == []
    assert store.status()["events"] == []
    assert [p.read_bytes() for p in (audit, sidecar)] == sources
    store.close()
