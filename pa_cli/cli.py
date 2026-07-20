"""
pa_cli.cli — Click command group for paper-agent CLI.

Usage examples:
  python -m pa_cli fetch 10.1016/j.caeo.2024.100184 --proxy http://127.0.0.1:7897
  python -m pa_cli search "AI literacy higher education" --year-min 2023 --limit 20
  python -m pa_cli review ./pdfs --output lit_review.md
  python -m pa_cli version
"""

import json
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
              help="HTTP proxy URL (e.g. http://127.0.0.1:7897)")
@click.option("--channels", default="openalex,arxiv,unpaywall,doi_redirect,scihub,playwright",
              show_default=True, help="Comma-separated channel list")
@click.option("--unpaywall-email", default="hello@example.com", show_default=True,
              help="Email registered with Unpaywall API")
@click.option("--max-total-sec", default=300, show_default=True,
              help="Hard cap on total runtime (paper-agent v4: 300s)")
@click.option("--no-cache", is_flag=True,
              help="Bypass cache lookup; cascade attempts download (cache still written on success)")
@click.option("--quiet", is_flag=True, help="Suppress progress output")
def fetch(doi, output_dir, proxy, channels, unpaywall_email, max_total_sec, no_cache, quiet):
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
        click.echo(f"[pa] channels={channels} cache={'disabled' if no_cache else 'enabled'}", err=True)
        click.echo(f"[pa] max_total_sec={max_total_sec}", err=True)
    result = fetch_doi(
        doi=doi, output_dir=output_dir, proxy=proxy,
        channels=channels.split(","), unpaywall_email=unpaywall_email,
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
        sys.exit(2)
    else:
        click.echo("\n[pa] ❌ all channels failed", err=True)
        sys.exit(1)


@main.command()
@click.argument("query")
@click.option("--year-min", type=int, default=None, help="Filter: min publication year")
@click.option("--year-max", type=int, default=None, help="Filter: max publication year")
@click.option("--limit", type=int, default=50, show_default=True,
              help="Max results per engine")
@click.option("--engine", default="all", show_default=True,
              help="all / crossref,openalex,arxiv,semanticscholar,aminer,cnki,core "
                   "(comma-separated; default 'all' = first 6; 'core' = explicit CORE-only)")
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
@click.option("--quiet", is_flag=True, help="Suppress progress output")
def search(query, year_min, year_max, limit, engine, out_format, output,
           concept_ids, concept_names, concept_mode, enrich_top, enrich_top_min_cites,
           enrich_max_age_years, sort_by, source_filter, quiet):
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
    click.echo("    C:\\Users\\DengN\\.paper-agent\\cookies\\cnki.json")
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