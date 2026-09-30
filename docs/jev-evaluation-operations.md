# Local evaluation coordination (M5)

Implementation status: export, frozen case grouping/splits, assignment, exposure,
human submission/correction, independent resolution and judgment freeze are present. Ten offline M5 tests now pass. No real labels,
holdout results or model-quality measurements have been produced.

## 1. Prepare and freeze a plan

Verification (2026-09-27): Luna independently reproduced an import-validation gap;
export and freeze now share passage/completeness validation. The M5 regression
suite covers the CLI flow, corrections, disagreement, exposure after freeze, and
nine independent malformed-input variants. All 5 M5 and 83 M4 tests passed after
the fix. Run `python -B test_output/test_jev_evaluation.py` for M5. Fixtures are
synthetic and do not establish real human blinding or model quality.

Export review bundles with `pa jev review-export` first. Keep coordinator files
private. Write a plan such as:

```json
{
  "evaluation_id": "employment-pilot-v1",
  "shadow_db": "shadow.sqlite",
  "cases": [
    {
      "bundle": "review-bundle",
      "study_id": "study-001",
      "split": "holdout",
      "grouping_reference": "local-grouping-review-001"
    }
  ]
}
```

The single case illustrates the format, not adequate study size or a recommended
split. Choose development/calibration/holdout groups before reviewing model
outputs. Group alternate PDFs, versions and packets from the same study under one
curated study ID. Use a local reference explaining that decision. Unknown grouping
must be resolved before attesting. IDs are exact and case-sensitive.

```text
pa jev evaluation-freeze --plan plan.json --db evaluation.sqlite --operator coordinator-1 --confirm-study-grouping
```

Source database and bundle paths resolve relative to the plan file. The output DB
path resolves relative to the working directory. The database must not exist; its
parent must exist. An interrupted initialization may leave a file that needs local
inspection; it is never silently reset. The source M3 database is read-only.

Freeze checks bundle hashes, reads the original packet/rubric in one M3 snapshot,
and compares the allowlisted reviewer content to that source. It refuses duplicate
cases, review IDs, conflicting group splits, and one artifact assigned to different
studies. Rubrics, packet bindings, groups and splits are immutable within this
ledger. It does not re-open the PDF, detect semantic duplicate studies or verify
the coordinator's grouping attestation. It creates no assignment automatically.

## 2. Record an assignment

Obtain the review ID from the exported bundle and a stable reviewer identifier.
Record the reviewer's explicit attestation before distributing review.json:

```text
pa jev review-assign --db evaluation.sqlite --review-id REVIEW_ID --reviewer reviewer-1 --operator coordinator-1 --confirm-no-prior-exposure
```

The ID must belong to the frozen plan. Repeating the same case/reviewer assignment
reuses its ID. Different reviewers have separate records. No message or file is
sent by this command. Attestation is stored through this command's required gate;
it is not proof that the reviewer has never seen predictions outside the system.
No human judgment or `blinded=1` label is created.

## 3. Record known exposure

```text
pa jev review-expose --db evaluation.sqlite --study-id study-001 --operator coordinator-1 --evidence-reference exposure-incident-001
pa jev evaluation-status --db evaluation.sqlite
```

Exposure means model answers/suggestions became visible, not merely that passages
were read. It conservatively disqualifies the entire study in this evaluation,
including all existing assignments, packets and reviewers. The record is retained;
later blind assignments are refused. An exposed holdout stays in its original
split with an exclusion flag; it is not moved into calibration. Re-exporting a
bundle or changing reviewer aliases cannot clear this ledger's exposure history.
The status command reports `blind_candidate`, never verified blinding.

There is no automatic detection of external exposure. Do not create a new ledger,
change study IDs or omit incidents to restore contaminated holdout eligibility.
Cross-ledger exposure inheritance and study identity resolution are not implemented.
These remain coordination responsibilities. A new evaluation needs genuinely
uncontaminated holdout cases. Read-only status omits passages but includes reviewer
identifiers; keep it within the local evaluation team.

## 4. Submit an explicit human judgment

Only after a human has reviewed the frozen passages and rubric, create an entry:

```json
{
  "submission_id": "reviewer-1-submission-001",
  "assignment_id": "REPLACE_WITH_ASSIGNMENT_ID",
  "reviewer": "reviewer-1",
  "operator": "coordinator-1",
  "outcome": "label",
  "label": "REPLACE_WITH_ALLOWED_LABEL",
  "evidence_ids": ["REPLACE_WITH_EVIDENCE_ID"],
  "reason_reference": "local-human-review-note-001",
  "supersedes": null
}
```

```text
pa jev review-submit --db evaluation.sqlite --entry entry.json --confirm-human-judgment
```

This confirms a human-origin submission; the software cannot detect a false
attestation or identify who actually wrote a label. Do not submit model predictions
as human judgments. The reviewer must match the assignment. A label must be in the
frozen rubric and cite at least one frozen evidence ID. For insufficient evidence
or other inability to judge, use `"outcome": "abstain"`, `"label": null`; evidence
IDs may then be empty. Keep the explanation in the referenced local review note.
Abstention is distinct from any rubric label named uncertain.

To correct a judgment, use a new submission ID and set `supersedes` to the current
submission ID for that assignment. Original records remain intact; stale or
cross-assignment corrections fail. Repeating the same submission ID/content is
idempotent; altered content under the same ID fails. Known study exposure blocks
new judgments and corrections. No existing human-label pool is updated.

## 5. Resolve disagreement independently

Use `pa jev review-resolve --db evaluation.sqlite --entry resolution.json
--confirm-human-judgment --confirm-no-prior-exposure` with an explicit human decision:

```json
{
  "resolution_id": "resolution-001",
  "review_id": "REPLACE_WITH_REVIEW_ID",
  "adjudicator": "independent-reviewer-3",
  "operator": "coordinator-1",
  "based_on": ["REPLACE_WITH_CURRENT_SUBMISSION_1", "REPLACE_WITH_CURRENT_SUBMISSION_2"],
  "outcome": "label",
  "label": "REPLACE_WITH_ALLOWED_LABEL",
  "evidence_ids": ["REPLACE_WITH_EVIDENCE_ID"],
  "reason_reference": "local-adjudication-note-001",
  "supersedes": null
}
```

Every assigned reviewer must first submit. `based_on` must name exactly their
current submission IDs; the first resolution requires disagreement. The adjudicator
must have a different stable ID from all assigned reviewers. Confirm that this is
an independent human who has not seen model answers; the software cannot detect
aliases or false attestations. Seeing other human reviews for adjudication is
permitted. Recorded study exposure blocks resolution.

A resolution may choose a permitted rubric label with evidence or abstain with a
null label. It leaves every original judgment intact. Repeated identical IDs reuse
the recorded resolution. To correct or refresh a resolution, use a new ID and name
the latest resolution in `supersedes`. Reviewer corrections or newly completed
assignments invalidate the old basis; refresh it before freezing, even if reviewers
now agree. No resolution or correction is accepted after judgment freeze.

## 6. Freeze reviewed judgments

```text
pa jev judgments-freeze --db evaluation.sqlite --operator coordinator-1 --evidence-reference final-human-review-001 --confirm-human-review
```

Every unexposed case must have assignments, all assigned reviewers must have
submitted, and their current outcome/label pairs must agree or have a current
independent resolution. Missing judgments and unresolved disagreement refuse
freezing. There is no automatic majority vote. The snapshot retains original
judgments plus the separate resolution; consumers use a valid resolution as the
case outcome, or otherwise the unanimous reviewer outcome. Cases with unanimous
abstention remain abstentions. Exposed cases are excluded regardless of resolution.
Exposed cases are retained as excluded, including their available judgments.
An evaluation with no completed unexposed cases cannot freeze.

The snapshot stores current judgment IDs/content and exposure exclusions, with a
hash and operator reference. After freezing, new assignments, judgments and
corrections are refused; identical submission retries return their stored record.
Exposure recording remains available. Later exposure can invalidate blind
eligibility even though the old snapshot stays immutable; downstream evaluation
must consult current exposure history. Freeze establishes neither sufficient sample
size nor prediction quality. It does not reveal model answers or calculate metrics.

Schema note: new ledgers use `evaluation-m5-3`, adding an append-only resolutions
table. Version 2 retains its previous assignment/submission/freeze/status operations
but cannot accept resolutions; no silent migration occurs. Frozen rubric/evidence
IDs are stored for validation. Version 1 ledgers are refused, not silently migrated or
reset. No actual v1 ledger was created during this implementation. If one was
created separately, preserve it and arrange an explicit migration before use;
recreating a ledger without its assignment/exposure history is not a migration.

## Guarantees and remaining work

Writes serialize through SQLite transactions. Case/config records, assignments
and exposure events reject ordinary updates/deletes via triggers; database owners
can bypass these controls. The files are local and unencrypted. No provider key,
network call, model-generated scientific judgment, `pa judge` write or screening action is involved.

Next: explicit schema migration if needed, prediction joins, synthetic exclusion
and calibrated reporting. Every future
consumer must check current exposure history rather than trust a past assignment
result. The previous 83 M4 checks do not validate these M5 operations.

Latest targeted verification: 5 adjudication tests, 5 existing M5 tests and 7 CLI
tests pass. The adjudication suite covers distinct reviewer IDs, required consent,
exact judgment basis, stale corrections/assignments, frozen refusal and CLI entry.
Run `python -B test_output/test_jev_adjudication.py`. No real labels were entered.
