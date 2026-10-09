"""Canonical single-machine gateway journal, using only the Python stdlib.

Reservations, immutable run ceilings, final receipts and operator recovery share
one SQLite transaction. Costs are Decimal text, never SQLite REAL. A local disk
and SQLite's durability guarantees are required; this is not a hosted SLA.
Legacy imports require all v3 writers stopped. Mixed backend epochs are unsafe.
"""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path
from typing import Any

APPLICATION_ID = 0x50414734  # PAG4
SCHEMA_VERSION = 1
MAX_TOKENS = 100000
MAX_COST = Decimal("0.01")
MAX_PAPERS = 25


class GatewayStoreError(ValueError):
    """Invalid, conflicting, unsupported or unavailable local journal state."""


class _InitializationPending(GatewayStoreError):
    """Release an empty-file transaction while its original creator starts."""


_SCHEMA = {
    "runs": """CREATE TABLE runs (
        run_id TEXT PRIMARY KEY, max_tokens INTEGER NOT NULL CHECK(max_tokens >= 0),
        max_cost TEXT NOT NULL)""",
    "requests": """CREATE TABLE requests (
        request_id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(run_id),
        tokens INTEGER NOT NULL CHECK(tokens >= 0), cost TEXT NOT NULL,
        owner TEXT NOT NULL, snapshot TEXT NOT NULL,
        state TEXT NOT NULL CHECK(state IN ('reserved','committed','aborted')))""",
    "receipts": """CREATE TABLE receipts (
        sequence INTEGER PRIMARY KEY, request_id TEXT NOT NULL UNIQUE,
        run_id TEXT NOT NULL, content TEXT NOT NULL)""",
    "events": """CREATE TABLE events (
        sequence INTEGER PRIMARY KEY, content TEXT NOT NULL)""",
    "imports": """CREATE TABLE imports (
        digest TEXT PRIMARY KEY, content TEXT NOT NULL)""",
    "runs_no_update": """CREATE TRIGGER runs_no_update BEFORE UPDATE ON runs
        BEGIN SELECT RAISE(ABORT, 'immutable run caps'); END""",
    "runs_no_delete": """CREATE TRIGGER runs_no_delete BEFORE DELETE ON runs
        BEGIN SELECT RAISE(ABORT, 'immutable run caps'); END""",
    "requests_no_delete": """CREATE TRIGGER requests_no_delete BEFORE DELETE ON requests
        BEGIN SELECT RAISE(ABORT, 'immutable request'); END""",
    "requests_transition": """CREATE TRIGGER requests_transition BEFORE UPDATE ON requests
        WHEN OLD.state != 'reserved' OR NEW.state NOT IN ('committed','aborted')
        OR NEW.request_id != OLD.request_id OR NEW.run_id != OLD.run_id
        OR NEW.tokens != OLD.tokens OR NEW.cost != OLD.cost
        OR NEW.owner != OLD.owner OR NEW.snapshot != OLD.snapshot
        BEGIN SELECT RAISE(ABORT, 'invalid request transition'); END""",
}
for _table in ("receipts", "events", "imports"):
    for _action in ("UPDATE", "DELETE"):
        _name = f"{_table}_no_{_action.lower()}"
        _SCHEMA[_name] = (f"CREATE TRIGGER {_name} BEFORE {_action} ON {_table} "
                          "BEGIN SELECT RAISE(ABORT, 'append-only history'); END")


def _json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise GatewayStoreError("Metadata must be finite JSON data") from exc


def _decode(raw: str) -> Any:
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise GatewayStoreError("Duplicate JSON object key")
            result[key] = value
        return result
    try:
        return json.loads(raw, object_pairs_hook=pairs,
                          parse_constant=lambda value: (_ for _ in ()).throw(
                              GatewayStoreError("Nonfinite JSON number")))
    except (TypeError, ValueError) as exc:
        raise GatewayStoreError("Invalid JSON journal or migration data") from exc


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GatewayStoreError(f"{name} must be a nonempty string")
    return value


def _tokens(value: Any) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise GatewayStoreError("Tokens must be a nonnegative integer")
    return value


def _cost(value: Any) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise GatewayStoreError("Cost must be a finite nonnegative decimal")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise GatewayStoreError("Cost must be a finite nonnegative decimal") from exc
    if not result.is_finite() or result < 0:
        raise GatewayStoreError("Cost must be a finite nonnegative decimal")
    return result


def _sum_cost(values) -> Decimal:
    values = list(values)
    if not values:
        return Decimal(0)
    # Avoid the caller's Decimal context rounding away a small reserved amount.
    minimum = min(value.as_tuple().exponent for value in values)
    maximum = max(value.adjusted() for value in values)
    with localcontext() as context:
        context.prec = max(28, maximum - minimum + len(str(len(values))) + 2)
        return sum(values, Decimal(0))


def _owner(value: Any) -> dict:
    if not isinstance(value, dict):
        raise GatewayStoreError("Owner must be an object")
    pid = value.get("pid")
    if not isinstance(pid, int) or isinstance(pid, bool) or pid < 0:
        raise GatewayStoreError("Owner PID must be a nonnegative integer")
    for key in ("birth", "boot_id"):
        if value.get(key) is not None and not isinstance(value[key], str):
            raise GatewayStoreError("Invalid process identity")
    _json(value)
    return value


def _owner_status(owner: dict) -> str:
    from .process_identity import owner_status
    try:
        result = owner_status(owner)
    except Exception:
        return "unknown"
    return result if result in {"alive", "dead", "unknown"} else "unknown"


def _receipt(value: Any, *, legacy: bool = False) -> dict:
    if hasattr(value, "to_dict"):
        value = value.to_dict()
    if not isinstance(value, dict):
        raise GatewayStoreError("Receipt must be an object")
    value = _decode(_json(value))  # detached immutable snapshot
    for key in ("run_id", "receipt_id"):
        _text(value.get(key), key)
    if not legacy:
        _text(value.get("request_id"), "request_id")
    if value.get("gateway_decision") not in {"AUTHORIZED", "REJECTED"}:
        raise GatewayStoreError("Invalid gateway decision")
    _tokens(value.get("estimated_tokens"))
    _cost(value.get("estimated_cost_usd"))
    return value


def _bind(rec: dict, request_id: str, run_id: str, tokens: int, cost: Decimal):
    if (rec["request_id"] != request_id or rec["run_id"] != run_id
            or rec["estimated_tokens"] != tokens or _cost(rec["estimated_cost_usd"]) != cost):
        raise GatewayStoreError("Receipt does not match reserved request identity and amounts")


def _bind_snapshot(rec: dict, snapshot: dict, *, recovery=None):
    expected = dict(snapshot)
    if recovery is not None:
        expected["recovery"] = recovery
    if rec["gateway_decision"] == "REJECTED":
        # A rejected finalization may explain rejection, not replace evidence.
        mutable = {"gateway_decision", "rejection_reasons", "ceiling_compliant"}
        expected = {key: value for key, value in expected.items() if key not in mutable}
        actual = {key: value for key, value in rec.items() if key not in mutable}
    else:
        actual = rec
    if actual != expected:
        raise GatewayStoreError("Final receipt differs from the verified reservation snapshot")


def _papers(rec: dict) -> int:
    # Unknown counts are tracked separately and block further reservations.
    # This permits migration/recovery alongside known historical receipts.
    return _tokens(rec.get("total_candidates", 0))


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


class GatewayStore:
    """Durable local journal. Invalid stores are never reset or repaired implicitly.

    ``reserve`` returns False only for exhausted quota. Other failures raise
    GatewayStoreError. ``totals`` returns (tokens, Decimal), counting committed
    plus reserved usage. All methods return only after their transaction commits.
    ``read_only=True`` never creates a file; mutations are refused.
    """

    def __init__(self, path, *, read_only: bool = False, create: bool = True):
        self.path = Path(path).resolve()
        self.read_only = read_only
        existed = self.path.exists()
        if not existed and (read_only or not create):
            raise GatewayStoreError("Gateway journal does not exist; initialize or migrate explicitly")
        if not existed:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = None
        try:
            if read_only or not create:
                mode = "ro" if read_only else "rw"
                self._conn = sqlite3.connect(self.path.as_uri() + "?mode=" + mode,
                                             uri=True, isolation_level=None, timeout=30)
            else:
                self._conn = sqlite3.connect(self.path, isolation_level=None, timeout=30)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.execute("PRAGMA synchronous=FULL")
            initialization_deadline = time.monotonic() + 1.0
            while True:
                try:
                    with self._transaction(validate=False):
                        app_id = self._conn.execute("PRAGMA application_id").fetchone()[0]
                        objects = self._conn.execute("SELECT name FROM sqlite_master").fetchall()
                        version = self._conn.execute("PRAGMA user_version").fetchone()[0]
                        if not existed and app_id == 0 and version == 0 and not objects:
                            for sql in _SCHEMA.values():
                                self._conn.execute(sql)
                            self._conn.execute(f"PRAGMA application_id={APPLICATION_ID}")
                            self._conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
                        elif (existed and app_id == 0 and version == 0 and not objects
                              and not read_only and create and time.monotonic() < initialization_deadline):
                            # SQLite creates the filename before BEGIN. Let the
                            # first creator acquire its transaction. ROLLBACK is
                            # essential: COMMIT would write an empty DB header.
                            raise _InitializationPending("Waiting for initial database creation")
                        self._validate()
                    break
                except _InitializationPending:
                    time.sleep(0.01)
        except Exception as exc:
            self.close()
            if isinstance(exc, GatewayStoreError):
                raise
            raise GatewayStoreError(f"Cannot open gateway journal: {exc}") from exc

    @contextmanager
    def _transaction(self, *, validate: bool = True, write: bool = False):
        if self._conn is None:
            raise GatewayStoreError("Gateway journal is closed")
        if write and self.read_only:
            raise GatewayStoreError("Gateway journal is read-only")
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            if validate:
                self._validate()
            yield
            self._conn.execute("COMMIT")
        except Exception as exc:
            if self._conn.in_transaction:
                self._conn.execute("ROLLBACK")
            if isinstance(exc, GatewayStoreError):
                raise
            raise GatewayStoreError(f"Gateway transaction failed: {exc}") from exc

    def _validate(self):
        conn = self._conn
        if (conn.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID
                or conn.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION):
            raise GatewayStoreError("Foreign or unsupported gateway schema")
        actual = {row["name"]: " ".join(row["sql"].split())
                  for row in conn.execute("SELECT name,sql FROM sqlite_master WHERE sql IS NOT NULL")}
        expected = {name: " ".join(sql.split()) for name, sql in _SCHEMA.items()}
        if actual != expected:
            raise GatewayStoreError("Altered or incomplete gateway schema")
        if [row[0] for row in conn.execute("PRAGMA integrity_check")] != ["ok"]:
            raise GatewayStoreError("Gateway integrity check failed")
        if conn.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise GatewayStoreError("Gateway foreign key integrity check failed")
        runs = {}
        for row in conn.execute("SELECT * FROM runs"):
            _text(row["run_id"], "run_id")
            self._caps(row["max_tokens"], row["max_cost"])
            runs[row["run_id"]] = row
        requests = {}
        for row in conn.execute("SELECT * FROM requests"):
            _text(row["request_id"], "request_id")
            tokens, cost = _tokens(row["tokens"]), _cost(row["cost"])
            _owner(_decode(row["owner"]))
            snapshot = _receipt(_decode(row["snapshot"]))
            _papers(snapshot)
            _bind(snapshot, row["request_id"], row["run_id"], tokens, cost)
            if row["state"] not in {"reserved", "committed", "aborted"}:
                raise GatewayStoreError("Invalid request state")
            requests[row["request_id"]] = row
        recorded = {}
        for row in conn.execute("SELECT * FROM receipts"):
            rec = _receipt(_decode(row["content"]))
            if rec["request_id"] != row["request_id"] or rec["run_id"] != row["run_id"]:
                raise GatewayStoreError("Invalid receipt journal identity")
            req = requests.get(row["request_id"])
            if req is None:
                if rec["gateway_decision"] != "REJECTED":
                    raise GatewayStoreError("Authorization without accounted request")
            else:
                _bind(rec, req["request_id"], req["run_id"], req["tokens"], _cost(req["cost"]))
                recovery = None
                if rec.get("recovery") is not None:
                    matching = [event for event in (_decode(row[0]) for row in conn.execute("SELECT content FROM events"))
                                if event.get("kind") == "recovery" and event.get("request_id") == req["request_id"]
                                and event.get("resolution") == "commit"]
                    if len(matching) != 1:
                        raise GatewayStoreError("Recovered receipt missing its accountable event")
                    recovery = {key: matching[0][key] for key in ("operator", "evidence")}
                _bind_snapshot(rec, _decode(req["snapshot"]), recovery=recovery)
                desired = "committed" if rec["gateway_decision"] == "AUTHORIZED" else "aborted"
                if req["state"] != desired:
                    raise GatewayStoreError("Receipt and reservation state conflict")
            recorded[row["request_id"]] = rec
        for req in requests.values():
            if req["state"] == "committed" and req["request_id"] not in recorded:
                raise GatewayStoreError("Committed request missing receipt")
        for row in conn.execute("SELECT content FROM events UNION ALL SELECT content FROM imports"):
            if not isinstance(_decode(row[0]), dict):
                raise GatewayStoreError("Invalid journal event")
        for run_id, row in runs.items():
            tokens, cost = self._totals(run_id)
            if tokens > row["max_tokens"] or cost > _cost(row["max_cost"]) or self._paper_total(run_id) > MAX_PAPERS:
                raise GatewayStoreError("Stored usage exceeds immutable run cap")

    @staticmethod
    def _caps(max_tokens, max_cost):
        tokens, cost = _tokens(max_tokens), _cost(max_cost)
        if tokens > MAX_TOKENS or cost > MAX_COST:
            raise GatewayStoreError("Run caps exceed gateway hard ceilings")
        return tokens, cost

    def _totals(self, run_id, state=None):
        sql = "SELECT tokens,cost FROM requests WHERE run_id=?"
        args = [run_id]
        if state is None:
            sql += " AND state IN ('reserved','committed')"
        else:
            sql += " AND state=?"
            args.append(state)
        rows = list(self._conn.execute(sql, args))
        return sum(row["tokens"] for row in rows), _sum_cost(_cost(row["cost"]) for row in rows)

    def totals(self, run_id):
        _text(run_id, "run_id")
        with self._transaction():
            result = self._totals(run_id)
        return result

    def _paper_total(self, run_id, state=None):
        sql = "SELECT snapshot FROM requests WHERE run_id=?"
        args = [run_id]
        if state is None:
            sql += " AND state IN ('reserved','committed')"
        else:
            sql += " AND state=?"
            args.append(state)
        return sum(_papers(_decode(row[0])) for row in self._conn.execute(sql, args))

    def _paper_unknown(self, run_id):
        return any("total_candidates" not in _decode(row[0]) for row in self._conn.execute(
            "SELECT snapshot FROM requests WHERE run_id=? AND state IN ('reserved','committed')", (run_id,)))

    def _run(self, run_id, max_tokens, max_cost):
        row = self._conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
        if row is None:
            self._conn.execute("INSERT INTO runs VALUES (?,?,?)", (run_id, max_tokens, str(max_cost)))
        elif row["max_tokens"] != max_tokens or _cost(row["max_cost"]) != max_cost:
            raise GatewayStoreError("Run caps are immutable; use the original ceilings")

    def reserve(self, request_id, run_id, tokens, cost, max_tokens, max_cost, owner, receipt):
        _text(request_id, "request_id")
        _text(run_id, "run_id")
        tokens, cost = _tokens(tokens), _cost(cost)
        max_tokens, max_cost = self._caps(max_tokens, max_cost)
        owner_json = _json(_owner(owner))
        rec = _receipt(receipt)
        _bind(rec, request_id, run_id, tokens, cost)
        if rec["gateway_decision"] != "AUTHORIZED":
            raise GatewayStoreError("Reserve requires an authorization candidate receipt")
        snapshot = _json(rec)
        with self._transaction(write=True):
            existing = self._conn.execute("SELECT * FROM requests WHERE request_id=?", (request_id,)).fetchone()
            if existing is not None:
                self._run(run_id, max_tokens, max_cost)
                if (existing["run_id"] != run_id or existing["tokens"] != tokens
                        or _cost(existing["cost"]) != cost or existing["owner"] != owner_json
                        or existing["snapshot"] != snapshot or existing["state"] != "reserved"):
                    raise GatewayStoreError("Conflicting or already resolved request identity")
                result = True
            else:
                if self._conn.execute("SELECT 1 FROM receipts WHERE request_id=?", (request_id,)).fetchone():
                    raise GatewayStoreError("Request identity already belongs to a receipt")
                self._run(run_id, max_tokens, max_cost)
                prior_tokens, prior_cost = self._totals(run_id)
                result = (prior_tokens + tokens <= max_tokens and _sum_cost([prior_cost, cost]) <= max_cost
                          and not self._paper_unknown(run_id)
                          and self._paper_total(run_id) + _papers(rec) <= MAX_PAPERS)
                if result:
                    self._conn.execute("INSERT INTO requests VALUES (?,?,?,?,?,?, 'reserved')",
                                       (request_id, run_id, tokens, str(cost), owner_json, snapshot))
        return result

    def _insert_receipt(self, rec):
        self._conn.execute("INSERT INTO receipts (request_id,run_id,content) VALUES (?,?,?)",
                           (rec["request_id"], rec["run_id"], _json(rec)))

    def finalize(self, request_id, receipt):
        _text(request_id, "request_id")
        rec = _receipt(receipt)
        with self._transaction(write=True):
            request = self._conn.execute("SELECT * FROM requests WHERE request_id=?", (request_id,)).fetchone()
            if request is None:
                raise GatewayStoreError("Unknown request")
            _bind(rec, request_id, request["run_id"], request["tokens"], _cost(request["cost"]))
            prior = self._conn.execute("SELECT content FROM receipts WHERE request_id=?", (request_id,)).fetchone()
            if prior is not None:
                if prior[0] != _json(rec):
                    raise GatewayStoreError("Conflicting finalization receipt")
            else:
                if request["state"] != "reserved":
                    raise GatewayStoreError("Request already resolved by recovery")
                _bind_snapshot(rec, _decode(request["snapshot"]))
                state = "committed" if rec["gateway_decision"] == "AUTHORIZED" else "aborted"
                self._insert_receipt(rec)
                self._conn.execute("UPDATE requests SET state=? WHERE request_id=?", (state, request_id))
        return rec

    def record_rejection(self, receipt):
        """Persist a failed preflight without allocating quota or freezing caps."""
        rec = _receipt(receipt)
        if rec["gateway_decision"] != "REJECTED":
            raise GatewayStoreError("Unreserved receipts must be REJECTED")
        with self._transaction(write=True):
            if self._conn.execute("SELECT 1 FROM requests WHERE request_id=?", (rec["request_id"],)).fetchone():
                raise GatewayStoreError("Reserved request must be finalized")
            prior = self._conn.execute("SELECT content FROM receipts WHERE request_id=?", (rec["request_id"],)).fetchone()
            if prior is not None:
                if prior[0] != _json(rec):
                    raise GatewayStoreError("Conflicting rejection receipt")
            else:
                self._insert_receipt(rec)
        return rec

    def status(self, run_id=None):
        if run_id is not None:
            _text(run_id, "run_id")
        with self._transaction():
            result = {"application_id": APPLICATION_ID, "schema_version": SCHEMA_VERSION,
                      "integrity": "ok", "runs": [], "pending": [], "events": []}
            run_sql = "SELECT * FROM runs" + (" WHERE run_id=?" if run_id is not None else "") + " ORDER BY run_id"
            for row in self._conn.execute(run_sql, () if run_id is None else (run_id,)):
                tokens, cost = self._totals(row["run_id"])
                committed_tokens, committed_cost = self._totals(row["run_id"], "committed")
                reserved_tokens, reserved_cost = self._totals(row["run_id"], "reserved")
                result["runs"].append({"run_id": row["run_id"], "max_tokens": row["max_tokens"],
                    "max_papers": MAX_PAPERS, "papers": self._paper_total(row["run_id"]),
                    "paper_count_unknown": self._paper_unknown(row["run_id"]),
                    "max_cost": row["max_cost"], "tokens": tokens, "cost": str(cost),
                    "committed_tokens": committed_tokens, "committed_cost": str(committed_cost),
                    "reserved_tokens": reserved_tokens, "reserved_cost": str(reserved_cost)})
            sql = "SELECT * FROM requests WHERE state='reserved'" + (" AND run_id=?" if run_id is not None else "")
            for row in self._conn.execute(sql + " ORDER BY request_id", () if run_id is None else (run_id,)):
                owner = _decode(row["owner"])
                result["pending"].append({"request_id": row["request_id"], "run_id": row["run_id"],
                    "tokens": row["tokens"], "cost": row["cost"],
                    "owner": {key: owner[key] for key in ("pid", "birth", "boot_id") if key in owner},
                    "owner_status": _owner_status(owner)})
            for row in self._conn.execute("SELECT content FROM events ORDER BY sequence"):
                event = _decode(row[0])
                if run_id is None or event.get("run_id") == run_id:
                    result["events"].append(event)
        return result

    def recover(self, request_id, resolution, operator, evidence):
        _text(request_id, "request_id")
        _text(operator, "operator")
        _text(evidence, "evidence")
        if resolution not in {"abort", "commit"}:
            raise GatewayStoreError("Recovery resolution must be abort or commit")
        with self._transaction(write=True):
            request = self._conn.execute("SELECT * FROM requests WHERE request_id=?", (request_id,)).fetchone()
            if request is None or request["state"] != "reserved":
                raise GatewayStoreError("Recovery requires an unresolved reservation")
            owner_state = _owner_status(_decode(request["owner"]))
            if resolution == "abort" and owner_state != "dead":
                raise GatewayStoreError("Cannot release quota without a confirmed dead owner")
            event = {"kind": "recovery", "request_id": request_id, "run_id": request["run_id"],
                     "resolution": resolution, "operator": operator, "evidence": evidence,
                     "owner_status": owner_state, "tokens": request["tokens"], "cost": request["cost"],
                     "timestamp_utc": _timestamp()}
            if resolution == "commit":
                rec = _decode(request["snapshot"])
                rec["gateway_decision"] = "AUTHORIZED"
                rec["recovery"] = {"operator": operator, "evidence": evidence}
                self._insert_receipt(rec)
            state = "committed" if resolution == "commit" else "aborted"
            self._conn.execute("UPDATE requests SET state=? WHERE request_id=?", (state, request_id))
            self._conn.execute("INSERT INTO events (content) VALUES (?)", (_json(event),))
        return event

    def receipts(self, limit=None):
        if limit is not None and (not isinstance(limit, int) or isinstance(limit, bool) or limit < 0):
            raise GatewayStoreError("Receipt limit must be a nonnegative integer")
        with self._transaction():
            rows = list(self._conn.execute("SELECT content FROM receipts ORDER BY sequence"))
            if limit is not None:
                rows = rows[-limit:] if limit else []
            result = [_decode(row[0]) for row in rows]
        return result

    def migrate(self, audit_path, reservation_path, operator, *, max_cost=None):
        """Explicit atomic v3 import. Sources are never changed.

        All v3 writers must be stopped by the operator. PID-only legacy owners
        remain unknown unless process death can be established. Dead pending
        amounts stay reserved until explicit operator recovery. v3 did not store
        run caps: operators must reconcile the original ceiling and supply
        max_cost when it was tighter. Absent cap fields otherwise import at hard
        ceilings, recorded in the event. A supplied cap can only tighten recorded
        caps; an identical repeated import must use the same reconciled ceiling.
        Imports are restricted to an empty target, except an identical repeat.
        """
        _text(operator, "operator")
        legacy_max_cost = None if max_cost is None else self._caps(MAX_TOKENS, max_cost)[1]
        audit_path, reservation_path = Path(audit_path).resolve(), Path(reservation_path).resolve()
        if self.path in {audit_path, reservation_path} or audit_path == reservation_path:
            raise GatewayStoreError("Migration source and target paths must be distinct")
        try:
            audit_bytes = audit_path.read_bytes() if audit_path.exists() else None
            reservation_bytes = reservation_path.read_bytes() if reservation_path.exists() else None
        except OSError as exc:
            raise GatewayStoreError("Cannot read migration sources") from exc
        if audit_bytes is None and reservation_bytes is None:
            raise GatewayStoreError("Both migration sources are missing")
        paths = {"audit": str(audit_path), "reservations": str(reservation_path)}
        digests = {"audit": hashlib.sha256(audit_bytes).hexdigest() if audit_bytes is not None else None,
                   "reservations": hashlib.sha256(reservation_bytes).hexdigest() if reservation_bytes is not None else None}
        digest = hashlib.sha256(_json(digests).encode("utf-8")).hexdigest()
        with self._transaction(write=True):
            prior = self._conn.execute("SELECT content FROM imports WHERE digest=?", (digest,)).fetchone()
            if prior:
                result = _decode(prior[0])
                prior_cap = result.get("legacy_max_cost")
                if result.get("source_paths") != paths:
                    raise GatewayStoreError("Conflicting migration source locations")
                if ((prior_cap is None) != (legacy_max_cost is None)
                        or (prior_cap is not None and _cost(prior_cap) != legacy_max_cost)):
                    raise GatewayStoreError("Conflicting reconciled legacy cap for repeated import")
                result["already_imported"] = True
            else:
                if any(self._conn.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone()
                       for table in ("runs", "requests", "receipts", "events", "imports")):
                    raise GatewayStoreError("Migration requires a dedicated empty target")
                result = self._import_sources(audit_bytes or b"", reservation_bytes, digests, operator, legacy_max_cost)
                result["source_paths"] = paths
                # Detect source edits during parsing. Concurrent mixed-version
                # writers are still unsupported; this is not a cross-file lock.
                if ((audit_path.read_bytes() if audit_path.exists() else None) != audit_bytes
                        or (reservation_path.read_bytes() if reservation_path.exists() else None) != reservation_bytes):
                    raise GatewayStoreError("Migration source changed; stop all legacy writers")
                self._validate()
                self._conn.execute("INSERT INTO imports VALUES (?,?)", (digest, _json(result)))
                event = {"kind": "migration", "operator": operator, "source_digests": digests, "source_paths": paths,
                         "imported_receipts": result["imported_receipts"],
                         "imported_reservations": result["imported_reservations"],
                         "legacy_max_cost": result["legacy_max_cost"],
                         "legacy_caps": "hard ceilings where absent", "timestamp_utc": _timestamp()}
                self._conn.execute("INSERT INTO events (content) VALUES (?)", (_json(event),))
        return result

    def _import_sources(self, audit_bytes, reservation_bytes, digests, operator, legacy_max_cost):
        try:
            text = audit_bytes.decode("utf-8")
            ledger = {} if reservation_bytes is None else _decode(reservation_bytes.decode("utf-8"))
        except UnicodeError as exc:
            raise GatewayStoreError("Migration sources must be UTF-8") from exc
        if not isinstance(ledger, dict):
            raise GatewayStoreError("Legacy reservation ledger must be an object")
        records = []
        for line_number, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            rec = _receipt(_decode(line), legacy=True)
            if not rec.get("request_id"):
                rec["request_id"] = f"legacy:{digests['audit']}:{line_number}"
            rec = _receipt(rec)
            records.append(rec)
        caps = {}
        def run_cap(run_id, data):
            max_tokens, max_cost = self._caps(data.get("max_tokens", MAX_TOKENS), data.get("max_cost", MAX_COST))
            if legacy_max_cost is not None:
                max_cost = min(max_cost, legacy_max_cost)
            prior = caps.get(run_id)
            caps[run_id] = (max_tokens, max_cost) if prior is None else (min(prior[0], max_tokens), min(prior[1], max_cost))
        for rec in records:
            if rec["gateway_decision"] == "AUTHORIZED":
                run_cap(rec["run_id"], rec)
        for run_id, pending in ledger.items():
            _text(run_id, "run_id")
            if not isinstance(pending, dict):
                raise GatewayStoreError("Invalid legacy reservation group")
            for info in pending.values():
                if not isinstance(info, dict):
                    raise GatewayStoreError("Invalid legacy reservation record")
                run_cap(run_id, info)
        for run_id, (max_tokens, max_cost) in caps.items():
            self._run(run_id, max_tokens, max_cost)
        count = 0
        for rec in records:
            if rec["gateway_decision"] == "AUTHORIZED":
                self._conn.execute("INSERT INTO requests VALUES (?,?,?,?,?,?, 'committed')",
                    (rec["request_id"], rec["run_id"], rec["estimated_tokens"], str(_cost(rec["estimated_cost_usd"])),
                     _json({"pid": 0, "birth": None}), _json(rec)))
            self._insert_receipt(rec)
            count += 1
        pending_count = 0
        for run_id, pending in ledger.items():
            _text(run_id, "run_id")
            if not isinstance(pending, dict):
                raise GatewayStoreError("Invalid legacy reservation group")
            for request_id, info in pending.items():
                _text(request_id, "request_id")
                if not isinstance(info, dict):
                    raise GatewayStoreError("Invalid legacy reservation record")
                tokens, cost = _tokens(info.get("tokens")), _cost(info.get("cost"))
                timestamp = info.get("timestamp")
                if (not isinstance(timestamp, (int, float)) or isinstance(timestamp, bool)
                        or not math.isfinite(timestamp)):
                    raise GatewayStoreError("Invalid legacy reservation timestamp")
                owner = _owner({key: info.get(key) for key in ("pid", "birth", "boot_id")})
                if _owner_status(owner) != "dead":
                    raise GatewayStoreError("Stop legacy writers: live or unknown pending owner cannot be imported")
                if self._conn.execute("SELECT 1 FROM receipts WHERE request_id=?", (request_id,)).fetchone():
                    raise GatewayStoreError("Ambiguous legacy pending/receipt identity")
                rec = {"request_id": request_id, "run_id": run_id, "receipt_id": "recovered_" + request_id,
                       "estimated_tokens": tokens, "estimated_cost_usd": str(cost),
                       "gateway_decision": "AUTHORIZED", "legacy_pending": True}
                self._conn.execute("INSERT INTO requests VALUES (?,?,?,?,?,?, 'reserved')",
                                   (request_id, run_id, tokens, str(cost), _json(owner), _json(rec)))
                pending_count += 1
        return {"imported_receipts": count, "imported_reservations": pending_count,
                "source_digests": digests, "already_imported": False,
                "legacy_max_cost": None if legacy_max_cost is None else str(legacy_max_cost)}

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()
