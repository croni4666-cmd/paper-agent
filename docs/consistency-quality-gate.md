# Evidence and gateway consistency quality gate

Run `python tools/consistency_quality_gate.py` before pushing changes to gateway
reservations, evidence snapshots or percentage extraction. Install the repository's
`[test]` dependencies first. The command exits nonzero on any check failure.

The gate checks whitespace errors against HEAD, compiles the Python package,
runs the nine related regression modules, and repeats the boundary suite three
times. Tests include actual pending processes, PID query failures, partial writes,
fsync/replace errors, artifact changes, byte normalization and linguistic variants.
Audit output and temporary files are isolated from the operator's normal ledger;
network connections are denied in the test runner.

GitHub Actions runs this gate on Ubuntu and Windows. Existing Python 3.10/3.11/3.12
regressions and package build verification remain independent checks. A successful
local gate permits uploading the fix branch for review; integration still requires
the remote CI jobs to pass. This workflow does not change branch protection rules
or automatically merge a pull request.

For this v3.10.0.29 fix, broad local pytest results were also compared with an
unmodified dee3e49 checkout. The restricted local environment produced the same
66 failed test IDs in both versions, with no new failures. This comparison is not
a permanent allowlist: CI's offline suites must pass, and known environment
limitations should be reported separately from new regressions.
