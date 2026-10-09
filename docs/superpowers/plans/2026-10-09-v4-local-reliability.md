# v4 Local Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox tracking.

**Goal:** Deliver a transactional, recoverable local gateway in v4.0.0 while real-corpus work is indefinitely suspended.
**Architecture:** One dedicated SQLite journal for reservations, receipts and recovery. Shared evidence validation, process-instance identity and explicit v3 migration/compatibility adapter.
**Tech Stack:** Python >=3.10, stdlib sqlite3/ctypes, existing Click and pytest/PyMuPDF test dependencies.
**Spec:** ../specs/2026-10-09-v4-local-reliability-design.md

## Global Constraints
- No new runtime dependencies, paid calls, hosted services or human sample-pool writes.
- Retain hard limits: 100000 tokens, 25 papers and at most $0.01/run; tighter caller caps persist.
- All unknown owners/storage outcomes retain budget. Rights/consent/provenance stay strict.
- Corpus-dependent work remains suspended, never marked completed through synthetic fixtures.

## Review Focus
- Reused PID must not identify a new process as the old owner; unknown remains held.
- Crash/failure between reserve and receipt must not lose quota or double count it.
- Repeated migration and corrupt/foreign files must not overwrite either source or target.
- Same request ID with different data must reject rather than silently deduplicate.
- Recovery of live/unknown owners or already committed rows must refuse unsafe release.

### Task 1: Roadmap and paused work
Files: ROADMAP.md. Add P3-39's dated v3.10.0.30 amendment, explicit data suspension and P3-40 letter subtasks/acceptance criteria.
- [ ] Inspect existing tickets; retain historical rationale/data gates.
- [ ] Write narrowly scoped changes, self-review against user's local budget rule.

### Task 2: Process-instance identity
Files: pa_cli/process_identity.py; test_output/test_process_identity_v4.py.
Interfaces: process_alive, process_birth, current_owner, owner_status as specified.
- [ ] Write tests: matched birth alive, mismatched birth dead, inaccessible birth unknown, invalid PID, native API failure and Linux proc parsing.
- [ ] Run red, implement minimal no-signal queries, run green.

### Task 3: Canonical journal and recovery
Files: pa_cli/gateway_store.py; test_output/test_gateway_store_v4.py.
Interfaces: GatewayStore methods from spec; costs serialize as finite Decimal text.
- [ ] Write tests for 60000+60000 >100000 concurrent reservation rejection and exact-once finalization.
- [ ] Add rollback/foreign schema/duplicate identity cases; implement transaction domain.
- [ ] Add explicit migration/recovery tests with source preservation and forbidden owner states; implement and verify.

### Task 4: Gateway and CLI integration
Files: pa_cli/gateway.py, pa_cli/cli.py; test_output/test_gateway_v4.py.
- [ ] Write default-backend and content-gate tests plus CLI status/doctor/migrate/recover/export assertions.
- [ ] Integrate shared validation, immutable receipts and canonical accounting; preserve named v3 adapter.
- [ ] Adapt historical tests to explicitly target v3 compatibility when testing its physical IO contract; never relax behavioral assertions.

### Task 5: Quality and release
Files: tools/consistency_quality_gate.py, .github/workflows/ci.yml, migration docs, metadata/changelog/README.
- [ ] Add new suites and real-process stress cases; run old and new gates plus full offline comparison.
- [ ] Independent read-only review of all state transitions; fix demonstrated issues and repeat relevant verification.
- [ ] Update version to 4.0.0 only when P3-40's criteria are met. Push reviewed PR, require all CI and package checks, integrate/tag/publish.
