# M4 offline Jev adapter (2026-09-26)

Update: the separate opt-in persistent dispatch API is now implemented; see
[jev-dispatch.md](jev-dispatch.md). This page documents the offline primitives.
The remaining-work list below is the earlier adapter checkpoint, superseded by
that dispatch document and the current Roadmap.

Official schema checked: https://api.typesafe.ai/openapi.json (OpenAPI info version
0.2.0). `pa_cli.jev` implements a local request builder, typed response validation,
review routing, budget reservation simulation, and `dry_run`. No API key is loaded,
no HTTP transport exists, and M3 still accepts offline fixtures only.

## API contract

The payload has `model`, named `questions`, and a `state` containing only evidence
IDs and passage text. Local paths and author metadata are omitted. Names appearing
inside the passages or question text are not automatically removed. Payload
construction alone does not verify provenance or authorize upload.

- `noul`: wire probability is `noul`; normalized local probability is `p_yes`.
- `choice`: verify selected choice against the named distribution and validate
  the vendor confidence field independently.
- `score`: validate requested legend, level distribution and its expected value.
- Reject missing/extra question names, mismatched types, nonfinite probabilities,
  distributions outside sum tolerance (1e-4), score mismatch (1e-3), and invalid
  input/output token usage. Return the actual model name and schema version.

Local pilot bounds are deliberately narrower than the API: 1..20 questions,
2..20 choice/score levels, six passages, 16KB question envelope, and 32KB request
envelope. These are local limits, not documented vendor limits.

## Routing

`route_answer` consumes a validated normalized answer. Noul uses 0.90/0.10;
choice uses top probability >=0.90 and margin >=0.20; score uses probability mass
relative to an explicitly configured action boundary. Missing boundary routes to
human review. High confidence yields only `triage_suggestion`. Uncertain answers
yield `human_review`, or `gpt_review_pending` when separately authorized. The latter
is a queue designation, not a GPT call. High-stakes or conflicting evidence always
routes to a person. Thresholds are pilot settings, not calibrated guarantees.
Task-specific critical-score-level rules remain to be added before live routing.

## Budget semantics

Construct a `Price` with the exact requested model, decimal USD per million input
tokens, a timezone-aware checked_at, and an HTTPS source. `Budget` rejects missing,
future or older-than-seven-day price timestamps at creation, nonfinite/nonpositive
prices, and invalid caps. Model matching is enforced by `dry_run`.

Default per-object limits: 25 reservation slots, 100000 input tokens, USD 0.01.
Slots conservatively count requests rather than unique papers. Reserve the caller's
token estimate before evaluating the supplied response. Known actual input usage
replaces the estimate, including when the answer itself is invalid. An overrun
halts further reservations. Unknown usage remains reserved and cannot retry.
Output tokens are validated, but not priced under the checked API's current
output-free contract; changed pricing requires a new policy before live use.

This is an in-memory, single-process simulation, not a persistent cross-process
spend cap. A new Budget object starts a new simulation. Price is checked at object
creation, not continuously. No vendor tokenizer or preflight billing endpoint was
established, so caller estimates cannot guarantee paid cost. No paid dispatch is
implemented until persistence, fresh-price preflight and explicit authorization
are joined with M3. Do not reuse this class as a production account quota.

## Offline example

```python
from datetime import datetime, timezone
from pa_cli.jev import Budget, Price, dry_run

# Supply independently checked current price metadata; this is NOT a live price.
price = Price("jev-test", "1.00", datetime.now(timezone.utc), "https://typesafe.ai/")
budget = Budget(price)
questions = {"support": {"type": "noul", "instructions": "Does the passage support the claim?"}}
fixture = {"model": "jev-test", "answers": {"support": {"type": "noul", "noul": 0.95}},
           "usage": {"input_tokens": 100, "output_tokens": 5}}
# packet is an existing local M2 packet; fixture is synthetic, not an API response.
result = dry_run(packet, questions, "jev-test", fixture, budget=budget,
                 estimated_input_tokens=200, rubric_version="pilot-1")
```

`dry_run` is always synthetic and upload-disabled. It is not an M3 production
dispatch entry point and does not persist an audit record. `None` as the fixture
simulates an unknown result and holds the reservation. The request ID incorporates
schema version, full minimal request, packet hash and rubric version.

## Remaining M4 work

1. Persist reservations/results in a transactionally shared run ledger, including
   crash recovery and explicit retry linkage; keep unknown billing reserved.
2. Bind the exact minimized payload to refreshed provenance, artifact hash,
   manual privacy review, explicit backend/data/budget authorization, and model price.
3. Implement timeout-bounded, redirect-rejecting HTTP transport with redacted errors
   and no automatic retries; reconcile usage and preserve raw/returned model IDs.
4. Join typed answers to separate suggestions, task-specific escalation policy and
   consent-aware GPT queue. Add critical-score handling and CLI configuration.
5. Revalidate pricing/terms and run the authorized pilot only after M5 evaluation.

Thirteen offline tests cover contract errors, routing, model/price matching,
freshness, budget reservations, unknown outcomes and known-usage reconciliation:
`python -B test_output/test_jev_m4.py`.
