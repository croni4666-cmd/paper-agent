# Local Jev commands

## Coordinate local evaluation

`review-resolve` now records an independent human resolution of disagreement,
bound to the current reviewer submissions. It requires schema v3 and two explicit
human/no-model-exposure attestations; see the operations guide. Version 2 keeps
its prior operations but does not support this new command without migration.

`evaluation-freeze`, `review-assign`, `review-expose` and `evaluation-status` now
provide local study-group split freezing, explicit assignments and exposure history.
See [evaluation operations](jev-evaluation-operations.md) for the input plan and
required attestations. These use a separate evaluation database, write no human
labels and make no network calls. Five offline M5 regression tests now pass.

`review-submit` now accepts explicitly confirmed human labels, abstentions and
linked corrections; `judgments-freeze` freezes complete consistent judgments.
These operations require schema v2 and do write human records to the dedicated
evaluation ledger, never to `pa judge`. See the operations guide for exact entry
fields, disagreement handling and post-freeze exposure limitations. The M5 suite
uses synthetic cases and labels only; it does not establish scientific quality.

## Export local review materials

`pa jev review-export --shadow-db shadow.sqlite --request-id REQUEST_ID --out review-bundle`

This reads an existing M3 ledger in read-only mode. `--out` must be a new directory
with an existing parent. It publishes `review.json` and `coordinator.json` together
through same-parent staging. Share only `review.json`; keep the coordinator file
private. The reviewer sees rubric, passages, page/evidence IDs and completeness
notices. Suggestions and provider metadata are not queried. No label is written.

Hashes do not revalidate the original PDF. Passage text may identify a study.
Export does not establish independent blinding or create a study split. Repeated
exports have different assignment IDs, not additional study cases. Files inherit
local access controls and are not encrypted. A crash can leave `.review-export-*`
staging or an `.export-lock` file; inspect these and confirm no exporter is active
before manual cleanup. Never distribute staging files.

Current verification: 5 M5 tests plus 83 M4 tests passed (88 total, 2026-09-27).
See [M5 design](jev-evaluation-m5.md).

Preview, status, quarantine, reconciliation, resumption and default dispatch preflight work without a Jev
account. Only `dispatch --send` can call the provider, after terminal approval.
Run from the development checkout with
`python -m pa_cli jev ...` if the installed `pa` entry point uses another checkout.

## Preview a request

```text
pa jev preview --packet packet.json --questions questions.json --model jev-test
```

Use a packet built locally by `pa_cli.evidence.build_packet`, plus a JSON object
of named questions accepted by `pa_cli.jev.prepare_request`. `jev-test` here is an
offline example identifier, not a verified provider model. For example:

```json
{"support": {"type": "noul", "instructions": "Does the passage explicitly report increased employment?"}}
```

Output contains the minimized `request`, its `request_hash`, schema version and
explicit false upload/network flags. The hash uses the same algorithm as the
dispatch approval API. Local PDF paths and other packet metadata are omitted.
Question text and selected passage text ARE printed for inspection: redirect only
to an appropriate local file if you need to save them.

Preview checks bounded JSON objects, packet integrity and the request schema.
It does not validate the actual PDF, provenance, source rights, extraction gaps,
current model availability, price, consent or eligibility to upload. An attacker
can recompute a packet hash; preview is not a trust or authorization boundary.
The dispatch API repeats its own PDF/provenance/consent checks. No preview can
approve a manuscript claim or exclude a paper.

## Inspect an existing dispatch run

```text
pa jev status --db dispatch.sqlite --run-id run-1
```

The database must be an existing M4 dispatch ledger. This does not accept the M3
shadow ledger or the human sample pool. It opens SQLite read-only, checks the
application identifier and reads the run and counters in one transaction. Output
includes caps, mode, halted flag, unresolved flag and counts/tokens by status.
It omits stored payloads, answers and approval snapshots. Missing databases/runs
fail without creating a database. It does not reset caps, release reservations or
retry requests.

`accounted_input_tokens` mixes retained estimates for unresolved requests with
known usage for settled requests; it is not invoiced usage. Pending requests can
block dispatch even when `halted` is false, so inspect `has_unresolved_requests`.
The existing `max_papers` limit conservatively counts requests, not unique papers.
Provider price/model mismatches and unknown billing still require operator review.

Add `--requests` to include request IDs, status and accounted input tokens for
each request in that run. Payloads, answers and approval snapshots stay omitted.

## Quarantine suspected interrupted work

```text
pa jev quarantine --db dispatch.sqlite --run-id run-1 --request-id REQUEST_ID --operator operator-1 --evidence-reference incident-1 --confirm-interrupted
```

Use this for a pending request that needs operator investigation after a suspected
interruption. It atomically changes `pending` to `interrupted`, halts the run and
appends the operator/incident reference. The token reservation stays intact.
It does not stop a worker or cancel an HTTP request already underway, and it does
not prove that billing is zero. Completed or already quarantined requests are
refused. A final local send gate prevents dispatch if quarantine has already
committed before that gate; quarantine after it can still race with the HTTP call.

Late outcomes become `late_result_review`, retain their reported usage and route
all answers to human review. Runs stay halted. If final usage was already manually
reconciled after quarantine, the late outcome preserves that operator evidence in
the append-only event and result. It retains the larger of the recorded usage and
new reported usage; unknown late usage restores at least the original reservation.
Another explicit final-usage reconciliation is required to resolve the discrepancy.

```text
pending --operator quarantine--> interrupted --late outcome--> late_result_review
unknown / interrupted / late_result_review --verified usage--> usage_reconciled
usage_reconciled (from interrupted) --late outcome--> late_result_review
```

Quarantine and reconciliation keep the run halted; only explicit resume clears it. An audit-write
failure rolls back the accounting transition. No recovery operation resends a
request, resets caps or automatically resumes a run.

## Reconcile an unresolved review outcome

After independently verifying final input usage and model for the exact request:

```text
pa jev reconcile --db dispatch.sqlite --run-id run-1 --request-id REQUEST_ID --actual-input-tokens 80 --confirmed-model jev-test --operator operator-1 --evidence-reference receipt-1 --confirm-final-usage
```

The values above are examples, not a receipt. Use the provider's verified usage
or a confirmed support resolution; a timeout does not establish zero usage. The
confirmation flag records your attestation, not automatic invoice verification.
Use a local receipt/support reference ID, without secrets or manuscript text.

`unknown`, `interrupted` and `late_result_review` requests qualify. The model must
match the run's priced model. Direct reconciliation of unquarantined `pending`
requests is refused. Completed, overrun and already-reconciled outcomes are also
refused. A timeout or operator quarantine alone does not establish final usage.

One transaction changes the request to `usage_reconciled`, replaces its retained
token estimate with operator-confirmed final usage and appends an audit event
containing the old estimate, new usage, operator and evidence reference. Previous
events remain intact. Failure to write the event rolls back all changes; concurrent
reconciliation permits only one winner. The run remains halted, including when
usage is zero or exceeds its cap. Reconciliation itself never resends or resumes.
Repeated dispatch of the same request returns the reconciled record without
resending. This establishes accounting only, not an answer or scientific judgment.

Run `python -B test_output/test_jev_recovery.py` for eight offline recovery checks.

## Resume a reviewed run and request a linked retry

```text
pa jev resume --db dispatch.sqlite --run-id run-1 --operator operator-1 --evidence-reference review-1 --confirm-workers-stopped --confirm-final-usage
```

Resume requires a halted run, settled outcomes, fresh stored price metadata and
remaining request/token/cost capacity. Both confirmations are operator attestations,
not automatic verification of worker termination or provider billing. Pending,
unknown, interrupted, late-review, model-mismatch and overrun states block resume.
The transaction appends an audit event and clears only the halted flag. It sends
nothing and preserves all usage, immutable limits and historical requests. Stale
price metadata cannot be silently refreshed within the existing run. A late worker
result can still halt a resumed run and require another accounting review.

For an explicit retry, add `"retry_of": "PARENT_REQUEST_ID"` to the job and follow
the normal preflight and interactive SEND approval below. The approval binds this
parent ID as well as the payload and caps. Only `invalid_response`,
`usage_reconciled` or `preflight_expired` parents qualify; completed answers do not.
Parent and child must share a run, payload, evidence packet, rubric and routing
policy. Parent eligibility is checked transactionally at dispatch, not by the
ledger-free job preview. Resume is needed only when the run is halted.

Each parent has one immutable, deterministic child link. Repeating the same retry
returns its recorded outcome without sending again; a further attempt must name
the failed child. A new retry may incur another provider charge. All attempts count
against the original run caps, including the request-count limit. `status
--requests` includes `retry_of` without exposing payloads. No automatic retry loop
is provided.

## Preflight and approve a complete dispatch job

```text
pa jev dispatch --job job.json --db dispatch.sqlite
```

Default mode validates the PDF, packet/index, source/identity/license metadata,
public classification, complete extraction, routing and fresh price/budget inputs.
It prints the exact minimized request, hash, destination and caps without reading
the Jev key or creating a ledger. Budget preflight checks this request in isolation;
the persistent ledger performs final run-cap and deduplication checks at dispatch.
The existing root CLI may load its normal local environment configuration.

Job format (replace every placeholder before use):

```json
{
  "pdf": "paper.pdf",
  "index": "index.json",
  "packet": "packet.json",
  "questions": "questions.json",
  "fetch_result": "fetch-result.json",
  "price": {
    "model": "REPLACE_WITH_VERIFIED_MODEL",
    "usd_per_million_input": "REPLACE_WITH_VERIFIED_PRICE",
    "checked_at": "REPLACE_WITH_TIMEZONE_AWARE_VERIFICATION_TIME",
    "source_url": "https://typesafe.ai/"
  },
  "run_id": "public-oa-pilot-1",
  "rubric_version": "REPLACE_WITH_YOUR_RUBRIC_VERSION",
  "estimated_input_tokens": 1000,
  "data_class": "public",
  "high_stakes": false,
  "conflicting_evidence": false,
  "max_papers": 25,
  "max_input_tokens": 100000,
  "max_cost_usd": "0.01"
}
```

Input paths resolve relative to the job file. The database path resolves relative
to the command's working directory and must not identify any input artifact.
Use existing M2 index/packet files and the original Fetch result, not hand-written
provenance. `checked_at` is an ISO timestamp with timezone no older than seven days.
It is the operator's verification record; this CLI does not fetch or verify prices.
Estimates and caps must be chosen for the actual workload; the example token
estimate is not a token count. Unknown fields, embedded keys and custom transports
are rejected. Optional fields: `expected_title`, `timeout` (0 < seconds <= 120),
`score_boundaries`, `critical_score_levels` and `retry_of` (a parent request ID).

Only after the required M5 human evaluation and pilot approval, use:

```text
pa jev dispatch --job job.json --db dispatch.sqlite --send --pilot-approved
```

Set `TYPESAFE_API_KEY` through the local environment; do not put it in command
arguments or job JSON. A visible interactive terminal is required. The command
shows the exact payload, price metadata, estimate and caps; type `SEND` only after
reviewing them. Any other answer cancels. Approval binds the reviewed payload hash
and caps, expires after five minutes, and the API rechecks the PDF/provenance and
price before dispatch. JSON is escaped for terminal-safe display. The approved
job snapshot is held in memory; the job files are not reread after confirmation.

`--pilot-approved` is an operator attestation recorded in the local snapshot,
not automatic verification of M5 results. It must not be used to skip evaluation.
No unattended `--yes` path, GPT upload, automatic retry or endpoint override is
provided. Unknown/noncompleted outcomes return a nonzero exit code with the local
recorded status; inspect accounting before further action. Estimates cannot cap
the provider's final invoice. Waitlist membership does not establish API access.

## Remaining work

M4 remains partial: GPT
provider execution and live validation remain open. M5 requires human adjudications
and a frozen holdout. The CLI does not remove those gates. See
[dispatch contract](jev-dispatch.md) and the canonical Roadmap.

Offline checks: `python -B test_output/test_jev_cli.py`.

Current verification (2026-09-27): 13 retry/resume, 11 interruption, 12 approval-CLI,
19 dispatch, 8 recovery, 7 local CLI and 13 adapter checks passed (83 total). PyMuPDF 1.28.2 was
installed into a fresh isolated test directory after the previous temporary
directory became unreadable to this session. No live provider
was called. The approval tests use actual PDF/provenance/ledger code with injected
synthetic transport; they do not establish model quality or real account access.
