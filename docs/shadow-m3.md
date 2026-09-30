# M3 local shadow harness (2026-09-26)

M3 connects M1B artifact identity/rights and M2 evidence to a dedicated local
SQLite ledger. It supports only trusted offline fixture providers. The values
returned by a fixture are synthetic test inputs, not Jev judgments or human truth.

## Local API

```python
from pa_cli.evidence import build_index, build_packet
from pa_cli.shadow import FixtureProvider, run_shadow

index = build_index("paper.pdf")
packet = build_packet(index, "employment")
result = run_shadow(
    pdf="paper.pdf", index=index, packet=packet,
    fetch_result={"doi": "10.1234/study", "via_channel": "pmc",
                  "via_url": "https://europepmc.org/articles/PMC1?pdf=render"},
    rubric={"task": "evidence_support", "version": "pilot-1",
            "question": "Does the supplied passage support increased employment?",
            "labels": ["supported", "unsupported", "uncertain"]},
    db_path="shadow.sqlite", data_class="public",
    provider=FixtureProvider({"supported": 0.8, "unsupported": 0.1, "uncertain": 0.1}),
)
```

Use actual Fetch source context rather than inventing a trusted channel or URL.
The example identifiers are placeholders. Unless the actual PDF metadata verifies
the DOI and license, the result is `blocked`. Optional `expected_title` is passed
into the fresh provenance check. `data_class` defaults to unknown/local-only.
Requires optional PyMuPDF already used by M2; this milestone adds no packages.

## Data flow and gates

```text
PDF + M2 index + packet + Fetch context + task rubric
  -> validate hashes and exact indexed excerpts
  -> reinspect PDF metadata, current hash, rights, and optional title
  -> refuse stale/tampered packets
  -> persist request + prepared event
  -> ineligible/insufficient/incomplete extraction: blocked event
  -> otherwise persist dispatched event before calling offline fixture
  -> completed + synthetic suggestion / invalid_response / unknown
```

Maximum packet size is 16000 UTF-8 JSON bytes and six excerpts. Any indexed page
marked as needing review blocks dispatch. Current section heuristics and lexical
retrieval limits still apply. Passing these gates does not establish factual
correctness or evidence completeness. External upload is always disabled.

## Storage and idempotency

- `requests`: exact local packet, rubric, provenance, provider identity/config hash,
  artifact hash, timestamp. Source URL is represented by a hash in provenance to
  avoid copying URL credentials/query tokens. Expected title is recorded locally.
- `events`: append-only lifecycle records; errors retain exception type, not
  exception messages or passage text. Requests are committed before provider use.
- `suggestions`: separate synthetic answer records. Valid categorical probabilities
  must cover the rubric labels, be finite and within 0..1, and sum to one.
- `adjudications`: schema only for later explicit human input, keyed by artifact,
  packet, task, and rubric. Development/calibration/holdout split and reviewer are
  required; holdout rows require blinded=1 and source=human. M3 never inserts rows.

Supported tasks: relevance, evidence support, population match, study design,
result direction, and field presence. Future human-entry code must validate labels
against the frozen rubric and enforce blind review before exposure to suggestions;
SQL declarations alone cannot prove a review was blinded.

The request hash includes packet, rubric, current provenance and provider identity.
Every prior outcome, including blocked/unknown/invalid, is reused without dispatch.
There is no automatic retry. A persisted dispatched request without a terminal
event is returned as unknown; operator resolution/retry linkage remains a future
feature. Same-request concurrency is serialized for insertion using SQLite.

Updates/deletes are rejected by database triggers. This protects ordinary API
usage, not against a file owner editing the database or dropping triggers. Use a
dedicated database: the harness refuses an existing unrelated application DB.
It does not import or write `pa judge`, the sample pool, screening, ranking,
citations, or manuscripts. No existing human records are migrated.

The DB stores passage text locally and is not encrypted by this module. It is a
research artifact, not an ordinary diagnostic log. Offline provider subclasses
are trusted Python code, not sandboxed plugins; no external provider is shipped.

## Implemented versus remaining

Implemented: local API orchestration, fresh provenance/evidence join, immutable-by-
API request/event ledger, independent suggestions, human adjudication schema,
offline fixture interface, validation, deduplication, and fail-closed routing.

Remaining within M3/M5: user-facing human labeling/blinding workflow, source
redaction review, M3-specific operator resolution/retry, production shadow CLI,
answer-type calibration and real holdout evaluation. See the proposed
[local blinded evaluation design](jev-evaluation-m5.md).

M4 now separately implements the typed Jev adapter, persistent dispatch consent,
token/cost accounting, interactive dispatch CLI, quarantine/reconciliation,
explicit resume and linked retry; see [dispatch contract](jev-dispatch.md).
These do not add network execution or recovery to the M3 fixture harness.
GPT execution and live validation remain open. Synthetic fixture outputs must not
enter evaluation truth or be reported as model quality measurements.

Run the 12 offline regression scenarios with:

```text
python -B test_output/test_shadow_m3.py
```
