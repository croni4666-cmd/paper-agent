"""Add 12 MoE router training samples (q051-q062) per bench/moe-keyword-samples.md.

Per the spec:
- 12 papers with 4-dim labels (topic/method/data/industry)
- Engine distribution: crossref=5, s2=3, openalex=2, arxiv=2, aminer=0
- Each new qid has 1 paper (label=2) + 4-6 noise candidates (label=0)
- Query text matches the topic cluster (so router can learn routing signal)

Outputs:
- bench/v01/labels_clean.json: append q051-q062 (label=2)
- bench/v01/system_outputs_combined/q051-q062.json: query + candidates
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, '.')

ROOT = Path(".")
BENCH = ROOT / "bench" / "v01"
LABELS_PATH = BENCH / "labels_clean.json"
SYS_OUT_DIR = BENCH / "system_outputs_combined"

# (qid, query_text, label2_doi, label2_engine, topic, method, data, industry)
SAMPLES = [
    # 主题 2: DEA-Tobit (t2) — 4 papers, all crossref
    ("q051",
     "DEA-CCR Charnes Cooper Rhodes 1978 data envelopment analysis origin EJOR",
     "10.1016/0377-2217(78)90138-6",  # placeholder DOI for Charnes 1978 EJOR
     "crossref", "t2", "m1", "d1", "i0"),
    ("q052",
     "DEA-SBM slacks-based measure Tone 2001 efficiency EJOR",
     "10.1016/S0377-2217(00)00118-0",  # placeholder DOI for Tone 2001
     "crossref", "t2", "m2", "d2", "i0"),
    ("q053",
     "DEA Tobit two-stage McDonald 2009 second stage regression EJOR",
     "10.1016/j.ejor.2008.04.001",  # placeholder
     "crossref", "t2", "m3", "d3", "i0"),
    ("q054",
     "Simar Wilson bootstrap confidence interval DEA caveat emptor",
     "10.1007/s11123-010-0200-8",  # placeholder for J.Prod.Anal.
     "crossref", "t2", "m4", "d4", "i0"),
    # 主题 1: 成熟度分级 (t1) — 2 openalex + 1 crossref
    ("q055",
     "smart manufacturing maturity model 5 levels SME Mittal J Manuf Sys 2018",
     "10.1016/j.jmsy.2018.05.003",  # placeholder
     "openalex", "t1", "m5", "d5", "i1"),
    ("q056",
     "digital transformation capability maturity DTCMM Gokalp Martinez IJPR 2022",
     "10.1080/00207543.2021.1905110",  # placeholder
     "openalex", "t1", "m6", "d6", "i0"),
    # 主题 3: 边缘算力 (t3) — 2 arxiv
    ("q057",
     "edge AI 4 layer architecture IoT CPS Singh Gill 2023 inference offloading",
     "10.1109/MC.2023.3254401",  # placeholder for IEEE
     "arxiv", "t3", "m7", "d7", "i0"),
    ("q058",
     "edge computing cloud edge end collaboration 4 layer Hua ACM CSur 2023",
     "10.1145/3581783",  # placeholder
     "arxiv", "t3", "m8", "d8", "i0"),
    # 主题 4: AI 鸿沟 (t4) — 3 s2
    ("q059",
     "AI divide generative AI Capraro PNAS Nexus 2024 Acemoglu inequality",
     "10.1093/pnasnexus/pgae018",  # placeholder
     "s2", "t4", "m9", "d9", "i0"),
    ("q060",
     "SME AI productivity Czarnitzki JEBO 2023 small medium enterprise",
     "10.1016/j.jebo.2023.01.005",  # placeholder
     "s2", "t4", "m10", "d10", "i0"),
    # 主题 1 again (Bibby): 1 crossref
    ("q061",
     "industry 4.0 SME 4 stages Bibby Dehe 2018 production planning control",
     "10.1080/09537287.2017.1381397",  # placeholder
     "crossref", "t1", "m11", "d5", "i2"),
    # 主题 4 (Peretz): 1 s2
    ("q062",
     "SME AI implementation success rate 67% 12% Peretz-Andersson IJIM 2024 resource-based view",
     "10.1016/j.ijinfomgt.2023.102672",  # placeholder
     "s2", "t4", "m12", "d5", "i0"),
]

# Noise candidates (label=0) to make the candidate pool realistic
# Each qid will have the label=2 paper + 3-4 noise papers
NOISE_TEMPLATES = {
    "crossref": [
        ("10.1109/ACCESS.2020.2981234", "A survey of manufacturing 4.0 adoption barriers"),
        ("10.1016/j.techfore.2019.03.025", "Technology forecasting and innovation policy"),
        ("10.1080/00207543.2018.1457808", "Lean production industry 4.0 integration"),
    ],
    "openalex": [
        ("10.1016/j.cie.2020.106789", "AI applications in industrial engineering review"),
        ("10.1016/j.engappai.2019.103456", "Machine learning manufacturing case study"),
        ("10.1016/j.procir.2018.03.123", "Procedia CIRP digital transformation"),
    ],
    "arxiv": [
        ("arXiv:2104.01266v2", "Deep learning for IoT edge devices survey"),
        ("arXiv:2302.07845v1", "Federated learning at the edge architecture"),
        ("arXiv:2411.12345v1", "5G MEC multi-access edge computing performance"),
    ],
    "s2": [
        ("10.1145/3411764.3445105", "ACM CHI human-AI collaboration 2021"),
        ("10.1126/science.abh1925", "Science AI productivity gap empirical"),
        ("10.1038/s41586-021-03819-2", "Nature AI ethics policy review"),
    ],
    "aminer": [
        ("10.1016/j.chb.2023.107789", "Computers in Human Behavior AI study"),
        ("10.1109/TSC.2022.3167890", "IEEE TSC cloud AI services"),
    ],
}

# Validation: confirm 12 entries with correct engine distribution
expected_dist = {"crossref": 5, "s2": 3, "openalex": 2, "arxiv": 2, "aminer": 0}
actual_dist = {}
for _, _, _, eng, _, _, _, _ in SAMPLES:
    actual_dist[eng] = actual_dist.get(eng, 0) + 1
print(f"Engine distribution: {actual_dist}")
for k, v in expected_dist.items():
    if actual_dist.get(k, 0) != v:
        raise AssertionError(f"Engine {k}: expected {v}, got {actual_dist.get(k, 0)}")
for k in actual_dist:
    if k not in expected_dist:
        raise AssertionError(f"Unexpected engine {k}: {actual_dist[k]}")
print(f"Total: {len(SAMPLES)} (expected 12)")
assert len(SAMPLES) == 12


def add_to_labels():
    """Add q051-q062 to labels_clean.json."""
    data = json.loads(LABELS_PATH.read_text(encoding="utf-8"))
    labels = data.get("labels", {})
    for qid, query, doi, eng, t, m, d, i in SAMPLES:
        if qid in labels:
            print(f"  WARN: {qid} already in labels_clean.json, overwriting")
        labels[qid] = {
            doi: {
                "label": 2,
                "reason": f"USER NOTE: v3.9.7.4 MoE sample [{t}/{m}/{d}/{i}] engine={eng}",
            }
        }
    data["labels"] = labels
    data["version"] = data.get("version", "v0.1-clean") + "+12-samples"
    LABELS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  labels_clean.json: added q051-q062 ({len(SAMPLES)} qids)")


def add_to_system_outputs():
    """Create q051-q062.json in system_outputs_combined/."""
    for qid, query, doi, eng, t, m, d, i in SAMPLES:
        # Label=2 paper (the one the engine is supposed to find)
        primary = {
            "doi": doi,
            "title": f"Paper {qid} ({t}/{m}/{d}/{i}) engine={eng}",
            "authors": ["Author A", "Author B"],
            "venue": "Sample Journal",
            "year": 2024,
            "cited_by_count": 50,
            "rank": 1,
            "v4_score": 1.0,
            "bm25_score": 10.0,
            "biencoder_score": 0.95,
            "engines_found_in": [eng],
            "source": eng,
        }
        # Noise candidates from same engine's pool (so they don't outvote)
        # But also from other engines to make distribution realistic
        candidates = [primary]
        # Add 3-4 noise candidates with label=0 (not in labels_clean)
        for j, (noise_doi, noise_title) in enumerate(NOISE_TEMPLATES[eng][:3]):
            candidates.append({
                "doi": noise_doi,
                "title": noise_title,
                "authors": ["Noise Author"],
                "venue": "Other Journal",
                "year": 2020,
                "cited_by_count": 5,
                "rank": j + 2,
                "v4_score": 0.3 - j * 0.05,
                "bm25_score": 2.0,
                "biencoder_score": 0.3,
                "engines_found_in": [eng],  # also from same engine
                "source": eng,
            })
        out = {
            "query_id": qid,
            "query": query,
            "topic_bucket": f"sample-{t}",
            "source": "moe-keyword-samples",
            "generated_at": "2026-07-22",
            "config": {
                "limit": 50,
                "engine": "arxiv,openalex,s2,crossref,aminer",
                "fix_version": "v3.9.10.11",
                "is_synthetic": True,
                "synth_purpose": "MoE router training sample (n=12 supplement)",
            },
            "n_returned": len(candidates),
            "top_n": 4,
            "by_engine": {eng: 1},
            "results": candidates,
        }
        out_path = SYS_OUT_DIR / f"{qid}.json"
        out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  system_outputs_combined/: wrote {len(SAMPLES)} files (q051-q062)")


if __name__ == "__main__":
    print("Adding 12 MoE router training samples...")
    add_to_labels()
    add_to_system_outputs()
    print()
    print("Done. Run `_run_moe_router_v3_9_7_1.py` to train + evaluate.")
