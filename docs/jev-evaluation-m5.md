# M5 local blinded evaluation — design for review

Status: export, frozen cases/splits, assignment/exposure, human entry/corrections, independent resolution and judgment freeze implemented; 10 offline M5 regressions pass. Scoring and explicit schema migration remain proposed. Reviewed against `pa_cli/shadow.py` and the
M4 dispatch/recovery interfaces on 2026-09-27. No labels or metrics are claimed.

## Purpose and implementation boundary

Collect independent human judgments over frozen Fetch evidence before selecting
Jev routing thresholds. Account waitlisting does not block local preparation.
The first increment is a read-only blind-packet export from the existing M3
ledger. Human entry, split freezing and evaluation follow separately. GPT execution
remains an independent M4 task with separate upload and spending authorization.

Alternatives considered:

- Export the complete shadow record: simple, but leaks synthetic answers and
  provider identity into review. Rejected.
- Build the entire labeling application now: supports reviewer sessions but adds
  assignment, correction and reporting state before an export contract is stable.
  Deferred.
- Export an explicit allowlist of evidence and rubric fields: chosen first step;
  useful locally and small enough to inspect before adding human-entry storage.

## First increment: read-only blind-packet export

Implemented interface (`--out` is a new directory with an existing parent):

```text
pa jev review-export --shadow-db shadow.sqlite --request-id REQUEST_ID --out review-bundle
```

Read an existing M3 ledger in SQLite read-only mode, validate its application ID,
and take one consistent snapshot. Do not open it with `_connect`, which creates
schema. Reject missing databases/requests, malformed or oversized JSON, invalid
rubrics, packet-hash mismatches and empty evidence. Refuse to overwrite an existing
output or any input database. Write an atomic new output only after validation.
No API key or provider connection is involved.

Export only:

- export schema version and a new random opaque review ID;
- task, rubric version, question and ordered allowed labels;
- passage text, page and evidence ID from an explicit field allowlist;
- evidence completeness notices required to avoid misleading the reviewer.

A separate local coordinator manifest maps the review ID to artifact, packet,
rubric hashes and the source request ID. It is not part of the reviewer artifact.
The manifest must be created together with the reviewer artifact: a failure leaves
no usable half-export. Neither file may overwrite an existing artifact. Repeated
exports produce distinct assignments; they do not create additional study cases.

Exclude suggestions, probabilities, provider/model identity, routing decisions,
request status, source URLs, local paths, cost, prior labels and split assignment.
Recompute integrity hashes but do not describe this as PDF revalidation: M3 stores
packets, not the complete index or current PDF. Evidence IDs/pages are locators,
not independent proof of authenticity. Passage text can itself reveal authors or
study identity; this is model-answer masking, not guaranteed anonymous review.

The first increment records no human label and does not set `blinded=1`. Export
cannot establish that a reviewer has never seen a prediction elsewhere. Reviewers
must be told which additional context is available and how to request it. A request
for new evidence produces a new packet and review assignment; never alter frozen
passages underneath an existing judgment.

## Later increments: assignment, judgment and correction

The first coordination increment now has a [local command workflow](jev-evaluation-operations.md).
Freeze binds bundles back to M3 source content; assignment requires no-exposure
attestation and known exposure disqualifies the entire study within the ledger.
Human judgments, linked corrections and consistent-judgment freezing are now
implemented in `jev_judgments`. Schema v3 adds independent human resolution in
`jev_adjudication`, bound to all current judgments with original reviews preserved.
Cross-ledger exposure inheritance remains unimplemented. Schema v2 binds allowed labels and
evidence IDs into frozen cases; v1 ledgers require an explicit future migration.

Use a dedicated evaluation ledger with an explicit schema/application ID. Preserve
M3's existing append-only `adjudications` table; it is a schema placeholder without
assignment, exposure or correction tracking and is not sufficient alone.

Before assignment, freeze eligible study groups, rubric/label definitions and
split membership (development, calibration, holdout). Group versions, duplicates
and packets of the same study together using a curated study ID; a file hash alone
cannot prevent leakage across alternate PDFs. Unknown study grouping is a review
issue that blocks holdout freeze. Preserve the grouping decision and source.

A judgment binds review ID, frozen case/rubric hashes, reviewer, allowed label,
evidence references and timestamp. Require explicit human submission; reject model
outputs as truth. Insufficient context and abstention must be representable without
forcing a binary answer. Record disagreements and reviewer resolutions separately;
never replace original judgments. Corrections append a superseding record.

Track assignment and model-answer exposure. A holdout requires an unexposed
assignment plus reviewer attestation of no prior external exposure. Attestation is
not technical proof. Once exposed, retain the record but exclude it from the blind
holdout; do not restore eligibility by re-exporting or changing reviewer aliases.
Freeze adjudications before revealing predictions. No automatic write to `pa judge`,
existing labels, screening exclusions, citations or manuscript claims.

## Later increment: measured evaluation

Join predictions to frozen cases by artifact/packet/rubric hashes and explicit
question/label mapping. The M3 synthetic fixtures and M4 choice/noul/score responses
have different schemas; no implicit conversion is permitted. Reject synthetic
predictions from real-quality reports. A fixture-only report must say so prominently.

Tune thresholds on calibration data only. Predeclare task-specific error tolerance,
coverage target, confidence level and treatment of abstentions before holdout use.
Report per-task counts, missing/failed calls, coverage, precision/recall, false
negatives and calibration with confidence intervals. Use study-level resampling or
another prespecified method that respects clustered packets. Do not pick numerical
acceptance thresholds or claim adequate sample size before the risk target is set.
Freeze thresholds before holdout scoring. Changing the rubric or evidence policy
requires a new evaluation version and an uncontaminated holdout.

## Acceptance criteria and order

1. Blind export: allowlist only, immutable source, coordinator/reviewer separation,
   atomic output, bounded inputs and no network or human-label writes.
2. Assignment ledger: frozen study-group splits, exposure tracking and audit history.
3. Explicit human entry: rubric validation, abstention, disagreements and corrections.
4. Freeze/score: versioned joins, synthetic exclusion and calibrated reporting.
5. Independently authorized public-OA pilot after human review of measured results.

Future verification should cover leaked fields, tampered packets, foreign SQLite
files, output collisions, partial-write cleanup, split leakage, exposed holdout
rejection and synthetic-report rejection. Five M5 regressions now cover the main
CLI flow, corrections, disagreement, exposure and nine malformed-input variants.
These pass alongside all 83 M4 checks; broader verification remains useful and
synthetic cases are not real evaluation truth or quality evidence.
