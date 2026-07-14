import json
snap = json.load(open(r"G:\minimax - workspace\Paper agent\bench\v01\system_outputs_combined\q026.json", encoding="utf-8"))
for i, c in enumerate(snap["results"][:5]):
    doi = c.get("doi", "")
    engines = c.get("engines_found_in", [])
    print(f"{i+1}. doi={doi!r}, engines={engines}")
