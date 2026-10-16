# 4.1.1 reliability repair

This release retains the v4 SQLite journal and backports the demonstrated 3.9.30
retrieval, PDF validation and corpus-inventory fixes onto the 4.1.0 baseline.

PDF writes and cold cache reads require a readable, unencrypted document with
pages and parseable content streams. Parsing runs in a memory/deadline bounded
worker, at most two per parent. Queue time counts toward the ten-second budget.
Every hot read hashes its observed bytes; up to 512 exact validated content
hashes are memoized in each process. This is structural validation, not a visual
or scientific quality check. Previously cached invalid PDFs become misses;
immutable old generations remain until explicit cache cleaning.

PMID-only records survive validation and publication merging. Available
OpenAlex abstracts and PMIDs are retained. PubMed additionally attempts batched
EFetch XML within an eight-second total detail budget; detail failure preserves
the summary metadata. Empty abstracts do not establish that a paper lacks one.
PubMed pacing serializes callers within a process, not independent processes.

`review` generates an auditable source inventory. It excludes its own output
on subsequent indexing, retains source hashes, and marks completeness unverified.
Word count does not certify full text. Historical fixed coverage percentages
are no longer included in generated inventories. This does not implement
automatic clinical adjudication or scientific conflict synthesis.

Europe PMC, the structured research-search interface and its exact-query cache
remain outside this v4 maintenance patch. Engineering pressure calls are not
independent clinical samples. Release attachments contain the validation
summary, source bindings and artifact checksums.
