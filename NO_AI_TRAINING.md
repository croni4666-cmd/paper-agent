# No-AI-Training Restriction (v1.0)

> **Note**: This file is a standalone, human-readable summary of the
> No-AI-Training restriction contained in `LICENSE` (PART 2). The
> full legally-binding text is in `LICENSE`. If this file and `LICENSE`
> ever conflict, `LICENSE` controls.

## TL;DR

This software — including source code, documentation, configuration,
sample data, and test fixtures — **may not be used to train, fine-tune,
validate, benchmark, or otherwise improve any AI/ML/LLM/embedding model**.

## Scope

The restriction covers:

- **LLMs** (e.g. GPT, Claude, LLaMA, Mistral, Qwen, DeepSeek, etc.)
- **Code-generation models** and AI pair-programming systems
- **Image / audio / video generation models**
- **Embedding models** and vector search systems whose training data
  incorporates this software or its outputs
- **Any system** whose model weights, prompts, or fine-tuning data are
  derived from this software

## What is prohibited

- Training or fine-tuning any AI/ML model on this software's source
- Using outputs of this software (search results, metadata, parsed
  PDFs, etc.) to train or improve any model
- Creating or distributing datasets derived from this software for
  training purposes
- Circumventing via intermediate representations (embeddings, features)

## What is allowed

- **Use** of the software for normal research, paper-search, and
  bibliographic workflows
- **Evaluation** of the software (e.g. academic paper that benchmarks
  the CLI on a holdout test set)
- **Security review** and vulnerability research
- **Modification** and redistribution under the AGPL-3.0 + No-AI-Training
  combined terms (i.e. you can fork it as long as you don't train on it)
- **Citing** this software in academic work (no special permission needed)

## Why this restriction

- The author publishes academic research using this tool. Allowing
  derivative LLM training would compromise the integrity of future
  empirical comparisons.
- Several upstream search engines (Crossref, OpenAlex, Semantic Scholar,
  arXiv) have their own ToS regarding bulk scraping and ML training.
  This restriction ensures downstream compliance.
- The author has no commercial incentive to license AI training rights
  and prefers to keep this work as a research artifact, not a training
  corpus.

## Reporting violations

If you find this software or its outputs being used to train a model
in violation of this restriction, please open an issue at the upstream
repository (croni4666-cmd/paper-agent on GitHub).

## License interaction

This restriction is in addition to the AGPL-3.0 terms (see `LICENSE`
PART 1). The restrictions in PART 2 are **irrevocable** for the
duration of the copyright and apply regardless of the recipient's
organizational affiliation or commercial nature. Violation is a
material breach that, at the copyright holder's option, terminates
licensee rights under both PART 1 and PART 2.

## Version

- **v1.0** (2026-08-14): Initial standalone summary, derived from
  `LICENSE` PART 2. See `LICENSE` for the binding text.

## SPDX

```
SPDX-License-Identifier: AGPL-3.0-only
Additional Restriction Identifier: LicenseRef-No-AI-Training-1.0
```
