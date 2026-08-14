# paper-agent v3.9.11.9 — Independent Fresh Test 4-DOI × 5-Prefer

**Date**: 2026-08-10  
**Paper-agent version**: v3.9.11.9 (commit 665394c)  
**Proxy**: 10808  
**Cache**: Bypassed (delete before each case)  
**DOIs**: 4 (arXiv / Nature / OSF / NEJM)  
**Prefers**: 5 (arxiv / annas / cnki / scihub / auto)

## Raw matrix

| DOI | arxiv | annas | cnki | scihub | auto |
|---|---|---|---|---|---|
| arXiv_2310.06825 | ✅ 3,749,788B / dfbac4e7 / arxiv (4.1s) | ❌ fetch_all_mirrors_failed (12.81s) | ❌ fetch_all_mirrors_failed (0.0s) | ❌ fetch_all_mirrors_failed (36.48s) | ✅ 3,749,788B / dfbac4e7 / arxiv (21.42s) |
| Nature_nature12373 | ❌ fetch_all_mirrors_failed (0.0s) | ❌ fetch_all_mirrors_failed (11.15s) | ❌ fetch_all_mirrors_failed (0.0s) | ✅ 943,776B / 5929b8e4 / scihub (25.8s) | ✅ 943,776B / 5929b8e4 / scihub (35.47s) |
| OSF_nxv6a | ❌ fetch_all_mirrors_failed (0.0s) | ❌ fetch_all_mirrors_failed (12.29s) | ❌ fetch_all_mirrors_failed (0.0s) | ❌ fetch_all_mirrors_failed (35.58s) | ❌ fetch_all_mirrors_failed (50.19s) |
| NEJM_oa2034577 | ❌ fetch_all_mirrors_failed (0.0s) | ❌ fetch_all_mirrors_failed (10.67s) | ❌ fetch_all_mirrors_failed (0.0s) | ✅ 774,219B / 572d9b28 / scihub (26.84s) | ✅ 774,219B / 572d9b28 / scihub (39.55s) |

## Per-prefer success rate (across 4 DOIs)

| prefer | success | fail | success rate |
|---|---|---|---|
| arxiv | 1 | 3 | 1/4 |
| annas | 0 | 4 | 0/4 |
| cnki | 0 | 4 | 0/4 |
| scihub | 2 | 2 | 2/4 |
| auto | 3 | 1 | 3/4 |

## Per-DOI success rate (across 5 prefers)

| DOI | success | fail | success rate |
|---|---|---|---|
| arXiv_2310.06825 | 2 | 3 | 2/5 |
| Nature_nature12373 | 2 | 3 | 2/5 |
| OSF_nxv6a | 0 | 5 | 0/5 |
| NEJM_oa2034577 | 2 | 3 | 2/5 |

## Hash diversity per DOI (real different sources = different sha8)

| DOI | unique sha8 count | sha8 set |
|---|---|---|
| arXiv_2310.06825 | 1 | dfbac4e7 |
| Nature_nature12373 | 1 | 5929b8e4 |
| OSF_nxv6a | 0 | - |
| NEJM_oa2034577 | 1 | 572d9b28 |

## Real working channels (independently re-verified 2026-08-10)

| Channel | DOIs that work | Status |
|---|---|---|
| **arXiv** (via arxiv/auto) | arXiv_2310.06825 | ✅ arXiv DOI 真走 arXiv channel |
| **sci-hub** (via scihub/auto) | Nature_nature12373, NEJM_oa2034577 | ✅ 真走 sci-hub 兜底 |
| annas | none | ❌ 0/4 |
| cnki | none | ❌ 0/4 (4 DOIs 都不是中文期刊, fast fail by design) |
| unpaywall | (not in prefer list) | 🟡 SSL EOF 仍未修 |
| OSF | (not in any prefer) | ❌ 不在 5 通道内,仍 fail |

## Comparison with 8/9 strict matrix (v3.9.11.7)

| 维度 | 8/9 v3.9.11.7 | 8/10 v3.9.11.9 (本次) | 变化 |
|---|---|---|---|
| arXiv_2310.06825 | 1/5 | 2/5 | +1 |
| Nature_nature12373 | 1/5 | 2/5 | +1 |
| OSF_nxv6a | 0/5 | 0/5 | 0 |
| NEJM_oa2034577 | 1/5 | 2/5 | +1 |

## 3-tier honest audit (this run)

**Work (independently re-confirmed)**:
- arXiv channel: 1/4 DOIs (arXiv-shaped DOI goes to arXiv channel)
- sci-hub channel: 2/4 DOIs (everything else falls to sci-hub in auto mode)

**Not work (independently re-confirmed)**:
- annas: 0/4 in this 4-DOI sample
- cnki: 0/4 in this 4-DOI sample (4 DOIs are not Chinese journals — by design fast fail)
- OSF: 0/5 (no OSF channel in v3.9.11.9 either — only arxiv/cnki/annas/unpaywall/scihub)

**Untested / unknown**:
- OpenAlex / DOI-redirect / Playwright channels advertised in banner but not in prefer list
  (these are search-engine names, not fetch channels — banner is misleading)

## Conclusion

- **Real working fetch channels**: 2 out of 5 advertised in prefer list
  (arXiv + sci-hub; annas + cnki are conditional; unpaywall still SSL EOF)
- **OSF preprint**: still needs direct fetch (was already grabbed 8/3 to `liu_plouffe_2025_sez_fdi.pdf`)
- **Banner cosmetics**: 6 names printed, only 5 actually routable (openalex is search-only)