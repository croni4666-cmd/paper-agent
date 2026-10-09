# v4 local gateway journal: operating and migration guide [P3-40]

## Scope

The gateway validates a request offline. It does not call a provider, charge an
account, or claim that a literature review is scientifically accurate. Estimated
usage and unresolved reservations share one local SQLite transaction journal.
No new runtime dependencies or hosted services are required.

Real-corpus collection, human labels and corpus-dependent evaluation are
indefinitely suspended by the operator as of 2026-10-09. Generated fixtures test
software consistency only. Existing consent, paper rights, snapshot provenance,
sanitization, 25-paper, 100000-token and $0.01/run hard ceilings still apply.

## Changed storage contract

v4 CLI and `evaluate_gateway_request` default to the transactional backend.
`audit_file` is now a **legacy locator**, not an automatically appended JSONL
destination. Its default is `~/.paper-agent/gateway_audit.jsonl`; the canonical
sibling is `~/.paper-agent/.gateway_audit.jsonl.gateway.sqlite3`. Supply `--ledger`
or Python `ledger_file=Path(...)` to choose a local journal. Keep the same journal
and `run_id` throughout one budget run. A run's first accepted reservation freezes
its limits; repeat a tighter `--max-cost` on subsequent calls in that run.

Paper count is cumulative across reserved and committed requests in a run;
repeating the same papers still consumes submitted-candidate quota. Unknown
legacy counts are flagged and block additional reservations rather than guessed
as zero. Aborting an unknown pending request releases its hold; committing
unknown historical usage conservatively keeps the run closed.

Each evaluation gets a unique `request_id`, including rejected evaluations.
`receipt_id` retains its older human-readable form and is not a uniqueness key.
The lower-level `GatewayStore.finalize` supports exact repeated finalization.
Calling the evaluator again is a new request and consumes additional estimated
usage if authorized; it is not an idempotent retry of a prior request.

Do not alternate independent journal paths/backends within a budget run. The
explicit deprecated Python `storage_backend="legacy-json"` adapter is for
unmigrated v3 compatibility. It refuses a known transactional epoch. Historical
JSONL write helpers remain legacy-only and never update canonical v4 accounting.
No legacy state is silently ignored, repaired, cleared or automatically imported.

## Normal local workflow

```console
pa gateway verify --file paper.xml --doi 10.1000/example --source pmc_xml \
  --url https://eutils.ncbi.nlm.nih.gov --text "Evidence from this artifact" \
  --operator local-user --run-id study-2026-10 --max-cost 0.005 \
  --consent-public-oa --consent-zero-retention --verify-provenance \
  --ledger ./gateway.sqlite3 --json
pa gateway status --ledger ./gateway.sqlite3 --json
pa gateway doctor --ledger ./gateway.sqlite3 --json
pa gateway audit --ledger ./gateway.sqlite3 --limit 20 --json
pa gateway export --ledger ./gateway.sqlite3 --output ./receipts.jsonl
```

The artifact must itself satisfy rights/identity checks; the example DOI is a
placeholder, not an attested paper. Backslashes above are shell continuation
markers; on PowerShell put the command on one line or use its continuation syntax.
`status`, `doctor` and `audit` open an existing journal read-only and do not
initialize a missing file. They never load unrelated API keys. `doctor` checks
schema, SQLite integrity, references, receipts and accounting; it does not repair.
`audit --json` returns a JSON array. `export` writes JSONL atomically and does not
change usage. Its output cannot overwrite the journal or SQLite auxiliary files.
Keep exports separate from preserved migration sources.

## Migrating an existing v3 ledger

1. Stop **every** v3/v4 writer using the old accounting domain. Mixed-version
   concurrent writers are unsupported. Keep backup copies of the original JSONL
   and reservation sidecar; do not edit them to make an import pass.
2. Reconcile the effective historical cost ceiling. v3 did not persist a custom
   tighter ceiling, so v4 cannot infer it. Choose the tightest applicable ceiling
   for imported runs; separate unrelated domains if they had different limits.
3. Import into a dedicated target. All valid receipts and dead owners' unresolved
   reservations are imported in one transaction. Live or unknown pending owners,
   malformed records, ambiguous identities and usage above the reconciled cap
   reject the import. The pending amount stays held until explicitly recovered.

```console
pa gateway migrate --audit-file ./gateway_audit.jsonl \
  --ledger ./.gateway_audit.jsonl.gateway.sqlite3 \
  --operator local-user --legacy-max-cost 0.005 --confirm-stopped
```

The default sidecar is `.gateway_audit.jsonl.reservations.json` beside the source;
`--reservation-file` may identify another preserved sidecar. Sources are read,
hashed and checked again, never rewritten. Source/target paths must be distinct.
An absent audit with an existing valid sidecar is a supported pre-first-receipt
crash state. Its absence is preserved in the manifest; do not manufacture an
empty audit file. Both sources missing or an unreadable existing file reject.
Actual custom source paths are stored with digests and used for later checks.
Identical repeated import is idempotent; changed sources, locations or reconciliation caps
conflict rather than being merged. A failed import may leave an empty initialized
target, but evaluation with legacy data still requires a completed matching import.
Foreign, altered, corrupt or future-schema databases are never reinitialized.

For Python evaluation after migrating this example, continue passing
`audit_file=Path('./gateway_audit.jsonl')` and the matching `ledger_file`, or use
the corresponding default home paths. The CLI `--ledger` selects a canonical
accounting domain; preserved home legacy state is still checked by the default
locator. Source digest checks use stored custom paths and refuse subsequent edits
by late v3 writers. Keep
the sources unchanged and all legacy writers stopped.

## Unknown outcomes and explicit recovery

A failed finalization returns REJECTED and keeps its reservation accounted.
Process existence or age alone never clears a pending v4 reservation. Owners
include a PID and creation token (boot identity on Linux), distinguishing PID
reuse. Unsupported/inaccessible process queries remain **unknown**. A long-lived
or inaccessible owner continues to hold quota. No process is signaled or killed.

Use `status` to identify the pending `request_id`. If the original owner is
confirmed dead **and no external operation consumed the reservation**, explicitly
abort it with an accountable explanation:

```console
pa gateway recover --ledger ./gateway.sqlite3 --request-id req_... \
  --resolution abort --operator local-user \
  --evidence "Original process exited; operation never executed"
```

If usage is known completed, `--resolution commit` retains the original reserved
amount and records the explanation, even if owner liveness is unknown. This is
accounting reconciliation, not permission to execute a new external request.
Live/unknown owners cannot be aborted; committed or already recovered rows cannot
be rewritten. Recovery never raises/resets ceilings. Both resolutions leave an
append-only recovery event. Legacy recovered receipts lacking content metadata
remain unverified rather than acquiring invented provenance attestations.

## Durability boundaries and rollback

Use a local filesystem supported by SQLite locking and durability semantics,
not a shared/network filesystem with uncertain locking. Synchronous FULL and a
single transaction domain handle normal concurrent access and injected write
failures. They are not a guarantee against failing hardware or every power-loss
environment. A malicious local administrator who can rewrite the entire database
is outside the append-only application contract; hashes are integrity bindings,
not signatures or independent notarization.

Before downgrading, stop all writers and retain the v4 database plus preserved v3
sources. Running an older binary against only its pre-migration JSONL would omit
v4 usage. JSONL export is a review artifact, not a supported automatic reverse
migration; do not reset a run or switch backend to make exhausted quota disappear.
Keep v3.10.0.30 installed separately for unmigrated workflows if needed.

The isolated offline quality gate is `python tools/consistency_quality_gate.py`.
It covers generated evidence, Windows/Linux process queries, real multiprocess
contention, failed commits, migration/recovery, source preservation and legacy
IO compatibility, with repeated stress checks. Release requires Ubuntu/Windows,
Python 3.10–3.12 and clean wheel-install CI. None of these checks substitute for
the suspended scientific/data evaluation.
