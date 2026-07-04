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
@click.option("--quiet", is_flag=True, help="Suppress progress output")
def search(query, year_min, year_max, limit, engine, out_format, output, quiet):
    """5-engine academic paper search (Crossref / OpenAlex / arXiv / S2 / CORE)."""
    from .search import run_search
    from .bibtex import write_bibtex
    if not quiet:
        click.echo(f"[pa] search query={query!r} years={year_min}-{year_max} format={out_format}", err=True)
    results = run_search(query, year_min, year_max, limit, engine)
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
@click.option("--quiet", is_flag=True, help="Suppress progress output")
def review(corpus_dir, template, output, word_count_min, quiet):
    """Synthesize lit review markdown from a corpus directory of PDFs."""
    from .review import synthesize
    corpus_path = Path(corpus_dir)
    if not quiet:
        click.echo(f"[pa] review corpus={corpus_path}", err=True)
        click.echo(f"[pa] word_count_min={word_count_min} template={template}", err=True)
    md = synthesize(corpus_path, template, word_count_min)
    if output:
        Path(output).write_text(md, encoding="utf-8")
        click.echo(f"[pa] saved {output}", err=True)
    else:
        click.echo(md)


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


if __name__ == "__main__":
    main()