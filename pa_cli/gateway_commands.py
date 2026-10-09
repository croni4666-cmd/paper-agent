"""P3-40 local journal inspection and explicit operator transitions."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import click

from .gateway_store import GatewayStore


def _path(ledger):
    from .gateway import gateway_store_path
    return Path(ledger) if ledger else gateway_store_path()


def _display(value, as_json):
    # Status contains accounting metadata only; never document text or keys.
    click.echo(json.dumps(value, ensure_ascii=False, indent=None if as_json else 2))


def _guarded(action):
    try:
        return action()
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc


def register_gateway_commands(group):
    @group.command("status")
    @click.option("--ledger", type=click.Path(dir_okay=False), help="Existing local gateway journal")
    @click.option("--run-id", default=None, help="Inspect one run")
    @click.option("--json", "as_json", is_flag=True)
    def status(ledger, run_id, as_json):
        """Inspect immutable caps, committed usage and unresolved owners."""
        def action():
            with GatewayStore(_path(ledger), read_only=True, create=False) as store:
                _display(store.status(run_id), as_json)
        _guarded(action)

    @group.command("doctor")
    @click.option("--ledger", type=click.Path(dir_okay=False), help="Existing local gateway journal")
    @click.option("--json", "as_json", is_flag=True)
    def doctor(ledger, as_json):
        """Check schema, physical integrity and accounting without repair."""
        def action():
            with GatewayStore(_path(ledger), read_only=True, create=False) as store:
                value = store.status()
                value["journal"] = str(store.path)
                _display(value, as_json)
        _guarded(action)

    @group.command("migrate")
    @click.option("--ledger", type=click.Path(dir_okay=False), help="Dedicated target journal")
    @click.option("--audit-file", required=True, type=click.Path(dir_okay=False))
    @click.option("--reservation-file", default=None, type=click.Path(dir_okay=False))
    @click.option("--operator", required=True)
    @click.option("--legacy-max-cost", required=True,
                  help="Reconciled USD ceiling for imported runs (at most 0.01)")
    @click.option("--confirm-stopped", is_flag=True,
                  help="Confirm all v3 writers stopped and historical run ceilings reconciled")
    def migrate(ledger, audit_file, reservation_file, operator, legacy_max_cost, confirm_stopped):
        """Import v3 sources atomically, preserving original bytes and digests."""
        if not confirm_stopped:
            raise click.ClickException("Migration requires --confirm-stopped; stop every v3 writer and reconcile historical caps")
        from .gateway import _get_resv_path, gateway_store_path
        audit = Path(audit_file)
        target = Path(ledger) if ledger else gateway_store_path(audit)
        sidecar = Path(reservation_file) if reservation_file else _get_resv_path(audit)
        # Check before opening: SQLite must never reinterpret a source as target.
        if target.resolve() in {audit.resolve(), sidecar.resolve()}:
            raise click.ClickException("Migration source and target must be distinct")
        def action():
            with GatewayStore(target) as store:
                _display(store.migrate(audit, sidecar, operator, max_cost=legacy_max_cost), True)
        _guarded(action)

    @group.command("recover")
    @click.option("--ledger", type=click.Path(exists=True, dir_okay=False))
    @click.option("--request-id", required=True)
    @click.option("--resolution", required=True, type=click.Choice(["commit", "abort"]))
    @click.option("--operator", required=True)
    @click.option("--evidence", required=True, help="Accountable explanation of the known outcome")
    def recover(ledger, request_id, resolution, operator, evidence):
        """Resolve one held request; abort requires a confirmed dead owner."""
        def action():
            with GatewayStore(_path(ledger), create=False) as store:
                _display(store.recover(request_id, resolution, operator, evidence), True)
        _guarded(action)

    @group.command("export")
    @click.option("--ledger", type=click.Path(exists=True, dir_okay=False))
    @click.option("--output", required=True, type=click.Path(dir_okay=False))
    def export(ledger, output):
        """Atomically export receipt JSONL; canonical accounting is unchanged."""
        def action():
            target = Path(output).resolve()
            journal = _path(ledger).resolve()
            protected = [journal, *(Path(str(journal) + suffix) for suffix in ("-journal", "-wal", "-shm"))]
            if any(target == p or (target.exists() and p.exists() and target.samefile(p)) for p in protected):
                raise ValueError("Cannot export over journal files")
            with GatewayStore(journal, read_only=True, create=False) as store:
                records = store.receipts()
            raw = "".join(json.dumps(rec, ensure_ascii=False) + "\n" for rec in records).encode("utf-8")
            target.parent.mkdir(parents=True, exist_ok=True)
            fd, temporary = tempfile.mkstemp(prefix=".gateway-export-", dir=target.parent)
            try:
                with os.fdopen(fd, "wb") as handle:
                    if handle.write(raw) != len(raw):
                        raise OSError("Incomplete gateway export")
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, target)
            finally:
                Path(temporary).unlink(missing_ok=True)
            click.echo(f"Exported {len(records)} receipts to {target}")
        _guarded(action)
