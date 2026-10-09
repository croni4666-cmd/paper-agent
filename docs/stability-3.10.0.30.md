# Stability assessment: v3.10.0.30

## Decision

The merged consistency fix is suitable for the current supervised offline desktop
workflow. No additional blocking defect was confirmed in the reviewed boundaries.
Release a patch revision containing these fixes rather than changing storage
architecture or adding new runtime dependencies during this stabilization cycle.

The v3.10.0.29 tag still points to the earlier implementation. The verified fix
landed through PR #61 (merge commit 4c223a44b71b4711649732412ecb1c48556d2c20),
so a new version is needed to make the corrected behavior available as a release.

## Evidence and operating boundaries

| Area | Current evidence | Operating boundary |
|---|---|---|
| Evidence consistency | One original byte snapshot drives hash and PDF/text parsing; mutation and raw text-byte regressions pass. | Publishers should use complete-file replacement or coordinated writes. Capturing bytes does not lock external writers or promise to detect every transient disk change. |
| Concurrent budgets | Live/unknown leases are retained; actual pending-process and query-error tests pass. | Processes sharing a budget must share the audit/lock domain. Unidentified legacy leases or failed cleanup may conservatively block further work pending explicit recovery. |
| Storage faults | Partial writes, fsync and replace faults preserve the existing ledger; corrupt/empty state fails closed. | The single-file publication protocol is not a cross-file transaction between audit history and reservations, nor a guarantee of every filesystem's power-loss behavior. |
| Percentage extraction | Tested directional forms, negation contractions, survey/side-effect and nominal variants are handled conservatively. | Lexical extraction is not full causal or linguistic interpretation. Review the original evidence before accepting a numerical benchmark. |
| Portability and packaging | Six merged-commit CI checks passed: Ubuntu/Windows gates, Python 3.10–3.12 regressions and wheel build/install. | Optional network providers, credentials and additional integrations require their own configured environment; they are not part of the offline stability claim. |

## Validation

- Fresh local consistency gate: 65 related tests pass, with 19 boundary tests
  passing three consecutive stress runs.
- Broad restricted-environment comparison: 683 passes versus 664 on unchanged
  dee3e49, with the same 66 failed IDs, 10 skips and one excluded MCP stdio case.
  Failures include offline network tests, SQLite access restrictions and missing
  pyzotero. This is not a permanent failure allowlist.
- Merged fix CI: https://github.com/croni4666-cmd/paper-agent/actions/runs/37886620122
- Before release, rerun the versioned tree's local quality gate and CI. Require
  the gate, existing offline regressions and package verification to succeed.

## When further strengthening becomes necessary

Prioritize process-instance identifiers and explicit lease recovery before
long-lived or unattended service deployment. Consider a transactional budget
store and crash-recovery protocol if accounting must survive power loss across
multiple files. Expand corpus-based linguistic validation before treating
automatic effect estimates as publication-ready conclusions.

These are next-stage requirements, not prerequisites for the current supervised
offline workflow. The present revision preserves conservative budget behavior
and evidence traceability without claiming production high availability.
