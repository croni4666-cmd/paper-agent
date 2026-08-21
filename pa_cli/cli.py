"""
pa_cli.cli — Click command group for paper-agent CLI.

Usage examples:
  python -m pa_cli fetch 10.1016/j.caeo.2024.100184 --proxy http://127.0.0.1:10808
  python -m pa_cli search "AI literacy higher education" --year-min 2023 --limit 20
  python -m pa_cli review ./pdfs --output lit_review.md
  python -m pa_cli version
"""

import json
import os
import re
import sys
from pathlib import Path

import click

from . import __version__


CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(__version__, prog_name="paper-agent (pa)")
def main():
    """paper-agent CLI — academic paper fetch + lit review synthesis.

    paper-agent v4 design principle: after 5 minutes of Cloudflare challenge
    failure, stop iterating and surface a "your turn" handoff. Real human
    browser sessions remain the only reliable Cloudflare bypass.
    """
    # At every CLI invocation:
    #   1. Load .env into os.environ (does not override existing values)
    #   2. Emit expiry reminders to stderr if any keys are <= 14 days
    #      to expiry or already expired. Quiet by default to keep
    #      subcommand output clean; use `pa keys remind` to force.
    from .keys import load_env_into_environ, cmd_remind
    n_loaded = load_env_into_environ()
    if n_loaded > 0:
        sys.stderr.write(f"[pa] loaded {n_loaded} env var(s) from .env\n")
    # Show expiry reminders on every CLI invocation (non-intrusive: stderr only)
    cmd_remind(quiet=False)


@main.command()
@click.option("--remind", is_flag=True,
              help="Force expiry reminders even when no warnings would print")
def version(remind):
    """Show paper-agent version + key dependency status."""
    import importlib.util
    deps = {
        "click": "click",
        "pymupdf": "fitz",
        "arxiv": "arxiv",
        "requests": "requests",
    }
    click.echo(f"paper-agent CLI v{__version__}")
    click.echo(f"\nDependency status:")
    for label, mod in deps.items():
        try:
            spec = importlib.util.find_spec(mod)
            if spec is not None:
                mod_obj = __import__(mod)
                ver = getattr(mod_obj, "__version__", "(unknown)")
                click.echo(f"  [OK] {label:10s} {ver}")
            else:
                click.echo(f"  [--] {label:10s} not installed")
        except Exception:
            click.echo(f"  [--] {label:10s} not installed")
    click.echo(f"\nPython: {sys.version.split()[0]}")
    click.echo(f"Entry: python -m pa_cli <command>")


# =============== keys subcommand group ===============

@main.group()
def keys():
    """Manage API keys + expiry reminders.

    Two-layer storage:
      - .env (gitignored): holds ACTUAL secrets
      - keys_registry.json (NOT gitignored): holds METADATA only

    Subcommands: list / check / add / audit / remind
    """


@keys.command("list")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def keys_list(as_json):
    """List all known API keys with status."""
    from .keys import cmd_list
    rows = cmd_list()
    if as_json:
        click.echo(json.dumps(rows, indent=2, ensure_ascii=False))
        return
    click.echo(f"{'ID':16s} {'STATUS':18s} {'EXPIRES':12s} {'DAYS':6s} {'TIER':5s} {'NAME':30s} HINT")
    click.echo("-" * 120)
    for r in rows:
        marker = {
            "active": "✓ active",
            "expiring-soon": "⏰ expiring-soon",
            "expiring-week": "⚠ expiring-week",
            "expiring-today": "🚨 expiring-today",
            "expired": "❌ EXPIRED",
            "missing": "✗ missing",
        }.get(r["status"], r["status"])
        click.echo(
            f"{r['id']:16s} {marker:18s} {str(r['expires'])[:12]:12s} "
            f"{str(r['days_to_expiry'])[:6]:6s} {r['tier']:5s} {r['name'][:30]:30s} {r['hint']}"
        )


@keys.command("check")
@click.argument("service_id", required=False)
@click.option("--alert-file", "alert_file_path", default=None,
              metavar="PATH",
              help="Also write current alerts to this path (default: ~/.mavis/state/api_key_alerts.json)")
@click.option("--no-cache", is_flag=True,
              help="Bypass the 30-min in-memory cache; do a fresh probe")
def keys_check(service_id, alert_file_path, no_cache):
    """Live-probe each API key (or one specific). Updates last_checked timestamp.

    P0-2 cache behaviour: results are cached in-memory for 30 min.
    Use --no-cache to force a fresh probe and refresh the cache.
    """
    from .keys import cmd_check, write_alerts_to_state, _check_cache_clear
    if no_cache:
        _check_cache_clear()
    results = cmd_check(service_id)
    click.echo(json.dumps(results, indent=2, ensure_ascii=False))
    # Also update alerts file for cross-session reminder pickup
    target = Path(alert_file_path) if alert_file_path else None
    path = write_alerts_to_state(target)
    # Count warnings
    n_warn = sum(1 for r in results.values()
                 if isinstance(r, dict) and r.get("status") not in ("ok", "missing"))
    cache_marker = " (bypassed)" if no_cache else ""
    click.echo(f"\n[pa-keys] alerts file: {path} ({n_warn} non-ok status){cache_marker}", err=True)


@keys.command("add")
@click.argument("service_id")
@click.argument("key_value")
@click.option("--expires", default=None,
              help="Expiry date YYYY-MM-DD (omit if no expiry)")
@click.option("--tier", default="free", type=click.Choice(["free", "paid", "institutional"]),
              help="Service tier (affects reminder urgency)")
@click.option("--notes", default=None, help="Free-text notes")
def keys_add(service_id, key_value, expires, tier, notes):
    """Add or rotate a key. Updates .env + keys_registry.json."""
    from .keys import cmd_add, cmd_check
    result = cmd_add(service_id, key_value, expires=expires, tier=tier, notes=notes)
    click.echo(f"[pa-keys] added {service_id} → {result['env_var']}")
    click.echo(f"[pa-keys] registry: {result['registry_path']}")
    click.echo(f"[pa-keys] .env:     {result['env_path']}")
    click.echo(json.dumps(result, indent=2, ensure_ascii=False))
    # Immediately live-check the new key
    click.echo(f"\n[pa-keys] live-probe {service_id} ...")
    chk = cmd_check(service_id)
    click.echo(json.dumps(chk, indent=2, ensure_ascii=False))


@keys.command("audit")
def keys_audit():
    """Audit: which keys are active, never-checked, never-used, etc."""
    from .keys import cmd_audit
    a = cmd_audit()
    click.echo(f"Total services in registry: {a['total']}")
    click.echo(f"  active:        {a['active']}")
    click.echo(f"  expiring soon: {a['expiring_soon']}")
    click.echo(f"  expired:       {a['expired']}")
    click.echo(f"  missing:       {a['missing']}")
    if a["never_checked"]:
        click.echo(f"\nNever-checked (run `pa keys check` to verify):")
        for sid in a["never_checked"]:
            click.echo(f"  - {sid}")
    if a["never_used"]:
        click.echo(f"\nNever-used (paper-agent has never called this key):")
        for sid in a["never_used"]:
            click.echo(f"  - {sid}")


@keys.command("remind")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.option("--write-alerts", "write_alerts_path", default=None,
              metavar="PATH",
              help="Write alerts to this path (default: ~/.mavis/state/api_key_alerts.json)")
def keys_remind(as_json, write_alerts_path):
    """Show expiry warnings for all keys (or write alerts file)."""
    from .keys import cmd_remind, write_alerts_to_state
    alerts = cmd_remind(quiet=True)
    if as_json:
        click.echo(json.dumps(alerts, indent=2, ensure_ascii=False))
        return
    if not alerts["warnings"]:
        click.echo("[pa-keys] all keys OK (no warnings)")
    else:
        click.echo(f"[pa-keys] {len(alerts['warnings'])} warning(s):")
        for w in alerts["warnings"]:
            click.echo("  " + w["reminder_message"])
    # Write alerts file by default (or to custom path if --write-alerts given)
    target = Path(write_alerts_path) if write_alerts_path else None
    path = write_alerts_to_state(target)
    click.echo(f"\n[pa-keys] alerts file written: {path}")


@main.command()
@click.argument("doi")
@click.option("-o", "--output-dir", default=".", show_default=True,
              help="Where to save PDF")
@click.option("--proxy", default=None,
              help="HTTP proxy URL (e.g. http://127.0.0.1:10808). "
                   "If unset, falls back to HTTPS_PROXY/HTTP_PROXY env vars. "
                   "v3.9.11.5: user's clash-verge proxy port changed 7897 -> 10808 "
                   "(see memory 2026-08-06); use 10808 to reach foreign services "
                   "via GFW bypass.")
@click.option("--prefer", default=None,
              type=click.Choice(["arxiv", "annas", "cnki", "scihub", "pmc", "unpaywall", "auto"]),
              help="v3.9.11.6 new: pick a single source first. "
                   "'arxiv' for arXiv preprints, 'annas' for annas-archive, "
                   "'cnki' for Chinese journals, 'scihub' for sci-hub, "
                   "'auto' (default) tries all in order: arxiv -> cnki -> "
                   "annas -> unpaywall -> scihub. Takes precedence over --channels.")
@click.option("--channels", default="pmc,arxiv,openalex,unpaywall,doi_redirect,scihub,playwright",
              show_default=True, help="[DEPRECATED v3.9.11.6] Comma-separated channel list. "
                   "Prefer --prefer instead. This legacy list maps heuristically to "
                   "--prefer: 'arxiv'->arxiv, 'pmc'->pmc, 'unpaywall'/'scihub'->scihub, "
                   "anything else->auto. v3.9.20.1: added 'pmc' (was missing — auto mode "
                   "was skipping PMC entirely, making most biomedical papers fail).")
@click.option("--unpaywall-email", default="hello@example.com", show_default=True,
              help="Email registered with Unpaywall API")
@click.option("--max-total-sec", default=300, show_default=True,
              help="Hard cap on total runtime (paper-agent v4: 300s)")
@click.option("--no-cache", is_flag=True,
              help="Bypass cache lookup; cascade attempts download (cache still written on success)")
@click.option("--quiet", is_flag=True, help="Suppress progress output")
def fetch(doi, output_dir, proxy, prefer, channels, unpaywall_email, max_total_sec, no_cache, quiet):
    """Fetch a single paper PDF by DOI using 8 channels with Cloudflare fallback.

    Cache behaviour (P0-2):
      - By default (~/.paper-agent/cache/), checks cache first; on hit returns
        immediately with via_channel=cache:* and elapsed < 1s.
      - Use --no-cache to skip the cache lookup (cascade proceeds to network).
        Even with --no-cache, a successful cascade still writes to cache.
    """
    from .fetch import fetch_doi
    if not quiet:
        click.echo(f"[pa] fetch DOI={doi}", err=True)
        click.echo(f"[pa] output_dir={output_dir} proxy={proxy or '(none)'}", err=True)
        prefer_msg = prefer or "(auto from --channels)"
        click.echo(f"[pa] prefer={prefer_msg} channels={channels} cache={'disabled' if no_cache else 'enabled'}", err=True)
        click.echo(f"[pa] max_total_sec={max_total_sec}", err=True)
    # v3.9.11.6: --prefer takes precedence over --channels when set.
    # If --prefer is set, we wrap fetch_doi by passing channels that map
    # to that single prefer. This is a hack — proper way is to expose
    # --prefer through fetch_doi. Done in v3.9.11.6 by overriding the
    # channels list to force a single prefer mapping.
    if prefer:
        # Force the channel list to one that maps to our prefer
        # (see fetch_doi channel->prefer mapping)
        channel_to_prefer = {
            "arxiv": ["arxiv"],
            "annas": ["annas"],
            "cnki": ["cnki"],
            "pmc": ["pmc"],
            "unpaywall": ["unpaywall"],  # v3.9.21+: explicit Unpaywall option
            "scihub": ["scihub", "unpaywall"],  # unpaywall is checked first
            "auto": [],  # empty list -> auto
        }
        channels_list = channel_to_prefer[prefer]
    else:
        channels_list = channels.split(",")
    result = fetch_doi(
        doi=doi, output_dir=output_dir, proxy=proxy,
        channels=channels_list, unpaywall_email=unpaywall_email,
        max_total_sec=max_total_sec,
        use_cache=not no_cache,
    )
    click.echo(json.dumps(result, indent=2, ensure_ascii=False))
    if result.get("saved_as"):
        suffix = " (cache hit)" if result.get("cache_hit") else ""
        click.echo(f"\n[pa] ✅ saved {result['saved_as']}{suffix}", err=True)
        sys.exit(0)
    elif result.get("handoff"):
        click.echo(f"\n[pa] ⚠ handoff: {result['handoff'].get('user_action_required')}", err=True)
        # v3.9.11.5: also surface a proxy-missing hint on handoff path, since
        # the most common cause of "all sources failed" is missing/wrong proxy.
        env_proxy = (
            os.environ.get("HTTPS_PROXY")
            or os.environ.get("HTTP_PROXY")
            or os.environ.get("ALL_PROXY")
        )
        if not proxy and not env_proxy:
            click.echo(
                "[pa] hint: no proxy is set. If you expected a paper to download,\n"
                "         try:  $env:HTTPS_PROXY = 'http://127.0.0.1:10808'\n"
                "         (user's clash-verge port changed 7897 -> 10808 on 2026-08-06)",
                err=True,
            )
        sys.exit(2)
    else:
        # v3.9.11.5: friendly hint when all channels fail (often = missing proxy)
        env_proxy = (
            os.environ.get("HTTPS_PROXY")
            or os.environ.get("HTTP_PROXY")
            or os.environ.get("ALL_PROXY")
        )
        if not proxy and not env_proxy:
            click.echo(
                "\n[pa] ❌ all channels failed AND no proxy is set.\n"
                "     Most likely cause: paper-agent needs a proxy to reach foreign\n"
                "     services (OpenAlex, arXiv, Unpaywall, Sci-Hub, annas, etc.).\n"
                "     Set one of:\n"
                "       $env:HTTPS_PROXY = 'http://127.0.0.1:10808'   # Windows PowerShell\n"
                "       export HTTPS_PROXY=http://127.0.0.1:10808      # bash/sh\n"
                "     Or pass --proxy http://127.0.0.1:10808 to this command.\n"
                "     v3.9.11.5: user's clash-verge proxy port changed 7897 -> 10808\n"
                "     (see memory note 2026-08-06); old 7897 is no longer listening.",
                err=True,
            )
        else:
            click.echo("\n[pa] ❌ all channels failed (proxy is set; check network/Cloudflare)", err=True)
        sys.exit(1)


@main.command()
@click.argument("query")
@click.option("--year-min", type=int, default=None, help="Filter: min publication year")
@click.option("--year-max", type=int, default=None, help="Filter: max publication year")
@click.option("--limit", type=int, default=50, show_default=True,
              help="Max results per engine")
@click.option("--engine", default="all", show_default=True,
              help="all / crossref,openalex,arxiv,semanticscholar,aminer,cnki,pubmed,clinicaltrials,core "
                   "(comma-separated; default 'all' = first 8 incl. pubmed + clinicaltrials; "
                   "'core' = explicit CORE-only)")
@click.option("--format", "out_format", default="json", show_default=True,
              type=click.Choice(["json", "bibtex"]),
              help="Output format: json (default) or bibtex")
@click.option("-o", "--output", default=None,
              help="Save results to file (.json or .bib)")
@click.option("--concepts", "concept_ids", default=None,
              help="OpenAlex concept IDs (C<digits>) — comma-separated; "
                   "OR by default, use --concept-mode for AND")
@click.option("--concept", "concept_names", multiple=True,
              help="Concept name(s) to resolve to IDs (repeatable). "
                   "Looked up via OpenAlex /concepts?search=")
@click.option("--concept-mode", "concept_mode", default="or", show_default=True,
              type=click.Choice(["or", "and"]),
              help="How to combine multiple concepts: or (any) or and (all)")
@click.option("--enrich-top", "enrich_top", default=0, show_default=True,
              help="Top-N deep enrichment (v3.9.7.8): second-hop lookups via "
                   "S2 paper/DOI + Crossref by title for top-N results. "
                   "0 = off (default). Adds ~12s for N=10 (S2 1 RPS free).")
@click.option("--enrich-top-min-cites", "enrich_top_min_cites", default=1, show_default=True,
              help="[P1-14] Skip S2 lookup for papers with cited_by_count < this. "
                   "Default 1 = skip 0-cite papers (saves ~12s/query when many "
                   "low-cite papers in top-N). Set 0 to try all (v3.9.7.8 behavior).")
@click.option("--enrich-max-age-years", "enrich_max_age_years", default=10, show_default=True,
              help="[P1-18] Skip ALL enrichment for papers older than this many years. "
                   "Default 10 (S2 cite often stale/unavailable for older papers; "
                   "Crossref rarely adds missing fields for pre-2010 papers). "
                   "Set 0 to enrich all papers regardless of age.")
@click.option("--sort-by", "sort_by", default="cite", show_default=True,
              type=click.Choice(["cite", "year", "relevance"]),
              help="[P1-16] Sort unified results. 'cite' (default) = most-cited first; "
                   "'year' = newest first; 'relevance' = keep each engine's natural order.")
@click.option("--source", "source_filter", default=None,
              help="[P1-17] Post-filter results to only show those from specified engines. "
                   "Comma-separated: e.g. 'openalex,cnki'. Matches 'source' field prefix "
                   "(so 'openalex' also matches 'openalex_title' enrichment). Default = no filter.")
@click.option("--quality-mode", "quality_mode", default="flag", show_default=True,
              type=click.Choice(["flag", "filter", "off"]),
              help="[P2-14] Quality filter mode. "
                   "'flag' (default) = annotate each result with `quality_flag` "
                   "('low_quality' if no-abstract+low-cite+no-year; 'outdated' if >25y+<100cites). "
                   "'filter' = drop 'low_quality' results. "
                   "'off' = no filter / no annotation.")
@click.option("--quiet", is_flag=True, help="Suppress progress output")
def search(query, year_min, year_max, limit, engine, out_format, output,
           concept_ids, concept_names, concept_mode, enrich_top, enrich_top_min_cites,
           enrich_max_age_years, sort_by, source_filter, quality_mode, quiet):
    """6-engine academic paper search (Crossref / OpenAlex / arXiv / S2 / AMiner / CNKI).

    Concept filtering (OpenAlex [P1-2]):
      --concepts C1,C2         direct concept IDs (OR by default)
      --concept "name"         resolve name to ID via OpenAlex search
      --concept-mode and       require ALL specified concepts

    Examples:
      pa search "AI literacy" --concepts C154945302
      pa search "ChatGPT" --concepts C154945302,C2779384929 --concept-mode and
      pa search "transformer" --concept "machine learning"
    """
    from .search import run_search
    from .bibtex import write_bibtex
    from .concepts import resolve_concept_ids, build_concepts_filter, fetch_concept_metadata

    # Resolve concepts (if any) before searching
    raw_concepts = []
    if concept_ids:
        raw_concepts.extend(s.strip() for s in concept_ids.split(",") if s.strip())
    raw_concepts.extend(concept_names)

    resolved_ids: list = []
    resolved_meta: list = []
    if raw_concepts:
        resolved_ids, warnings = resolve_concept_ids(raw_concepts)
        if warnings:
            for w in warnings:
                click.echo(f"[pa] concept warning: {w['input']!r} -> {w['reason']}",
                           err=True)
        for cid in resolved_ids:
            meta = fetch_concept_metadata(cid)
            if meta:
                resolved_meta.append(meta)
                if not quiet:
                    click.echo(f"[pa] concept: {cid} = {meta['display_name']!r} "
                               f"(works={meta['works_count']:,})", err=True)
        if not resolved_ids:
            click.echo("[pa] no concepts resolved; running search without concept filter",
                       err=True)
    concepts_filter = build_concepts_filter(resolved_ids, mode=concept_mode)
    if not quiet:
        click.echo(f"[pa] search query={query!r} years={year_min}-{year_max} "
                   f"concepts={resolved_ids or 'none'} mode={concept_mode if resolved_ids else 'n/a'} "
                   f"format={out_format}", err=True)
    # [P1-17] Parse --source comma list
    src_list = None
    if source_filter:
        src_list = [s.strip() for s in source_filter.split(",") if s.strip()]
    results = run_search(query, year_min, year_max, limit, engine,
                         concepts_filter=concepts_filter or None,
                         enrich_top=enrich_top,
                         enrich_top_min_cites=enrich_top_min_cites,
                         sort_by=sort_by,
                         source_filter=src_list,
                         enrich_max_age_years=enrich_max_age_years)
    # [P2-14] Quality filter: flag/filter/off (default flag — annotates, doesn't drop)
    from .quality_filter import apply_quality_filter, summarize_quality
    pre_count = len(results.get("results", []))
    apply_quality_filter(results.get("results", []), mode=quality_mode)
    post_count = len(results.get("results", []))
    if quality_mode != "off" and not quiet:
        qs = summarize_quality(results.get("results", []))
        click.echo(f"[pa] quality: {qs} (mode={quality_mode}, kept {post_count}/{pre_count})", err=True)
    if quality_mode == "filter" and pre_count != post_count:
        results["dedup_count"] = post_count  # update reported count
    # Augment with concept metadata so user sees what was applied
    if resolved_meta:
        results["applied_concepts"] = resolved_meta
        results["concept_mode"] = concept_mode
    if not quiet:
        click.echo(f"[pa] by_engine: {results['by_engine']}", err=True)
        click.echo(f"[pa] dedup_count: {results['dedup_count']}", err=True)
    if out_format == "bibtex":
        # Determine default output path if none given
        if not output:
            safe_q = re.sub(r'[^A-Za-z0-9_-]+', '_', query)[:40]
            output = f"{safe_q}.bib"
        papers = results["results"]
        out_path = write_bibtex(papers, output)
        click.echo(f"[pa] wrote {len(papers)} BibTeX entries to {out_path}", err=True)
        if not quiet:
            click.echo(f"[pa] cite-key format: doi-stripped (e.g. 1186_s41239_023_00411_8)", err=True)
        return
    # Default: JSON
    out = json.dumps(results, indent=2, ensure_ascii=False)
    if output:
        Path(output).write_text(out, encoding="utf-8")
        click.echo(f"[pa] saved to {output}", err=True)
    else:
        click.echo(out)


@main.command()
@click.argument("corpus_dir", type=click.Path(exists=True, file_okay=False))
@click.option("--template", default="v32", show_default=True, help="Lit review template version")
@click.option("-o", "--output", default=None, help="Output markdown file (else stdout)")
@click.option("--word-count-min", type=int, default=1000, show_default=True,
              help="Min words extracted to count as full-text (else abstract-only)")
@click.option("--with-prisma", is_flag=True,
              help="Prepend a PRISMA 2020 flow diagram (auto-derived from corpus)")
@click.option("--quiet", is_flag=True, help="Suppress progress output")
def review(corpus_dir, template, output, word_count_min, with_prisma, quiet):
    """Synthesize lit review markdown from a corpus directory of PDFs.

    --with-prisma adds a PRISMA 2020 flow diagram at the top of the output,
    auto-derived from the corpus (identified=PDFs found, after-screening=
    full-text vs abstract-only by word_count_min).
    """
    from .review import synthesize
    corpus_path = Path(corpus_dir)
    if not quiet:
        click.echo(f"[pa] review corpus={corpus_path}", err=True)
        click.echo(f"[pa] word_count_min={word_count_min} template={template}", err=True)
        if with_prisma:
            click.echo(f"[pa] including PRISMA flow diagram", err=True)
    md = synthesize(corpus_path, template, word_count_min)
    if with_prisma:
        from .prisma import derive_counts_from_corpus, render_prisma
        counts = derive_counts_from_corpus(corpus_path, word_count_min)
        prisma_block = render_prisma(
            identified=counts["identified"],
            after_screening=counts["after_screening"],
            after_eligibility=counts["after_eligibility"],
            included=counts["included"],
            pdf_count=counts["pdf_count"],
            abstract_count=counts["abstract_count"],
        )
        md = f"{prisma_block}\n\n---\n\n{md}"
        if not quiet:
            click.echo(f"[pa] PRISMA: identified={counts['identified']} "
                       f"screened={counts['after_screening']} "
                       f"abstract_only={counts['abstract_count']}", err=True)
    if output:
        Path(output).write_text(md, encoding="utf-8")
        click.echo(f"[pa] saved {output}", err=True)
    else:
        click.echo(md)


@main.command()
@click.argument("corpus_dir", type=click.Path(exists=True, file_okay=False))
@click.option("-o", "--output", default=None,
              help="Output topics.json path (default: <corpus_dir>/topics.json)")
@click.option("--alpha", type=float, default=0.4, show_default=True,
              help="Weight on OpenAlex concept-Jaccard vs TF-IDF cosine (0..1)")
@click.option("--word-count-min", type=int, default=1000, show_default=True,
              help="Min words extracted to count as full-text (passed to review.build_corpus_index)")
@click.option("--label-method", default="auto", show_default=True,
              type=click.Choice(["auto", "ctfidf", "handroll", "custom"]),
              help="[P1-4 v3.8.0] Label generator to use")
@click.option("--custom-labels", default=None,
              help="[P1-4 v3.8.0] JSON dict {topic_id: label_str} to override auto labels. "
                   "E.g. '{\"1\": \"PPT 设计文档\", \"2\": \"PPT 内容来源\"}'")
@click.option("--domain-stopwords-file", default=None, type=click.Path(exists=True),
              help="[P1-4 v3.8.0] File with domain-specific stopwords (one per line). "
                   "If omitted, auto-mines from corpus.")
@click.option("--quiet", is_flag=True, help="Suppress progress output")
def review_topics(corpus_dir, output, alpha, word_count_min,
                  label_method, custom_labels, domain_stopwords_file, quiet):
    """Cluster corpus papers by topic (cross-paper synthesis prep, zero LLM).

    Algorithm (3-stage ensemble):
      1. Per-paper OpenAlex concept vectors
      2. TF-IDF on (title + abstract)
      3. Hybrid agglomerative clustering with silhouette-driven k selection

    Output: topics.json with clusters, keywords, top concepts, cohesion scores.
    For downstream narrative synthesis, feed this file (along with relations.json
    from `pa review relations`) to an LLM session — or read it yourself.

    [P1-4 v3.8.0 polish]
      --label-method: switch between ctfidf / handroll / custom generators
      --custom-labels: override topic labels with human-written names (highest priority)
      --domain-stopwords-file: extend c-TF-IDF stop_words with corpus-specific noise terms
    """
    from .topics import cluster_topics
    from .labels.domain_stopwords import load_domain_stopwords_file

    corpus_path = Path(corpus_dir)
    output_path = Path(output) if output else (corpus_path / "topics.json")

    # Parse custom_labels JSON (string → Dict[int, str])
    parsed_custom_labels = None
    if custom_labels:
        import json as _json
        try:
            raw = _json.loads(custom_labels)
            parsed_custom_labels = {int(k): str(v) for k, v in raw.items()}
        except (ValueError, TypeError) as e:
            raise click.BadParameter(
                f"custom-labels must be valid JSON dict like '{{\"1\": \"label\"}}': {e}"
            )

    # Load domain stopwords file
    parsed_domain_stopwords = None
    if domain_stopwords_file:
        parsed_domain_stopwords = load_domain_stopwords_file(Path(domain_stopwords_file))

    if not quiet:
        click.echo(f"[pa] review-topics corpus={corpus_path}", err=True)
        click.echo(f"[pa] alpha={alpha} word_count_min={word_count_min}", err=True)
        click.echo(f"[pa] label_method={label_method}", err=True)
        if parsed_custom_labels:
            click.echo(f"[pa] custom_labels={parsed_custom_labels}", err=True)
        if parsed_domain_stopwords:
            click.echo(f"[pa] domain_stopwords={len(parsed_domain_stopwords)} terms", err=True)
    result = cluster_topics(
        corpus_dir=corpus_path,
        output_path=output_path,
        alpha=alpha,
        word_count_min=word_count_min,
        label_method=label_method,
        custom_labels=parsed_custom_labels,
        domain_stopwords=parsed_domain_stopwords,
    )
    if not quiet:
        click.echo(
            f"[pa] n_papers={result['n_papers']} k={result['k']} "
            f"topics={len(result['topics'])} warnings={len(result['warnings'])}",
            err=True,
        )
        for w in result["warnings"][:5]:
            click.echo(f"[pa]   warn: {w}", err=True)
    click.echo(f"[pa] saved {output_path}", err=True)


@main.command()
@click.option("--identified", "identified", type=int, required=True,
              help="Total papers identified from search (PRISMA stage 1)")
@click.option("--after-screening", "after_screening", type=int, required=True,
              help="Papers remaining after title/abstract screening (stage 2)")
@click.option("--after-eligibility", "after_eligibility", type=int, required=True,
              help="Papers remaining after full-text eligibility check (stage 3)")
@click.option("--included", "included", type=int, required=True,
              help="Papers finally included in the review (stage 4)")
@click.option("--by-source", "by_source", default="",
              help='JSON dict of source→count, e.g. \'{"arxiv":15,"openalex":50}\'')
@click.option("--pdf", "pdf_count", type=int, default=0,
              help="Of included, how many are full-text PDFs")
@click.option("--abstract", "abstract_count", type=int, default=0,
              help="Of included, how many are abstract-only")
@click.option("--excluded-reasons", "excluded_reasons", default="",
              help='JSON dict of stage→excluded count, e.g. \'{"stage1":50,"stage2":30}\'')
@click.option("--format", "out_format", default="markdown", show_default=True,
              type=click.Choice(["markdown", "mermaid"]),
              help="Output: full markdown report (default) or just the mermaid block")
@click.option("-o", "--output", default=None, help="Save to file (else stdout)")
@click.option("--quiet", is_flag=True, help="Suppress progress output")
def prisma(identified, after_screening, after_eligibility, included,
          by_source, pdf_count, abstract_count, excluded_reasons,
          out_format, output, quiet):
    """Generate a PRISMA 2020 flow diagram (standalone).

    Use this for systematic-review journal submissions. Provide the 4
    count stages explicitly; the diagram auto-derives exclusions as the
    differences between stages. Output is a GitHub-renderable mermaid
    block (within a full markdown report by default).

    Examples:
      pa prisma --identified 287 --after-screening 57 \\
        --after-eligibility 57 --included 57 --pdf 25 --abstract 32
      pa prisma --identified 100 --after-screening 30 \\
        --after-eligibility 20 --included 15 \\
        --by-source '{"arxiv":40,"openalex":60}' --format mermaid
    """
    from .prisma import render_prisma, parse_json_arg
    by_source_d = parse_json_arg(by_source) if by_source else None
    excluded_d = parse_json_arg(excluded_reasons) if excluded_reasons else None
    if not quiet:
        click.echo(
            f"[pa] PRISMA: identified={identified} after_screening={after_screening} "
            f"after_eligibility={after_eligibility} included={included} "
            f"format={out_format}", err=True,
        )
    out = render_prisma(
        identified=identified,
        after_screening=after_screening,
        after_eligibility=after_eligibility,
        included=included,
        by_source=by_source_d,
        pdf_count=pdf_count,
        abstract_count=abstract_count,
        excluded_reasons=excluded_d,
        output_format=out_format,
    )
    if output:
        Path(output).write_text(out, encoding="utf-8")
        click.echo(f"[pa] saved {output}", err=True)
    else:
        click.echo(out)


# =============== cache subcommand group (P0-2, 2026-07-04) ===============

@main.group()
def cache():
    """Manage the local PDF + meta cache (~/.paper-agent/cache/).

    The cache avoids re-downloading PDFs across `pa fetch` calls. Each entry
    is a `<doi_slug>.pdf` + `<doi_slug>.meta.json` pair. After 7-day TTL
    (matches skill/core/api_pool/cache.py convention), entries are treated
    as miss on read; admin path is `pa cache clean --older-than 30d`.

    Subcommands: path / stats / clean / put / drop
    """


@cache.command("path")
def cache_path():
    """Show the cache root directory currently in use."""
    from .cache import get_cache_root
    root = get_cache_root()
    click.echo(str(root))


@cache.command("stats")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def cache_stats(as_json):
    """Show cache size / entry count / age distribution."""
    from .cache import cache_stats as _cache_stats_impl
    stats = _cache_stats_impl()
    if as_json:
        click.echo(json.dumps(stats, indent=2, ensure_ascii=False))
        return
    click.echo(f"Cache root:       {stats['root']}")
    click.echo(f"Total entries:    {stats['paper_count']} PDF(s) / "
               f"{stats['total_files']} total files")
    size_kb = stats['total_size_bytes'] / 1024
    if size_kb < 1024:
        click.echo(f"Total size:       {size_kb:.1f} KB ({stats['total_size_bytes']} bytes)")
    else:
        click.echo(f"Total size:       {size_kb/1024:.2f} MB ({stats['total_size_bytes']} bytes)")
    if stats.get("oldest_age_days") is not None:
        click.echo(f"Oldest entry:     {stats['oldest_age_days']:.1f} days ago")
        click.echo(f"Newest entry:     {stats['newest_age_days']:.1f} days ago")
    else:
        click.echo("Oldest entry:     (empty cache)")
        click.echo("Newest entry:     (empty cache)")


@cache.command("clean")
@click.option("--older-than", "older_than_days", type=int, default=None,
              metavar="N", help="Remove entries older than N days")
@click.option("--all", "purge_all", is_flag=True,
              help="Remove ALL entries (equivalent to --older-than 0)")
@click.option("--dry-run", is_flag=True,
              help="Print what would be removed without actually deleting")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def cache_clean(older_than_days, purge_all, dry_run, as_json):
    """Remove cache entries. Default: requires --older-than or --all.

    Examples:
      pa cache clean --older-than 30d
      pa cache clean --all
      pa cache clean --all --dry-run
    """
    from .cache import cache_clean as _cache_clean_impl, cache_stats as _cache_stats_impl
    if purge_all:
        older_than_days = older_than_days if older_than_days is not None else 0
    if older_than_days is None:
        click.echo("Refusing to clean: spec --older-than Nd OR --all", err=True)
        sys.exit(2)
    if dry_run:
        stats = _cache_stats_impl()
        click.echo(f"[dry-run] would remove entries older than {older_than_days}d")
        click.echo(f"[dry-run] currently {stats['paper_count']} entries, "
                   f"oldest {stats.get('oldest_age_days'):.1f}d" if stats.get('oldest_age_days')
                   else f"[dry-run] currently {stats['paper_count']} entries")
        click.echo("[dry-run] use without --dry-run to actually delete")
        sys.exit(0)
    result = _cache_clean_impl(older_than_days=older_than_days)
    if as_json:
        click.echo(json.dumps(result, indent=2, ensure_ascii=False))
        return
    click.echo(f"Removed:  {result['removed_files']} file(s)")
    click.echo(f"Freed:    {result['freed_bytes']} bytes ({result['freed_bytes']/1024:.1f} KB)")
    click.echo(f"Remaining: {result['remaining_papers']} PDF(s) in {result['remaining_files']} total files")


@cache.command("put")
@click.argument("doi")
@click.argument("pdf_path", type=click.Path(exists=True, dir_okay=False))
@click.option("--channel", default="manual", show_default=True,
              help="Channel name to record in meta (e.g. 'openalex', 'manual')")
@click.option("--url", default="", help="Originating URL to record in meta")
def cache_put(doi, pdf_path, channel, url):
    """Manually insert a PDF into cache (e.g. for offline-routed downloads)."""
    from .cache import cache_put as _cache_put_impl
    body = Path(pdf_path).read_bytes()
    try:
        entry = _cache_put_impl(doi, body, channel=channel, url=url)
    except ValueError as e:
        click.echo(f"[pa-cache] ❌ {e}", err=True)
        sys.exit(2)
    click.echo(f"[pa-cache] ✅ cached {doi}")
    click.echo(f"  pdf:  {entry['pdf_path']}")
    click.echo(f"  meta: {entry['meta_path']}")
    click.echo(f"  sha256: {entry['sha256'][:16]}...  size: {entry['size']}")


@cache.command("drop")
@click.argument("doi")
def cache_drop(doi):
    """Remove a single entry from cache."""
    from .cache import cache_remove
    if cache_remove(doi):
        click.echo(f"[pa-cache] ✅ dropped {doi}")
    else:
        click.echo(f"[pa-cache] nothing to drop for {doi} (no entry found)")


@main.group()
def mcp():
    """Integrate paper-agent with a public MCP server.

    Self-hosted `pa mcp-serve` was removed 2026-07-04 (see ROADMAP [P0-3]
    Deprecated). Use the public `paper-search-mcp` (PyPI) instead — this
    subcommand group helps you install it and prints the JSON config block
    to paste into your MCP client.

    Subcommands: install / config / serve-deprecated
    """


@mcp.command("install")
@click.option("--uvx", "use_uvx", is_flag=True,
              help="Use uvx (no install) instead of pip")
@click.option("--dry-run", is_flag=True,
              help="Don't actually run pip; just print what would happen")
def mcp_install(use_uvx, dry_run):
    """Install the public paper-search-mcp package and print config block.

    Default: `python -m pip install --user paper-search-mcp`
    Falls back to: print `uvx` command if pip install fails.

    Does NOT auto-edit your MCP client config. Prints the JSON block
    for you to paste (per Global Rule: user sovereignty over their own
    config files).
    """
    from .mcp_setup import install as _install
    result = _install(use_uvx=use_uvx, dry_run=dry_run)
    if result["status"] == "install_failed":
        click.echo(f"\n[pa-mcp] FAILED to install via pip. Try: pa mcp install --uvx",
                   err=True)
        sys.exit(1)


@mcp.command("config")
def mcp_config():
    """Print the JSON config block for your MCP client (no install)."""
    from .mcp_setup import _print_config_block
    _print_config_block(method="pip")


@mcp.command("serve-deprecated")
def mcp_serve_deprecated():
    """DEPRECATED 2026-07-04: removed. Use `pa mcp install` instead.

    Original `pa mcp-serve` self-hosted the MCP server. That was reverted
    per the Global Rule (one-hobbyist maintenance budget). For academic
    paper search via MCP, run `pa mcp install` to set up paper-search-mcp.
    """
    click.echo(
        "[pa] mcp-serve was removed 2026-07-04. "
        "Use `pa mcp install` to set up paper-search-mcp (PyPI).",
        err=True,
    )
    sys.exit(1)


@main.command()
def mcp_serve():
    """DEPRECATED: shim that points to `pa mcp install` (kept for grep-ability).

    See `pa mcp --help` for the new subcommand group.
    """
    click.echo(
        "[pa] `pa mcp-serve` was removed 2026-07-04. Use `pa mcp install` instead.\n"
        "  pip install paper-search-mcp  (or `pa mcp install` to do it + print config)\n"
        "  See `pa mcp --help` for the new subcommand group.",
        err=True,
    )
    sys.exit(1)


# =============== CNKI subcommand group (P0-9, added 2026-07-15) ===============

@main.group()
def cnki():
    """CNKI 6th search engine (Chinese papers, optional).

    Per ROADMAP [P0-9] (added 2026-07-14, skeleton in v3.9.7.3):
    - Adds Chinese-paper coverage (0% → ~15-25% on Chinese queries)
    - User-maintained cookies (4-8h proxy session TTL)
    - NOT through clash proxy (CNKI 国内站, user 用"其他代理")

    Subcommands: status / setup / search
    """


@cnki.command("status")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def cnki_status(as_json):
    """Check CNKI channel readiness (cookies, playwright, TTL)."""
    from .cnki_channel import status_report
    s = status_report()
    if as_json:
        click.echo(json.dumps(s, indent=2, ensure_ascii=False))
        return
    marker = "[OK]" if s["ready_for_search"] else "[WARN]"
    click.echo(f"{marker} CNKI channel status (v{s['version']})")
    click.echo(f"  cookies_path:           {s['cookies_path']}")
    click.echo(f"  cookies_exist:          {s['cookies_exist']}")
    if s["cookie_age_hours"] is not None:
        click.echo(f"  cookie_age_hours:       {s['cookie_age_hours']:.1f}h "
                   f"(max {s['max_cookie_age_hours']:.1f}h)")
    else:
        click.echo(f"  cookie_age_hours:       (no file)")
    click.echo(f"  n_cookies:              {s['n_cookies']}")
    click.echo(f"  playwright_installed:   {s['playwright_installed']}")
    click.echo(f"  search_implemented:     {s['search_implemented']} (v3.9.7.6 close-out: cite/dl deprecated, see ROADMAP [P0-9.1b])")
    click.echo(f"  cite/dl:                None (deprecated per [P0-9.1b]; 5 paths blocked)")
    click.echo(f"                          see CHANGELOG v3.9.7.6 for honest audit")
    click.echo()
    if not s["ready_for_search"]:
        click.echo(f"[pa-cnki] {s['next_action']}", err=True)
    else:
        click.echo("[pa-cnki] ready (cookies fresh + playwright installed)", err=True)


@cnki.command("setup")
def cnki_setup():
    """Print CNKI setup instructions (proxy + cookies + Export script).

    Per ROADMAP [P0-9] "User confirmation needed" list:
    - 代理类型 (校园 VPN / EZproxy / 机构图书馆代理)
    - 代理登录 session 实际过期时间
    - cookies 维护自动化
    """
    click.echo("[pa-cnki] Setup instructions for CNKI 6th engine")
    click.echo()
    click.echo("STEP 1: Provide proxy access")
    click.echo("  - 校园 VPN / EZproxy / 机构图书馆代理")
    click.echo("  - 必须能访问 CNKI hostname (www.cnki.net)")
    click.echo("  - 不能走 clash (CNKI 反爬可能检测到 proxy 流量)")
    click.echo()
    click.echo("STEP 2: Manual cookies export (one-time setup)")
    click.echo("  - 用 Chrome / Edge 登录代理入口")
    click.echo("  - 跳转 CNKI 后, 跑 Export-CNKICookies.ps1 (待写)")
    click.echo("  - script 导出 cookies 到:")
    click.echo("    ~/.paper-agent\\cookies\\cnki.json")
    click.echo()
    click.echo("STEP 3: Verify")
    click.echo("  $ pa cnki status")
    click.echo("  $ pa search \"东数西算\" --engine cnki")
    click.echo()
    click.echo("Cookie TTL: 4-8 hours (proxy session)")
    click.echo("  - 每天 user 重跑一次 export script")
    click.echo("  - 或设置 Windows 任务计划每日自动跑 (TODO)")
    click.echo()
    click.echo("Per ROADMAP [P0-9] status: skeleton code ready (v3.9.7.3)")
    click.echo("Real playwright + HTML parser will be wired in after you provide proxy + cookies.")


@cnki.command("search")
@click.argument("query")
@click.option("--limit", type=int, default=10, show_default=True,
              help="Max results to return (1-100)")
@click.option("--year-min", type=int, default=None,
              help="Earliest year filter (CNKI may not honor in simple search)")
@click.option("--year-max", type=int, default=None,
              help="Latest year filter (CNKI may not honor in simple search)")
@click.option("--field", "field", default="subject", show_default=True,
              type=click.Choice(["subject", "title", "keyword", "tka", "abstract",
                                 "fulltext", "author", "affiliation"]),
              help="Search field")
@click.option("--db", "db", default="all", show_default=True,
              type=click.Choice(["all", "journal", "thesis", "book", "conference",
                                 "newspaper", "almanac", "patent", "standard",
                                 "law", "achievement"]),
              help="CNKI database to search")
@click.option("--format", "out_format", default="summary", show_default=True,
              type=click.Choice(["json", "summary"]))
def cnki_search(query, limit, year_min, year_max, field, db, out_format):
    """Search CNKI directly (v3.9.7.4 real search).

    Examples:
        pa cnki search "东数西算"
        pa cnki search "保险精算" --field title --limit 5
        pa cnki search "深度学习" --db journal --limit 10
    """
    from .cnki_channel import search_cnki
    results = search_cnki(query, year_min=year_min, year_max=year_max,
                         limit=limit, field=field, db=db)
    if not results:
        click.echo("[pa-cnki] No results returned", err=True)
        sys.exit(1)
    # If first result is an error dict, surface it
    if "error" in results[0]:
        click.echo(f"[pa-cnki] {results[0]['error']}: {results[0].get('message', '')}",
                  err=True)
        if results[0].get("hint"):
            click.echo(f"  Hint: {results[0]['hint']}", err=True)
        sys.exit(2)
    if out_format == "summary":
        click.echo(f"Found {len(results)} results for query: {query!r}")
        click.echo(f"  field={field}, db={db}, limit={limit}")
        click.echo()
        for i, r in enumerate(results):
            click.echo(f"[{i+1}] {r.get('title', '?')[:60]}")
            click.echo(f"    venue: {r.get('venue', '?')}, year: {r.get('year', '?')}, "
                      f"type: {r.get('type', '?')}, db_type: {r.get('db_type', '?')}")
            authors = r.get('authors', [])
            if authors:
                click.echo(f"    authors: {', '.join(authors[:3])}"
                          + (" ..." if len(authors) > 3 else ""))
            click.echo(f"    cnki_url: {r.get('cnki_url', '?')[:100]}")
            click.echo()
    else:
        click.echo(json.dumps(results, indent=2, ensure_ascii=False))


@main.command()
@click.argument("doi")
@click.option("--direction", "direction",
              type=click.Choice(["forward", "backward"]),
              default="forward", show_default=True,
              help="forward = papers that cite <DOI>; backward = papers <DOI> cites")
@click.option("--limit", default=100, show_default=True, type=int,
              help="Max papers to return (forward default 100; backward 50 recommended)")
@click.option("--save-bib", "save_bib_path", default=None, metavar="PATH",
              help="Also write BibTeX to this path")
@click.option("-o", "--output", default=None, metavar="PATH",
              help="Save JSON result to this path (else stdout)")
@click.option("--quiet", is_flag=True, help="Suppress progress output")
def citations(doi, direction, limit, save_bib_path, output, quiet):
    """Walk citation graph via OpenAlex.

    Examples:
      pa citations 10.1186/s41239-023-00411-8 --direction forward --limit 20
      pa citations 10.1186/s41239-023-00411-8 --direction backward --limit 50
      pa citations 10.1186/s41239-023-00411-8 --save-bib crompton_citers.bib

    forward = "who cites this paper?"
      Cursor-paginated; bounded by --limit.

    backward = "what does this paper cite?"
      Resolves DOI -> referenced_works[] via OpenAlex, fetches each.
      N+1 API calls (one per reference). Use --limit wisely (default 100,
      but recommend 50 since each ref = a separate HTTP request).

    Requires OPENALEX_API_KEY env var for higher rate limit (1 RPS free, faster
    with key). Without key, the walk still works but slower.
    """
    import json as _json
    from .citations import citation_walk
    from .bibtex import write_bibtex
    if not quiet:
        click.echo(f"[pa] citations doi={doi} direction={direction} limit={limit}", err=True)
    result = citation_walk(doi, direction=direction, limit=limit)
    if result.get("error"):
        click.echo(f"[pa] error: {result['error']}", err=True)
        click.echo(_json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(2)
    if not quiet:
        click.echo(f"[pa] source: {result['source_work'].get('title', '')[:80]!r}", err=True)
        click.echo(f"[pa] fetched {result['count']} papers (truncated={result['truncated']})", err=True)
    out_json = _json.dumps(result, indent=2, ensure_ascii=False)
    if output:
        Path(output).write_text(out_json, encoding="utf-8")
        click.echo(f"[pa] saved JSON to {output}", err=True)
    else:
        click.echo(out_json)
    if save_bib_path:
        write_bibtex(result["results"], save_bib_path)
        click.echo(f"[pa] saved BibTeX ({result['count']} entries) to {save_bib_path}", err=True)


@main.command()
@click.option("-i", "--input", "input_file", required=True,
              type=click.Path(exists=True, dir_okay=False),
              help="Text file with one query per line (DOI or title)")
@click.option("-o", "--output", default="batch_download_guide.md",
              type=click.Path(dir_okay=False),
              help="Output markdown guide (default: ./batch_download_guide.md)")
@click.option("--year-min", type=int, default=None,
              help="Filter: min publication year")
@click.option("--year-max", type=int, default=None,
              help="Filter: max publication year")
@click.option("--quiet", is_flag=True, help="Suppress per-paper progress output")
def fetch_batch(input_file, output, year_min, year_max, quiet):
    """Generate a batch download guide for CNKI PDF (semi-automated, v3.9.8.3).

    Input: a text file with one query per line. Each line can be either:
      - a DOI (e.g. 10.3969/j.issn.1003-9031.2022.04.008)
      - a title  (e.g. 数字普惠金融对经济高质量发展的影响)

    Output: a markdown guide with:
      - Per-paper table (title, DOI, year, found status, xueshu789 search URL)
      - An Edge console JS snippet that auto-scrapes doDownload URLs from
        xueshu789 search result pages
      - Step-by-step instructions for user (the actual PDF download must be
        done in user's real Edge browser to bypass bar.cnki.net vLevel=5
        CAPTCHA)

    Honest limitation: paper-agent cannot auto-download CNKI PDFs because
    bar.cnki.net detects all non-real-browser automation and triggers
    vLevel=5 CAPTCHA. This tool's value is in:
      1. Validating that DOIs exist (skip non-existent papers)
      2. Generating per-paper search URLs for xueshu789
      3. Providing the Edge console snippet for batch doDownload URL extraction
    User's manual Edge workflow is the only working path (verified 2026-07-15).
    """
    from pathlib import Path
    from .batch_fetch import generate_guide

    input_path = Path(input_file)
    output_path = Path(output)
    queries = [line.strip() for line in input_path.read_text(encoding="utf-8").splitlines()
               if line.strip() and not line.strip().startswith("#")]
    if not queries:
        click.echo("[pa] no queries in input file", err=True)
        sys.exit(1)
    if not quiet:
        click.echo(f"[pa] {len(queries)} queries from {input_file}", err=True)
    summary = generate_guide(queries, output_path,
                            year_min=year_min, year_max=year_max)
    if not quiet:
        click.echo(f"[pa] {summary['n_found']}/{summary['n_total']} papers metadata found", err=True)
        click.echo(f"[pa] {summary['n_not_found']} not found (likely Chinese-only, not in OpenAlex/Crossref)", err=True)
        click.echo(f"[pa] guide saved to {summary['output']}", err=True)
        click.echo("", err=True)
        click.echo("[pa] Next: open the guide and follow the Edge workflow", err=True)


if __name__ == "__main__":
    main()


# =============== [P2-5] build + scaffold subcommands ===============
# Appended at end of file (rather than inserted in middle) to minimize diff
# against v3.9.8.4 baseline. Both are part of v3.9.9 release.

@main.command()
@click.argument("bibtex_file", type=click.Path(exists=True, dir_okay=False))
@click.option("--skeleton", "skeleton_file", required=True,
              type=click.Path(exists=True, dir_okay=False),
              help="Markdown skeleton with [@bibkey] or [cite: bibkey] placeholders")
@click.option("-o", "--output", required=True, type=click.Path(dir_okay=False),
              help="Output file. Suffix determines format: .html / .docx / .pdf / .tex / .md")
@click.option("--csl", "csl_file", default=None,
              type=click.Path(exists=True, dir_okay=False),
              help="Citation style (CSL). Default: bundled chinese-gb7714-2005-numeric.csl")
@click.option("--format", "out_format", default=None,
              help="Override format detection (html / docx / pdf / tex / md / epub / odt / rtf)")
@click.option("--pdf-engine", default=None,
              help="Force a specific PDF engine (xelatex / pdflatex / lualatex / weasyprint). "
                   "Auto-detected by default. xelatex is best for CJK (Chinese).")
@click.option("--pandoc-arg", "extra_args", multiple=True,
              help="Passthrough extra pandoc CLI arg (repeatable, e.g. --pandoc-arg=-V --pandoc-arg=geometry:margin=2cm)")
@click.option("--quiet", is_flag=True, help="Suppress progress output")
def build(bibtex_file, skeleton_file, output, csl_file, out_format,
          pdf_engine, extra_args, quiet):
    """[P2-5] Typeset manuscript from Bibtex + markdown skeleton via pandoc.

    Per ROADMAP "Writing pipeline": paper-agent handles scaffold + typeset;
    prose is Mavis's job. This command is the typeset half.

    Typical flow:
      1. pa search "topic" --format bibtex --out refs.bib
      2. (optionally) pa scaffold refs.bib --out skeleton.md
      3. (user / Mavis) fill in prose between [cite: key] placeholders
      4. pa build refs.bib --skeleton manuscript.md --out manuscript.html

    Output formats and required engines:
      .html / .docx / .tex / .md / .epub / .odt / .rtf  -> no engine needed
      .pdf                                                -> xelatex / pdflatex / weasyprint
                                                            (xelatex recommended for CJK)

    Examples:
      pa build refs.bib --skeleton ms.md --out ms.html
      pa build refs.bib --skeleton ms.md --out ms.pdf
      pa build refs.bib --skeleton ms.md --out ms.pdf --pdf-engine xelatex
      pa build refs.bib --skeleton ms.md --csl my-style.csl --out ms.docx
    """
    from .build import build as _build, DEFAULT_CSL
    bib_path = Path(bibtex_file)
    skel_path = Path(skeleton_file)
    out_path = Path(output)
    csl_path = Path(csl_file) if csl_file else DEFAULT_CSL
    fmt = out_format
    extras = list(extra_args) if extra_args else None
    if not quiet:
        click.echo(f"[pa build] bib={bib_path.name} skeleton={skel_path.name} "
                   f"csl={csl_path.name if csl_path else 'default'}",
                   err=True)
    try:
        result = _build(
            bibtex_path=bib_path,
            skeleton_path=skel_path,
            output_path=out_path,
            csl_path=csl_path,
            output_format=fmt,
            pdf_engine=pdf_engine,
            extra_args=extras,
            quiet=quiet,
        )
    except Exception as e:
        click.echo(f"[pa build] FAILED: {e}", err=True)
        sys.exit(2)
    if not quiet:
        click.echo(f"[pa build] saved {result}", err=True)


@main.command()
@click.argument("bibtex_file", type=click.Path(exists=True, dir_okay=False))
@click.option("--group-by", default="year", show_default=True,
              type=click.Choice(["year", "topic", "author", "none"]),
              help="How to section the skeleton: by publication year, by topic cluster, "
                   "by first author, or no grouping (one big list)")
@click.option("--topics", "topics_file", default=None,
              type=click.Path(exists=True, dir_okay=False),
              help="topics.json from `pa review-topics` (required if --group-by topic)")
@click.option("--title", default="文献综述", show_default=True,
              help="Top-level skeleton title (markdown H1)")
@click.option("-o", "--output", default=None, type=click.Path(dir_okay=False),
              help="Output file (else stdout)")
@click.option("--quiet", is_flag=True, help="Suppress progress output")
def scaffold(bibtex_file, group_by, topics_file, title, output, quiet):
    """[P2-5] Generate markdown outline skeleton from Bibtex.

    Per ROADMAP "Writing pipeline": this is the scaffold half. Outputs:
      - Section headings (H1 / H2 / H3)
      - Per-paper [@bibkey] cite placeholders
      - Inline `> prompt: ...` blocks that tell Mavis (or the user) what
        kind of paragraph to write for each section

    The output is NOT prose. It's an outline + breadcrumb prompts. Fill in
    the prose, then run `pa build` to typeset the result.

    Examples:
      pa scaffold refs.bib > skeleton.md
      pa scaffold refs.bib --group-by year --out skeleton.md
      pa scaffold refs.bib --group-by topic --topics topics.json --out skeleton.md
      pa scaffold refs.bib --group-by author --title "数字普惠金融综述" --out skel.md
    """
    from .scaffold import scaffold as _scaffold
    bib_path = Path(bibtex_file)
    out_path = Path(output) if output else None
    topics_path = Path(topics_file) if topics_file else None
    if not quiet:
        click.echo(f"[pa scaffold] bib={bib_path.name} group_by={group_by} "
                   f"topics={topics_path.name if topics_path else 'N/A'}",
                   err=True)
    try:
        md = _scaffold(
            bibtex_path=bib_path,
            group_by=group_by,
            topics_path=topics_path,
            title=title,
            output_path=out_path,
        )
    except Exception as e:
        click.echo(f"[pa scaffold] FAILED: {e}", err=True)
        sys.exit(2)
    if not out_path:
        click.echo(md)
    elif not quiet:
        click.echo(f"[pa scaffold] saved {out_path}", err=True)


# =============== [P2-7] cite-check subcommand ===============
# Pre-build validator: scan markdown skeleton for [@key] placeholders, cross-ref
# against Bibtex, report 3 buckets (missing / typo'd / orphan).
# Solves user pain: today `pa build` failure with "undefined reference" gives
# the wrong key but not the file/line.

@main.command(name="cite-check")
@click.argument("bibtex_file", type=click.Path(exists=True, dir_okay=False))
@click.argument("skeleton_file", type=click.Path(exists=True, dir_okay=False))
@click.option("--json", "as_json", is_flag=True, help="Output as JSON (machine-readable)")
@click.option("--strict", is_flag=True, help="Exit 1 if any missing or typo'd (CI-friendly)")
def cite_check(bibtex_file, skeleton_file, as_json, strict):
    """[P2-7] Pre-build validator: scan skeleton for [@key] placeholders.

    Per ROADMAP [P2-7]: cross-references every `[@bibkey]` placeholder in a
    markdown skeleton against a Bibtex file. Reports 3 buckets:
      - [MISSING]  placeholder has no bib entry
      - [TYPOED]   placeholder has a near match (edit distance 1-2)
      - [ORPHAN]   bib entry is never cited in the skeleton

    Use this BEFORE `pa build` to catch citation errors with line numbers,
    not just "undefined reference" without context.

    Examples:
      pa cite-check refs.bib skeleton.md
      pa cite-check refs.bib skeleton.md --json | jq .missing
      pa cite-check refs.bib skeleton.md --strict  # exit 1 on missing/typo
    """
    from .cite_check import run_cite_check
    bib_path = Path(bibtex_file)
    skel_path = Path(skeleton_file)
    try:
        result, report = run_cite_check(bib_path, skel_path, output_json=as_json)
    except Exception as e:
        click.echo(f"[pa cite-check] FAILED: {e}", err=True)
        sys.exit(2)
    click.echo(report)
    if strict and (result['missing'] or result['typoed']):
        sys.exit(1)


# =============== [P2-8] export-screening subcommand ===============
# Bibtex (+ optional pa judge data) → systematic-review CSV ready for
# Notion / Excel / RevMan / Covidence import.

@main.command(name="export-screening")
@click.argument("bibtex_file", type=click.Path(exists=True, dir_okay=False))
@click.option("--out", "out_file", required=True, type=click.Path(dir_okay=False),
              help="Output CSV file path")
@click.option("--judges", "judges_db", default=None, type=click.Path(exists=True, dir_okay=False),
              help="Optional pa judge sqlite db (default: ~/.paper-agent/judgements.sqlite). "
                   "If not given, only bib metadata is exported (relevance=empty).")
@click.option("--query", default=None,
              help="Filter to a single pa judge query (default: all queries)")
@click.option("--no-unrated", is_flag=True,
              help="Skip bib papers that have NO judge data (default: include them as empty rows)")
def export_screening(bibtex_file, out_file, judges_db, query, no_unrated):
    """[P2-8] Export Bibtex (+ optional judge data) to screening CSV.

    Per ROADMAP [P2-8]: produces a CSV with one row per (paper, query) pair,
    joined with bib metadata. Columns:
      paper_key, query, relevance, reason, source,
      title, authors, year, venue, doi, abstract, type, bib_url

    Pluggable into Notion (csv import), Excel (utf-8), RevMan (CSV), or
    Covidence (CSV). UTF-8 with BOM (utf-8-sig) for Excel compatibility.

    Examples:
      pa export-screening refs.bib --out screening.csv
      pa export-screening refs.bib --out screening.csv --no-unrated
      pa export-screening refs.bib --judges judgements.sqlite --query "AI literacy" --out lit.csv
    """
    from .export_screening import run_export_screening
    bib_path = Path(bibtex_file)
    out_path = Path(out_file)
    judges_path = Path(judges_db) if judges_db else None
    try:
        result = run_export_screening(
            bib_path=bib_path,
            out_path=out_path,
            judges_db=judges_path,
            query=query,
            include_unrated=not no_unrated,
        )
    except Exception as e:
        click.echo(f"[pa export-screening] FAILED: {e}", err=True)
        sys.exit(2)
    click.echo(
        f"[pa export-screening] bib={result['n_bib_papers']} papers, "
        f"judge_rows={result['n_judge_rows']}, unrated={result['n_unrated']}, "
        f"wrote {result['n_csv_rows']} rows → {result['out_path']}",
        err=True,
    )


# =============== [P2-9] search-saved subcommand group ===============
# Named search presets with parameter snapshots. Re-run `pa search` without
# retyping all the flags.

@main.group()
def search_saved():
    """[P2-9] Manage named search presets (list/run/add/del/edit).

    Per ROADMAP [P2-9]: stores named search presets at
    ~/.paper-agent/saved_searches.json. Each preset is a dict of all
    `pa search` flags. Re-run without retyping:
        pa search-saved run <name>

    Subcommands:
      list                   - list all saved searches
      run <name>             - re-run a saved search
      add <name> --query Q   - create a new saved search
      del <name>             - delete a saved search
      edit <name> [flags]    - update an existing saved search
    """
    pass


@search_saved.command(name="list")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def search_saved_list(as_json):
    """List all saved searches."""
    from .search_saved import list_all, DEFAULT_PATH
    rows = list_all(DEFAULT_PATH)
    if as_json:
        click.echo(json.dumps(rows, indent=2, ensure_ascii=False))
        return
    if not rows:
        click.echo(f"(no saved searches; use `pa search-saved add <name>` to create one)")
        return
    click.echo(f"Saved searches ({len(rows)}) at {DEFAULT_PATH}:")
    click.echo("")
    click.echo(f"  {'NAME':<30s} {'#FLAGS':>7s}  QUERY")
    click.echo(f"  {'-'*30} {'-'*7}  {'-'*50}")
    for r in rows:
        q = r['query'][:50] if r['query'] else '(no query)'
        click.echo(f"  {r['name']:<30s} {r['n_flags']:>7d}  {q}")


@search_saved.command(name="add")
@click.argument("name")
@click.option("--query", required=True, help="Search query string")
@click.option("--year-min", type=int, default=None)
@click.option("--year-max", type=int, default=None)
@click.option("--engine", default=None, help="Comma-separated engine list (default: all)")
@click.option("--limit", type=int, default=None, help="Max results per engine (default: 50)")
@click.option("--concepts", default=None, help="OpenAlex concept IDs, comma-separated")
@click.option("--concept", default=None, help="Concept name(s) to resolve")
@click.option("--concept-mode", default=None, type=click.Choice(["or", "and"]))
@click.option("--enrich-top", type=int, default=None)
@click.option("--enrich-top-min-cites", type=int, default=None)
@click.option("--enrich-max-age-years", type=int, default=None)
@click.option("--sort-by", default=None, type=click.Choice(["cite", "year", "relevance"]))
@click.option("--source", default=None, help="Post-filter to specific engines")
def search_saved_add(name, query, year_min, year_max, engine, limit, concepts,
                     concept, concept_mode, enrich_top, enrich_top_min_cites,
                     enrich_max_age_years, sort_by, source):
    """Create a new saved search."""
    from .search_saved import add, DEFAULT_PATH
    flags = {
        'year_min': year_min, 'year_max': year_max, 'engine': engine,
        'limit': limit, 'concepts': concepts, 'concept': concept,
        'concept_mode': concept_mode, 'enrich_top': enrich_top,
        'enrich_top_min_cites': enrich_top_min_cites,
        'enrich_max_age_years': enrich_max_age_years,
        'sort_by': sort_by, 'source': source,
    }
    try:
        entry = add(name, query, DEFAULT_PATH, **flags)
    except (ValueError, FileExistsError) as e:
        click.echo(f"[pa search-saved add] FAILED: {e}", err=True)
        sys.exit(1)
    click.echo(f"[pa search-saved add] saved {name!r} to {DEFAULT_PATH}", err=True)


@search_saved.command(name="del")
@click.argument("name")
def search_saved_del(name):
    """Delete a saved search."""
    from .search_saved import delete, DEFAULT_PATH
    if delete(name, DEFAULT_PATH):
        click.echo(f"[pa search-saved del] deleted {name!r}", err=True)
    else:
        click.echo(f"[pa search-saved del] {name!r} not found", err=True)
        sys.exit(1)


@search_saved.command(name="edit")
@click.argument("name")
@click.option("--query", default=None, help="New query (replaces existing)")
@click.option("--year-min", type=int, default=None)
@click.option("--year-max", type=int, default=None)
@click.option("--engine", default=None)
@click.option("--limit", type=int, default=None)
@click.option("--sort-by", default=None, type=click.Choice(["cite", "year", "relevance"]))
def search_saved_edit(name, query, year_min, year_max, engine, limit, sort_by):
    """Update an existing saved search (only specified flags change)."""
    from .search_saved import update, DEFAULT_PATH
    flags = {
        'query': query, 'year_min': year_min, 'year_max': year_max,
        'engine': engine, 'limit': limit, 'sort_by': sort_by,
    }
    try:
        update(name, DEFAULT_PATH, **flags)
    except (ValueError, KeyError) as e:
        click.echo(f"[pa search-saved edit] FAILED: {e}", err=True)
        sys.exit(1)
    click.echo(f"[pa search-saved edit] updated {name!r}", err=True)


@search_saved.command(name="run")
@click.argument("name")
@click.option("-o", "--output", default=None, type=click.Path(dir_okay=False),
              help="Optional output file path (.json or .bib)")
@click.option("--quiet", is_flag=True, help="Suppress progress output")
def search_saved_run(name, output, quiet):
    """Re-run a saved search with its stored flags."""
    from .search_saved import get, to_pa_args, DEFAULT_PATH
    entry = get(name, DEFAULT_PATH)
    if entry is None:
        click.echo(f"[pa search-saved run] {name!r} not found", err=True)
        sys.exit(1)
    if not entry.get('query'):
        click.echo(f"[pa search-saved run] {name!r} has no query field", err=True)
        sys.exit(1)
    # Call the search command programmatically
    # We need to convert stored flags → kwargs for search() function
    from .cli import search as search_cmd
    args = to_pa_args(name, DEFAULT_PATH)
    if not quiet:
        click.echo(f"[pa search-saved run] {name!r}: query={args['query']!r}, "
                   f"engine={args.get('engine', 'all')}, year_min={args.get('year_min')}, "
                   f"year_max={args.get('year_max')}, limit={args.get('limit', 50)}",
                   err=True)
    try:
        search_cmd(
            query=args['query'],
            year_min=args.get('year_min'),
            year_max=args.get('year_max'),
            limit=args.get('limit', 50),
            engine=args.get('engine', 'all'),
            out_format=args.get('format', 'json'),
            output=output,
            concept_ids=args.get('concepts'),
            concept_names=args.get('concept'),
            concept_mode=args.get('concept_mode', 'or'),
            enrich_top=args.get('enrich_top', 0),
            enrich_top_min_cites=args.get('enrich_top_min_cites', 1),
            enrich_max_age_years=args.get('enrich_max_age_years', 10),
            sort_by=args.get('sort_by', 'cite'),
            source_filter=args.get('source'),
            quiet=quiet,
        )
    except SystemExit as e:
        # search() may call sys.exit on its own errors; re-raise to let click handle
        raise
    except Exception as e:
        click.echo(f"[pa search-saved run] FAILED: {e}", err=True)
        sys.exit(2)


# =============== [P2-10] dedup-strict subcommand ===============
# Stricter dedup than default DOI-only: catches fuzzy title, same-author+year,
# same-arxiv across venues. Uses difflib.SequenceMatcher (no new deps).

@main.command(name="dedup-strict")
@click.argument("bibtex_file", type=click.Path(exists=True, dir_okay=False))
@click.option("-o", "--output", "out_file", required=True, type=click.Path(dir_okay=False),
              help="Output deduped Bibtex file")
@click.option("--report", "report_file", default=None, type=click.Path(dir_okay=False),
              help="Optional JSON report of duplicate groups (for review)")
@click.option("--fuzzy-threshold", type=float, default=0.85, show_default=True,
              help="SequenceMatcher ratio for title fuzzy match (0.0-1.0)")
def dedup_strict(bibtex_file, out_file, report_file, fuzzy_threshold):
    """[P2-10] Stricter Bibtex dedup with fuzzy title matching.

    Per ROADMAP [P2-10]: catches near-duplicates that default DOI-only
    dedup misses:
      - Fuzzy title match (difflib.SequenceMatcher ratio >= 0.85)
      - Same first author + same year (cross-DOI merge)
      - Same arxiv-ID (cross-venue merge)
    Reuses pa_cli/scaffold.py:parse_bibtex for parsing.

    Examples:
      pa dedup-strict refs.bib --out deduped.bib
      pa dedup-strict refs.bib --out deduped.bib --report dups.json
      pa dedup-strict refs.bib --out deduped.bib --fuzzy-threshold 0.90
    """
    from .dedup_strict import run_dedup
    bib_path = Path(bibtex_file)
    out_path = Path(out_file)
    rpt_path = Path(report_file) if report_file else None
    if not 0.0 <= fuzzy_threshold <= 1.0:
        click.echo(f"[pa dedup-strict] FAILED: --fuzzy-threshold must be in [0.0, 1.0]",
                   err=True)
        sys.exit(2)
    try:
        report = run_dedup(
            bib_path=bib_path,
            out_path=out_path,
            report_path=rpt_path,
            fuzzy_threshold=fuzzy_threshold,
        )
    except Exception as e:
        click.echo(f"[pa dedup-strict] FAILED: {e}", err=True)
        sys.exit(2)
    click.echo(
        f"[pa dedup-strict] total={report['n_total_entries']}, "
        f"unique={report['n_unique_entries']}, "
        f"removed={report['n_removed']} from {report['n_duplicate_groups']} dup groups, "
        f"wrote {report['n_written']} → {report['out_path']}",
        err=True,
    )
    if rpt_path:
        click.echo(f"[pa dedup-strict] report: {rpt_path}", err=True)


# =============== [P2-11] fetch-batch subcommand ===============
# Batch PDF download from a Bibtex: walks each entry through fetch channels
# in priority order (CNKI, Unpaywall, Sci-Hub, etc.). Saves to out_dir/{key}.pdf.

@main.command(name="fetch-batch")
@click.argument("bibtex_file", type=click.Path(exists=True, dir_okay=False))
@click.option("--out-dir", required=True, type=click.Path(file_okay=False),
              help="Directory to save PDFs (created if not exists)")
@click.option("--max-total-sec", type=int, default=1800, show_default=True,
              help="Global timeout for the whole batch (s)")
@click.option("--skip-existing", is_flag=True,
              help="Skip entries whose PDF already exists in out_dir")
@click.option("--report", "report_file", default=None, type=click.Path(dir_okay=False),
              help="Optional markdown failure report path")
@click.option("--summary-json", default=None, type=click.Path(dir_okay=False),
              help="Optional JSON summary path (for programmatic use)")
@click.option("--quiet", is_flag=True, help="Suppress per-entry progress output")
def fetch_batch(bibtex_file, out_dir, max_total_sec, skip_existing, report_file,
                summary_json, quiet):
    """[P2-11] Batch PDF download from a Bibtex file.

    Per ROADMAP [P2-11]: walks every entry through 8 fetch channels in
    priority order (CNKI, Unpaywall, Sci-Hub, etc.). Saves to out_dir/{key}.pdf.
    Lists what failed and why.

    Examples:
      pa fetch-batch refs.bib --out-dir ./pdfs/
      pa fetch-batch refs.bib --out-dir ./pdfs/ --skip-existing
      pa fetch-batch refs.bib --out-dir ./pdfs/ --report failed.md
    """
    from .fetch_batch import run_fetch_batch, write_failure_report, write_summary_json
    from pathlib import Path
    bib_path = Path(bibtex_file)
    out_path = Path(out_dir)
    rpt_path = Path(report_file) if report_file else None
    sum_path = Path(summary_json) if summary_json else None

    def on_progress(i, n, result):
        if not quiet:
            status = "OK" if result.success else "FAIL"
            print(f"  [{i}/{n}] {status} {result.key} ({result.elapsed_sec:.1f}s)",
                  file=sys.stderr)

    try:
        summary = run_fetch_batch(
            bib_path=bib_path,
            out_dir=out_path,
            max_total_sec=max_total_sec,
            skip_existing=skip_existing,
            progress_callback=on_progress,
        )
    except Exception as e:
        click.echo(f"[pa fetch-batch] FAILED: {e}", err=True)
        sys.exit(2)

    click.echo(
        f"[pa fetch-batch] total={summary.n_total} "
        f"success={summary.n_success} failure={summary.n_failure} "
        f"skipped={summary.n_skipped} "
        f"size={summary.total_size_bytes // 1024} KB "
        f"time={summary.total_elapsed_sec:.1f}s",
        err=True,
    )
    if rpt_path:
        n_failures = write_failure_report(summary, rpt_path, bib_path, out_path)
        click.echo(f"[pa fetch-batch] report: {rpt_path} ({n_failures} failures)", err=True)
    if sum_path:
        write_summary_json(summary, sum_path, bib_path, out_path, max_total_sec)
        click.echo(f"[pa fetch-batch] summary JSON: {sum_path}", err=True)
    if summary.n_failure > 0 and not rpt_path and not quiet:
        click.echo(
            f"[pa fetch-batch] hint: {summary.n_failure} failures; "
            f"use --report to save details",
            err=True,
        )


# =============== [P2-12] project subcommand group ===============
# Multi-corpus management for 课题. Phase 1: init/list/status/corpus/rm.
# Phase 2 (deferred): corpus-search / corpus-merge.

@main.group()
def project():
    """[P2-12] Manage per-topic project corpora (Phase 1: init/list/status/corpus/rm).

    Per ROADMAP [P2-12]: each research topic = one project at
    ~/.paper-agent/projects/<slug>/, holding its own refs.bib + judges.sqlite
    + cross-corpus dedup (Phase 2).

    Phase 1 subcommands:
      init <slug> [--title "..."]  - create project skeleton
      list                          - list all projects
      status [slug]                 - show n_papers, n_labels
      corpus [slug]                 - print path to refs.bib
      rm <slug>                     - remove project

    Phase 2 (deferred; needs user input on corpus names):
      corpus-search <slug>          - re-execute saved search scoped
      corpus-merge <slug1> <slug2>  - cross-corpus dedup
    """
    pass


@project.command(name="init")
@click.argument("slug")
@click.option("--title", default="", help="Human-readable project title")
@click.option("--description", default="", help="Long-form description (markdown ok)")
@click.option("--root", "root_path", default=None, type=click.Path(file_okay=False),
              help="Override default ~/.paper-agent/projects/ root")
def project_init(slug, title, description, root_path):
    """Create a new project (skeleton: meta.json, empty refs.bib, judges.sqlite)."""
    from .project import init_project, DEFAULT_ROOT
    from pathlib import Path
    root = Path(root_path) if root_path else DEFAULT_ROOT
    try:
        meta = init_project(slug, title=title, description=description, root=root)
    except (ValueError, FileExistsError) as e:
        click.echo(f"[pa project init] FAILED: {e}", err=True)
        sys.exit(1)
    click.echo(f"[pa project init] created {slug!r} at {root / slug}/", err=True)
    click.echo(f"  title: {meta['title']}", err=True)
    click.echo(f"  meta:  {root / slug / 'meta.json'}", err=True)
    click.echo(f"  refs:  {root / slug / 'refs.bib'}", err=True)
    click.echo(f"  judges:{root / slug / 'judges.sqlite'}", err=True)


@project.command(name="list")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.option("--root", "root_path", default=None, type=click.Path(file_okay=False),
              help="Override default project root")
def project_list(as_json, root_path):
    """List all projects."""
    from .project import list_projects, DEFAULT_ROOT
    from pathlib import Path
    root = Path(root_path) if root_path else DEFAULT_ROOT
    projects = list_projects(root)
    if as_json:
        click.echo(json.dumps(projects, indent=2, ensure_ascii=False))
        return
    if not projects:
        click.echo(f"(no projects; use `pa project init <slug>` to create one)")
        return
    click.echo(f"Projects ({len(projects)}) at {root}:")
    click.echo("")
    click.echo(f"  {'SLUG':<25s} {'TITLE':<35s}  CREATED")
    click.echo(f"  {'-'*25} {'-'*35}  {'-'*19}")
    for p in projects:
        title = p.get('title', '')[:35]
        created = p.get('created_at', '')[:19]
        click.echo(f"  {p['slug']:<25s} {title:<35s}  {created}")


@project.command(name="status")
@click.argument("slug", required=False)
@click.option("--root", "root_path", default=None, type=click.Path(file_okay=False),
              help="Override default project root")
def project_status(slug, root_path):
    """Show project status (n_papers, n_labels). If slug omitted, shows all."""
    from .project import project_status as get_status, list_projects, DEFAULT_ROOT
    from pathlib import Path
    root = Path(root_path) if root_path else DEFAULT_ROOT
    if slug:
        try:
            s = get_status(slug, root)
        except (ValueError, FileNotFoundError) as e:
            click.echo(f"[pa project status] FAILED: {e}", err=True)
            sys.exit(1)
        click.echo(json.dumps(s, indent=2, ensure_ascii=False))
    else:
        # All projects
        projects = list_projects(root)
        if not projects:
            click.echo("(no projects)")
            return
        for p in projects:
            try:
                s = get_status(p['slug'], root)
                click.echo(
                    f"  {s['slug']:<25s} papers={s['n_papers']:4d}  labels={s['n_labels']:4d}  "
                    f"title={s['title']}",
                    err=True,
                )
            except Exception as e:
                click.echo(f"  {p['slug']:<25s} ERROR: {e}", err=True)


@project.command(name="corpus")
@click.argument("slug")
def project_corpus(slug):
    """Print path to project refs.bib (for piping to other tools)."""
    from .project import project_files, DEFAULT_ROOT
    files = project_files(slug, DEFAULT_ROOT)
    if not files['dir'].exists():
        click.echo(f"[pa project corpus] FAILED: project {slug!r} not found", err=True)
        sys.exit(1)
    click.echo(str(files['refs']))


@project.command(name="corpus-stats")
@click.argument("slug", required=False)
@click.option("--root", "root_path", default=None, type=click.Path(file_okay=False),
              help="Override default project root")
@click.option("--top", "top_n", default=10, show_default=True,
              help="How many top authors/venues to show")
@click.option("--json", "as_json", is_flag=True,
              help="Output full JSON (else human-readable summary)")
def project_corpus_stats(slug, root_path, top_n, as_json):
    """[P2-19] Show aggregate stats for a project's refs.bib corpus.

    Computes: total count, with/without DOI, by type, year range +
    median, decade histogram, top N authors (by paper count), top N
    venues (journal/publisher/booktitle).

    If `slug` is omitted, shows stats for all projects (one section
    per project). If project is a Zotero-pulled project
    (meta.json has zotero_collection_key), shows sync info too.

    Examples:
      pa project corpus-stats long-term-care
      pa project corpus-stats --json | jq .top_authors
      pa project corpus-stats                      # all projects
    """
    from .project import list_projects, project_files, DEFAULT_ROOT
    from . import corpus_stats as cs
    from pathlib import Path
    root = Path(root_path) if root_path else DEFAULT_ROOT

    if slug:
        slugs = [slug]
    else:
        slugs = [p["slug"] for p in list_projects(root)]

    if not slugs:
        click.echo(f"[corpus-stats] no projects found at {root}")
        return

    for s in slugs:
        files = project_files(s, root)
        if not files["dir"].exists():
            click.echo(f"[corpus-stats] {s}: project not found", err=True)
            continue
        stats = cs.compute_corpus_stats(files["refs"], top_n=top_n)
        if as_json:
            # Augment with slug for clarity when batch
            result = {"slug": s, **stats}
            # Also include zotero info if present
            if files["meta"].exists():
                try:
                    meta = json.loads(files["meta"].read_text(encoding="utf-8"))
                    if "zotero_collection_key" in meta:
                        result["zotero_collection_key"] = meta["zotero_collection_key"]
                        result["zotero_collection_version"] = meta.get("zotero_collection_version")
                        result["zotero_last_sync_at"] = meta.get("zotero_last_sync_at")
                except Exception:
                    pass
            click.echo(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            click.echo(cs.format_corpus_stats_human(stats))
            # Zotero info if present
            if files["meta"].exists():
                try:
                    meta = json.loads(files["meta"].read_text(encoding="utf-8"))
                    if "zotero_collection_key" in meta:
                        ver = meta.get("zotero_collection_version", "?")
                        sync = meta.get("zotero_last_sync_at", "never")
                        click.echo(
                            f"  zotero:        key={meta['zotero_collection_key']} "
                            f"version={ver} last_sync={sync}"
                        )
                except Exception:
                    pass
        click.echo("")  # blank line between projects


@project.command(name="rm")
@click.argument("slug")
@click.option("--force", is_flag=True, help="Remove even without meta.json")
@click.option("--root", "root_path", default=None, type=click.Path(file_okay=False),
              help="Override default project root")
@click.confirmation_option(prompt="Are you sure you want to delete this project?")
def project_rm(slug, force, root_path):
    """Remove a project (deletes refs.bib, judges.sqlite, meta.json, all files)."""
    from .project import remove_project, DEFAULT_ROOT
    from pathlib import Path
    root = Path(root_path) if root_path else DEFAULT_ROOT
    try:
        if remove_project(slug, root, force=force):
            click.echo(f"[pa project rm] removed {slug!r}", err=True)
        else:
            click.echo(f"[pa project rm] {slug!r} not found", err=True)
            sys.exit(1)
    except ValueError as e:
        click.echo(f"[pa project rm] FAILED: {e}", err=True)
        sys.exit(1)


# =============== [P3-1] judge subcommand ===============
# Relevance judgement collection for ML/DL rerank (per ROADMAP Tier 5
# long-term). Stores in ~/.paper-agent/judgements.sqlite. Re-probe ML/DL
# rerank when n >= 500.

@main.group()
def judge():
    """[P3-1] Collect relevance judgements for future ML/DL rerank.

    Per ROADMAP "Tier 5 long-term" (post-v3.9.7.9): v3.9.7.0-7.2 ML/DL
    local rerank failed at n=50 (data problem, not absolute). This is the
    data-collection track. Re-probe when n >= 500.

    Relevance scale (matches bench/v01/labels.json):
      0 = irrelevant  (off-topic, or wrong level+topic)
      1 = marginal    (topic adjacent OR level wrong OR scope right but topic wrong)
      2 = relevant    (matches query topic + level + scope)

    Subcommands: add / bulk / list / stats / export / import
    """


@judge.command("add")
@click.option("--query", required=True, help="Query string or query_id (e.g. 'q001')")
@click.option("--key", "paper_key", required=True,
              help="Paper identifier (DOI, bibtex key, or OpenAlex ID)")
@click.option("--relevance", required=True,
              type=click.Choice([0, 1, 2]),
              help="0=irrelevant, 1=marginal, 2=relevant")
@click.option("--title", "paper_title", default=None,
              help="Optional paper title for display")
@click.option("--reason", default=None, help="Why this label (e.g. 'matches topic + K-12')")
@click.option("--source", default="manual", show_default=True,
              help="Provenance tag: manual / mavis-auto / bulk-bibtex / import")
@click.option("--db", "db_path", default=None,
              type=click.Path(dir_okay=False),
              help=f"Override DB path (default: ~/.paper-agent/judgements.sqlite)")
def judge_add(query, paper_key, relevance, paper_title, reason, source, db_path):
    """Add a single relevance judgement."""
    from .judge import add as _add, RELEVANCE_LABELS
    try:
        rid = _add(
            query=query,
            paper_key=paper_key,
            relevance=relevance,
            paper_title=paper_title,
            reason=reason,
            source=source,
            db_path=Path(db_path) if db_path else None,
        )
    except Exception as e:
        click.echo(f"[pa judge] FAILED: {e}", err=True)
        sys.exit(2)
    click.echo(f"[pa judge] added id={rid} "
               f"query={query!r} key={paper_key!r} "
               f"relevance={relevance}({RELEVANCE_LABELS[relevance]})",
               err=True)


@judge.command("bulk")
@click.argument("bibtex_file", type=click.Path(exists=True, dir_okay=False))
@click.option("--query", required=True, help="Query string for all papers in this batch")
@click.option("--relevance", required=True,
              type=click.Choice([0, 1, 2]),
              help="Relevance label to apply to ALL papers (use `add` for per-paper labels)")
@click.option("--reason", default=None,
              help="Optional single reason for the whole batch")
@click.option("--source", default="bulk-bibtex", show_default=True)
@click.option("--db", "db_path", default=None, type=click.Path(dir_okay=False))
@click.option("--quiet", is_flag=True, help="Suppress per-paper output")
def judge_bulk(bibtex_file, query, relevance, reason, source, db_path, quiet):
    """Bulk-add judgements for every entry in a .bib file.

    All entries get the same relevance label. Use `pa judge add` for
    per-paper labels. Use this for large-scale 'I have a corpus, all
    papers are X-relevant' workflows.
    """
    from .scaffold import load_bibtex
    from .judge import add_bulk, RELEVANCE_LABELS
    entries = load_bibtex(Path(bibtex_file))
    items = []
    for e in entries:
        items.append((e["key"], e.get("title"), relevance, reason))
    db = Path(db_path) if db_path else None
    n_added, n_updated, n_skipped = add_bulk(query, items, source=source, db_path=db)
    if not quiet:
        click.echo(f"[pa judge bulk] {len(items)} entries from {bibtex_file}", err=True)
    click.echo(
        f"[pa judge bulk] added={n_added} updated={n_updated} skipped={n_skipped} "
        f"relevance={relevance}({RELEVANCE_LABELS[relevance]}) query={query!r}",
        err=True,
    )


@judge.command("list")
@click.option("--query", default=None, help="Filter by query")
@click.option("--relevance", default=None,
              type=click.Choice([0, 1, 2]), help="Filter by relevance")
@click.option("--limit", type=int, default=50, show_default=True)
@click.option("--db", "db_path", default=None, type=click.Path(dir_okay=False))
@click.option("--format", "out_format", default="table", show_default=True,
              type=click.Choice(["table", "json", "jsonl"]),
              help="Output format")
def judge_list(query, relevance, limit, db_path, out_format):
    """List judgements, optionally filtered."""
    from .judge import list_judgements, RELEVANCE_LABELS
    db = Path(db_path) if db_path else None
    rows = list_judgements(query=query, relevance=relevance, limit=limit, db_path=db)
    if out_format == "json":
        click.echo(json.dumps([dict(r) for r in rows], ensure_ascii=False, indent=2))
    elif out_format == "jsonl":
        for r in rows:
            click.echo(json.dumps(dict(r), ensure_ascii=False))
    else:
        if not rows:
            click.echo("(no judgements match filter)", err=True)
            return
        click.echo(f"{'id':>4s}  {'query':30s}  {'paper_key':40s}  {'rel':>3s}  source", err=False)
        click.echo("-" * 110)
        for r in rows:
            q = (r["query"] or "")[:28]
            k = (r["paper_key"] or "")[:38]
            click.echo(
                f"{r['id']:>4d}  {q:30s}  {k:40s}  {r['relevance']:>3d}  {r['source']}"
            )
        click.echo(f"\n{len(rows)} row(s) shown (use --limit for more)", err=True)


@judge.command("stats")
@click.option("--query", default=None, help="Stats for one query (else aggregate over all)")
@click.option("--db", "db_path", default=None, type=click.Path(dir_okay=False))
def judge_stats(query, db_path):
    """Show n_relevant / n_marginal / n_irrelevant + per-query breakdown."""
    from .judge import stats as _stats
    db = Path(db_path) if db_path else None
    s = _stats(query=query, db_path=db)
    click.echo(f"Total judgements: {s['n_total']}")
    click.echo(f"  irrelevant (0): {s['n_irrelevant']}")
    click.echo(f"  marginal   (1): {s['n_marginal']}")
    click.echo(f"  relevant   (2): {s['n_relevant']}")
    click.echo(f"  queries:        {s['n_queries']}")
    if s["queries"] and not query:
        click.echo("\nTop queries by n:")
        for q, n in s["queries"][:20]:
            click.echo(f"  {n:>5d}  {q[:80]}")
    # Honest signal: when do we have enough to re-probe ML/DL?
    if s["n_total"] < 100:
        click.echo(f"\n[hint] n={s['n_total']} is below the noise threshold (100). "
                   f"Keep labelling; re-probe ML/DL when n>=500.", err=True)
    elif s["n_total"] < 500:
        click.echo(f"\n[hint] n={s['n_total']} is informative but small. "
                   f"Re-probe ML/DL rerank at n>=500 for statistical power.", err=True)
    else:
        click.echo(f"\n[hint] n={s['n_total']} >= 500. Ready to re-probe ML/DL rerank.",
                   err=True)


@judge.command("export")
@click.option("-o", "--output", required=True, type=click.Path(dir_okay=False),
              help="Output file path (.jsonl or .json)")
@click.option("--format", "out_format", default=None,
              type=click.Choice(["jsonl", "bench-json"]),
              help="Output format (auto-detect from suffix if not set)")
@click.option("--db", "db_path", default=None, type=click.Path(dir_okay=False))
def judge_export(output, out_format, db_path):
    """Export judgements. Default: JSONL. Use --format bench-json for
    compatibility with bench/v01/labels.json (LTR pipeline input)."""
    from .judge import export_jsonl, export_bench_format
    out = Path(output)
    if out_format is None:
        out_format = "jsonl" if out.suffix == ".jsonl" else "bench-json"
    db = Path(db_path) if db_path else None
    if out_format == "jsonl":
        n = export_jsonl(out, db_path=db)
    else:
        n_queries = export_bench_format(out, db_path=db)
        n = n_queries
    click.echo(f"[pa judge export] {n} {'queries' if out_format == 'bench-json' else 'rows'} -> {out}",
               err=True)


@judge.command("import")
@click.argument("input_path", type=click.Path(exists=True, dir_okay=False))
@click.option("--source", default="import", show_default=True,
              help="Provenance tag for all imported rows")
@click.option("--db", "db_path", default=None, type=click.Path(dir_okay=False))
def judge_import(input_path, source, db_path):
    """Import from bench/v01/labels.json (or any compatible JSON)."""
    from .judge import import_bench_format
    n_added, n_updated, n_skipped = import_bench_format(
        Path(input_path), db_path=Path(db_path) if db_path else None,
        default_source=source,
    )
    click.echo(f"[pa judge import] {input_path}", err=True)
    click.echo(f"  added={n_added} updated={n_updated} skipped={n_skipped}", err=True)


# =============== sample-pool subcommand group ===============
# [P3-26] v02 Global Sample Pool -- user-owned, Mavis-read-only, training-isolated
# Canonical doc: ~/.paper-agent/sample_pool/README.md (cross-platform, user home)
# Three iron rules enforced at API + CLI level:
#   1. User-only write: add/label/deprecate require --confirm-y or interactive y/n
#   2. Mavis read-only: list/get/stats/count/query/export work for any session
#   3. Training-isolated: export writes to OUT path, never touches pool.sqlite


@main.group(name="sample-pool")
def sample_pool_cmd():
    """Global Sample Pool -- relevance labels for held-out evaluation.

    See ~/.paper-agent\\sample_pool\\README.md for the
    canonical design doc. Briefly: this is a user-owned, Mavis-read-only,
    training-isolated pool of query+candidate+relevance_label triples.

    \b
    Read paths (any session may call):
      list / get / stats / count / query / export / audit / verify

    \b
    Propose path (Mavis may call, no write):
      suggest

    \b
    Write paths (require --confirm-y or interactive y/n, Iron Rule 5.1):
      add / label / deprecate
    """


@sample_pool_cmd.command("init")
@click.option("--force", is_flag=True,
              help="Re-create schema even if pool.sqlite exists (DESTRUCTIVE)")
def sample_pool_init(force):
    """Initialize pool.sqlite from schema.sql. Idempotent unless --force."""
    from .sample_pool import cmd_init
    result = cmd_init(force=force)
    click.echo(json.dumps(result, indent=2, ensure_ascii=False))


@sample_pool_cmd.command("verify")
def sample_pool_verify():
    """Verify pool integrity: schema version, tables, counts, gate status."""
    from .sample_pool import cmd_verify
    result = cmd_verify()
    click.echo(json.dumps(result, indent=2, ensure_ascii=False))


@sample_pool_cmd.command("list")
@click.option("--domain", default=None,
              help="Filter: econ / cs_ai / medical / legal / social / other")
@click.option("--project", default=None,
              help="Filter by project tag (e.g. long-term-care)")
@click.option("--difficulty", default=None,
              help="Filter: easy / medium / hard")
@click.option("--limit", default=20, show_default=True, type=int,
              help="Max rows to show")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def sample_pool_list(domain, project, difficulty, limit, as_json):
    """List active entries (Mavis may call)."""
    from .sample_pool import cmd_list
    rows = cmd_list(
        domain=domain, project=project, difficulty=difficulty, limit=limit,
    )
    if as_json:
        click.echo(json.dumps(rows, indent=2, ensure_ascii=False))
        return
    if not rows:
        click.echo("[sample-pool] no entries yet. Run `pa sample-pool suggest` to preview, then `pa sample-pool add`.")
        return
    click.echo(f"{'QID':24s} {'DOMAIN':8s} {'DIFF':6s} {'PROJECT':24s} {'N_CAND':6s} {'ADDED_AT':20s} QUERY")
    click.echo("-" * 130)
    for r in rows:
        q = (r["query"][:50] + "...") if len(r["query"]) > 53 else r["query"]
        click.echo(
            f"{r['qid']:24s} {r['domain']:8s} {r['difficulty']:6s} "
            f"{(r['project'] or 'global')[:24]:24s} {r['n_candidates']:6d} "
            f"{r['added_at'][:19]:20s} {q}"
        )


@sample_pool_cmd.command("get")
@click.argument("qid")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def sample_pool_get(qid, as_json):
    """Get full entry with all labels (Mavis may call)."""
    from .sample_pool import cmd_get
    entry = cmd_get(qid)
    if not entry:
        click.echo(f"[sample-pool] qid {qid!r} not found or deprecated", err=True)
        sys.exit(2)
    if as_json:
        click.echo(json.dumps(entry, indent=2, ensure_ascii=False))
        return
    # pretty print
    click.echo(f"QID:        {entry['qid']}")
    click.echo(f"Query:      {entry['query']}")
    click.echo(f"Domain:     {entry['domain']}  Difficulty: {entry['difficulty']}")
    click.echo(f"Project:    {entry.get('project') or 'global'}")
    click.echo(f"Source:     {entry.get('source', '-')}")
    click.echo(f"Added:      {entry.get('added_at', '-')}  by {entry.get('added_by', '-')}")
    click.echo(f"Candidates: {entry.get('n_candidates', 0)}  Labeled: {entry.get('n_labeled', 0)}  Unlabeled: {entry.get('n_unlabeled', 0)}")
    if entry.get("notes"):
        click.echo(f"Notes:      {entry['notes']}")
    click.echo("")
    click.echo(f"Labels ({len(entry.get('labels', []))} rows):")
    click.echo(f"  {'RANK':4s} {'LABEL':5s} {'CANDIDATE_KEY':50s} NOTES")
    click.echo("  " + "-" * 100)
    for l in entry.get("labels", []):
        ck = (l["candidate_key"] or "")[:50]
        notes = (l.get("notes") or "")[:30]
        label = str(l.get("label")) if l.get("label") is not None else "(unlabeled)"
        click.echo(f"  {l['rank']:4d} {label:5s} {ck:50s} {notes}")


@sample_pool_cmd.command("stats")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def sample_pool_stats(as_json):
    """Show pool stats + gate status (Mavis may call)."""
    from .sample_pool import cmd_stats
    s = cmd_stats()
    if as_json:
        click.echo(json.dumps(s, indent=2, ensure_ascii=False))
        return
    p = s["pool"]
    click.echo(f"[sample-pool] stats")
    click.echo(f"  n_entries (active): {p.get('n_entries', 0)}")
    click.echo(f"  n_labels total:     {p.get('n_labels_total', 0)}")
    click.echo(f"  by label:           0={p.get('n_label_0', 0)}  1={p.get('n_label_1', 0)}  2={p.get('n_label_2', 0)}  3={p.get('n_label_3', 0)}")
    click.echo("")
    click.echo("  by_domain:")
    for d, v in s["by_domain"].items():
        click.echo(f"    {d:10s} entries={v['n_entries']:3d}  labels={v['n_labels']}")
    click.echo("  by_project:")
    for p_name, v in s["by_project"].items():
        click.echo(f"    {p_name:24s} entries={v['n_entries']:3d}  labels={v['n_labels']}")
    click.echo("  by_difficulty:")
    for diff, n in s["by_difficulty"].items():
        click.echo(f"    {diff:8s} entries={n}")
    click.echo("")
    click.echo("  gates:")
    for g in s["gates"]:
        marker = "UNLOCKED" if g["unlocked"] else "LOCKED  "
        extra = f" + {g['threshold_other']}" if g["threshold_other"] else ""
        click.echo(
            f"    [{marker}] {g['gate_name']:24s} need n>={g['threshold_n']:3d}{extra}  "
            f"current_n={g['current_n']}"
        )


@sample_pool_cmd.command("count")
@click.option("--by", default="domain", show_default=True,
              type=click.Choice(["domain", "project", "difficulty"]),
              help="Group by dimension")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def sample_pool_count(by, as_json):
    """Count entries by dimension (Mavis may call)."""
    from .sample_pool import cmd_count
    rows = cmd_count(by=by)
    if as_json:
        click.echo(json.dumps(rows, indent=2, ensure_ascii=False))
        return
    if not rows:
        click.echo(f"[sample-pool] no entries")
        return
    cols = list(rows[0].keys())
    header = "  ".join(f"{c:24s}" for c in cols)
    click.echo(header)
    click.echo("-" * len(header))
    for r in rows:
        click.echo("  ".join(f"{str(r[c])[:24]:24s}" for c in cols))


@sample_pool_cmd.command("query")
@click.argument("sql")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def sample_pool_query(sql, as_json):
    """Run a read-only SELECT/WITH query (Mavis may call).

    Iron Rule 5.2: rejects INSERT/UPDATE/DELETE/DDL keywords.
    """
    from .sample_pool import cmd_query
    try:
        rows = cmd_query(sql)
    except ValueError as e:
        click.echo(f"[sample-pool] query rejected: {e}", err=True)
        sys.exit(2)
    if as_json:
        click.echo(json.dumps(rows, indent=2, ensure_ascii=False))
        return
    if not rows:
        click.echo("[sample-pool] 0 rows")
        return
    cols = list(rows[0].keys())
    widths = {c: max(len(c), max(len(str(r[c]) if r[c] is not None else "") for r in rows)) for c in cols}
    line_width = sum(widths.values()) + 2 * (len(cols) - 1)
    click.echo("  ".join(f"{c[:widths[c]]:>{widths[c]}}" for c in cols))
    click.echo("-" * line_width)
    for r in rows:
        click.echo("  ".join(f"{(str(r[c]) if r[c] is not None else '')[:widths[c]]:>{widths[c]}}" for c in cols))


@sample_pool_cmd.command("suggest")
@click.option("--query", required=True, help="The query string (what the user searched)")
@click.option("--domain", required=True,
              type=click.Choice(list(__import__("pa_cli.sample_pool", fromlist=["ALLOWED_DOMAINS"]).ALLOWED_DOMAINS)),
              help="Research domain")
@click.option("--difficulty", required=True,
              type=click.Choice(list(__import__("pa_cli.sample_pool", fromlist=["ALLOWED_DIFFICULTY"]).ALLOWED_DIFFICULTY)),
              help="Query difficulty")
@click.option("--project", default="global", show_default=True,
              help="Project tag (e.g. long-term-care, korea-tripartite-game)")
@click.option("--notes", default="", help="Free-text notes")
@click.option("--source", default="manual-pa-search", show_default=True,
              type=click.Choice(list(__import__("pa_cli.sample_pool", fromlist=["ALLOWED_SOURCE"]).ALLOWED_SOURCE)),
              help="Provenance tag")
@click.option("--n-candidates", default=30, show_default=True, type=int,
              help="Number of candidates (1-50)")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def sample_pool_suggest(query, domain, difficulty, project, notes, source, n_candidates, as_json):
    """Propose a new entry (Mavis may call; NOT written to pool).

    Returns a preview dict. User reviews and runs `pa sample-pool add` to commit.
    """
    from .sample_pool import cmd_suggest
    preview = cmd_suggest(
        query=query, domain=domain, difficulty=difficulty,
        project=project, notes=notes, source=source, n_candidates=n_candidates,
    )
    if as_json:
        click.echo(json.dumps(preview, indent=2, ensure_ascii=False))
        return
    click.echo("[sample-pool] SUGGESTION (not written to pool):")
    click.echo(json.dumps(preview, indent=2, ensure_ascii=False))
    click.echo("")
    click.echo("To commit, run `pa sample-pool add` with these values (or save to JSON, then --from-file).")


@sample_pool_cmd.command("add")
@click.option("--from-file", "from_file", default=None, type=click.Path(exists=True, dir_okay=False),
              help="Load entry from JSON file (recommended). Format: see example_entry.json")
@click.option("--qid", default=None, help="Entry qid (ASCII slug). Required if --from-file not used.")
@click.option("--query", default=None, help="Query string. Required if --from-file not used.")
@click.option("--domain", default=None,
              type=click.Choice(list(__import__("pa_cli.sample_pool", fromlist=["ALLOWED_DOMAINS"]).ALLOWED_DOMAINS)),
              help="Research domain")
@click.option("--difficulty", default=None,
              type=click.Choice(list(__import__("pa_cli.sample_pool", fromlist=["ALLOWED_DIFFICULTY"]).ALLOWED_DIFFICULTY)),
              help="Query difficulty")
@click.option("--project", default="global", show_default=True, help="Project tag")
@click.option("--notes", default="", help="Free-text notes")
@click.option("--source", default="manual-pa-search", show_default=True,
              type=click.Choice(list(__import__("pa_cli.sample_pool", fromlist=["ALLOWED_SOURCE"]).ALLOWED_SOURCE)),
              help="Provenance tag")
@click.option("--n-candidates", default=30, show_default=True, type=int,
              help="Number of candidates (1-50)")
@click.option("--added-by", default="user", show_default=True,
              type=click.Choice(["user", "mavis-suggested"]),
              help="Who added this. mavis-suggested requires --user-approved.")
@click.option("--user-approved", is_flag=True,
              help="Required when --added-by=mavis-suggested (Iron Rule 5.1)")
@click.option("--confirm-y", "confirm", is_flag=True,
              help="Bypass interactive prompt (REQUIRED for non-interactive use)")
def sample_pool_add(from_file, qid, query, domain, difficulty, project, notes,
                    source, n_candidates, added_by, user_approved, confirm):
    """INSERT a new entry (USER ONLY, Iron Rule 5.1).

    By default, prompts for y/n confirmation. Use --confirm-y for non-interactive.
    Rejects mavis-suggested entries without --user-approved (Iron Rule 5.1).
    """
    from .sample_pool import cmd_add
    # Load entry from file or build from args
    if from_file:
        try:
            with open(from_file, encoding="utf-8") as f:
                entry = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            click.echo(f"[sample-pool] failed to read {from_file}: {e}", err=True)
            sys.exit(2)
    else:
        if not (qid and query and domain and difficulty):
            click.echo(
                "[sample-pool] --from-file OR (--qid, --query, --domain, --difficulty) required",
                err=True,
            )
            sys.exit(2)
        entry = {
            "qid": qid, "query": query, "domain": domain, "difficulty": difficulty,
            "project": project, "notes": notes, "source": source,
            "n_candidates": n_candidates, "added_by": added_by,
            "user_approved": user_approved,
            "added_at": __import__("pa_cli.sample_pool", fromlist=["now_iso"]).now_iso(),
        }
    # Interactive confirm unless --confirm-y
    if not confirm:
        click.echo("[sample-pool] About to add this entry to pool:")
        click.echo(json.dumps({k: v for k, v in entry.items() if k != "candidates"}, indent=2, ensure_ascii=False))
        if entry.get("candidates"):
            n_lab = sum(1 for c in entry["candidates"] if c.get("label") is not None)
            click.echo(f"  + {len(entry['candidates'])} candidates ({n_lab} pre-labeled)")
        if not click.confirm("Proceed?"):
            click.echo("[sample-pool] cancelled.", err=True)
            sys.exit(1)
    try:
        result = cmd_add(entry, confirm=True, session_id="cli")
    except (PermissionError, ValueError) as e:
        click.echo(f"[sample-pool] add rejected: {e}", err=True)
        sys.exit(2)
    click.echo(json.dumps(result, indent=2, ensure_ascii=False))


@sample_pool_cmd.command("label")
@click.argument("qid")
@click.argument("candidate_key")
@click.argument("label", type=int)
@click.option("--notes", default=None, help="Label notes (optional)")
@click.option("--confirm-y", "confirm", is_flag=True,
              help="Bypass interactive prompt (REQUIRED for non-interactive use)")
def sample_pool_label(qid, candidate_key, label, notes, confirm):
    """Add or update a single relevance label (USER ONLY, Iron Rule 5.1).

    LABEL is one of: 0=irrelevant, 1=marginal, 2=relevant, 3=highly relevant.
    Refuses if qid is deprecated. Refuses if candidate_key is not registered
    (use `pa sample-pool add` to register candidates first).
    """
    from .sample_pool import cmd_label
    if label not in (0, 1, 2, 3):
        click.echo(f"[sample-pool] label must be 0, 1, 2, or 3 (got {label})", err=True)
        sys.exit(2)
    if not confirm:
        click.echo(f"[sample-pool] About to set label:")
        click.echo(f"  qid:           {qid}")
        click.echo(f"  candidate_key: {candidate_key}")
        click.echo(f"  label:         {label}  (0=irrelevant, 1=marginal, 2=relevant, 3=highly relevant)")
        if notes:
            click.echo(f"  notes:         {notes}")
        if not click.confirm("Proceed?"):
            click.echo("[sample-pool] cancelled.", err=True)
            sys.exit(1)
    try:
        result = cmd_label(qid, candidate_key, label, notes=notes, confirm=True, session_id="cli")
    except (PermissionError, ValueError) as e:
        click.echo(f"[sample-pool] label rejected: {e}", err=True)
        sys.exit(2)
    click.echo(json.dumps(result, indent=2, ensure_ascii=False))


@sample_pool_cmd.command("deprecate")
@click.argument("qid")
@click.argument("reason")
@click.option("--confirm-y", "confirm", is_flag=True,
              help="Bypass interactive prompt (REQUIRED for non-interactive use)")
def sample_pool_deprecate(qid, reason, confirm):
    """Mark entry as deprecated (NOT delete, Iron Rule 5.1)."""
    from .sample_pool import cmd_deprecate
    if not confirm:
        click.echo(f"[sample-pool] About to DEPRECATE:")
        click.echo(f"  qid:    {qid}")
        click.echo(f"  reason: {reason}")
        click.echo("  (entry is hidden from active views, NOT deleted)")
        if not click.confirm("Proceed?"):
            click.echo("[sample-pool] cancelled.", err=True)
            sys.exit(1)
    try:
        result = cmd_deprecate(qid, reason, confirm=True, session_id="cli")
    except (PermissionError, ValueError) as e:
        click.echo(f"[sample-pool] deprecate rejected: {e}", err=True)
        sys.exit(2)
    click.echo(json.dumps(result, indent=2, ensure_ascii=False))


@sample_pool_cmd.command("export")
@click.option("--format", "fmt", default="json", show_default=True,
              type=click.Choice(list(__import__("pa_cli.sample_pool", fromlist=["ALLOWED_EXPORT_FORMATS"]).ALLOWED_EXPORT_FORMATS)),
              help="Output format")
@click.option("--out", "out_path", required=True, type=click.Path(),
              help="Where to write (relative paths resolved against cwd; absolute OK)")
@click.option("--min-n-labeled", default=1, show_default=True, type=int,
              help="Skip entries with fewer than N labels")
def sample_pool_export(fmt, out_path, min_n_labeled):
    """Export pool to working/ in given format (Mavis may call, Iron Rule 5.3).

    Reads from pool.sqlite (immutable), writes to OUT path. Training scripts
    must read from OUT path, NOT from pool.sqlite directly.
    """
    from .sample_pool import cmd_export
    try:
        result = cmd_export(fmt, out_path, min_n_labeled=min_n_labeled, session_id="cli")
    except (ValueError, FileNotFoundError) as e:
        click.echo(f"[sample-pool] export failed: {e}", err=True)
        sys.exit(2)
    click.echo(json.dumps(result, indent=2, ensure_ascii=False))
    click.echo(f"[sample-pool] working copy at {result['out']}", err=True)
    click.echo(f"[sample-pool] original pool at {__import__('pa_cli.sample_pool', fromlist=['POOL_DB']).POOL_DB} is UNTOUCHED", err=True)


@sample_pool_cmd.command("audit")
@click.option("--limit", default=50, show_default=True, type=int,
              help="Max rows to show")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def sample_pool_audit(limit, as_json):
    """Show recent audit log entries (Mavis may call)."""
    from .sample_pool import cmd_audit
    rows = cmd_audit(limit=limit)
    if as_json:
        click.echo(json.dumps(rows, indent=2, ensure_ascii=False))
        return
    if not rows:
        click.echo("[sample-pool] audit log empty (no operations yet)")
        return
    for r in rows:
        click.echo(f"{r['ts'][:19]}  {r['op']:10s} target={r.get('target') or '-':24s} session={r.get('source_session', '-')}")
        if r.get("details"):
            click.echo(f"    {json.dumps(r['details'], ensure_ascii=False)}")


@main.command()
@click.option("--corpus", "corpus", default=None,
              help="Path to Bibtex file (refs.bib). If omitted, expects DOIs via --doi.")
@click.option("--doi", "dois", multiple=True,
              help="One or more DOIs to check (repeatable). Mutually exclusive with --corpus.")
@click.option("--zotero-db", "zotero_db", default=None,
              help="Explicit path to zotero.sqlite (else $ZOTERO_LOCAL_DB or auto-detect)")
@click.option("--json", "as_json", is_flag=True,
              help="Output JSON (else human-readable summary)")
@click.option("--quiet", is_flag=True, help="Suppress progress output (just print the summary)")
def zotero_check(corpus, dois, zotero_db, as_json, quiet):
    """[P2-16] Check which DOIs in a corpus are already in your local Zotero library.

    READ-ONLY: opens zotero.sqlite in `mode=ro` (writes impossible even on bug).
    NO API key, NO network, NO cloud. The only state read is your local Zotero DB.

    Use case: after `pa fetch-pdf-batch` returns N papers, run this to filter
    out DOIs you already have in your Zotero library, so you can focus the
    lit review on new papers.

    Auto-detects Zotero DB on macOS / Linux (`~/Zotero/zotero.sqlite`) and
    Windows (`~/Zotero/Profiles/*/zotero.sqlite`). Override with `--zotero-db`
    or $ZOTERO_LOCAL_DB env var.

    Examples:
      pa zotero check --corpus refs.bib
      pa zotero check --doi 10.1038/nature12373 --doi 10.1126/science.1259855
      pa zotero check --corpus refs.bib --json > check.json
      pa zotero check --corpus refs.bib --zotero-db "D:\\Zotero\\zotero.sqlite"
    """
    from . import zotero_local

    # Resolve DB path
    db_path = None
    if zotero_db:
        from pathlib import Path as _P
        db_path = _P(zotero_db)
    if db_path is None:
        db_path = zotero_local.find_zotero_db()
    if db_path is None:
        click.echo(
            "[zotero-check] ERROR: Zotero local DB not found. "
            "Tried: $ZOTERO_LOCAL_DB, ~/Zotero/zotero.sqlite (macOS/Linux), "
            "~/Zotero/Profiles/*/zotero.sqlite (Windows). "
            "Use --zotero-db to specify explicitly.",
            err=True,
        )
        sys.exit(2)

    # Resolve corpus DOIs
    if corpus and dois:
        click.echo(
            "[zotero-check] ERROR: --corpus and --doi are mutually exclusive.",
            err=True,
        )
        sys.exit(2)

    if corpus:
        from pathlib import Path as _P
        corpus_path = _P(corpus)
        if not corpus_path.exists():
            click.echo(f"[zotero-check] ERROR: corpus file not found: {corpus}", err=True)
            sys.exit(2)
        corpus_dois = zotero_local.extract_dois_from_bibtex(corpus_path)
        if not corpus_dois:
            click.echo(
                f"[zotero-check] WARNING: no DOIs found in {corpus}. "
                f"Expected entries with `doi = {{...}}` or `doi = \"...\"` fields.",
                err=True,
            )
    elif dois:
        corpus_dois = list(dois)
    else:
        click.echo(
            "[zotero-check] ERROR: must provide either --corpus <refs.bib> or --doi <DOI>.",
            err=True,
        )
        sys.exit(2)

    if not quiet and not as_json:
        click.echo(
            f"[zotero-check] Zotero DB: {db_path}\n"
            f"[zotero-check] corpus size: {len(corpus_dois)}",
            err=True,
        )

    # Read library + compare
    library = zotero_local.get_library_dois(db_path=db_path)
    result = zotero_local.check_corpus(corpus_dois, library_dois=library)

    # Output
    if as_json:
        click.echo(json.dumps(
            {
                "zotero_db": str(db_path),
                "library_doi_count": len(library),
                "corpus_size": len(corpus_dois),
                "in_library": result["in_library"],
                "not_in_library": result["not_in_library"],
                "invalid_doi": result["invalid_doi"],
                "duplicates_in_corpus": result["duplicates_in_corpus"],
                "summary": {
                    "in_library": len(result["in_library"]),
                    "not_in_library": len(result["not_in_library"]),
                    "invalid_doi": len(result["invalid_doi"]),
                    "duplicates_in_corpus": len(result["duplicates_in_corpus"]),
                },
            },
            indent=2,
            ensure_ascii=False,
        ))
        return

    n_in = len(result["in_library"])
    n_out = len(result["not_in_library"])
    n_inv = len(result["invalid_doi"])
    n_dup = len(result["duplicates_in_corpus"])
    n_total = n_in + n_out
    pct = (n_in / n_total * 100) if n_total else 0.0

    click.echo(
        f"[zotero-check] {n_total} valid DOIs in corpus\n"
        f"[zotero-check]   in_library:    {n_in:5d}  ({pct:5.1f}%)\n"
        f"[zotero-check]   not_in_library:{n_out:5d}\n"
        f"[zotero-check]   invalid_doi:   {n_inv:5d}  (unparseable inputs)\n"
        f"[zotero-check]   duplicates:    {n_dup:5d}  (same DOI in corpus multiple times)\n"
        f"[zotero-check] library size: {len(library)} DOIs"
    )


@main.command()
@click.option("--debug", is_flag=True, help="Verbose logging (default quiet)")
def mcp_fetch_serve(debug):
    """[P0-15] Run the pa fetch MCP server over stdio JSON-RPC.

    Exposes 2 tools to MCP clients (Codex / Claude Code / Cursor / etc.):
      - pa_fetch(doi, prefer, use_cache)
      - pa_batch_fetch(dois, output_dir, prefer)

    Same trust boundary as `pa fetch` CLI invocation. NO api keys / passwords
    accepted through this MCP (would have to go through existing CLI env vars).

    Client config (paste into your MCP client's config file):
      {
        "mcpServers": {
          "paper-agent-fetch": {
            "command": "python",
            "args": ["-m", "pa_cli.mcp_fetch"]
          }
        }
      }
    """
    import logging as _logging
    if debug:
        _logging.getLogger("pa.mcp_fetch").setLevel(_logging.DEBUG)
    from . import mcp_fetch
    mcp_fetch.main()


@main.group()
def jobs():
    """[P2-15] Manage batch fetch jobs (status / tail / resume).

    Backed by ~/.paper-agent/jobs/<job_id>/{manifest.json, log.txt}.
    Inspired by `instsci jobs status/tail/resume` (Round 14 coupling).

    Subcommands:
      pa jobs start   --input <refs.bib> --out <dir> --job-id <id> [--prefer auto]
      pa jobs list
      pa jobs status  <job_id>
      pa jobs tail    <job_id> [-n 50]
      pa jobs resume  <job_id>

    Override jobs root via $PA_JOBS_DIR.
    """


@jobs.command(name="start")
@click.option("--job-id", "job_id", required=True,
              help="Unique job ID (alphanumeric + _/-). Becomes subdir under ~/.paper-agent/jobs/")
@click.option("--input", "input_file", required=True, type=click.Path(exists=True),
              help="Input Bibtex file (refs.bib)")
@click.option("--out", "output_dir", required=True, type=click.Path(),
              help="Output directory for fetched PDFs (created if missing)")
@click.option("--prefer", default="auto",
              type=click.Choice(["auto", "scihub", "annas", "cnki", "arxiv", "direct"]),
              help="Preferred fetch channel (default: auto)")
@click.option("--max-total-sec", "max_total_sec", default=1800, type=int,
              help="Max total seconds before timeout (default 1800 = 30 min)")
def jobs_start(job_id, input_file, output_dir, prefer, max_total_sec):
    """[P2-15] Start a new fetch-pdf-batch job.

    Creates ~/.paper-agent/jobs/<job_id>/{manifest.json, log.txt} and
    runs `pa fetch-pdf-batch` synchronously, writing the manifest on
    completion. For long jobs, run in one terminal and `pa jobs status`
    / `pa jobs tail` in another.
    """
    from . import jobs as jobs_mod
    from pathlib import Path as _P

    # Validate job_id
    try:
        jobs_mod.get_job_dir(job_id)  # raises if invalid
    except ValueError as e:
        click.echo(f"[pa jobs] ERROR: {e}", err=True)
        sys.exit(2)

    # Refuse if job already exists (avoid clobbering manifest)
    existing = jobs_mod.read_manifest(job_id)
    if existing is not None:
        click.echo(
            f"[pa jobs] ERROR: job '{job_id}' already exists "
            f"(status={existing.status}, created_at={existing.created_at}). "
            f"Use `pa jobs resume {job_id}` to retry, or pick a different --job-id.",
            err=True,
        )
        sys.exit(2)

    click.echo(f"[pa jobs] starting {job_id} ...", err=True)
    click.echo(f"[pa jobs]   input:  {input_file}", err=True)
    click.echo(f"[pa jobs]   output: {output_dir}", err=True)
    click.echo(f"[pa jobs]   log:    {jobs_mod.get_log_path(job_id)}", err=True)
    click.echo(f"[pa jobs]   manifest: {jobs_mod.get_manifest_path(job_id)}", err=True)
    click.echo(f"[pa jobs] (this may take a while; Ctrl+C to interrupt)", err=True)

    returncode = jobs_mod.start_job(
        job_id=job_id,
        input_file=_P(input_file),
        output_dir=_P(output_dir),
        prefer=prefer,
        max_total_sec=max_total_sec,
    )
    final = jobs_mod.read_manifest(job_id)
    if final is not None:
        click.echo(
            f"[pa jobs] done: status={final.status} "
            f"n_success={final.n_success}/{final.n_total} "
            f"failed={final.n_failed}",
            err=True,
        )
    sys.exit(returncode if returncode > 0 else 0)


@jobs.command(name="list")
def jobs_list():
    """[P2-15] List all jobs (newest first)."""
    from . import jobs as jobs_mod
    items = jobs_mod.list_jobs()
    if not items:
        click.echo("[pa jobs] no jobs found")
        click.echo(f"[pa jobs] jobs root: {jobs_mod.get_jobs_root()}", err=True)
        return
    click.echo(f"[pa jobs] {len(items)} job(s) in {jobs_mod.get_jobs_root()}:")
    for job_id, m in items:
        click.echo(jobs_mod.format_status_line(job_id, m))


@jobs.command(name="status")
@click.argument("job_id")
def jobs_status(job_id):
    """[P2-15] Show full status block for a job."""
    from . import jobs as jobs_mod
    try:
        m = jobs_mod.read_manifest(job_id)
    except ValueError as e:
        click.echo(f"[pa jobs] ERROR: {e}", err=True)
        sys.exit(2)
    if m is None:
        click.echo(f"[pa jobs] ERROR: job '{job_id}' not found", err=True)
        sys.exit(2)
    click.echo(jobs_mod.format_status_block(m))


@jobs.command(name="tail")
@click.argument("job_id")
@click.option("-n", "n_lines", default=50, type=int,
              help="Number of lines to show (default 50)")
def jobs_tail(job_id, n_lines):
    """[P2-15] Show last N lines of log.txt (like `tail -n`)."""
    from . import jobs as jobs_mod
    try:
        if jobs_mod.read_manifest(job_id) is None:
            click.echo(f"[pa jobs] ERROR: job '{job_id}' not found", err=True)
            sys.exit(2)
    except ValueError as e:
        click.echo(f"[pa jobs] ERROR: {e}", err=True)
        sys.exit(2)
    lines = jobs_mod.tail_log(job_id, n=n_lines)
    if not lines:
        click.echo(f"[pa jobs] log empty or not found for '{job_id}'")
        return
    for line in lines:
        click.echo(line)


@jobs.command(name="resume")
@click.argument("job_id")
@click.option("--max-total-sec", "max_total_sec", default=1800, type=int,
              help="Max total seconds before timeout (default 1800 = 30 min)")
def jobs_resume(job_id, max_total_sec):
    """[P2-15] Re-run a job (only failed/missing entries, --skip-existing)."""
    from . import jobs as jobs_mod
    try:
        returncode = jobs_mod.resume_job(job_id, max_total_sec=max_total_sec)
    except FileNotFoundError as e:
        click.echo(f"[pa jobs] ERROR: {e}", err=True)
        sys.exit(2)
    except RuntimeError as e:
        click.echo(f"[pa jobs] ERROR: {e}", err=True)
        sys.exit(2)
    final = jobs_mod.read_manifest(job_id)
    if final is not None:
        click.echo(
            f"[pa jobs] resume done: status={final.status} "
            f"n_success={final.n_success}/{final.n_total} "
            f"failed={final.n_failed}",
            err=True,
        )
    sys.exit(returncode if returncode > 0 else 0)


@main.command()
@click.option("--corpus", "corpus", required=True, type=click.Path(exists=True),
              help="Path to Bibtex file (refs.bib). DOIs are extracted.")
@click.option("--pdf-dir", "pdf_dir", default=None, type=click.Path(),
              help="Optional PDF directory ({key}.pdf files). PDF upload is currently metadata-only ([P2-17.1] follow-up).")
@click.option("--mode", "mode", default="linked_file",
              type=click.Choice(["linked_file", "imported_file"]),
              help="Attachment mode (default: linked_file, PDF stays at original path).")
@click.option("--no-skip-existing", "no_skip_existing", is_flag=True,
              help="If set, RE-push even DOIs already in library. Default skips them (idempotent).")
@click.option("--json", "as_json", is_flag=True,
              help="Output JSON (else human-readable summary)")
@click.option("--quiet", is_flag=True, help="Suppress progress output (just print the summary)")
def zotero_push(corpus, pdf_dir, mode, no_skip_existing, as_json, quiet):
    """[P2-17] Push Bibtex entries (+ optional PDFs) to your Zotero library.

    Uses the official Zotero Web API v3 (via `pyzotero` library). API key +
    library ID must be set via env vars:
        $ZOTERO_API_KEY       — get at https://www.zotero.org/settings/keys
        $ZOTERO_LIBRARY_ID    — find yours at the same page (numeric ID, not username)

    NO api key is read from .env file (per留痕 discipline; user exports per session).

    IDEMPOTENT: by default, re-running same corpus does NOT duplicate items.
    The library is checked first via Zotero's `check_items()` API; only
    new DOIs are pushed. Use --no-skip-existing to override.

    PDF upload is metadata-only in v3.9.15.0; the --pdf-dir flag is
    parsed but the actual file upload is tracked as [P2-17.1] follow-up
    (requires a separate item.attachment_simple() API call after push).
    """
    from . import zotero_api

    try:
        client = zotero_api.get_client()
    except (ImportError, ValueError) as e:
        click.echo(f"[zotero-push] ERROR: {e}", err=True)
        sys.exit(2)

    if not quiet and not as_json:
        click.echo(f"[zotero-push] reading {corpus} ...", err=True)

    entries = zotero_api.parse_bibtex_for_doi(Path(corpus))
    if not entries:
        click.echo(f"[zotero-push] no DOIs found in {corpus}", err=True)
        sys.exit(2)

    if not quiet and not as_json:
        click.echo(f"[zotero-push] found {len(entries)} entries with DOIs", err=True)
        click.echo(f"[zotero-push] pushing to Zotero library (id={zotero_api.get_library_id()})...", err=True)

    result = zotero_api.push_items(
        client=client,
        bibtex_entries=entries,
        pdf_dir=Path(pdf_dir) if pdf_dir else None,
        mode=mode,
        skip_existing=not no_skip_existing,
    )

    if as_json:
        click.echo(json.dumps(result, ensure_ascii=False, indent=2))
        return

    click.echo(
        f"[zotero-push] {result['n_total']} entries from corpus\n"
        f"[zotero-push]   pushed:    {result['n_pushed']:5d}\n"
        f"[zotero-push]   skipped:   {result['n_skipped']:5d}  (already in library)\n"
        f"[zotero-push]   failed:    {result['n_failed']:5d}"
    )
    if result["n_failed"] > 0:
        click.echo("[zotero-push] failures (first 5):", err=True)
        for r in result["results"][:5]:
            if r.get("status") == "failed":
                click.echo(
                    f"[zotero-push]   key={r.get('key', '?')}  doi={r.get('doi', '?')[:40]}  err={r.get('error', '?')[:80]}",
                    err=True,
                )


@main.command()
@click.option("--query", "query", required=True,
              help="Search query (matched against title, creator, year)")
@click.option("--limit", "limit", default=20, type=int,
              help="Max results to return (default 20)")
@click.option("--json", "as_json", is_flag=True,
              help="Output JSON (else human-readable summary)")
def zotero_search(query, limit, as_json):
    """[P2-18] Search your Zotero library by title/author/year.

    Uses Zotero Web API v3 `search()` call (qmode=titleCreatorYear).
    Returns items already in your library that match the query — useful
    for "do I have any papers on topic X?" before deciding what to fetch.

    Requires:
        $ZOTERO_API_KEY
        $ZOTERO_LIBRARY_ID
    """
    from . import zotero_api
    try:
        client = zotero_api.get_client()
    except (ImportError, ValueError) as e:
        click.echo(f"[zotero-search] ERROR: {e}", err=True)
        sys.exit(2)

    results = zotero_api.search_library(client, query, limit=limit)
    if as_json:
        click.echo(json.dumps(results, ensure_ascii=False, indent=2))
        return
    if not results:
        click.echo(f"[zotero-search] no items match '{query}'")
        return
    click.echo(f"[zotero-search] {len(results)} match(es) for '{query}':")
    for r in results:
        creators = ", ".join(
            f"{c.get('name', '?')}" for c in r.get("creators", [])[:3]
        )
        click.echo(
            f"[zotero-search]   {r.get('date', '????')[:4]}  "
            f"{creators:50s}  {r.get('title', '?')[:60]}"
        )


@main.command()
@click.option("--corpus", "corpus", default=None, type=click.Path(exists=True),
              help="Path to Bibtex file. If omitted, only search runs (no check+push).")
@click.option("--doi", "dois", multiple=True,
              help="One or more DOIs to check (repeatable). Mutually exclusive with --corpus.")
@click.option("--query", "query", default=None,
              help="Optional library search query (matches [P2-18] search)")
@click.option("--push/--no-push", "do_push", default=True,
              help="Push new DOIs to library (default yes). --no-push = check + search only.")
@click.option("--mode", "mode", default="linked_file",
              type=click.Choice(["linked_file", "imported_file"]),
              help="Attachment mode for push (default: linked_file)")
@click.option("--quiet", is_flag=True, help="Suppress progress output")
def zotero_sync(corpus, dois, query, do_push, mode, quiet):
    """[P2-18] Combined Zotero workflow: check + push + search in one call.

    Workflow:
        1. (Optional) `pa zotero check` against local zotero.sqlite for
           instant "do I have these?" without hitting the API
        2. (Optional) Search your Zotero library for related items
        3. (Optional) Push new DOIs from corpus to library (idempotent)

    Examples:
      pa zotero sync --corpus refs.bib
      pa zotero sync --corpus refs.bib --query "long-term care insurance"
      pa zotero sync --doi 10.1038/nature12373 --query "warp drive"
      pa zotero sync --corpus refs.bib --no-push   # check only
    """
    from . import zotero_local, zotero_api

    # Step 1: local check (read-only, fast)
    if corpus or dois:
        if corpus and dois:
            click.echo("[zotero-sync] ERROR: --corpus and --doi are mutually exclusive", err=True)
            sys.exit(2)
        if corpus:
            corpus_dois = zotero_local.extract_dois_from_bibtex(Path(corpus))
        else:
            corpus_dois = list(dois)
        if not corpus_dois:
            click.echo("[zotero-sync] no DOIs to process", err=True)
            return
        library = zotero_local.get_library_dois()
        result = zotero_local.check_corpus(corpus_dois, library_dois=library)
        n_in = len(result["in_library"])
        n_out = len(result["not_in_library"])
        click.echo(
            f"[zotero-sync] local check: {n_in} in local Zotero / "
            f"{n_out} not / {len(corpus_dois)} total"
        )

    # Step 2: library search (if query)
    if query:
        try:
            client = zotero_api.get_client()
        except (ImportError, ValueError) as e:
            click.echo(f"[zotero-sync] (search skipped: {e})", err=True)
        else:
            results = zotero_api.search_library(client, query, limit=20)
            click.echo(f"[zotero-sync] library search for '{query}': {len(results)} match(es)")
            for r in results[:5]:
                click.echo(f"[zotero-sync]   {r.get('title', '?')[:80]}")

    # Step 3: push (if requested + corpus available)
    if do_push and corpus:
        try:
            client = zotero_api.get_client()
        except (ImportError, ValueError) as e:
            click.echo(f"[zotero-sync] push skipped: {e}", err=True)
            return
        entries = zotero_api.parse_bibtex_for_doi(Path(corpus))
        if not entries:
            click.echo(f"[zotero-sync] no DOIs in {corpus}, nothing to push", err=True)
            return
        click.echo(f"[zotero-sync] pushing {len(entries)} new entries to library...", err=True)
        result = zotero_api.push_items(client=client, bibtex_entries=entries, mode=mode)
        click.echo(
            f"[zotero-sync] push done: "
            f"pushed={result['n_pushed']} skipped={result['n_skipped']} "
            f"failed={result['n_failed']}"
        )


# ─────────────────────────────────────────────────────────────────
# v3.9.16 [P3-28] pa zotero project — collection-as-research-project
# ─────────────────────────────────────────────────────────────────
@main.group()
def zotero_project():
    """[P3-28] Manage research projects as Zotero collections.

    A "project" in pa-paper-agent is a Zotero collection (= folder). Each
    project can hold:
    - Bibliographic items (papers pushed via `pa zotero push`)
    - A master note (= project summary, research log, links)
    - Sub-collections (for nested topics / sub-projects)

    **Workflow**:
        pa zotero project create --name "long-term care"   # create
        pa zotero push --corpus refs.bib                  # add papers
        pa zotero project add --name "long-term care" --doi 10.xxxx/yyy
        pa zotero project note --name "long-term care"     # create master note
        pa zotero project status --name "long-term care"   # see progress

    **Auto-create from pa search-and-import** (planned v3.9.16.1):
        pa search-and-import --query "long-term care" --project "long-term care"
        # = fetch → bucket (downloaded/failed) → push downloaded → auto-create
        # project if missing + auto-append to master note
    """
    pass


@zotero_project.command(name="create")
@click.option("--name", "name", required=True,
              help="Project name (= Zotero collection name, case-insensitive dedup)")
@click.option("--parent-key", "parent_key", default=None,
              help="Optional parent collection key (for nested projects)")
@click.option("--json", "as_json", is_flag=True,
              help="Output JSON (else human-readable)")
def zotero_project_create(name, parent_key, as_json):
    """[P3-28] Create a Zotero collection for a research project (idempotent).

    If a collection with the same name already exists, returns its key
    with status='exists' (no error). Re-running is safe.
    """
    from . import zotero_api
    try:
        client = zotero_api.get_client()
    except (ImportError, ValueError) as e:
        click.echo(f"[zotero-project] ERROR: {e}", err=True)
        sys.exit(2)
    result = zotero_api.create_collection(client, name, parent_key=parent_key)
    if as_json:
        click.echo(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if result["status"] == "created":
            click.echo(
                f"[zotero-project] created collection '{result['name']}' "
                f"(key={result['key']})"
            )
        elif result["status"] == "exists":
            click.echo(
                f"[zotero-project] collection '{result['name']}' already exists "
                f"(key={result['key']}, items={result.get('numItems', 0)})"
            )
        else:
            click.echo(
                f"[zotero-project] ERROR: {result.get('error', 'unknown')}",
                err=True,
            )
            sys.exit(1)
    if result["status"] == "error":
        sys.exit(1)


@zotero_project.command(name="list")
@click.option("--json", "as_json", is_flag=True,
              help="Output JSON (else human-readable table)")
@click.option("--include-nested", "include_nested", is_flag=True,
              help="Include sub-collections (default: top-level only)")
def zotero_project_list(as_json, include_nested):
    """[P3-28] List all research projects (= Zotero collections)."""
    from . import zotero_api
    try:
        client = zotero_api.get_client()
    except (ImportError, ValueError) as e:
        click.echo(f"[zotero-project] ERROR: {e}", err=True)
        sys.exit(2)
    colls = zotero_api.list_collections(client, top_only=not include_nested)
    if as_json:
        click.echo(json.dumps(colls, ensure_ascii=False, indent=2))
        return
    if not colls:
        click.echo("[zotero-project] no collections (= no projects) found")
        return
    click.echo(f"[zotero-project] {len(colls)} collection(s):")
    click.echo(f"  {'NAME':<40s}  {'ITEMS':>6s}  {'SUBS':>5s}  KEY")
    for c in colls:
        click.echo(
            f"  {c['name'][:38]:<40s}  {c.get('numItems', 0):>6d}  "
            f"{c.get('numCollections', 0):>5d}  {c['key']}"
        )


@zotero_project.command(name="status")
@click.option("--name", "name", default=None,
              help="Project name (mutually exclusive with --key)")
@click.option("--key", "key", default=None,
              help="Project collection key (mutually exclusive with --name)")
@click.option("--json", "as_json", is_flag=True,
              help="Output JSON (else human-readable)")
def zotero_project_status(name, key, as_json):
    """[P3-28] Show project status: item count, sub-collections, master notes."""
    from . import zotero_api
    if not name and not key:
        click.echo("[zotero-project] ERROR: must provide --name or --key", err=True)
        sys.exit(2)
    if name and key:
        click.echo("[zotero-project] ERROR: --name and --key are mutually exclusive", err=True)
        sys.exit(2)
    try:
        client = zotero_api.get_client()
    except (ImportError, ValueError) as e:
        click.echo(f"[zotero-project] ERROR: {e}", err=True)
        sys.exit(2)

    coll = None
    if key:
        # Direct lookup not exposed; use list + filter
        all_colls = zotero_api.list_collections(client, top_only=False)
        coll = next((c for c in all_colls if c["key"] == key), None)
    else:
        coll = zotero_api.find_collection_by_name(client, name)

    if not coll:
        click.echo(
            f"[zotero-project] project not found: name={name!r} key={key!r}",
            err=True,
        )
        sys.exit(1)

    items = zotero_api.get_collection_items(client, coll["key"])
    notes = zotero_api.list_collection_notes(client, coll["key"])

    status = {
        "name": coll["name"],
        "key": coll["key"],
        "numItems": coll.get("numItems", len(items)),
        "numCollections": coll.get("numCollections", 0),
        "version": coll.get("version", 0),
        "items_returned": len(items),
        "master_notes": [
            {"key": n["key"], "title": n.get("title", ""), "dateModified": n.get("dateModified", "")}
            for n in notes
        ],
        "recent_items": items[:5],  # most recent 5
    }
    if as_json:
        click.echo(json.dumps(status, ensure_ascii=False, indent=2))
        return
    click.echo(
        f"[zotero-project] '{status['name']}' (key={status['key']})\n"
        f"  items:           {status['numItems']}\n"
        f"  sub-collections: {status['numCollections']}\n"
        f"  master notes:    {len(status['master_notes'])}"
    )
    for n in status["master_notes"]:
        click.echo(
            f"    - {n['title']}  ({n['dateModified'][:10] if n['dateModified'] else '?'})  "
            f"key={n['key']}"
        )
    if status["recent_items"]:
        click.echo(f"  recent items (top 5 of {len(items)}):")
        for r in status["recent_items"]:
            date = r.get("date", "????")[:10]
            title = r.get("title", "?")[:60]
            doi = r.get("DOI", "")
            click.echo(f"    {date}  {title:60s}  {doi}")


@zotero_project.command(name="note")
@click.option("--name", "name", default=None,
              help="Project name (mutually exclusive with --key)")
@click.option("--key", "key", default=None,
              help="Project collection key (mutually exclusive with --name)")
@click.option("--title", "title", default=None,
              help="Note title (default: '<project> — research note')")
@click.option("--content-file", "content_file", default=None,
              type=click.Path(exists=True),
              help="Path to a markdown/text file with note body")
@click.option("--append", "append_text", default=None,
              help="Append a one-liner to existing master note (creates note if missing)")
def zotero_project_note(name, key, title, content_file, append_text):
    """[P3-28] Create or append to a project's master note (Zotero note).

    Master note is attached to the collection. Use to track research
    questions, synthesis, links to external docs, etc.

    Examples:
      pa zotero project note --name "long-term care" --content-file note.md
      pa zotero project note --name "long-term care" --append "2026-08-18: read 5 papers on X"
    """
    from . import zotero_api
    if not name and not key:
        click.echo("[zotero-project] ERROR: must provide --name or --key", err=True)
        sys.exit(2)
    if name and key:
        click.echo("[zotero-project] ERROR: --name and --key are mutually exclusive", err=True)
        sys.exit(2)
    if not content_file and not append_text:
        click.echo("[zotero-project] ERROR: must provide --content-file or --append", err=True)
        sys.exit(2)

    try:
        client = zotero_api.get_client()
    except (ImportError, ValueError) as e:
        click.echo(f"[zotero-project] ERROR: {e}", err=True)
        sys.exit(2)

    coll = None
    if key:
        all_colls = zotero_api.list_collections(client, top_only=False)
        coll = next((c for c in all_colls if c["key"] == key), None)
    else:
        coll = zotero_api.find_collection_by_name(client, name)
    if not coll:
        click.echo(
            f"[zotero-project] project not found. Create it first: "
            f"pa zotero project create --name {name!r}",
            err=True,
        )
        sys.exit(1)

    final_title = title or f"{coll['name']} — research note"

    # If --append, fetch the latest master note and append to it
    if append_text:
        from datetime import datetime
        existing_notes = zotero_api.list_collection_notes(client, coll["key"])
        if existing_notes:
            latest = existing_notes[0]  # most recent
            # Strip HTML tags to get plain text, then append
            from html.parser import HTMLParser
            class Stripper(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.parts = []
                def handle_data(self, d):
                    self.parts.append(d)
            s = Stripper()
            s.feed(latest.get("note", ""))
            plain = "".join(s.parts).strip()
            stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            new_content = f"{plain}\n\n---\n\n**{stamp}**  {append_text}\n"
            new_html = new_content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            new_html = new_html.replace("\n", "<br/>\n")
            try:
                item = client.item(latest["key"])
                item_data = item.get("data", item)
                item_data["note"] = f"<pre>{new_html}</pre>"
                client.update_item(item)
                click.echo(
                    f"[zotero-project] appended to note {latest['key']} in '{coll['name']}'"
                )
            except Exception as e:
                click.echo(f"[zotero-project] ERROR: append failed: {e}", err=True)
                sys.exit(1)
            return
        else:
            # No existing note: create one with the append text
            content = (
                f"# {final_title}\n\n"
                f"Project master note for Zotero collection '{coll['name']}' "
                f"(key={coll['key']}).\n\n"
                f"---\n\n"
                f"**{datetime.now().strftime('%Y-%m-%d %H:%M')}**  {append_text}\n"
            )
    else:
        content = Path(content_file).read_text(encoding="utf-8", errors="replace")

    result = zotero_api.create_collection_note(
        client=client,
        collection_key=coll["key"],
        title=final_title,
        content=content,
    )
    if result["status"] == "created":
        click.echo(
            f"[zotero-project] created note '{result['title']}' "
            f"(key={result['key']}) in '{coll['name']}'"
        )
    else:
        click.echo(
            f"[zotero-project] ERROR: {result.get('error', 'unknown')}",
            err=True,
        )
        sys.exit(1)


@zotero_project.command(name="add")
@click.option("--name", "name", default=None,
              help="Project name (mutually exclusive with --key)")
@click.option("--key", "key", default=None,
              help="Project collection key (mutually exclusive with --name)")
@click.option("--doi", "dois", multiple=True,
              help="One or more DOIs to add (repeatable)")
@click.option("--corpus", "corpus", default=None, type=click.Path(exists=True),
              help="Bibtex file to extract DOIs from")
def zotero_project_add(name, key, dois, corpus):
    """[P3-28] Add papers to a project collection.

    Papers must already exist in the Zotero library (use `pa zotero push`
    first). This command then attaches them to the project collection.

    Examples:
      pa zotero project add --name "long-term care" --doi 10.xxxx/yyy
      pa zotero project add --name "long-term care" --corpus refs.bib
    """
    from . import zotero_api
    if not name and not key:
        click.echo("[zotero-project] ERROR: must provide --name or --key", err=True)
        sys.exit(2)
    if name and key:
        click.echo("[zotero-project] ERROR: --name and --key are mutually exclusive", err=True)
        sys.exit(2)
    if not dois and not corpus:
        click.echo("[zotero-project] ERROR: must provide --doi or --corpus", err=True)
        sys.exit(2)

    try:
        client = zotero_api.get_client()
    except (ImportError, ValueError) as e:
        click.echo(f"[zotero-project] ERROR: {e}", err=True)
        sys.exit(2)

    coll = None
    if key:
        all_colls = zotero_api.list_collections(client, top_only=False)
        coll = next((c for c in all_colls if c["key"] == key), None)
    else:
        coll = zotero_api.find_collection_by_name(client, name)
    if not coll:
        click.echo(
            f"[zotero-project] project not found. Create it first: "
            f"pa zotero project create --name {name!r}",
            err=True,
        )
        sys.exit(1)

    # Collect DOIs
    doi_list = list(dois)
    if corpus:
        entries = zotero_api.parse_bibtex_for_doi(Path(corpus))
        for e in entries:
            d = zotero_api.normalize_doi(e.get("doi", ""))
            if d and d not in doi_list:
                doi_list.append(d)
    if not doi_list:
        click.echo("[zotero-project] no DOIs to add", err=True)
        return

    # Find items in library by DOI
    existing = zotero_api.check_dois_in_library(client, doi_list)
    if not existing:
        click.echo(
            f"[zotero-project] none of the {len(doi_list)} DOIs are in your Zotero library. "
            f"Run `pa zotero push` first.",
            err=True,
        )
        sys.exit(1)
    # Note: check_items returns which DOIs exist, but doesn't give item keys.
    # For each existing DOI, do a search to get the key.
    item_keys = []
    missing = []
    for d in doi_list:
        norm = zotero_api.normalize_doi(d)
        if norm in existing:
            # Search by exact DOI to get key
            try:
                items = client.items(q=norm, qmode="everything", limit=5)
                for it in items:
                    data = it.get("data", it)
                    if data.get("DOI", "").lower() == norm.lower():
                        item_keys.append(data["key"])
                        break
                else:
                    missing.append(d)
            except Exception:
                missing.append(d)
        else:
            missing.append(d)

    if missing:
        click.echo(
            f"[zotero-project] {len(missing)} DOIs not in library: {missing[:3]}...",
            err=True,
        )
    if not item_keys:
        click.echo("[zotero-project] no items to add", err=True)
        sys.exit(1)

    result = zotero_api.add_items_to_collection(client, item_keys, coll["key"])
    click.echo(
        f"[zotero-project] added {result['n_added']} item(s) to '{coll['name']}' "
        f"(failed={result['n_failed']})"
    )


@zotero_project.command(name="search")
@click.option("--query", "query", required=True,
              help="Search query (matched against title/creator/year)")
@click.option("--name", "name", default=None,
              help="Limit to a specific project collection")
@click.option("--limit", "limit", default=20, type=int,
              help="Max results to return (default 20)")
@click.option("--json", "as_json", is_flag=True,
              help="Output JSON (else human-readable)")
def zotero_project_search(query, name, limit, as_json):
    """[P3-28] Search across all (or one) project collections.

    Without --name: searches entire Zotero library.
    With --name: limits to items in that project's collection.

    Examples:
      pa zotero project search --query "long-term care insurance"
      pa zotero project search --query "warp drive" --name "long-term care"
    """
    from . import zotero_api
    try:
        client = zotero_api.get_client()
    except (ImportError, ValueError) as e:
        click.echo(f"[zotero-project] ERROR: {e}", err=True)
        sys.exit(2)

    if name:
        coll = zotero_api.find_collection_by_name(client, name)
        if not coll:
            click.echo(
                f"[zotero-project] project not found: {name!r}",
                err=True,
            )
            sys.exit(1)
        # Search within the collection
        try:
            raw = client.collection_items(coll["key"])
        except Exception as e:
            click.echo(f"[zotero-project] ERROR: {e}", err=True)
            sys.exit(1)
        # Filter by query (simple case-insensitive substring)
        needle = query.lower()
        results = []
        for item in raw:
            data = item.get("data", item)
            if data.get("itemType") in ("attachment", "note"):
                continue
            title = data.get("title", "").lower()
            if needle in title or any(
                needle in (c.get("name", "") or "").lower()
                for c in data.get("creators", [])
            ):
                results.append({
                    "key": data.get("key", ""),
                    "title": data.get("title", "(no title)"),
                    "creators": data.get("creators", []),
                    "date": data.get("date", ""),
                    "DOI": data.get("DOI", ""),
                    "itemType": data.get("itemType", ""),
                    "project": coll["name"],
                })
        results = results[:limit]
    else:
        # Library-wide search
        results = zotero_api.search_library(client, query, limit=limit)

    if as_json:
        click.echo(json.dumps(results, ensure_ascii=False, indent=2))
        return
    if not results:
        click.echo(f"[zotero-project] no matches for '{query}'")
        return
    scope = f"in project '{name}'" if name else "library-wide"
    click.echo(f"[zotero-project] {len(results)} match(es) for '{query}' ({scope}):")
    for r in results:
        date = r.get("date", "????")[:10]
        creators = ", ".join(
            c.get("name", c.get("lastName", "?")) for c in r.get("creators", [])[:2]
        )
        click.echo(
            f"  {date:10s}  {creators:30s}  {r.get('title', '?')[:60]}"
        )


# ─────────────────────────────────────────────────────────────────
# v3.9.18 [P3-28.2] pa zotero project pull / export-bib — bidirectional
# Zotero <-> local pa project
# ─────────────────────────────────────────────────────────────────
@zotero_project.command(name="pull")
@click.option("--name", "name", default=None,
              help="Collection name (mutually exclusive with --key)")
@click.option("--key", "key", default=None,
              help="Collection key (mutually exclusive with --name)")
@click.option("--slug", "slug", default=None,
              help="Local project slug (default: derived from collection name)")
@click.option("--root", "root_path", default=None, type=click.Path(file_okay=False),
              help="Override project root (default: ~/.paper-agent/projects/)")
@click.option("--overwrite", is_flag=True,
              help="Replace existing local project (default: refuse if exists)")
@click.option("--json", "as_json", is_flag=True,
              help="Output JSON (else human-readable summary)")
def zotero_project_pull(name, key, slug, root_path, overwrite, as_json):
    """[P3-28.2] Pull a Zotero collection into a local pa project.

    Creates a new pa project at <root>/<slug>/ with:
    - meta.json (with zotero_collection_key + name + version)
    - refs.bib (all bibliographic items as Bibtex)
    - judges.sqlite (empty)

    Use case: take a Zotero collection offline for local analysis
    (pa review, pa topics, pa search, etc.) without losing the
    Zotero-side authorship. To push local changes BACK to Zotero,
    use `pa zotero push --corpus <project>/refs.bib`.

    Examples:
      pa zotero project pull --name "long-term care"
      pa zotero project pull --name "long-term care" --slug ltc
      pa zotero project pull --key COLL_KEY --overwrite
    """
    from . import zotero_api
    if not name and not key:
        click.echo("[zotero-project] ERROR: must provide --name or --key", err=True)
        sys.exit(2)
    if name and key:
        click.echo("[zotero-project] ERROR: --name and --key are mutually exclusive", err=True)
        sys.exit(2)

    try:
        client = zotero_api.get_client()
    except (ImportError, ValueError) as e:
        click.echo(f"[zotero-project] ERROR: {e}", err=True)
        sys.exit(2)

    # Resolve collection
    coll = None
    if key:
        all_colls = zotero_api.list_collections(client, top_only=False)
        coll = next((c for c in all_colls if c["key"] == key), None)
    else:
        coll = zotero_api.find_collection_by_name(client, name)
    if not coll:
        click.echo(
            f"[zotero-project] collection not found: name={name!r} key={key!r}",
            err=True,
        )
        sys.exit(1)

    # Use the canonical collection name for the project title (so slug = name)
    canonical_name = coll["name"]

    result = zotero_api.pull_collection_to_project(
        client,
        collection_name=canonical_name,
        project_slug=slug,
        project_root=Path(root_path) if root_path else None,
        overwrite=overwrite,
    )

    if result["status"] == "error":
        click.echo(f"[zotero-project] ERROR: {result.get('error', 'unknown')}", err=True)
        sys.exit(1)

    if as_json:
        click.echo(json.dumps(result, ensure_ascii=False, indent=2))
        return

    click.echo(
        f"[zotero-project] '{result['project_slug']}' ({result['status']}) "
        f"from Zotero collection '{result['zotero_collection_name']}' "
        f"(key={result['zotero_key']})\n"
        f"  project dir:    {result['project_path']}\n"
        f"  refs.bib:       {result['refs_path']}\n"
        f"  meta.json:      {result['meta_path']}\n"
        f"  judges.sqlite:  {result['judges_path']}\n"
        f"  items:          {result['n_total']} total, "
        f"{result['n_converted']} converted, "
        f"{result['n_skipped']} skipped, "
        f"{result['n_failed']} failed"
    )


@zotero_project.command(name="export-bib")
@click.option("--name", "name", default=None,
              help="Collection name (mutually exclusive with --key)")
@click.option("--key", "key", default=None,
              help="Collection key (mutually exclusive with --name)")
@click.option("--out", "out_path", required=True, type=click.Path(dir_okay=False),
              help="Output .bib file path (will be overwritten)")
@click.option("--json", "as_json", is_flag=True,
              help="Output JSON summary (else human-readable)")
def zotero_project_export_bib(name, key, out_path, as_json):
    """[P3-28.2] Export a Zotero collection to a .bib file.

    Use case: share a Zotero collection with a colleague who doesn't
    use Zotero (e.g. Overleaf user). Converts each item to a Bibtex
    entry with the standard fields (title, author, year, doi, journal,
    volume, number, pages, abstract, zotero_key).

    Examples:
      pa zotero project export-bib --name "long-term care" --out ltc.bib
      pa zotero project export-bib --key COLL_KEY --out ltc.bib
    """
    from . import zotero_api
    if not name and not key:
        click.echo("[zotero-project] ERROR: must provide --name or --key", err=True)
        sys.exit(2)
    if name and key:
        click.echo("[zotero-project] ERROR: --name and --key are mutually exclusive", err=True)
        sys.exit(2)

    try:
        client = zotero_api.get_client()
    except (ImportError, ValueError) as e:
        click.echo(f"[zotero-project] ERROR: {e}", err=True)
        sys.exit(2)

    coll = None
    if key:
        all_colls = zotero_api.list_collections(client, top_only=False)
        coll = next((c for c in all_colls if c["key"] == key), None)
    else:
        coll = zotero_api.find_collection_by_name(client, name)
    if not coll:
        click.echo(
            f"[zotero-project] collection not found: name={name!r} key={key!r}",
            err=True,
        )
        sys.exit(1)

    result = zotero_api.collection_items_to_bibtex(
        client, coll["key"], out_path=Path(out_path)
    )

    if as_json:
        # Don't dump the whole bibtex_str; just summary
        summary = {
            "zotero_collection": coll["name"],
            "zotero_key": coll["key"],
            "out_path": result.get("out_path"),
            "n_total": result["n_total"],
            "n_converted": result["n_converted"],
            "n_skipped": result["n_skipped"],
            "n_failed": result["n_failed"],
            "results": result["results"],
        }
        click.echo(json.dumps(summary, ensure_ascii=False, indent=2))
        return

    click.echo(
        f"[zotero-project] exported collection '{coll['name']}' to {result['out_path']}\n"
        f"  total:     {result['n_total']}\n"
        f"  converted: {result['n_converted']}\n"
        f"  skipped:   {result['n_skipped']}  (no title or unsupported)\n"
        f"  failed:    {result['n_failed']}"
    )


# ─────────────────────────────────────────────────────────────────
# v3.9.19 [P3-28.3] pa zotero-project diff / sync -- incremental updates
# ─────────────────────────────────────────────────────────────────
@zotero_project.command(name="diff")
@click.option("--name", "name", default=None,
              help="Collection name (mutually exclusive with --key)")
@click.option("--key", "key", default=None,
              help="Collection key (mutually exclusive with --name)")
@click.option("--slug", "slug", default=None,
              help="Local project slug (default: derived from collection name)")
@click.option("--root", "root_path", default=None, type=click.Path(file_okay=False),
              help="Override project root (default: ~/.paper-agent/projects/)")
@click.option("--json", "as_json", is_flag=True,
              help="Output JSON (else human-readable)")
def zotero_project_diff(name, key, slug, root_path, as_json):
    """[P3-28.3] Show what changed in a Zotero collection vs local project.

    Compares a Zotero collection against the local refs.bib (from a
    previous `pa zotero-project pull`). Returns:
    - new DOIs (in Zotero but not local)
    - removed DOIs (in local but not Zotero) — NOT auto-deleted locally
    - unchanged count (matched in both)

    Does NOT modify any files. Use `pa zotero-project sync --apply`
    to actually pull the new items.

    Examples:
      pa zotero-project diff --name "long-term care"
      pa zotero-project diff --name "long-term care" --json
    """
    from . import zotero_api
    from .project import (
        DEFAULT_ROOT as PA_DEFAULT_ROOT,
        project_files,
    )
    if not name and not key:
        click.echo("[zotero-project] ERROR: must provide --name or --key", err=True)
        sys.exit(2)
    if name and key:
        click.echo("[zotero-project] ERROR: --name and --key are mutually exclusive", err=True)
        sys.exit(2)

    try:
        client = zotero_api.get_client()
    except (ImportError, ValueError) as e:
        click.echo(f"[zotero-project] ERROR: {e}", err=True)
        sys.exit(2)

    coll = None
    if key:
        all_colls = zotero_api.list_collections(client, top_only=False)
        coll = next((c for c in all_colls if c["key"] == key), None)
    else:
        coll = zotero_api.find_collection_by_name(client, name)
    if not coll:
        click.echo(
            f"[zotero-project] collection not found: name={name!r} key={key!r}",
            err=True,
        )
        sys.exit(1)

    # Resolve local project
    canonical_name = coll["name"]
    if not slug:
        slug = re.sub(r"[^A-Za-z0-9._-]+", "-", canonical_name.strip()).strip("-").lower() or "zotero-project"
    root = Path(root_path) if root_path else PA_DEFAULT_ROOT
    refs_path = project_files(slug, root)["refs"]
    meta_path = project_files(slug, root)["meta"]
    if not refs_path.exists():
        click.echo(
            f"[zotero-project] local project '{slug}' not found at {refs_path.parent} "
            f"(run `pa zotero-project pull --name {canonical_name!r}` first)",
            err=True,
        )
        sys.exit(1)

    diff = zotero_api.diff_collection_to_local(client, coll["key"], refs_path, local_meta_path=meta_path)

    if as_json:
        click.echo(json.dumps(diff, ensure_ascii=False, indent=2))
        return

    click.echo(
        f"[zotero-project] diff: Zotero collection '{coll['name']}' "
        f"(key={coll['key']}) vs local project '{slug}'\n"
        f"  zotero items:  {diff['zotero_n_items']}\n"
        f"  local DOIs:    {diff['local_n_dois']}\n"
        f"  unchanged:     {diff['unchanged_n']}\n"
        f"  new in zotero: {len(diff['new_dois'])}  (in Zotero, not in local)\n"
        f"  removed:       {len(diff['removed_dois'])}  (in local, not in Zotero)\n"
        f"  updated:       {diff.get('n_updated', 0)}  (Zotero items edited since last sync)"
    )
    if diff["new_dois"]:
        click.echo(f"\n  New DOIs (use `pa zotero-project sync --apply` to pull):")
        for d in diff["new_dois"][:20]:
            click.echo(f"    + {d}")
        if len(diff["new_dois"]) > 20:
            click.echo(f"    ... and {len(diff['new_dois']) - 20} more")
    if diff["removed_dois"]:
        click.echo(f"\n  Removed from Zotero (kept in local; tracked in meta.json):")
        for d in diff["removed_dois"][:20]:
            click.echo(f"    - {d}")
        if len(diff["removed_dois"]) > 20:
            click.echo(f"    ... and {len(diff['removed_dois']) - 20} more")
    if diff.get("n_updated", 0) > 0:
        click.echo(
            f"\n  Updated items (Zotero version > stored; "
            f"use `pa zotero-project pull --overwrite` to refresh):"
        )
        for it in diff.get("updated_items", [])[:20]:
            doi = it.get("DOI", "")
            title = (it.get("title", "") or "")[:50]
            zk = it.get("key", "")
            click.echo(f"    ~ [{zk}] {title}  ({doi})")
        if diff.get("n_updated", 0) > 20:
            click.echo(f"    ... and {diff['n_updated'] - 20} more")
    if not diff["new_dois"] and not diff["removed_dois"] and diff.get("n_updated", 0) == 0:
        click.echo("\n  Up to date. Nothing to sync.")


@zotero_project.command(name="sync")
@click.option("--name", "name", default=None,
              help="Collection name (mutually exclusive with --key)")
@click.option("--key", "key", default=None,
              help="Collection key (mutually exclusive with --name)")
@click.option("--slug", "slug", default=None,
              help="Local project slug (default: derived from collection name)")
@click.option("--root", "root_path", default=None, type=click.Path(file_okay=False),
              help="Override project root (default: ~/.paper-agent/projects/)")
@click.option("--apply/--no-apply", "apply", default=False,
              help="Actually write to refs.bib and meta.json (default: dry-run, "
                   "just shows the diff)")
@click.option("--json", "as_json", is_flag=True,
              help="Output JSON (else human-readable)")
def zotero_project_sync(name, key, slug, root_path, apply, as_json):
    """[P3-28.3] Incrementally sync a Zotero collection into a local pa project.

    Default: dry-run (just shows the diff like `pa zotero-project diff`).
    With `--apply`: appends new items to local refs.bib and refreshes
    meta.json (`zotero_collection_version`, `zotero_last_sync_at`,
    `removed_from_zotero` list).

    **Safety**: removed items in Zotero are NOT deleted from local
    refs.bib (you might want to keep them). They are recorded in
    `meta.json` under `removed_from_zotero: [dois]` so you can decide
    later.

    Use this after adding papers to a Zotero collection to keep your
    local pa project in sync, instead of doing a full re-pull.

    Examples:
      # Dry-run: see what would change
      pa zotero-project sync --name "long-term care"

      # Actually apply the changes
      pa zotero-project sync --name "long-term care" --apply
    """
    from . import zotero_api
    if not name and not key:
        click.echo("[zotero-project] ERROR: must provide --name or --key", err=True)
        sys.exit(2)
    if name and key:
        click.echo("[zotero-project] ERROR: --name and --key are mutually exclusive", err=True)
        sys.exit(2)

    try:
        client = zotero_api.get_client()
    except (ImportError, ValueError) as e:
        click.echo(f"[zotero-project] ERROR: {e}", err=True)
        sys.exit(2)

    coll = None
    if key:
        all_colls = zotero_api.list_collections(client, top_only=False)
        coll = next((c for c in all_colls if c["key"] == key), None)
    else:
        coll = zotero_api.find_collection_by_name(client, name)
    if not coll:
        click.echo(
            f"[zotero-project] collection not found: name={name!r} key={key!r}",
            err=True,
        )
        sys.exit(1)

    result = zotero_api.sync_collection_to_local(
        client,
        collection_name=coll["name"],
        project_slug=slug,
        project_root=Path(root_path) if root_path else None,
        dry_run=not apply,
    )

    if result["status"] == "error":
        click.echo(f"[zotero-project] ERROR: {result.get('error', 'unknown')}", err=True)
        sys.exit(1)

    if as_json:
        click.echo(json.dumps(result, ensure_ascii=False, indent=2))
        return

    mode = "DRY-RUN" if result["dry_run"] else "APPLIED"
    click.echo(
        f"[zotero-project] sync ({mode}): '{result['zotero_collection_name']}' "
        f"-> local project '{result['project_slug']}'\n"
        f"  new (will append):  {result['n_new']}\n"
        f"  removed (kept):     {result['n_removed']}\n"
        f"  updated:            {result.get('n_updated', 0)}  (use `pa zotero project pull --overwrite` to refresh)\n"
        f"  unchanged:          {result['n_unchanged']}\n"
        f"  refs.bib:           {result['refs_path']}\n"
        f"  meta.json:          {result['meta_path']}"
    )
    if result["dry_run"]:
        if result["n_new"] or result["n_removed"]:
            click.echo(
                "\n  Re-run with --apply to actually write to refs.bib and meta.json."
            )
        else:
            click.echo("\n  Up to date. Nothing to apply.")
    else:
        click.echo(
            f"\n  Applied: {result['n_new']} new item(s) added to refs.bib. "
            f"meta.json refreshed."
        )
        if result["n_removed"]:
            click.echo(
                f"  Note: {result['n_removed']} item(s) removed from Zotero are "
                f"kept locally and tracked in meta.json (removed_from_zotero)."
            )


# ─────────────────────────────────────────────────────────────────
# v3.9.16 [P3-29] pa obsidian — research sub-vault + project management
# ─────────────────────────────────────────────────────────────────
@main.group()
def obsidian():
    """[P3-29] Manage a research sub-vault inside your Obsidian vault.

    Adds a `0-Research/` folder to an existing Obsidian vault
    (configured via $PAPER_AGENT_OBSIDIAN_VAULT env var). Provides:

    - `init` — create the sub-folder skeleton
    - `project` subcommands — create / list / status / thought / note
    - `inbox` subcommands — drop uncategorized thoughts

    **Layout**:
        <vault>/0-Research/
        ├── Inbox/                  # uncategorized thoughts
        └── Projects/<slug>/
            ├── index.md            # project home
            ├── ideas.md            # raw thoughts
            ├── notes/              # atomic notes
            └── synthesis.md        # cross-paper synthesis

    Examples:
      pa obsidian init
      pa obsidian project create --name "long-term care" \\
          --research-question "How does public LTCI affect family caregivers?" \\
          --direction "empirical microeconomics"
      pa obsidian project thought --name "long-term care" \\
          --content "Wang 2020 has good identification but small sample"
      pa obsidian project note --name "long-term care" --type reading \\
          --content "Wang (2020) finds X. Key insight: Y. Open question: Z."
      pa obsidian inbox add --content "cross-ref: paper X about Y"
    """
    pass


@obsidian.command(name="init")
@click.option("--force-readme/--no-force-readme", default=False,
              help="Overwrite existing 0-Research/README.md if present")
def obsidian_init(force_readme):
    """[P3-29] Initialize the research sub-folder inside the Obsidian vault.

    Creates:
      - <vault>/0-Research/Inbox/
      - <vault>/0-Research/Projects/
      - <vault>/0-Research/README.md (if not exists)

    Idempotent: re-running is safe. Use --force-readme to overwrite README.
    """
    from . import obsidian as obs_mod
    try:
        result = obs_mod.init_vault()
    except ValueError as e:
        click.echo(f"[obsidian] ERROR: {e}", err=True)
        sys.exit(2)
    click.echo(f"[obsidian] research root: {result['root']}")
    if result["created"]:
        click.echo(f"[obsidian] created {len(result['created'])} item(s):")
        for p in result["created"]:
            click.echo(f"  + {p}")
    if result["existed"]:
        click.echo(f"[obsidian] {len(result['existed'])} item(s) already existed (skipped)")
    if force_readme:
        readme = Path(result["root"]) / "README.md"
        if readme.exists():
            readme.write_text(obs_mod._README_TEMPLATE, encoding="utf-8")
            click.echo(f"[obsidian] README.md overwritten")


@obsidian.group(name="project")
def obsidian_project():
    """[P3-29] Manage research projects in the sub-vault."""
    pass


@obsidian_project.command(name="create")
@click.option("--name", "name", required=True,
              help="Project name (will be slugified for folder name)")
@click.option("--research-question", "research_question", default="",
              help="The core research question this project addresses")
@click.option("--direction", "direction", default="",
              help="Research direction / methodology (e.g. 'empirical microeconomics')")
@click.option("--topic", "topic", default="",
              help="Free-text topic tag")
@click.option("--json", "as_json", is_flag=True,
              help="Output JSON (else human-readable)")
def obsidian_project_create(name, research_question, direction, topic, as_json):
    """[P3-29] Create a new research project in the sub-vault.

    Creates a folder Projects/<slug>/ with index.md, ideas.md, notes/.
    Idempotent: returns status='exists' if a project with the same slug
    already exists.
    """
    from . import obsidian as obs_mod
    try:
        result = obs_mod.create_project(
            name=name,
            research_question=research_question,
            direction=direction,
            topic=topic,
        )
    except ValueError as e:
        click.echo(f"[obsidian] ERROR: {e}", err=True)
        sys.exit(2)
    if as_json:
        click.echo(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if result["status"] == "created":
            click.echo(
                f"[obsidian] created project '{name}'\n"
                f"  slug:  {result['slug']}\n"
                f"  path:  {result['path']}"
            )
        elif result["status"] == "exists":
            click.echo(
                f"[obsidian] project '{name}' already exists (slug={result['slug']})\n"
                f"  path:  {result['path']}"
            )
        else:
            click.echo(f"[obsidian] ERROR: {result.get('error', 'unknown')}", err=True)
            sys.exit(1)
    if result["status"] == "error":
        sys.exit(1)


@obsidian_project.command(name="list")
@click.option("--json", "as_json", is_flag=True,
              help="Output JSON (else human-readable table)")
def obsidian_project_list(as_json):
    """[P3-29] List all research projects in the sub-vault."""
    from . import obsidian as obs_mod
    try:
        projects = obs_mod.list_projects()
    except ValueError as e:
        click.echo(f"[obsidian] ERROR: {e}", err=True)
        sys.exit(2)
    if as_json:
        click.echo(json.dumps(projects, ensure_ascii=False, indent=2))
        return
    if not projects:
        click.echo("[obsidian] no projects found. Create one with: pa obsidian project create --name ...")
        return
    click.echo(f"[obsidian] {len(projects)} project(s):")
    click.echo(f"  {'NAME':<40s}  {'SLUG':<25s}  {'THOUGHTS':>8s}  {'NOTES':>6s}  SYNTH")
    for p in projects:
        name = p["name"][:38]
        slug = p["slug"][:23]
        click.echo(
            f"  {name:<40s}  {slug:<25s}  {p['thought_count']:>8d}  "
            f"{p['note_count']:>6d}  {'Y' if p['synthesis_present'] else '-'}"
        )


@obsidian_project.command(name="status")
@click.option("--name", "name", required=True,
              help="Project name (will be slugified)")
@click.option("--json", "as_json", is_flag=True,
              help="Output JSON (else human-readable)")
def obsidian_project_status(name, as_json):
    """[P3-29] Show project status: thoughts, notes, recent activity."""
    from . import obsidian as obs_mod
    slug = obs_mod.slugify(name)
    try:
        result = obs_mod.project_status(slug)
    except ValueError as e:
        click.echo(f"[obsidian] ERROR: {e}", err=True)
        sys.exit(2)
    if result["status"] == "error":
        click.echo(f"[obsidian] ERROR: {result['error']}", err=True)
        sys.exit(1)
    if as_json:
        click.echo(json.dumps(result, ensure_ascii=False, indent=2))
        return
    click.echo(
        f"[obsidian] project '{result['name']}' (slug={result['slug']})\n"
        f"  root:           {result['root']}\n"
        f"  index.md:       {'Y' if result['has_index'] else '-'}\n"
        f"  ideas.md:       {'Y' if result['has_ideas'] else '-'}  ({result['thought_count']} thought(s))\n"
        f"  notes/:         {result['note_count']} note(s)\n"
        f"  synthesis.md:   {'Y' if result['synthesis_present'] else '-'}"
    )
    if result["recent_notes"]:
        click.echo(f"  recent notes:")
        for n in result["recent_notes"]:
            click.echo(
                f"    [{n['modified'][:16]}]  {n['title'][:50]}\n"
                f"      {n['path']}"
            )


@obsidian_project.command(name="thought")
@click.option("--name", "name", required=True,
              help="Project name (auto-creates project if missing)")
@click.option("--content", "content", required=True,
              help="The thought text (1-3 sentences)")
def obsidian_project_thought(name, content):
    """[P3-29] Append a raw/unformed thought to a project's ideas.md.

    Auto-creates the project (with minimal index.md) if it doesn't exist,
    so you can quickly capture ideas before formalizing the project.
    """
    from . import obsidian as obs_mod
    try:
        result = obs_mod.add_thought(name, content)
    except ValueError as e:
        click.echo(f"[obsidian] ERROR: {e}", err=True)
        sys.exit(2)
    if result["status"] == "error":
        click.echo(f"[obsidian] ERROR: {result['error']}", err=True)
        sys.exit(1)
    click.echo(
        f"[obsidian] appended thought to '{result['name']}' "
        f"(total {result['thought_count']} thought(s))"
    )


@obsidian_project.command(name="note")
@click.option("--name", "name", required=True,
              help="Project name (auto-creates project if missing)")
@click.option("--type", "note_type", default="idea",
              type=click.Choice(list(obs_mod := __import__('pa_cli.obsidian', fromlist=['NOTE_TYPES']).NOTE_TYPES)),
              help="Note type (idea/reading/synthesis/question/evidence)")
@click.option("--title", "title", default="",
              help="Explicit title (else inferred from first line of content)")
@click.option("--content", "content", required=True,
              help="Note body (markdown)")
def obsidian_project_note(name, note_type, title, content):
    """[P3-29] Create a new atomic note in a project.

    Stored in <vault>/0-Research/Projects/<slug>/notes/<timestamp>.md
    with YAML frontmatter (title, type, project, created).
    """
    from . import obsidian as obs_mod
    try:
        result = obs_mod.add_note(name, content, note_type=note_type, title=title)
    except ValueError as e:
        click.echo(f"[obsidian] ERROR: {e}", err=True)
        sys.exit(2)
    if result["status"] == "error":
        click.echo(f"[obsidian] ERROR: {result['error']}", err=True)
        sys.exit(1)
    click.echo(
        f"[obsidian] created {result['type']} note '{result['title']}'\n"
        f"  project: {result['name']}\n"
        f"  path:    {result['path']}"
    )


@obsidian.group(name="inbox")
def obsidian_inbox():
    """[P3-29] Inbox — uncategorized thoughts not tied to a project."""
    pass


@obsidian_inbox.command(name="add")
@click.option("--content", "content", required=True,
              help="The thought text")
def obsidian_inbox_add(content):
    """[P3-29] Drop a thought into the global Inbox (no project)."""
    from . import obsidian as obs_mod
    try:
        result = obs_mod.inbox_add(content)
    except ValueError as e:
        click.echo(f"[obsidian] ERROR: {e}", err=True)
        sys.exit(2)
    if result["status"] == "error":
        click.echo(f"[obsidian] ERROR: {result['error']}", err=True)
        sys.exit(1)
    click.echo(
        f"[obsidian] inbox note created\n"
        f"  filename: {result['filename']}\n"
        f"  path:     {result['path']}"
    )


@obsidian_inbox.command(name="list")
@click.option("--limit", "limit", default=20, type=int,
              help="Max results to return (default 20)")
@click.option("--json", "as_json", is_flag=True,
              help="Output JSON (else human-readable)")
def obsidian_inbox_list(limit, as_json):
    """[P3-29] List recent inbox notes (most recent first)."""
    from . import obsidian as obs_mod
    try:
        items = obs_mod.inbox_list(limit=limit)
    except ValueError as e:
        click.echo(f"[obsidian] ERROR: {e}", err=True)
        sys.exit(2)
    if as_json:
        click.echo(json.dumps(items, ensure_ascii=False, indent=2))
        return
    if not items:
        click.echo("[obsidian] inbox empty")
        return
    click.echo(f"[obsidian] {len(items)} recent inbox note(s):")
    for it in items:
        click.echo(f"  [{it['modified'][:16]}]  {it['title'][:50]}")
        click.echo(f"      {it['path']}")


# ─────────────────────────────────────────────────────────────────
# v3.9.20 [P3-29.2] pa obsidian daily-link -- backlink in GTD daily note
# ─────────────────────────────────────────────────────────────────
@obsidian.command(name="daily-link")
@click.option("--project", "project", required=True,
              help="Research project name (= Zotero collection / Obsidian project)")
@click.option("--date", "date", default=None,
              help="ISO date YYYY-MM-DD (default: today, local time)")
@click.option("--vault", "vault_path", default=None, type=click.Path(file_okay=False),
              help="Override vault path (default: $PAPER_AGENT_OBSIDIAN_VAULT)")
@click.option("--create/--no-create", "create_if_missing", default=False,
              help="Create a stub daily note if it doesn't exist "
                   "(default: skip gracefully)")
@click.option("--json", "as_json", is_flag=True,
              help="Output JSON (else human-readable)")
def obsidian_daily_link(project, date, vault_path, create_if_missing, as_json):
    """[P3-29.2] Add a backlink to a project in today's (or a given date's) daily note.

    Writes a `## Active research projects` section to
    `<vault>/4-Daily/<date>.md` with a wiki-link to the project's
    index page (`0-Research/Projects/<slug>/index`).

    Idempotent: re-running for the same project is a no-op
    (per-project HTML comment marker handles dedup).

    Multiple projects on the same day: each gets its own line in
    the same section.

    If the daily note doesn't exist and `--create` is not set, the
    command skips gracefully (no error, no file created).

    Use case: at the end of a research session, add a backlink so
    the day's daily note has 1-click access to the project you're
    working on. Common workflow:

        # at end of research session:
        pa obsidian daily-link --project "long-term care"
        # tomorrow's daily note will show this project
    """
    from . import obsidian as obs_mod
    result = obs_mod.daily_link(
        project_name=project,
        date=date,
        vault_path=Path(vault_path) if vault_path else None,
        create_if_missing=create_if_missing,
    )
    if as_json:
        click.echo(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if result["status"] == "error":
        click.echo(f"[obsidian] ERROR: {result.get('error', 'unknown')}", err=True)
        sys.exit(1)
    if result["status"] == "skipped_no_vault":
        click.echo(
            f"[obsidian] skipped: {result.get('error', 'vault not configured')}",
            err=True,
        )
        sys.exit(2)
    if result["status"] == "skipped_no_daily_note":
        click.echo(
            f"[obsidian] skipped: daily note does not exist at {result['daily_path']}\n"
            f"  Re-run with --create to create a stub, or create the note manually first.",
            err=True,
        )
        return
    # status == "linked"
    if result.get("link_added"):
        if result.get("section_created"):
            click.echo(
                f"[obsidian] created section + added backlink to '{project}' "
                f"in {result['daily_path']}"
            )
        else:
            click.echo(
                f"[obsidian] added backlink to '{project}' "
                f"in {result['daily_path']} (section already existed)"
            )
    else:
        click.echo(
            f"[obsidian] '{project}' already linked in {result['daily_path']} (no change)"
        )


# ─────────────────────────────────────────────────────────────────
# v3.9.17.0 [P3-28.1] pa search-and-import — end-to-end research loop
# ─────────────────────────────────────────────────────────────────
@main.command(name="search-and-import")
@click.option("--query", "query", required=True,
              help="Search query (topic name)")
@click.option("--project", "project", required=True,
              help="Zotero project name (= collection, auto-created if missing)")
@click.option("--limit", "limit", default=20, type=int, show_default=True,
              help="Max results per engine (default 20)")
@click.option("--year-min", "year_min", type=int, default=None,
              help="Filter: min publication year")
@click.option("--year-max", "year_max", type=int, default=None,
              help="Filter: max publication year")
@click.option("--engine", "engine", default="all", show_default=True,
              help="Search engines (comma-separated; default 'all' = 8 engines)")
@click.option("--out-dir", "out_dir", default="./pdfs",
              type=click.Path(file_okay=False),
              help="Where to save PDFs (default ./pdfs/)")
@click.option("--max-total-sec", "max_total_sec", default=1800, type=int, show_default=True,
              help="Global timeout for the fetch batch (s)")
@click.option("--no-skip-existing", "no_skip_existing", is_flag=True,
              help="Re-fetch even if PDF already exists in out_dir")
@click.option("--no-push/--push", "do_push", default=True,
              help="Skip Zotero push step (default: push downloaded DOIs)")
@click.option("--no-project/--project", "do_project", default=True,
              help="Skip Zotero project setup (default: create/add/note)")
@click.option("--with-obsidian/--no-obsidian", "with_obsidian", default=False,
              help="[v3.9.17.2 / P3-29.1] Also create matching Obsidian project page. "
                   "Requires $PAPER_AGENT_OBSIDIAN_VAULT env var (else gracefully skipped). "
                   "Default: --no-obsidian (Obsidian hint shown at end instead).")
@click.option("--json", "as_json", is_flag=True,
              help="Output full JSON report (else human-readable summary)")
@click.option("--quiet", is_flag=True, help="Suppress progress output")
def search_and_import(
    query, project, limit, year_min, year_max, engine, out_dir,
    max_total_sec, no_skip_existing, do_push, do_project, with_obsidian, as_json, quiet,
):
    """[P3-28.1] End-to-end research workflow: search → fetch → bucket → push to Zotero project + master note.

    Steps (per ROADMAP Round 16 deferred):
      1. Search (8 default engines) → write temp Bibtex
      2. Fetch PDFs (8 channels: arxiv → unpaywall → scihub → annas → cnki → ...)
      3. Bucket results: downloaded vs failed-to-download
      4. (optional) Push downloaded DOIs to your Zotero library (idempotent)
      5. (optional) Create Zotero project (= collection) if missing
      6. Add downloaded items to project collection
      7. Append fetch log to project's master note (downloaded + failed tables)

    Use this for: "every time I run paper-agent to study a topic X, set up
    the Zotero project X with papers + note + bucket log automatically."

    Required env vars for steps 4-7:
      $ZOTERO_API_KEY       — https://www.zotero.org/settings/keys
      $ZOTERO_LIBRARY_ID    — numeric ID, same page

    Examples:
      pa search-and-import --query "long-term care insurance" --project "long-term care"
      pa search-and-import --query "数字普惠金融" --project "digital-finance" \\
          --limit 30 --year-min 2018
    """
    from . import search_and_import as sai

    try:
        result = sai.run_search_and_import(
            query=query,
            project_name=project,
            year_min=year_min, year_max=year_max,
            limit=limit, engine=engine,
            out_dir=Path(out_dir),
            max_total_sec=max_total_sec,
            skip_existing=not no_skip_existing,
            do_push=do_push and do_project,  # skip both together if --no-project
            with_obsidian=with_obsidian,
            quiet=quiet,
        )
    except Exception as e:
        click.echo(f"[search-and-import] FATAL: {e}", err=True)
        sys.exit(2)

    if as_json:
        click.echo(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return

    # Human-readable summary
    s = result.get("summary", {})
    steps = result.get("steps", {})
    click.echo(
        f"[search-and-import] DONE\n"
        f"  query:           {query!r}\n"
        f"  project:         {project!r}\n"
        f"  search results:  {s.get('n_search_results', 0)}\n"
        f"  downloaded:      {s.get('n_downloaded', 0)}\n"
        f"  failed:          {s.get('n_failed', 0)}"
    )
    if "push" in steps:
        p = steps["push"]
        click.echo(
            f"  Zotero push:     {p.get('status', '?')}  "
            f"(pushed={p.get('n_pushed', 0)} skipped={p.get('n_skipped', 0)} "
            f"failed={p.get('n_failed', 0)})"
        )
    proj = steps.get("project", {})
    if proj.get("status") == "ok":
        click.echo(
            f"  Zotero project:  {proj.get('project_name', '?')}  "
            f"({proj.get('project_status', '?')}, key={proj.get('project_key', '?')})\n"
            f"  items added:     {proj.get('n_added', 0)}\n"
            f"  master note:     key={proj.get('note_key', '?')}  "
            f"({proj.get('note_status', '?')})"
        )
    elif proj:
        click.echo(f"  Zotero project:  {proj.get('status', '?')}  {proj.get('error', '')}", err=True)

    # v3.9.17.2 [P3-29.1]: Obsidian step output
    obs = steps.get("obsidian")
    if obs:
        if obs.get("status") == "ok":
            click.echo(
                f"  Obsidian project: {obs.get('project_status', '?')}  "
                f"(slug={obs.get('project_slug', '?')}, "
                f"thoughts={obs.get('thought_count', 0)})\n"
                f"  Obsidian path:    {obs.get('obsidian_path', '?')}"
            )
        elif obs.get("status") == "skipped":
            click.echo(
                f"  Obsidian:         skipped ({obs.get('reason', 'env not set')})",
                err=True,
            )
        else:
            click.echo(
                f"  Obsidian:         {obs.get('status', '?')}  {obs.get('error', '')}",
                err=True,
            )

    if result.get("errors"):
        click.echo("\n[search-and-import] errors:", err=True)
        for err in result["errors"]:
            click.echo(f"  - {err}", err=True)

    # Obsidian hint (if project is set up OK)
    if proj.get("status") == "ok":
        click.echo(
            f"\n[search-and-import] Hint: also create an Obsidian project page with:\n"
            f"  pa obsidian project create --name \"{project}\" \\\n"
            f"      --research-question \"...\" --direction \"...\"\n"
            f"  pa obsidian project thought --name \"{project}\" \\\n"
            f"      --content \"(see Zotero project {proj.get('project_key', '?')} for papers)\""
        )

    # Exit code: 0 if download+project OK, 1 if any error
    if result.get("errors"):
        sys.exit(1)



