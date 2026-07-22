"""Render q001 candidate pool + labels side by side as a clean table."""
import json
from pathlib import Path

bench = Path("bench/v01")
sys_out = json.loads((bench / "system_outputs" / "q001.json").read_text(encoding="utf-8"))
labels_data = json.loads((bench / "labels.json").read_text(encoding="utf-8"))
labels = labels_data["labels"]["q001"]

label_emoji = {2: "[REL]", 1: "[MAR]", 0: "[IRR]"}
label_name = {2: "relevant", 1: "marginal", 0: "irrelevant"}

print(f"Query: {sys_out['query']}\n")
print(f"{'rank':>4} {'cite':>5} {'yr':>4} {'lbl':>5}  {'engines':<25}  title")
print("-" * 130)

rel, mar, irr = [], [], []
for r in sys_out["results"]:
    doi = r["doi"]
    lab = labels.get(doi, {"label": 0, "reason": "no label"})["label"]
    reason = labels.get(doi, {}).get("reason", "")
    engines = ",".join(r.get("engines_found_in", []))
    title = r["title"][:90] + ("..." if len(r["title"]) > 90 else "")
    print(f"{r['rank']:>4} {r['citation_count']:>5} {r['year'] or '-':>4} {label_emoji[lab]:>5}  {engines[:25]:<25}  {title}")
    print(f"      └─ {reason}")

    if lab == 2: rel.append(r["rank"])
    elif lab == 1: mar.append(r["rank"])
    else: irr.append(r["rank"])

print()
print(f"Stats: {len(rel)} relevant {rel} | {len(mar)} marginal {mar} | {len(irr)} irrelevant")

# Cross-verify: do my rels cluster topically?
print("\nTop 10 by rank (sorted by pa_cli's order — popularity bias test):")
for r in sys_out["results"][:10]:
    doi = r["doi"]
    lab = labels.get(doi, {"label": 0})["label"]
    print(f"  rank {r['rank']:>2}: {label_emoji[lab]} (cited {r['citation_count']})  {r['title'][:75]}")
