# M2 local PDF evidence index (2026-09-26)

The first M2 implementation is a standalone local Python API and module command.
It does not call Jev, send data, infer consent, mutate labels, or change existing
`pa review` / ranking behavior. Those integrations belong to M3 onward.

## Usage

Use the project's Python environment with optional PyMuPDF installed:

```text
python -m pa_cli.evidence paper.pdf --output paper.index.json
python -m pa_cli.evidence paper.pdf --query "employment methods results" --max-bytes 16000 --output paper.packet.json
```

The output parent directory must exist. Existing output files and the source PDF
cannot be overwritten. Both files contain research text and should stay local.
The second command rebuilds the index from the current PDF snapshot before
selecting passages. For repeated queries, retain the index locally:

```python
from pa_cli.evidence import build_index, build_packet
index = build_index("paper.pdf")
packet = build_packet(index, "employment", required_sections=["methods", "results"])
```

## Evidence contract

- SHA-256 binds the index to the exact PDF bytes read. Extraction uses that same
  in-memory snapshot. PDF parser/version and extraction settings are recorded.
- Pages are one-based physical PDF pages. Offsets are zero-based Python Unicode
  character positions within the stored page text; end is exclusive. These are
  not printed page labels, PDF byte offsets, or bounding boxes.
- Each evidence ID binds PDF hash, extractor, page, character range, and exact
  text. `page_text[start:end]` reconstructs the excerpt without normalization.
- Index and packet hashes detect accidental alteration and support later cache
  keys. They are not signatures or independent proofs of authenticity.
- Headings identify advisory sections. `section_confidence=0.5` means a heuristic
  label, not a measured probability. Unknown labels receive zero. Unrecognized
  headings and layout changes can cause incorrect section carryover.
- Blank/unreadable-text pages are retained as `empty_needs_review`; OCR status
  is `not_attempted`. A text-bearing page is not a guarantee of extraction
  completeness or correct reading order, especially with columns/tables.

## Bounds and routing

Default index limits: 100 MiB PDF, 500 pages, 2 million extracted characters,
1200 characters per span. Limits stop extraction explicitly; pages are not
silently dropped. Page extraction itself is delegated to PyMuPDF; a pathological
PDF is not protected by a process deadline in this milestone.

Default packet limits: 6 spans and 16000 UTF-8 bytes for the complete canonical
JSON output, including metadata and hashes. This is a byte limit, not a token
or billing estimate. Queries are limited to 2000 characters.

Retrieval is deterministic lexical overlap. It does not expand synonyms, resolve
bibliographies, or perform semantic entailment. A citation query may retrieve
its surrounding chunk, but citation resolution and cross-chunk context expansion
remain follow-ups. Fixed-size chunks may cut a sentence. No-match or missing
required sections yields `insufficient_evidence`; never interpret that as a
negative scientific finding. Oversized spans are omitted, not shortened.

`ready_for_local_review` only means matching passages fit the requested bounds;
it is not a claim of complete evidence. `pages_needing_review` remains visible.
`external_upload_allowed` is always false. M3 must join the exact artifact hash
to M1B's current provenance, check extraction uncertainty, minimize identifying
text, collect authorization, and enforce provider/token/cost policy before any
external dispatch. This module does not automatically remove names inside
passages and does not copy filesystem paths or author metadata into packets.

## Verification

Ten offline tests use generated three-page PDFs and cover exact reconstruction,
stable IDs, artifact changes, blank pages, section requirements, no matches,
index tampering, budgets, CLI export, and overwrite refusal. Run:

```text
python -B test_output/test_evidence_m2.py
```
