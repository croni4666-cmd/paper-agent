"""Try to auto-download the 10 papers from v3.9.5 manual downloads list.

Uses ALL 6 channels including scihub + playwright (was disabled in v3.9.5 demo).
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Patch fetch_doi to use clash proxy
import os
os.environ["HTTP_PROXY"] = "http://127.0.0.1:7897"
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7897"

from pa_cli.deep_rerank import stage1_download_orchestration, DeepRerankConfig
from pa_cli.fetch import fetch_doi


def main():
    bench_dir = ROOT / "bench" / "v01"
    output_dir = Path.home() / ".paper-agent" / "deep_rerank" / "manual_retry"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 10 DOIs from the v3.9.5 manual downloads list
    manual_dois = [
        ("q001", "10.1186/s41239-021-00292-9", "The impact of artificial intelligence on learner–instructor interaction"),
        ("q001", "10.1001/jamanetworkopen.2021.49008", "Effect of AI Tutoring vs Expert Instruction"),
        ("q001", "10.3390/su151612451", "New Era of Artificial Intelligence in Education"),
        ("q002", "10.1093/oxrep/graa051", "Do technological advances reduce the gender wage gap"),
        ("q002", "10.1016/j.jebo.2020.07.014", "Robots, computers, and the gender wage gap"),
        ("q002", "10.1111/j.1467-9914.2007.00378.x", "The Gender Wage Gap in the Turkish Labor Market"),
        ("q002", "10.5089/9781498303743.001", "Is Technology Widening the Gender Gap"),
        ("q002", "10.1037/e686432011-001", "Separate and Not Equal Gender Segregation"),
        ("q003", "10.1145/3488560.3498443", "Learning Discrete Representations via Constrained Clustering"),
        ("q003", "10.1109/icdar.2013.114", "Writer Identification and Writer Retrieval"),
    ]

    # Use ALL 6 channels with longer timeout
    config = DeepRerankConfig(
        top_k_per_query=5,
        per_doi_timeout_sec=60,
        output_dir=output_dir,
        cascade_channels=["openalex", "arxiv", "unpaywall", "doi_redirect", "scihub", "playwright"],
    )

    print(f"[Manual retry] Trying {len(manual_dois)} DOIs with full 6-channel cascade")
    print(f"  channels: {config.cascade_channels}")
    print(f"  per_doi_timeout: {config.per_doi_timeout_sec}s")
    print(f"  proxy: {os.environ.get('HTTP_PROXY')}")

    auto_downloaded = []
    manual_still_needed = []
    for qid, doi, title in manual_dois:
        print(f"\n  {qid} | {doi[:50]}...", flush=True)
        try:
            pdf_dir = output_dir / qid
            result = fetch_doi(
                doi,
                output_dir=str(pdf_dir),
                channels=config.cascade_channels,
                max_total_sec=config.per_doi_timeout_sec,
                use_cache=True,
            )
            if result.get("saved_as") and Path(result["saved_as"]).exists():
                size = Path(result["saved_as"]).stat().st_size
                print(f"    OK via {result.get('via_channel', '?')} ({size/1024:.0f} KB)")
                auto_downloaded.append({
                    "qid": qid, "doi": doi, "title": title[:80],
                    "saved_as": result["saved_as"],
                    "via_channel": result.get("via_channel", ""),
                    "size_bytes": size,
                })
            else:
                reason = "no_success"
                if "handoff" in result:
                    reason = result["handoff"].get("reason", reason)
                channels_tried = list(result.get("channels", {}).keys())
                print(f"    FAIL ({reason[:80]})")
                print(f"    channels tried: {channels_tried}")
                manual_still_needed.append({
                    "qid": qid, "doi": doi, "title": title[:80],
                    "reason": reason,
                    "channels_tried": channels_tried,
                })
        except Exception as e:
            print(f"    EXC: {str(e)[:100]}")
            manual_still_needed.append({
                "qid": qid, "doi": doi, "title": title[:80],
                "reason": f"exception: {str(e)[:100]}",
            })

    # Save results
    summary = {
        "n_attempted": len(manual_dois),
        "n_auto_downloaded": len(auto_downloaded),
        "n_manual_still_needed": len(manual_still_needed),
        "auto_downloaded": auto_downloaded,
        "manual_still_needed": manual_still_needed,
    }
    out_path = output_dir / f"manual_retry_{time.strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print(f"\n{'='*60}")
    print(f"RESULTS")
    print(f"{'='*60}")
    print(f"  Attempted: {len(manual_dois)}")
    print(f"  Auto-downloaded (with full 6 channels + proxy): {len(auto_downloaded)}")
    print(f"  Still manual: {len(manual_still_needed)}")
    print(f"\n  Output: {out_path}")
    if auto_downloaded:
        print(f"\n  Auto-downloaded DOIs:")
        for a in auto_downloaded:
            print(f"    {a['doi'][:40]:40s} via {a['via_channel']:20s} ({a['size_bytes']/1024:.0f} KB)")
    if manual_still_needed:
        print(f"\n  Still manual (after full 6 channels):")
        for m in manual_still_needed:
            print(f"    {m['doi'][:40]:40s} reason: {m['reason'][:60]}")


if __name__ == "__main__":
    main()
