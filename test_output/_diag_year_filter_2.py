"""Adversarial probes for the PubMed engine.

1. Year filter with SPECIFIC query (not broad MeSH)
2. Year filter with year-min 2024 only (no year-max) — should give 2024+
3. Test 6 re-run: BibTeX writes to file, check file
4. Test what happens with limit > 200 (chunking)
5. PubMed with explicit MeSH term
"""
import json
import os
import subprocess
import sys
from pathlib import Path

PROJ = r"G:\minimax - workspace\Paper agent"
os.chdir(PROJ)
env = os.environ.copy()
env["PYTHONIOENCODING"] = "utf-8"
env["PYTHONUTF8"] = "1"
env["PYTHONPATH"] = PROJ + os.pathsep + env.get("PYTHONPATH", "")


def run_pa(args, timeout=120):
    cmd = [sys.executable, "-m", "pa_cli", "search"] + args
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env, timeout=timeout)
    return r


def parse_json_output(stdout):
    cleaned = "\n".join(L for L in stdout.splitlines() if not L.startswith("[pa]"))
    for i, c in enumerate(cleaned):
        if c in "{[":
            start = i
            break
    else:
        return None
    try:
        return json.loads(cleaned[start:].strip())
    except json.JSONDecodeError:
        return None


# Probe A: SPECIFIC year-filter test — "sotorasib KRAS G12C" + 2021 only
# This was a famous paper in 2021 NEJM, should be tight
print("=" * 70)
print("Probe A: 'sotorasib KRAS G12C' + 2021-only filter")
print("        This was the famous 2021 NEJM paper — should be very specific")
print("=" * 70)
r = run_pa(["sotorasib KRAS G12C", "--engine", "pubmed",
            "--year-min", "2021", "--year-max", "2021", "--limit", "5",
            "--format", "json"])
d = parse_json_output(r.stdout)
if d and d.get("results"):
    papers = [p for p in d["results"] if p.get("source") == "pubmed"]
    print(f"  Got {len(papers)} papers, years: {[p.get('year') for p in papers]}")
    for p in papers[:5]:
        print(f"  - pmid={p.get('pmid')} year={p.get('year')} "
              f"title={(p.get('title') or '')[:60]}")
    all_2021 = all(p.get("year") == 2021 for p in papers)
    print(f"  All 2021: {all_2021}")
else:
    print(f"  No results. r.stdout[:200]={r.stdout[:200]!r}")
    print(f"  r.stderr[:200]={r.stderr[:200]!r}")
print()

# Probe B: year-min only, 2024+, broad query
print("=" * 70)
print("Probe B: 'mRNA vaccine' + year-min 2024 (no max)")
print("=" * 70)
r = run_pa(["mRNA vaccine", "--engine", "pubmed",
            "--year-min", "2024", "--limit", "5", "--format", "json"])
d = parse_json_output(r.stdout)
if d and d.get("results"):
    papers = [p for p in d["results"] if p.get("source") == "pubmed"]
    years = [p.get("year") for p in papers]
    print(f"  Got {len(papers)} papers, years: {years}")
    all_ge_2024 = all((y or 0) >= 2024 for y in years)
    print(f"  All >= 2024: {all_ge_2024}")
else:
    print(f"  No results")
print()

# Probe C: Test 6 properly — bibtex writes to file
print("=" * 70)
print("Probe C: --format bibtex writes to FILE, not stdout")
print("=" * 70)
# Remove old file first
old = Path("hypertension_treatment.bib")
if old.exists():
    old.unlink()
r = run_pa(["hypertension treatment", "--engine", "pubmed",
            "--limit", "3", "--format", "bibtex"])
print(f"  rc={r.returncode}  stdout_len={len(r.stdout)}")
print(f"  stderr (last 200): ...{r.stderr[-200:]!r}")
# Check file
bib = Path("hypertension_treatment.bib")
if bib.exists():
    text = bib.read_text(encoding="utf-8")
    import re
    n_article = text.count("@article")
    n_total = len(re.findall(r"@\w+\s*\{", text))
    print(f"  file: {bib}  size={len(text)}  @article={n_article}  total entries={n_total}")
    print(f"  first entry: {text.split('@', 1)[1][:200] if '@' in text else 'NONE'}")
else:
    print(f"  NO bib file written")
print()

# Probe D: limit > 200 (chunking test, just smoke test)
print("=" * 70)
print("Probe D: limit=250 (tests chunking)")
print("=" * 70)
r = run_pa(["cancer", "--engine", "pubmed", "--limit", "250", "--format", "json"],
           timeout=180)
d = parse_json_output(r.stdout)
if d:
    n = len(d.get("results", []))
    print(f"  Got {n} papers with limit=250")
    if n > 0:
        by_engine = d.get("by_engine", {})
        print(f"  by_engine: {by_engine}")
        first = d["results"][0]
        print(f"  first paper: pmid={first.get('pmid')} year={first.get('year')}")
print()

# Probe E: query with boolean operators (PubMed-specific syntax)
print("=" * 70)
print("Probe E: PubMed boolean syntax (AND)")
print("=" * 70)
r = run_pa(["(breast cancer) AND (immunotherapy)", "--engine", "pubmed",
            "--year-min", "2024", "--limit", "3", "--format", "json"])
d = parse_json_output(r.stdout)
if d and d.get("results"):
    papers = [p for p in d["results"] if p.get("source") == "pubmed"]
    print(f"  Got {len(papers)} papers")
    for p in papers[:3]:
        print(f"  - pmid={p.get('pmid')} year={p.get('year')} title={(p.get('title') or '')[:50]}")
print()

# Probe F: query with MeSH field tag
print("=" * 70)
print("Probe F: PubMed MeSH field tag")
print("=" * 70)
r = run_pa(['"Hypertension"[Mesh]', "--engine", "pubmed",
            "--year-min", "2024", "--limit", "3", "--format", "json"])
d = parse_json_output(r.stdout)
if d and d.get("results"):
    papers = [p for p in d["results"] if p.get("source") == "pubmed"]
    print(f"  Got {len(papers)} papers")
    for p in papers[:3]:
        print(f"  - pmid={p.get('pmid')} year={p.get('year')} title={(p.get('title') or '')[:50]}")
print()

# Probe G: zero limit (boundary)
print("=" * 70)
print("Probe G: limit=0 (boundary)")
print("=" * 70)
r = run_pa(["aspirin", "--engine", "pubmed", "--limit", "0", "--format", "json"])
d = parse_json_output(r.stdout)
if d:
    n = len(d.get("results", []))
    print(f"  limit=0 -> {n} papers")
print()

# Probe H: negative year (should be ignored or rejected)
print("=" * 70)
print("Probe H: --year-min -100 (negative)")
print("=" * 70)
r = run_pa(["aspirin", "--engine", "pubmed", "--year-min", "-100",
            "--limit", "3", "--format", "json"])
print(f"  rc={r.returncode}  stderr[:200]={r.stderr[:200]!r}")
d = parse_json_output(r.stdout)
if d and d.get("results"):
    print(f"  Got {len(d['results'])} papers")
