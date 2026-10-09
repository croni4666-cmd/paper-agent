# v4: local reliability and recoverable gateway state

## Intent

The user has no time for real-corpus validation and explicitly suspends it long
term. Deliver engineering reliability independently of that work: no fabricated
labels, no reopened data gates, no claim of improved scientific accuracy. Preserve
the personal-hobbyist local-first maintenance and zero-paid-call constraints.

## Architecture and major-version contract

Introduce a canonical stdlib SQLite gateway journal that keeps estimated spend,
in-flight ownership, receipt history and recovery events in one transaction domain.
The v4 CLI uses it by default. Retain an explicit deprecated v3 JSON backend as a
compatibility adapter; do not run both backend epochs against the same budget.
Existing eligibility/provenance/sanitization functions and token limits remain.

The database has a dedicated application_id/schema version, integrity validation,
immutable run limits and append-only receipt/recovery events. Every operation uses
BEGIN IMMEDIATE, foreign keys and synchronous=FULL on a local filesystem. This is
a single-machine transactional durability contract, not a hosted SLA or universal
filesystem/power-loss guarantee. Unsupported schema/foreign/corrupt stores reject
mutations without reinitialization.

State transitions: reserved -> committed or aborted. A committed authorization
and removal of its pending reservation occur atomically with its audit receipt,
so spend is counted once. Failure before transaction commit leaves the reservation
accounted and cannot return AUTHORIZED. Repeated finalization is idempotent only
for the same request and exact receipt. Different receipts cannot overwrite history.

## Process identity

New reservations record pid and process creation token, plus machine boot identity
where available. Windows uses typed native process APIs; Linux uses proc start ticks
and boot id. Unavailable metadata/liveness is unknown and retains quota. A reused PID
with a different token establishes that the original owner has exited. Queries and
recovery must not signal, kill or modify any process.

## Operator surface

- gateway status/doctor: read-only budget totals, pending IDs/owner states, schema
  and integrity diagnostics; no full passage or credential payloads.
- gateway migrate: explicit confirmed import from v3 JSONL/sidecar to a dedicated
  database, with source digests, one atomic import and unchanged source bytes.
  Reject malformed records and any live/unknown pending ownership. All legacy
  writers must be stopped before migration; mixed v3/v4 concurrent writers are
  unsupported and must be stated clearly.
- gateway recover: explicit request ID, operator, evidence reference and confirmed
  resolution. Abort only a confirmed dead reserved owner; committing known usage
  retains already reserved amounts. Live/unknown owners cannot be released.
  Run limits never reset. Recovery emits an immutable event.
- gateway export: produce JSONL from canonical receipts, atomically to an operator
  selected file. Export failure does not change budget state.

## Interfaces

process_identity.py: process_alive(pid)->bool|None; process_birth(pid)->str|None;
current_owner()->dict with pid/birth; owner_status(owner)->alive/dead/unknown.

gateway_store.py: GatewayStore(path), totals(run_id), reserve(request_id, run_id,
tokens, cost, max_tokens, max_cost, owner, receipt), finalize(request_id, receipt),
status(run_id=None), recover(request_id, resolution, operator, evidence),
receipts(limit=None), migrate(audit_path, reservation_path, operator, max_cost=None), close().
Migration manifests preserve actual source paths and absence; the CLI requires
an explicitly reconciled historical cap. Unknown legacy paper counts block new
reservations, while known counts enforce25 papers cumulatively per run.

gateway.py: shared content validation, an explicit storage backend selector and a
transactional evaluation path. Preserve existing fields and add a unique request
identifier for durable/idempotent receipt binding. Public function kwargs are
additive; CLI's default storage contract changes and requires explicit migration
where legacy state already exists.

## Verification and release gate

Tests use generated documents and isolated stores. Required: exact-once accounting,
real multi-process contention, process death/reuse/unknown, failed commits, corrupt
or foreign schema, migration rollback/source preservation, refused unsafe recovery,
CLI behavior and continued v3 contract coverage. Add independent review and full
offline regressions; Ubuntu/Windows gates, Python 3.10–3.12 and clean wheel install
must pass before v4.0.0 publication. No real-corpus result is claimed by this gate.
