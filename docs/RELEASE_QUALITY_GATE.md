# Stable release quality gates

1. Run `python tools/release_quality_gate.py --output <evidence-directory>`.
   It runs the full offline suite and rejects test failures, unexpected skips,
   removed required tests, missing repair modules, and inconsistent versions.
   Seven named original-corpus tests may remain **unexecuted** when their original
   data are unavailable. Windows may skip the POSIX FIFO test; Linux may skip the
   two Windows API fault tests. These exceptions are never added to pass counts.
2. Run every offline CI command, consistency and capability stress gates. Re-run
   real failed inputs and complete live workflows in a fresh runtime. Inspect
   JSON status/errors and PDF structure; process exit zero is insufficient.
   Record external HTTP429 or outages as unavailable, never as successful source
   coverage. Missing selected dependencies or a failed selected browser-render
   probe block local runtime acceptance. Browser packages need matching binaries.
3. Freeze source hashes. Run search/cache/corrupt-PDF/inventory/gateway pressure
   checks and bounded live searches, verify no input corruption or child leaks.
   Evidence obtained before a source change does not certify the changed source.
4. Commit the validated source; require successful Windows/Linux and Python
   3.10/3.11/3.12 CI, package and dependency audit jobs for that exact commit.
   Download and inspect the CI wheel independently. Build clean wheel/sdist,
   compare packaged runtime files to source, inspect Skill ZIP and exclude local
   configuration, credentials, PDFs, caches and private evidence.
5. Publish only after every applicable product gate passes. Release attachments
   must include validation limitations, exact commit/source hashes and SHA256
   sums. Download them again and verify checksums and remote tag target.
   Preserve previous releases and local runtime backups. Verify the installed
   default entrypoints, interpreter, package version and loaded file hashes.

Offline gate success does not mean every source is available. Disclose partial
online availability in release notes and validation evidence. Replayed requests,
multiple calls and engineering documents are not independent clinical samples.
Lexical claim candidates require human review and do not establish support,
contradiction, clinical efficacy or complete literature retrieval.
