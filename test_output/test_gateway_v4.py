"""P3-40: default transactional gateway and operator-only local tools."""
import json
import multiprocessing
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from pa_cli import gateway as g
from pa_cli.cli import main


def candidate(tmp_path):
    artifact = tmp_path / "paper.txt"
    artifact.write_text("Licensed evidence passage.", encoding="utf-8")
    return g.PaperEvaluationCandidate("p", str(artifact), "10.1000/test")


def verified(cand):
    raw = Path(cand.artifact_path).read_bytes()
    import hashlib
    return g.PaperVerificationResult(cand.paper_id, cand.doi, True,
        "VERIFIED_PUBLIC_OA", "public_oa", artifact_sha256=hashlib.sha256(raw).hexdigest(), raw_bytes=raw)


def evaluate(tmp_path, **kwargs):
    with patch.object(g, "verify_paper_rights", side_effect=verified):
        return g.evaluate_gateway_request(run_id="run", operator="tester",
            candidates=[candidate(tmp_path)], passages=["Licensed evidence passage."],
            consent_public_oa=True, consent_zero_retention=True,
            audit_file=tmp_path / "audit.jsonl", verify_passage_provenance=True, **kwargs)


def test_default_is_transactional_and_commits_once(tmp_path):
    from pa_cli.gateway_store import GatewayStore
    receipt, passages = evaluate(tmp_path)
    assert receipt.gateway_decision == "AUTHORIZED"
    assert receipt.request_id
    assert receipt.provenance_verified
    assert passages == ["Licensed evidence passage."]
    assert not (tmp_path / "audit.jsonl").exists()
    store = GatewayStore(g.gateway_store_path(tmp_path / "audit.jsonl"), read_only=True, create=False)
    assert store.status()["pending"] == []
    assert store.totals("run")[0] == receipt.estimated_tokens
    assert store.receipts() == [receipt.to_dict()]
    store.close()


def test_finalize_failure_keeps_accounted_reservation(tmp_path):
    from pa_cli.gateway_store import GatewayStore
    with patch.object(GatewayStore, "finalize", side_effect=OSError("write failure")):
        receipt, _ = evaluate(tmp_path)
    assert receipt.gateway_decision == "REJECTED"
    store = GatewayStore(g.gateway_store_path(tmp_path / "audit.jsonl"), read_only=True, create=False)
    assert len(store.status()["pending"]) == 1
    assert store.totals("run")[0] == receipt.estimated_tokens
    store.close()


def test_legacy_epoch_requires_explicit_migration(tmp_path):
    audit = tmp_path / "audit.jsonl"
    audit.write_text('{"gateway_decision":"AUTHORIZED"}\n', encoding="utf-8")
    original = audit.read_bytes()
    receipt, _ = evaluate(tmp_path)
    assert receipt.gateway_decision == "REJECTED"
    assert any("migrat" in reason.lower() for reason in receipt.rejection_reasons)
    assert audit.read_bytes() == original
    assert not g.gateway_store_path(audit).exists()


def test_legacy_adapter_refuses_transactional_epoch(tmp_path):
    evaluate(tmp_path)
    receipt, _ = evaluate(tmp_path, storage_backend="legacy-json")
    assert receipt.gateway_decision == "REJECTED"
    assert not (tmp_path / "audit.jsonl").exists()


@pytest.mark.parametrize("limit", ["NaN", "Infinity", "-0.01", "nonsense"])
def test_invalid_cost_fails_closed(tmp_path, limit):
    receipt, _ = evaluate(tmp_path, max_cost_usd_limit=limit)
    assert receipt.gateway_decision == "REJECTED"
    assert not receipt.ceiling_compliant


def test_read_only_cli_never_initializes_missing_store(tmp_path):
    runner = CliRunner()
    path = tmp_path / "missing.sqlite3"
    for command in ("status", "doctor", "audit"):
        result = runner.invoke(main, ["gateway", command, "--ledger", str(path), "--json"])
        assert result.exit_code != 0
        assert not path.exists()


def test_status_doctor_export_do_not_change_accounting(tmp_path):
    from pa_cli.gateway_store import GatewayStore
    evaluate(tmp_path)
    path = g.gateway_store_path(tmp_path / "audit.jsonl")
    runner = CliRunner()
    for command in ("status", "doctor", "audit"):
        result = runner.invoke(main, ["gateway", command, "--ledger", str(path), "--json"])
        assert result.exit_code == 0, result.output
        assert json.loads(result.output)
    output = tmp_path / "export.jsonl"
    result = runner.invoke(main, ["gateway", "export", "--ledger", str(path), "--output", str(output)])
    assert result.exit_code == 0, result.output
    store = GatewayStore(path, read_only=True, create=False)
    assert json.loads(output.read_text(encoding="utf-8")) == store.receipts()[0]
    assert store.status()["pending"] == []
    store.close()


def test_cli_migrate_requires_confirmation_and_preserves_source(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    audit = tmp_path / "legacy.jsonl"
    audit.write_text("", encoding="utf-8")
    result = CliRunner().invoke(main, ["gateway", "migrate", "--ledger", str(path),
        "--audit-file", str(audit), "--operator", "tester"])
    assert result.exit_code != 0
    assert not path.exists()
    assert audit.read_bytes() == b""


def test_gateway_cli_does_not_load_key_registry(tmp_path):
    with patch("pa_cli.keys.load_env_into_environ", side_effect=AssertionError("unrelated key read")):
        result = CliRunner().invoke(main, ["gateway", "doctor", "--ledger", str(tmp_path / "missing")])
    assert "unrelated key read" not in str(result.exception)
    assert "does not exist" in result.output


def test_failed_migration_target_cannot_start_new_epoch(tmp_path):
    from pa_cli.gateway_store import GatewayStore
    audit = tmp_path / "audit.jsonl"
    audit.write_text('{bad-json}\n', encoding="utf-8")
    with GatewayStore(g.gateway_store_path(audit)) as store:
        with pytest.raises(ValueError):
            store.migrate(audit, g._get_resv_path(audit), "tester", max_cost="0.01")
    receipt, _ = evaluate(tmp_path)
    assert receipt.gateway_decision == "REJECTED"
    assert any("migration" in reason for reason in receipt.rejection_reasons)


def test_explicit_migration_and_python_audit_reader(tmp_path):
    from pa_cli.gateway_store import GatewayStore
    audit = tmp_path / "audit.jsonl"
    # An authentic v3-shaped receipt: request_id did not exist before v4.
    with patch.object(g, "verify_paper_rights", side_effect=verified):
        rec, _ = g._evaluate_legacy_gateway_request("run", "tester", [candidate(tmp_path)],
            ["Licensed evidence passage."], True, True, audit_file=audit)
    result = CliRunner().invoke(main, ["gateway", "migrate", "--audit-file", str(audit),
        "--operator", "tester", "--confirm-stopped", "--legacy-max-cost", "0.002"])
    assert result.exit_code == 0, result.output
    with GatewayStore(g.gateway_store_path(audit), read_only=True, create=False) as store:
        assert store.status()["runs"][0]["max_cost"] == "0.002"
    # Imported caps are immutable: the caller repeats the reconciled cap.
    next_receipt, _ = evaluate(tmp_path, max_cost_usd_limit="0.002")
    assert next_receipt.gateway_decision == "AUTHORIZED"
    events = g.read_gateway_audit_events(audit_file=audit)
    assert len(events) == 2
    assert events[0].estimated_tokens == rec.estimated_tokens
    audit.write_text(audit.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    changed, _ = evaluate(tmp_path, max_cost_usd_limit="0.002")
    assert changed.gateway_decision == "REJECTED"


def _exit_with_pending(directory):
    with patch("pa_cli.gateway_store.GatewayStore.finalize", side_effect=OSError("outcome unknown")):
        evaluate(Path(directory))


def test_native_exited_owner_explicit_abort_releases_only_pending(tmp_path):
    from pa_cli.gateway_store import GatewayStore
    process = multiprocessing.get_context("spawn").Process(target=_exit_with_pending, args=(str(tmp_path),))
    process.start()
    process.join(20)
    assert process.exitcode == 0
    path = g.gateway_store_path(tmp_path / "audit.jsonl")
    with GatewayStore(path, read_only=True, create=False) as store:
        pending = store.status()["pending"]
        assert len(pending) == 1
        assert pending[0]["owner_status"] == "dead"
    result = CliRunner().invoke(main, ["gateway", "recover", "--ledger", str(path),
        "--request-id", pending[0]["request_id"], "--resolution", "abort",
        "--operator", "tester", "--evidence", "Child exited; no external execution occurred"])
    assert result.exit_code == 0, result.output
    with GatewayStore(path, read_only=True, create=False) as store:
        assert store.totals("run")[0] == 0
        assert store.status()["events"][0]["kind"] == "recovery"


def test_recovery_commit_remains_counted_and_audit_readable(tmp_path):
    from pa_cli.gateway_store import GatewayStore
    with patch.object(GatewayStore, "finalize", side_effect=OSError("outcome unknown")):
        rec, _ = evaluate(tmp_path)
    path = g.gateway_store_path(tmp_path / "audit.jsonl")
    with GatewayStore(path) as store:
        store.recover(rec.request_id, "commit", "tester", "Known completed outcome")
        assert store.totals("run")[0] == rec.estimated_tokens
    events = g.read_gateway_audit_events(audit_file=tmp_path / "audit.jsonl")
    assert len(events) == 1
    assert events[0].gateway_decision == "AUTHORIZED"


def test_export_cannot_overwrite_canonical_store(tmp_path):
    evaluate(tmp_path)
    path = g.gateway_store_path(tmp_path / "audit.jsonl")
    original = path.read_bytes()
    result = CliRunner().invoke(main, ["gateway", "export", "--ledger", str(path), "--output", str(path)])
    assert result.exit_code != 0
    assert path.read_bytes() == original


def test_minimal_legacy_pending_recovery_has_readable_history(tmp_path):
    from pa_cli.gateway_store import GatewayStore
    audit = tmp_path / "audit.jsonl"
    audit.write_bytes(b"")
    sidecar = g._get_resv_path(audit)
    sidecar.write_text(json.dumps({"run": {"legacy": {"tokens": 5, "cost": "0.001",
        "pid": 123, "timestamp": 1.0}}}), encoding="utf-8")
    with GatewayStore(g.gateway_store_path(audit)) as store, patch("pa_cli.gateway_store._owner_status", return_value="dead"):
        store.migrate(audit, sidecar, "tester", max_cost="0.01")
        store.recover("legacy", "commit", "tester", "Legacy completed amount confirmed")
    events = g.read_gateway_audit_events(audit_file=audit)
    assert events[0].estimated_tokens == 5
    assert events[0].legacy_pending
    assert not events[0].provenance_verified


def test_custom_migration_sidecar_is_used_for_later_integrity_checks(tmp_path):
    audit = tmp_path / "audit.jsonl"
    audit.write_bytes(b"")
    sidecar = tmp_path / "custom-pending.json"
    sidecar.write_bytes(b"{}")
    ledger = g.gateway_store_path(audit)
    result = CliRunner().invoke(main, ["gateway", "migrate", "--audit-file", str(audit),
        "--reservation-file", str(sidecar), "--ledger", str(ledger),
        "--operator", "tester", "--confirm-stopped", "--legacy-max-cost", "0.01"])
    assert result.exit_code == 0, result.output
    rec, _ = evaluate(tmp_path)
    assert rec.gateway_decision == "AUTHORIZED"
    sidecar.write_bytes(b'{"changed":{}}')
    changed, _ = evaluate(tmp_path)
    assert changed.gateway_decision == "REJECTED"


def _legacy_pending_exit(directory):
    from decimal import Decimal
    g._save_reservation(Path(directory) / "audit.jsonl", "run", "legacy-pending", 60000, Decimal("0.00252"))


def test_pre_first_receipt_crash_sidecar_can_migrate_without_audit(tmp_path):
    from pa_cli.gateway_store import GatewayStore
    child = multiprocessing.get_context("spawn").Process(target=_legacy_pending_exit, args=(str(tmp_path),))
    child.start()
    child.join(20)
    assert child.exitcode == 0
    audit = tmp_path / "audit.jsonl"
    assert not audit.exists()
    before = g._get_resv_path(audit).read_bytes()
    result = CliRunner().invoke(main, ["gateway", "migrate", "--audit-file", str(audit),
        "--operator", "tester", "--confirm-stopped", "--legacy-max-cost", "0.01"])
    assert result.exit_code == 0, result.output
    with GatewayStore(g.gateway_store_path(audit), read_only=True, create=False) as store:
        assert store.totals("run")[0] == 60000
        assert len(store.status()["pending"]) == 1
        assert store.status()["events"][0]["source_digests"]["audit"] is None
    assert not audit.exists()
    assert g._get_resv_path(audit).read_bytes() == before
    # Still counted, with the configured original cap, after migration.
    rec, _ = evaluate(tmp_path)
    assert rec.gateway_decision == "REJECTED"  # legacy paper count is unknown
    with GatewayStore(g.gateway_store_path(audit)) as store:
        assert store.status()["runs"][0]["paper_count_unknown"]
        store.recover("legacy-pending", "abort", "tester", "Exited before first audit, no operation executed")
    healthy, _ = evaluate(tmp_path)
    assert healthy.gateway_decision == "AUTHORIZED"
