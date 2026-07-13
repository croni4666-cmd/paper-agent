# Spot-Check Index — All 25 Queries (2026-07-12)

> **What this is**: A user-friendly interface to verify Mavis's preliminary labels for 750 candidates (25 queries × 30 candidates). Each candidate has a checkbox list (0/1/2). Open a query file, fill in `user_label` for candidates where you disagree with Mavis, save the file, hand back.

> **Time estimate**: 30-60 sec per candidate when scanning title only. 750 candidates × 30 sec = ~6 hr full. 30-40% disagreement rate expected, so partial review (only flagging disagreements) takes 1-2 hr.

## How to use

1. Open the file for a query (e.g. `SPOT_CHECK_q019.md` — the most dramatic failure case, 19/30 are Mavis-labeled relevant)
2. For each candidate section, the Mavis label is shown — agree or override
3. **You only need to fill in candidates where you DISAGREE with Mavis** (or to confirm a few high-confidence ones for sanity check)
4. Save the file
5. Mavis reads back, computes new `labels_clean.json` from your overrides + Mavis labels for the rest

## Per-query navigation

| Q | Query | n_relevant (Mavis) | File |
|---|---|---:|---|
| q001 | AI tutoring systems and their effect on K-12 student learning outcomes | 2/30 | [SPOT_CHECK_q001.md](./SPOT_CHECK_q001.md) |
| q002 | automation impact on labor market gender wage gap | 3/30 | [SPOT_CHECK_q002.md](./SPOT_CHECK_q002.md) |
| q003 | vector quantized representations for document retrieval | 2/30 | [SPOT_CHECK_q003.md](./SPOT_CHECK_q003.md) |
| q004 | Bayesian structural time series for causal inference | 3/30 | [SPOT_CHECK_q004.md](./SPOT_CHECK_q004.md) |
| q005 | effects of universal basic income on labor supply | 8/30 | [SPOT_CHECK_q005.md](./SPOT_CHECK_q005.md) |
| q006 | long-context transformer attention degradation on long documents | 9/30 | [SPOT_CHECK_q006.md](./SPOT_CHECK_q006.md) |
| q007 | climate change adaptation in agricultural production | 25/30 | [SPOT_CHECK_q007.md](./SPOT_CHECK_q007.md) |
| q008 | drug repurposing using graph neural networks | 9/30 | [SPOT_CHECK_q008.md](./SPOT_CHECK_q008.md) |
| q009 | randomized controlled trial designs for digital health interventions | 10/30 | [SPOT_CHECK_q009.md](./SPOT_CHECK_q009.md) |
| q010 | institutional trust and policy compliance in pandemic responses | 12/30 | [SPOT_CHECK_q010.md](./SPOT_CHECK_q010.md) |
| q011 | federated learning privacy guarantees in healthcare | 13/30 | [SPOT_CHECK_q011.md](./SPOT_CHECK_q011.md) |
| q012 | carbon pricing effectiveness in OECD countries | 4/30 | [SPOT_CHECK_q012.md](./SPOT_CHECK_q012.md) |
| q013 | transformer-based protein structure prediction methods | 4/30 | [SPOT_CHECK_q013.md](./SPOT_CHECK_q013.md) |
| q014 | inequality and intergenerational mobility in education | 15/30 | [SPOT_CHECK_q014.md](./SPOT_CHECK_q014.md) |
| q015 | few-shot prompting strategies for domain-specific question answering | 14/30 | [SPOT_CHECK_q015.md](./SPOT_CHECK_q015.md) |
| q016 | labor economics gender wage gap empirical evidence | 14/30 | [SPOT_CHECK_q016.md](./SPOT_CHECK_q016.md) |
| q017 | industrial economics AI productivity gains in manufacturing | 7/30 | [SPOT_CHECK_q017.md](./SPOT_CHECK_q017.md) |
| q018 | AI education impact on student learning outcomes | 1/30 | [SPOT_CHECK_q018.md](./SPOT_CHECK_q018.md) |
| q019 | intelligent tutoring systems adaptive learning algorithms | 19/30 | [SPOT_CHECK_q019.md](./SPOT_CHECK_q019.md) |
| q020 | ChatGPT in higher education student performance study | 11/30 | [SPOT_CHECK_q020.md](./SPOT_CHECK_q020.md) |
| q021 | automation displacement manufacturing workers empirical | 6/30 | [SPOT_CHECK_q021.md](./SPOT_CHECK_q021.md) |
| q022 | machine learning labor market polarization | 4/30 | [SPOT_CHECK_q022.md](./SPOT_CHECK_q022.md) |
| q023 | personalized learning adaptive educational technology RCT | 10/30 | [SPOT_CHECK_q023.md](./SPOT_CHECK_q023.md) |
| q024 | Acemoglu Restrepo automation tasks model | 10/30 | [SPOT_CHECK_q024.md](./SPOT_CHECK_q024.md) |
| q025 | AI bias in education gender race | 3/30 | [SPOT_CHECK_q025.md](./SPOT_CHECK_q025.md) |

---

## Priority order (if you don't have time to do all 25)

1. **q019** (intelligent tutoring systems) — 19/30 Mavis says relevant, but baseline top-5 missed them all (rank 14+). Biggest lift if labels confirmed
2. **q005** (universal basic income) — known hard case, multiple definitions
3. **q007** (climate ag adaptation) — 25/30 Mavis says relevant, recall@10=0.32, hard to crack
4. **q013** (protein structure) — recall@10=0.25, transformer papers don't always have 'transformer' in abstract
5. **q010** (broad AI) — high false-positive baseline, Mavis labels a sanity check for noise filtering

The other 20 queries are more 'typical' — doing 1-5 already gives 80% of the ground-truth-stability win.

## What Mavis does with your labels

After you fill in, Mavis will:
1. Merge your overrides with Mavis labels → `labels_clean.json`
2. Recompute baseline + BM25 metrics on clean labels
3. Run E (ablation), A (cross-encoder), C (PaSa-lite) on clean labels
4. Report v3.9.0 lift numbers in CHANGELOG

If 5-10% of Mavis labels are wrong after your review, the v3.9 numbers will shift by ~0.02-0.05 — not material. If 30%+ are wrong, the strategy needs revisiting (we'll know).
