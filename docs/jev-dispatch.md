# M4 persistent dispatch API (2026-09-26)

`pa_cli.jev_dispatch` joins local evidence validation, fresh provenance, explicit
approval, persistent reservations and an opt-in HTTPS transport. Importing it does
not send requests. This change was verified only with injected offline responses;
no real key, paper passage or paid request was sent during implementation.

## Trusted caller contract

Call `prepare_request(packet, questions, price.model)` to obtain the exact minimal
payload for user review. After the user approves that payload, data upload, the
configured estimated caps and estimate-overrun risk, the application may construct:

```python
from pa_cli.jev_dispatch import Approval, dispatch
from pa_cli.evidence import _hash
# expires_at: timezone-aware time no more than 15 minutes in the future.
approval = Approval(run_id, _hash(reviewed_request), True, True, expires_at,
                    max_papers=25, max_input_tokens=100000, max_cost_usd="0.01")
```

Supply the matching `approval`, `run_id`, dedicated `db_path`, explicit `api_key`,
`pdf`, M2 `index` and `packet`, `questions`, original `fetch_result`, `price`, positive
`estimated_input_tokens`, and `rubric_version` to `dispatch`. Also explicitly set
`data_class="public"` only for confirmed public material. Defaults remain unknown.
Pass `expected_title` when title matching is required. Caps must match approval.
The approval object is a trusted application's record of user consent, not a
cryptographic credential; arbitrary Python callers are outside its trust boundary.

Omitting `transport` selects the real fixed HTTPS endpoint. Supplying a callable
`transport(payload, api_key, timeout)` selects an offline testing boundary and marks
results synthetic. That callable is trusted Python, not a sandbox. Never put keys
in source files, fixtures, command lines, or stored approval objects.

## Before sending

The API validates index/packet integrity and exact spans, current PDF hash, original
source context, identity, license and public classification. Blank-page extraction
gaps, insufficient evidence, unpublished/private data, high-stakes work and known
evidence conflicts cannot pass. User approval binds the exact request hash, run,
caps and short expiry. Approval expiry and price freshness are checked again after reservation, immediately
before transport; expiration settles zero known usage without sending. Price must match the requested
model. Existing schema/packet size bounds apply. Text names are not automatically
redacted: the user's reviewed payload is the privacy boundary.

## Durable per-run accounting

- A dedicated SQLite application ID protects unrelated existing databases. This
  DB is separate from M3's synthetic suggestions and the human sample pool.
- The transaction stores request snapshot, approval evidence, routing policy,
  provenance and reserved tokens before invoking transport. API keys are never
  persisted. Snapshots contain local research text and need local access controls.
- Run caps, model, price metadata and test/live mode are immutable for a run ID.
  A reopened connection cannot reset its caps. `BEGIN IMMEDIATE` serializes claims.
- Identical requests reuse durable outcomes. A pending/interrupted request returns
  unknown without resending; new requests in a run with unresolved reservations
  are refused. Run IDs are user-defined run boundaries, not an account-wide quota.
- Unknown transport/billing retains the reservation and halts that run. No automatic
  retry/refund exists. `pa jev reconcile` can record independently verified final
  usage for unknown, quarantined/interrupted and late-result review outcomes while
  keeping the run halted; see [jev-cli.md](jev-cli.md). `pa jev quarantine` retains
  pending reservations and records suspected interruption without claiming worker
  cancellation. Late outcomes remain auditable and require human review. Explicit
  `pa jev resume` requires settled outcomes, worker/final-usage attestations, fresh
  price and remaining budget; it clears the halt without resetting counters.
- Known usage reconciles the reservation even if an answer is invalid. Usage above
  the reservation halts the run, records `budget_overrun`, and forces human review.
- Event history is append-only by triggers; request status and usage are mutable
  projections. Database owners can bypass triggers: this is not tamper-proof storage.

Limits apply to estimated reservations. They cannot guarantee the final provider
invoice: tokenizer/preflight guarantees are unavailable. The caller must explicitly
accept that an actual request may exceed its estimate before further requests stop.
Wrong returned model yields `model_price_unverified` and halts the run; its cost
field is only an estimate at the requested model's rate, not confirmed billing.
Use a concrete priced model; alias remapping intentionally fails closed.

## Explicit linked retries

Pass the same optional `retry_of` parent request ID to `Approval` and `dispatch`.
An original approval cannot authorize a retry. Eligible parents are failed outcomes
`invalid_response`, `usage_reconciled` or `preflight_expired` in the same run with
unchanged payload, packet, rubric and routing. New children consume the same caps;
parent usage is retained. An immutable unique parent-child link and deterministic
child ID prevent duplicate concurrent retries. Repeats return the child record.
A further attempt must explicitly name a failed child and obtain fresh approval.
Recovery functions never send requests. See [CLI workflow](jev-cli.md).

## Transport and result policy

The only live target is `https://api.typesafe.ai/v1/systemone`. The standard-library
HTTPS client uses certificate verification, rejects redirects, disables ambient
proxies, has no retry loop, and limits response reads to 1 MiB. An isolated spawned
worker bounds the network phase to the configured timeout (default 30s, maximum
120s), plus process startup/cleanup overhead. This timeout does not cover local
PDF extraction. Every non-success/timeout is conservatively billing-unknown.
Errors retain exception class only, not response text, keys, or passage content.

Typed responses use `pa_cli.jev` validation and pilot thresholds. Optional
`score_boundaries` defines per-question action cutoffs. Any nonzero probability at
an explicitly configured `critical_score_levels` entry forces human review.
`fallback_authorized=True` permits an uncertain result to be labeled
`gpt_review_pending`; no GPT network call is implemented. Without separate approval
it goes to human review. Neither route approves manuscript claims or excludes papers.
Routing policy is part of the request identity; changing it creates a new logical
request, so consider costs before rerunning. Thresholds still need M5 calibration.

## Remaining work

M4 is still partial at product level. Local preview/status CLI is available (see
[jev-cli.md](jev-cli.md)), including interruption quarantine, late-result handling
and final-usage reconciliation.
The CLI now supports local job preflight and explicit interactive dispatch approval;
its pilot approval attestation is recorded in the request snapshot. A final local
send gate checks quarantine before transport; approval/price expiry is checked
after that gate. `dispatch_started` records send intent, not confirmed delivery.
Cross-provider GPT execution and live site
validation remain open. M5 still needs
explicit human entry, blinded holdout collection and measured calibration. A paid
pilot requires separate authorization; offline tests do not establish model quality.

Run `python -B test_output/test_jev_dispatch.py`: 19 offline scenarios cover
reservations/restarts, concurrent deduplication, consent, private/stale artifacts,
overruns, response validation, price/model mismatch, transport behavior, routing,
quarantine races and expiry during the final send gate. Eleven more interruption
checks in `test_jev_interrupted.py` cover late outcomes, accounting and atomic audit.
