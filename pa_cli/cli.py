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
              help="all / crossref,openalex,arxiv,semanticscholar,core (comma-separated)")
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
@click.option("--quiet", is_flag=True, help="Suppress progress output")
def search(query, year_min, year_max, limit, engine, out_format, output,
           concept_ids, concept_names, concept_mode, quiet):
    """5-engine academic paper search (Crossref / OpenAlex / arXiv / S2 / CORE).

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
    results = run_search(query, year_min, year_max, limit, engine,
                         concepts_filter=concepts_filter or None)
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
    click.echo(f"  search_implemented:     {s['search_implemented']} (real wiring in v3.9.7.5 + year filter + jitter)")
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


if __name__ == "__main__":
    main()