# v4.0.0 software acceptance [P3-40]

The software gate is independent of the indefinitely suspended real-corpus,
human-label and dependent scientific evaluation. All new fixtures are generated;
no accuracy/benchmark uplift, provider execution or scientific acceptance is
claimed. No new runtime dependencies or hosted infrastructure.

## Evidence

| Gate | Observed result |
|---|---|
| Process identity | 51 passing cases, including native Windows queries and naturally exiting children; native Linux also passes CI |
| Canonical journal | 54 passing cases, including real multi-process contention/creation, failed transactions, immutable snapshots/caps, migration and recovery |
| Default gateway/CLI | 20 passing cases, including custom/absent migration sources, crash-held quota, source edits, inspection/export and recovery |
| Offline joint gate | 190 passed plus 18 subtests |
| Repeated stress | Three rounds each: 19 legacy boundaries plus 74 journal/integration checks passed |
| Broad restricted local regression | 808 passed, 10 skipped, 28 subtests; same 66 failed IDs as the recorded v3 baseline, no new failures; one known blocking MCP stdio case deselected |
| Candidate cross-platform/package CI | [10/10 jobs passed on 7d00b61](https://github.com/croni4666-cmd/paper-agent/actions/runs/37913639257): Windows/Linux × Python 3.10–3.12, three original Python regression jobs, clean build/install |
| Installed gateway smoke | Generated licensed XML → frozen provenance → durable authorization → read-only doctor. CI runs this outside the checkout using the installed wheel on the final candidate |

The 66 restricted local failures cover network-dependent citation/concept
fixtures, existing Jev filesystem restrictions and absent optional pyzotero.
They are baseline comparison evidence, not passed checks or a waiver of normal
CI. CI retains the normal MCP stdio regression. The local runtime lacks setuptools;
clean package build/install is proven in CI, not inferred from an editable checkout.

Final publication requires every check on the PR's **current exact head**, with
no force/admin bypass. The GitHub release/tag identifies the integrated commit.
See [PR #63](https://github.com/croni4666-cmd/paper-agent/pull/63) for exact-head
checks and integration evidence.

## Independent review and verified corrections

One independent, read-only whole-branch review examined `b6841255..27f34e3`.
It found no Critical and three Important issues, with no deferred minor finding.
The coordinator reproduced each issue before implementing its regression fix:

1. First finalization accepted changed payload/provenance/operator metadata.
   It now binds the full frozen reservation snapshot; hash, receipt ID, operator
   and provenance mutations reject and leave quota held. Journal validation uses
   the same invariant; recovery metadata must match its accountable event.
2. Custom migration sidecar digests were later recomputed using the default path.
   The manifest now stores actual resolved source paths and verifies those bytes.
3. An exited legacy owner could leave a valid reservation sidecar before the first
   audit existed. Migration now preserves the absent audit in the manifest,
   retains the pending amount and permits explicit accountable recovery.

The coordinator additionally closed the inherited per-call paper-count loophole:
pending and committed submissions now enforce 25 papers cumulatively per run.
Unknown legacy counts permit migration/recovery but block additional reservations.
These seven added regression variants were observed failing before passing. The
full joint gate and broad comparison were repeated after the fix pass.

## Engineering decisions and practical costs

- Require an explicit reconciled legacy CLI cost cap: v3 did not persist tighter
  caps. Import may conservatively refuse when historical usage exceeds that cap.
- Validate preserved import paths/digests during evaluation: empty failed targets
  and late legacy edits cannot start fresh accounting. Conflicts stop authorization
  until deliberately reconciled; this adds local reads of preserved source files.
- Skip unrelated key-registry loading in gateway CLI: local journal operations
  need no credentials. Gateway commands consequently omit API expiry reminders.
- Enforce paper counts cumulatively: repeated submissions consume candidate quota.
  A committed legacy record with unknown count keeps its run conservatively closed.
- Suspend real-corpus/scientific gates under the user's instruction: synthetic
  checks cannot certify research accuracy, so ranking/label claims remain unavailable.
- Support one local machine and stopped legacy writers: SQLite cannot transact
  other-version writers or guarantee locking on an arbitrary shared filesystem.
- Treat administrator rewriting as outside application integrity: append-only
  triggers/hashes are not independent signatures against whole-database replacement.
- Coordinate docs/version/publication after immutable code review: final metadata,
  examples and package checks are verified by the coordinator/CI, rather than an
  additional independent code-review pass.

For storage changes, migration, unknown outcomes and downgrade limits, see
[the v4 operating guide](gateway-v4.md). The broader NLP and scientific quality
limits described in [v3.10.0.30 stability](stability-3.10.0.30.md) remain applicable.
