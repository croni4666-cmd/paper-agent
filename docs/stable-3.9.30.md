# 3.9.30 maintenance release

Based on fc2a68b, incorporating the locally reviewed retrieval, PDF/cache,
provenance, export and wrapper repairs. Europe PMC is explicit opt-in; historical
`all` and default PubMed remain unchanged. This branch does not supersede 4.1.

Install core: `pip install paper-agent-3.9.30-py3-none-any.whl`.
Optional PDF inventory extraction: install the `review` extra (PyMuPDF).
Browser rendering uses the `browser` extra and a matching Chromium installation;
MCP uses the `mcp` extra. `test` declares formal test-only dependencies.
Do not install all model extras just to search or fetch papers.

No API keys, personal paths, corpus PDFs or private experiment outputs belong in
the release. `runtime.local.json` remains machine-local. Exported test abstracts
are synthetic; real-response audit records stay outside this repository.

Scientific claim adjudication and cross-proposition conflict synthesis are not
implemented by the inventory generator. Europe PMC DOI-fetch cascade fallback
has not been added. A successful stress run is engineering evidence, not proof
of clinical coverage, retrieval efficacy or independent-study sufficiency.

Release gates and immutable artifact SHA256 values are attached to the Release.
