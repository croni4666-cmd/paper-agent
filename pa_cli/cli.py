"""
pa_cli.cli — Click command group for paper-agent CLI.

Usage examples:
  python -m pa_cli fetch 10.1016/j.caeo.2024.100184 --proxy http://127.0.0.1:7897
  python -m pa_cli search "AI literacy higher education" --year-min 2023 --limit 20
  python -m pa_cli review ./pdfs --output lit_review.md
  python -m pa_cli version
"""

import json
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
    cmd_remind(quiet=True)


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
@click.option("--alert-file", default=None,
              help="Also write current alerts to this path (default: ~/.mavis/state/api_key_alerts.json)")
def keys_check(service_id, alert_file):
    """Live-probe each API key (or one specific). Updates last_checked timestamp."""
    from .keys import cmd_check, write_alerts_to_state
    results = cmd_check(service_id)
    click.echo(json.dumps(results, indent=2, ensure_ascii=False))
    # Also update alerts file for cross-session reminder pickup
    if alert_file:
        path = write_alerts_to_state(Path(alert_file))
    else:
        path = write_alerts_to_state()
    # Count warnings
    n_warn = sum(1 for r in results.values()
                 if isinstance(r, dict) and r.get("status") not in ("ok", "missing"))
    click.echo(f"\n[pa-keys] alerts file: {path} ({n_warn} non-ok status)", err=True)


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
@click.option("--write-alerts", default=None,
              help="Write alerts to this path (default: ~/.mavis/state/api_key_alerts.json)")
def keys_remind(as_json, write_alerts):
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
    # Write alerts file by default
    target = Path(write_alerts) if write_alerts else None
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
@click.option("--quiet", is_flag=True, help="Suppress progress output")
def fetch(doi, output_dir, proxy, channels, unpaywall_email, max_total_sec, quiet):
    """Fetch a single paper PDF by DOI using 8 channels with Cloudflare fallback."""
    from .fetch import fetch_doi
    if not quiet:
        click.echo(f"[pa] fetch DOI={doi}", err=True)
        click.echo(f"[pa] output_dir={output_dir} proxy={proxy or '(none)'}", err=True)
        click.echo(f"[pa] channels={channels}", err=True)
        click.echo(f"[pa] max_total_sec={max_total_sec}", err=True)
    result = fetch_doi(
        doi=doi, output_dir=output_dir, proxy=proxy,
        channels=channels.split(","), unpaywall_email=unpaywall_email,
        max_total_sec=max_total_sec,
    )
    click.echo(json.dumps(result, indent=2, ensure_ascii=False))
    if result.get("saved_as"):
        click.echo(f"\n[pa] ✅ saved {result['saved_as']}", err=True)
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
@click.option("-o", "--output", default=None,
              help="Save JSON results to file")
@click.option("--quiet", is_flag=True, help="Suppress progress output")
def search(query, year_min, year_max, limit, engine, output, quiet):
    """5-engine academic paper search (Crossref / OpenAlex / arXiv / S2 / CORE)."""
    from .search import run_search
    if not quiet:
        click.echo(f"[pa] search query={query!r} years={year_min}-{year_max}", err=True)
    results = run_search(query, year_min, year_max, limit, engine)
    if not quiet:
        click.echo(f"[pa] by_engine: {results['by_engine']}", err=True)
        click.echo(f"[pa] dedup_count: {results['dedup_count']}", err=True)
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


if __name__ == "__main__":
    main()