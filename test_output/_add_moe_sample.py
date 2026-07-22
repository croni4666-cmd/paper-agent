"""[v3.9.7.4-indep] Add a new MoE router training sample to the sample library.

Per user request 2026-07-22: build a sample library that user can grow
incrementally as the Haining research progresses. This script is the
ADD entry point.

Usage:
    # Interactive
    python test_output/_add_moe_sample.py

    # Parameterized
    python test_output/_add_moe_sample.py \\
        --qid q063 \\
        --query "China Haining warp knitting industry 4.0 case study" \\
        --doi "10.1234/example.2024" \\
        --engine aminer \\
        --topic t5 --method m13 --data d11 --industry i3

The 4-dim labels (topic/method/data/industry) follow
bench/moe-keyword-samples.md §1 convention:

Topic (t):
  t1=成熟度 / t2=DEA-Tobit / t3=边缘算力 / t4=AI 鸿沟 / t5=中国本土

Method (m):
  m1=DEA-CCR / m2=DEA-SBM / m3=DEA-Tobit / m4=bootstrap / m5=5级框架 /
  m6=DTCMM / m7=综述 / m8=4层架构 / m9=综述 / m10=计量经济 / m11=4阶段 /
  m12=资源基础观 / m13=案例研究 / m14=政策评估 / m15=仿真

Data (d):
  d1=企业效率 / d2=松弛 / d3=政策评估 / d4=序列相关 / d5=SME /
  d6=工业 / d7=IoT / d8=云边端 / d9=GenAI / d10=企业 / d11=产业案例 /
  d12=面板数据

Industry (i):
  i0=一般 / i1=制造 / i2=工业 / i3=纺织经编 / i4=AI产业

Engine (one of arxiv/openalex/s2/crossref/aminer/cnki):
  The engine that ACTUALLY returned the paper. This is what the MoE
  router should learn to route to.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(".")
BENCH = ROOT / "bench" / "v01"
SAMPLES_JSON = BENCH / "moe_keyword_samples_12.json"
SYS_OUT_DIR = BENCH / "system_outputs_combined_moe_samples_12"

VALID_ENGINES = {"arxiv", "openalex", "s2", "crossref", "aminer", "cnki"}
VALID_TOPICS = {f"t{i}" for i in range(1, 6)}
VALID_METHODS = {f"m{i}" for i in range(1, 16)}
VALID_DATA = {f"d{i}" for i in range(1, 13)}
VALID_INDUSTRY = {f"i{i}" for i in range(0, 5)}

# Noise candidates template per engine (so label=2 paper is the only label=2 in top-10)
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
        ("10.1016/j.jmse.2023.101234", "Journal of Manufacturing Systems edge AI"),
    ],
    "cnki": [
        ("10.1234/cnki.2024.001", "中国纺织工业 4.0 转型"),
        ("10.1234/cnki.2024.002", "海宁经编产业大脑研究"),
        ("10.1234/cnki.2024.003", "算力券补贴政策评估"),
    ],
}


def find_next_qid(samples: dict) -> str:
    """Find the next available qid (q051, q052, ...)."""
    used = set(int(qid[1:]) for qid in samples.keys() if qid.startswith("q"))
    n = max(used) + 1 if used else 51
    return f"q{n:03d}"


def add_sample(qid: str, query: str, doi: str, engine: str,
               topic: str, method: str, data: str, industry: str) -> None:
    """Add one sample to the library."""
    # Validate
    for name, val, valid in [
        ("engine", engine, VALID_ENGINES),
        ("topic", topic, VALID_TOPICS),
        ("method", method, VALID_METHODS),
        ("data", data, VALID_DATA),
        ("industry", industry, VALID_INDUSTRY),
    ]:
        if val not in valid:
            raise ValueError(f"Invalid {name}: {val!r} not in {valid}")

    # Load samples
    if SAMPLES_JSON.exists():
        data_loaded = json.loads(SAMPLES_JSON.read_text(encoding="utf-8-sig"))
    else:
        data_loaded = {
            "version": "v0.1-moe-samples-library",
            "source": "bench/moe-keyword-samples.md (incremental library)",
            "labels": {},
        }
    labels = data_loaded.get("labels", {})

    if qid in labels:
        raise ValueError(f"{qid} already in sample library")

    # Auto-assign qid if empty
    if not qid:
        qid = find_next_qid(labels)

    # Add label entry
    labels[qid] = {
        doi: {
            "label": 2,
            "reason": f"USER NOTE: v3.9.7.4 MoE sample [{topic}/{method}/{data}/{industry}] engine={engine}",
        }
    }
    data_loaded["labels"] = labels
    # Atomic write
    tmp = SAMPLES_JSON.with_suffix(".tmp")
    tmp.write_text(json.dumps(data_loaded, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(SAMPLES_JSON)
    print(f"  [labels] {qid} added (engine={engine}, tags={topic}/{method}/{data}/{industry})")

    # Add system_outputs file
    SYS_OUT_DIR.mkdir(parents=True, exist_ok=True)
    primary = {
        "doi": doi,
        "title": f"Paper {qid} ({topic}/{method}/{data}/{industry}) engine={engine}",
        "authors": ["Author A", "Author B"],
        "venue": "Sample Journal",
        "year": 2024,
        "cited_by_count": 50,
        "rank": 1,
        "v4_score": 1.0,
        "bm25_score": 10.0,
        "biencoder_score": 0.95,
        "engines_found_in": [engine],
        "source": engine,
    }
    candidates = [primary]
    for j, (ndoi, ntitle) in enumerate(NOISE_TEMPLATES.get(engine, [])[:3]):
        candidates.append({
            "doi": ndoi,
            "title": ntitle,
            "authors": ["Noise Author"],
            "venue": "Other Journal",
            "year": 2020,
            "cited_by_count": 5,
            "rank": j + 2,
            "v4_score": 0.3 - j * 0.05,
            "bm25_score": 2.0,
            "biencoder_score": 0.3,
            "engines_found_in": [engine],
            "source": engine,
        })
    out = {
        "query_id": qid,
        "query": query,
        "topic_bucket": f"sample-{topic}",
        "source": "moe-keyword-samples-library",
        "generated_at": "2026-07-22",
        "config": {
            "limit": 50,
            "engine": "arxiv,openalex,s2,crossref,aminer,cnki",
            "fix_version": "v3.9.10.11",
            "is_synthetic": True,
            "synth_purpose": "MoE router training sample (incremental library)",
        },
        "n_returned": len(candidates),
        "top_n": 4,
        "by_engine": {engine: 1},
        "results": candidates,
    }
    out_path = SYS_OUT_DIR / f"{qid}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [system_outputs] {out_path.name} written")

    # Print current status
    from _status_moe_samples import print_status
    print()
    print_status()


def main():
    parser = argparse.ArgumentParser(
        description="Add a MoE training sample to the library",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--qid", default="", help="e.g. q063 (auto if empty)")
    parser.add_argument("--query", required=True, help="Search query text")
    parser.add_argument("--doi", required=True, help="DOI of the label=2 paper")
    parser.add_argument("--engine", required=True, choices=sorted(VALID_ENGINES),
                        help="Engine that returned the paper")
    parser.add_argument("--topic", required=True, choices=sorted(VALID_TOPICS),
                        help="Topic tag (t1=成熟度, t2=DEA-Tobit, t3=边缘算力, t4=AI 鸿沟, t5=中国本土)")
    parser.add_argument("--method", required=True, choices=sorted(VALID_METHODS),
                        help="Method tag")
    parser.add_argument("--data", required=True, choices=sorted(VALID_DATA),
                        help="Data tag")
    parser.add_argument("--industry", required=True, choices=sorted(VALID_INDUSTRY),
                        help="Industry tag (i0=一般, i1=制造, i2=工业, i3=纺织经编, i4=AI 产业)")
    args = parser.parse_args()

    add_sample(args.qid, args.query, args.doi, args.engine,
               args.topic, args.method, args.data, args.industry)


if __name__ == "__main__":
    main()
