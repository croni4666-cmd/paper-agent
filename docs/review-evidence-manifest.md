# Evidence-traceable reviews

`pa review` can write two sidecar files with its Markdown output:

```bash
pa review ./corpus --output review.md
```

This writes `review.md.manifest.json` and `review.md.validation.json`. Use
`--manifest` and `--validation-report` to choose other paths.

Each manifest entry has a stable evidence ID, source path, available DOI and
title metadata, and one evidence basis: `full_text`, `abstract`, `metadata`,
or `unavailable`. The generated review labels every corpus entry with its ID.

The validation report lists cited IDs, unresolved IDs, unused inputs, inputs
without a valid classification, and citations that rely on abstracts. A report
with unresolved or unclassified IDs has `valid: false`.
