"""pa_cli.search_and_import — end-to-end research workflow orchestrator (v3.9.17.0, [P3-28.1])

**Purpose**: glue together `pa search` + `pa fetch-batch` + `pa zotero push`
+ `pa zotero project` into a single command that, for a given research
topic, does:

1. **Search** — multi-engine paper search (8 default engines)
2. **Write Bibtex** — convert results to a temporary `.bib` file
3. **Fetch PDFs** — batch download via `pa fetch-batch` (cascade of
   8 channels: arxiv → unpaywall → doi_redirect → scihub → annas →
   cnki → playwright → openalex)
4. **Bucket** — split into `downloaded` (PDF saved) vs `failed` (no
   PDF saved, fetch error captured)
5. **Push to Zotero library** — push downloaded DOIs (idempotent via
   `pyzotero.check_items()`)
6. **Create Zotero project** (= Zotero collection) — auto-create if
   missing (idempotent by name)
7. **Add papers to project** — attach the just-pushed items to the
   collection
8. **Append to master note** — write a structured fetch log to the
   project's master note (per-bucket table + metadata)

**Why a single command?** The user pain point is: "every time I run
paper-agent to study a topic, I want the papers, the project, and the
note all set up automatically." Without this, you chain 4-5 commands
(`pa search` → `pa fetch-batch` → `pa zotero push` → `pa zotero
project create` → `pa zotero project add` → `pa zotero project note`)
and lose track of which corpus matches which project.

**Obsidian integration deferred to v3.9.17.1**: see ROADMAP Round 16
deferred section. For now, after a successful run, a one-liner hint
tells you the corresponding `pa obsidian project` commands to run
manually if you want.

**No state** lives outside Zotero + the local out_dir. The temporary
Bibtex file is deleted after the run.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Lazy imports for heavy modules
def _import_run_search():
    from . import search
    return search.run_search


def _import_run_fetch_batch():
    from . import fetch_batch as fb
    return fb.run_fetch_batch, fb.FetchResult, fb.FetchSummary, fb.write_summary_json


def _import_write_bibtex():
    from . import bibtex
    return bibtex.write_bibtex


def _import_zotero_api():
    from . import zotero_api
    return zotero_api


def _import_obsidian():
    from . import obsidian as obs_mod
    return obs_mod


# ─────────────────────────────────────────────────────────────────
# Step 1: search → bibtex
# ─────────────────────────────────────────────────────────────────
def search_to_bibtex(
    query: str,
    year_min: Optional[int] = None,
    year_max: Optional[int] = None,
    limit: int = 20,
    engine: str = "all",
    out_bib_path: Optional[Path] = None,
    quiet: bool = False,
) -> Tuple[Path, List[Dict[str, Any]]]:
    """Run search and write the unified results to a Bibtex file.

    Args:
        query: search query
        year_min/year_max: optional year filter
        limit: max results per engine
        engine: comma-separated engines or 'all'
        out_bib_path: where to write the .bib (default: temp file)
        quiet: suppress progress

    Returns:
        (Path to Bibtex, list of result dicts from search)
    """
    run_search = _import_run_search()
    write_bibtex = _import_write_bibtex()

    results = run_search(
        query, year_min=year_min, year_max=year_max,
        limit=limit, engine=engine,
    )
    paper_list = results.get("results", [])
    if not paper_list:
        if not quiet:
            print(f"[search-and-import] search returned 0 results for {query!r}", file=sys.stderr)
        # Still write an empty bib to avoid downstream errors
        if out_bib_path is None:
            out_bib_path = Path(tempfile.gettempdir()) / f"pa_search_import_{datetime.now().strftime('%Y%m%d%H%M%S')}.bib"
        out_bib_path.write_text("", encoding="utf-8")
        return out_bib_path, paper_list

    if not quiet:
        print(
            f"[search-and-import] search returned {len(paper_list)} papers "
            f"(by_engine={results.get('by_engine', {})})",
            file=sys.stderr,
        )

    if out_bib_path is None:
        out_bib_path = Path(tempfile.gettempdir()) / f"pa_search_import_{datetime.now().strftime('%Y%m%d%H%M%S')}.bib"
    write_bibtex(paper_list, str(out_bib_path))
    return out_bib_path, paper_list


# ─────────────────────────────────────────────────────────────────
# Step 2-3: fetch + bucket
# ─────────────────────────────────────────────────────────────────
def fetch_and_bucket(
    bib_path: Path,
    out_dir: Path,
    max_total_sec: int = 1800,
    skip_existing: bool = True,
    quiet: bool = False,
) -> Dict[str, Any]:
    """Run batch fetch and bucket results into downloaded / failed.

    Args:
        bib_path: path to .bib file
        out_dir: where to save PDFs
        max_total_sec: global timeout for the whole batch
        skip_existing: if True, skip entries whose PDF already exists
        quiet: suppress per-entry progress

    Returns:
        Dict with:
          summary: FetchSummary object
          downloaded: list of {key, doi, title, saved_as, size_bytes}
          failed: list of {key, doi, title, error}
          n_total, n_downloaded, n_failed
          summary_json_path: path to the summary JSON (for audit)
    """
    run_fetch_batch, FetchResult, FetchSummary, write_summary_json = _import_run_fetch_batch()

    out_dir.mkdir(parents=True, exist_ok=True)
    if not quiet:
        print(f"[search-and-import] fetching PDFs from {bib_path} to {out_dir}/", file=sys.stderr)

    summary = run_fetch_batch(
        bib_path=bib_path,
        out_dir=out_dir,
        max_total_sec=max_total_sec,
        skip_existing=skip_existing,
    )

    downloaded = []
    failed = []
    for r in summary.results:
        item = {
            "key": r.key,
            "doi": r.doi or "",
            "title": r.title or "",
            "saved_as": r.saved_as or "",
            "size_bytes": r.size_bytes or 0,
        }
        if r.success and r.saved_as:
            downloaded.append(item)
        else:
            failed.append({**item, "error": r.error or "unknown"})

    # Write summary JSON for audit + master note
    summary_json_path = out_dir / "_search_import_summary.json"
    try:
        write_summary_json(summary, str(summary_json_path))
    except Exception as e:
        if not quiet:
            print(f"[search-and-import] warning: could not write summary json: {e}", file=sys.stderr)

    if not quiet:
        print(
            f"[search-and-import] fetch done: downloaded={len(downloaded)} "
            f"failed={len(failed)} total={summary.n_total}",
            file=sys.stderr,
        )
    return {
        "summary": summary,
        "downloaded": downloaded,
        "failed": failed,
        "n_total": summary.n_total,
        "n_downloaded": len(downloaded),
        "n_failed": len(failed),
        "summary_json_path": summary_json_path,
    }


# ─────────────────────────────────────────────────────────────────
# Step 4-5: Zotero push (downloaded only)
# ─────────────────────────────────────────────────────────────────
def push_downloaded(
    downloaded: List[Dict[str, Any]],
    pdf_dir: Optional[Path] = None,
    mode: str = "linked_file",
    quiet: bool = False,
) -> Dict[str, Any]:
    """Push downloaded papers to Zotero library.

    Reuses `pa zotero push` logic (parse_bibtex_for_doi + push_items)
    by writing a temporary Bibtex file from the downloaded list and
    calling push_items. If `pdf_dir` is set, also uploads matching
    PDFs as attachments via `pa zotero upload_pdfs` (v3.9.17.1 [P2-17.1]).

    Args:
        downloaded: list of {key, doi, title, saved_as, ...} from fetch_and_bucket
        pdf_dir: directory containing PDFs named {key}.pdf (optional,
                 v3.9.17.1+ — enables PDF attachment upload)
        mode: 'linked_file' (default) or 'imported_file'
        quiet: suppress progress

    Returns:
        Dict with pushed/skipped/failed counts + n_pdf_uploaded + n_pdf_failed
        + per-item results
    """
    if not downloaded:
        return {
            "n_pushed": 0, "n_skipped": 0, "n_failed": 0,
            "n_pdf_uploaded": 0, "n_pdf_failed": 0,
            "results": [],
        }

    # Build a minimal Bibtex file from the downloaded items
    tmp_bib = Path(tempfile.gettempdir()) / f"pa_push_{datetime.now().strftime('%Y%m%d%H%M%S')}.bib"
    try:
        with tmp_bib.open("w", encoding="utf-8") as f:
            for item in downloaded:
                key = item.get("key") or f"item_{abs(hash(item.get('doi', ''))) % 10**8}"
                doi = item.get("doi", "")
                title = item.get("title", "(no title)")
                f.write(f"@article{{{key},\n  doi = {{{doi}}},\n  title = {{{title}}},\n}}\n\n")
        zotero_api = _import_zotero_api()
        client = zotero_api.get_client()
        entries = zotero_api.parse_bibtex_for_doi(tmp_bib)
        if not quiet:
            print(f"[search-and-import] pushing {len(entries)} downloaded DOIs to Zotero library...", file=sys.stderr)
        # Pass pdf_dir through to push_items (v3.9.17.1+ PDF upload integration)
        result = zotero_api.push_items(
            client=client,
            bibtex_entries=entries,
            pdf_dir=pdf_dir,
            mode=mode,
            skip_existing=True,
        )
        if not quiet:
            print(
                f"[search-and-import] push: pushed={result['n_pushed']} "
                f"skipped={result['n_skipped']} failed={result['n_failed']} "
                f"pdf_uploaded={result.get('n_pdf_uploaded', 0)} "
                f"pdf_failed={result.get('n_pdf_failed', 0)}",
                file=sys.stderr,
            )
        return result
    finally:
        try:
            tmp_bib.unlink()
        except OSError:
            pass


# ─────────────────────────────────────────────────────────────────
# Step 6-8: Zotero project (create / add items / master note)
# ─────────────────────────────────────────────────────────────────
def setup_zotero_project(
    project_name: str,
    downloaded: List[Dict[str, Any]],
    failed: List[Dict[str, Any]],
    query: str,
    do_push: bool = True,
    push_results: Optional[Dict[str, Any]] = None,
    quiet: bool = False,
) -> Dict[str, Any]:
    """Create the Zotero project (= collection) and attach papers + master note.

    Steps:
    1. create_collection(name=project_name) — idempotent
    2. Resolve each downloaded DOI to a Zotero item key (via search)
    3. add_items_to_collection(item_keys, collection_key)
    4. create_collection_note(coll_key, title, content) with the
       fetch log (downloaded + failed table + metadata)

    Args:
        project_name: Zotero collection name (= research topic)
        downloaded: list of {key, doi, title, saved_as, size_bytes}
        failed: list of {key, doi, title, error}
        query: original search query (for the master note header)
        do_push: if False, skip push step (assume items already in library)
        push_results: output of push_downloaded() — needed to resolve
                      DOI → Zotero key
        quiet: suppress progress

    Returns:
        Dict with:
          status, project_key, project_name, n_added, n_failed_items,
          note_key, note_status, error?
    """
    zotero_api = _import_zotero_api()
    try:
        client = zotero_api.get_client()
    except (ImportError, ValueError) as e:
        return {
            "status": "error",
            "error": f"Zotero client init failed: {e}",
            "project_name": project_name,
        }

    # 1. Create collection (idempotent)
    coll_result = zotero_api.create_collection(client, project_name)
    if coll_result["status"] == "error":
        return {
            "status": "error",
            "error": f"create_collection failed: {coll_result.get('error')}",
            "project_name": project_name,
        }
    coll_key = coll_result["key"]
    if not quiet:
        print(
            f"[search-and-import] Zotero project '{project_name}' "
            f"({coll_result['status']}, key={coll_key})",
            file=sys.stderr,
        )

    # 2. Resolve DOIs to Zotero item keys
    item_keys = []
    if push_results and downloaded:
        # Build a DOI -> zotero_key map from push_results
        doi_to_key = {}
        for r in push_results.get("results", []):
            if r.get("status") == "pushed" and r.get("zotero_key"):
                doi_to_key[r.get("doi", "")] = r["zotero_key"]
        for item in downloaded:
            doi = item.get("doi", "")
            if doi in doi_to_key:
                item_keys.append(doi_to_key[doi])
            elif do_push:
                # Try searching for it (maybe it was already in library)
                try:
                    norm = zotero_api.normalize_doi(doi)
                    if norm:
                        items = client.items(q=norm, qmode="everything", limit=3)
                        for it in items:
                            data = it.get("data", it)
                            if data.get("DOI", "").lower() == norm.lower():
                                item_keys.append(data["key"])
                                break
                except Exception:
                    pass

    # 3. Add items to collection
    n_added = 0
    n_failed_items = 0
    if item_keys:
        add_result = zotero_api.add_items_to_collection(client, item_keys, coll_key)
        n_added = add_result["n_added"]
        n_failed_items = add_result["n_failed"]
        if not quiet:
            print(
                f"[search-and-import] added {n_added} item(s) to project "
                f"(failed={n_failed_items})",
                file=sys.stderr,
            )

    # 4. Create master note with fetch log
    note_content = _render_master_note(
        project_name=project_name,
        query=query,
        downloaded=downloaded,
        failed=failed,
        coll_key=coll_key,
        n_added=n_added,
    )
    note_title = f"{project_name} — fetch log {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    note_result = zotero_api.create_collection_note(
        client=client,
        collection_key=coll_key,
        title=note_title,
        content=note_content,
    )

    return {
        "status": "ok",
        "project_name": project_name,
        "project_key": coll_key,
        "project_status": coll_result["status"],  # 'created' or 'exists'
        "n_added": n_added,
        "n_failed_items": n_failed_items,
        "n_items_resolved": len(item_keys),
        "note_key": note_result.get("key", ""),
        "note_status": note_result.get("status", ""),
    }


def _render_master_note(
    project_name: str,
    query: str,
    downloaded: List[Dict[str, Any]],
    failed: List[Dict[str, Any]],
    coll_key: str,
    n_added: int,
) -> str:
    """Render the master note as Markdown. Will be wrapped in <pre> by
    zotero_api.create_collection_note() (since it's plain text)."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    parts = [
        f"# {project_name} — fetch log {now}",
        "",
        f"- **Project Zotero collection**: key={coll_key}",
        f"- **Search query**: {query}",
        f"- **Total papers**: {len(downloaded) + len(failed)}",
        f"- **Downloaded**: {len(downloaded)}",
        f"- **Failed**: {len(failed)}",
        f"- **Added to project**: {n_added}",
        "",
        "## Downloaded",
        "",
    ]
    if downloaded:
        parts.append("| Key | Title | DOI | File | Size |")
        parts.append("|---|---|---|---|---|")
        for d in downloaded:
            key = d.get("key", "?")
            title = (d.get("title", "") or "(no title)")[:80].replace("|", "\\|")
            doi = d.get("doi", "")
            file_ = d.get("saved_as", "")
            size_kb = (d.get("size_bytes", 0) or 0) // 1024
            parts.append(f"| {key} | {title} | {doi} | {file_} | {size_kb} KB |")
    else:
        parts.append("_(none)_")
    parts += ["", "## Failed to download", ""]
    if failed:
        parts.append("| Key | Title | DOI | Error |")
        parts.append("|---|---|---|---|")
        for f_item in failed:
            key = f_item.get("key", "?")
            title = (f_item.get("title", "") or "(no title)")[:60].replace("|", "\\|")
            doi = f_item.get("doi", "")
            err = (f_item.get("error", "") or "unknown")[:60]
            parts.append(f"| {key} | {title} | {doi} | {err} |")
    else:
        parts.append("_(none)_")
    parts += [
        "",
        "## Next steps",
        "",
        "- Read the downloaded papers (annotate in Zotero reader)",
        f"- `pa zotero project search --query \"{project_name}\"` to find this project later",
        f"- `pa zotero project status --name \"{project_name}\"` to see progress",
        "- (Optional) `pa obsidian project create --name \"" + project_name + "\"` for Obsidian notes",
        "",
    ]
    # PRISMA flow diagram (v3.9.20 [P2-19.1]) — auto-embed in master note
    # Maps pa search-and-import stages to PRISMA's 4 stages:
    #   Identification = total results (downloaded + failed)
    #   Screening      = downloaded
    #   Eligibility    = downloaded (no manual step)
    #   Included       = added to project
    prisma_block = _render_prisma_block(
        identified=len(downloaded) + len(failed),
        after_screening=len(downloaded),
        after_eligibility=len(downloaded),
        included=n_added,
        excluded=len(failed),
    )
    if prisma_block:
        parts += ["", "## PRISMA flow", "", prisma_block, ""]
    return "\n".join(parts)


def _render_prisma_block(
    identified: int,
    after_screening: int,
    after_eligibility: int,
    included: int,
    excluded: int,
) -> str:
    """Render a PRISMA flow diagram as a Mermaid code block.

    Maps pa search-and-import stages to PRISMA's 4 stages:
    - Identification  = total results from search (downloaded + failed)
    - Screening       = successfully downloaded (passed PDF fetch)
    - Eligibility     = same as screening (no manual eligibility step)
    - Included        = actually added to Zotero project

    Returns a markdown string with embedded mermaid block, or empty
    string if `pa_cli.prisma` is not available.

    Added in v3.9.20 [P2-19.1].
    """
    try:
        from . import prisma as prisma_mod
        if prisma_mod.generate_mermaid is None:
            return ""
        # generate_mermaid already wraps in ```mermaid ... ``` block
        return prisma_mod.generate_mermaid(
            identified_count=identified,
            after_screening_count=after_screening,
            after_eligibility_count=after_eligibility,
            included_count=included,
            by_source={},
            pdf_count=after_screening,
            abstract_count=0,
        )
    except Exception:
        return ""


# ─────────────────────────────────────────────────────────────────
# Step 9 (v3.9.17.2 [P3-29.1]): Obsidian project sync (opt-in via --with-obsidian)
# ─────────────────────────────────────────────────────────────────
def setup_obsidian_project(
    project_name: str,
    zotero_project_key: str = "",
    zotero_note_key: str = "",
    n_downloaded: int = 0,
    n_failed: int = 0,
    quiet: bool = False,
) -> Dict[str, Any]:
    """Auto-create matching Obsidian project for the research topic.

    Steps (v3.9.17.2 [P3-29.1]):
    1. Read vault path from $PAPER_AGENT_OBSIDIAN_VAULT env var
    2. If unset: return status='skipped' (graceful; same-name convention
       still works via manual `pa obsidian project create` hint)
    3. If set: call `obs_mod.create_project(name=project_name, ...)` (idempotent)
    4. Add a thought referencing the Zotero project key + note key + counts

    Args:
        project_name: research topic name (= Zotero project name)
        zotero_project_key: Zotero collection key (e.g. "ABC123")
        zotero_note_key: Zotero note key (e.g. "DEF456")
        n_downloaded: number of papers downloaded
        n_failed: number of papers that failed to download
        quiet: suppress progress

    Returns:
        Dict with status, obsidian_path, project_slug, thought_count, error?
    """
    obs_mod = _import_obsidian()
    vault = obs_mod.get_vault_path()
    if vault is None:
        return {
            "status": "skipped",
            "reason": "$PAPER_AGENT_OBSIDIAN_VAULT not set",
            "project_name": project_name,
        }

    # 1. Create project (idempotent)
    result = obs_mod.create_project(name=project_name, research_question="", direction="")
    if result["status"] == "error":
        return {
            "status": "error",
            "error": result.get("error", "create_project failed"),
            "project_name": project_name,
        }

    # 2. Add a thought that cross-references the Zotero project + note
    from datetime import datetime
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    zotero_refs = []
    if zotero_project_key:
        zotero_refs.append(f"Zotero project (collection) key: `{zotero_project_key}`")
    if zotero_note_key:
        zotero_refs.append(f"Zotero master note key: `{zotero_note_key}`")
    zotero_block = ("\n".join(f"- {r}" for r in zotero_refs) + "\n") if zotero_refs else ""
    thought_content = (
        f"Auto-created by `pa search-and-import --with-obsidian` at {stamp}.\n"
        f"Topic: {project_name}\n"
        f"Fetched: {n_downloaded} paper(s) downloaded, {n_failed} failed.\n"
        f"{zotero_block}"
    )
    thought_result = obs_mod.add_thought(name=project_name, content=thought_content)
    if not quiet:
        if thought_result["status"] == "ok":
            print(
                f"[search-and-import] Obsidian: project '{project_name}' "
                f"({result['status']}, slug={result['slug']}), "
                f"thought added (total {thought_result.get('thought_count', 0)})",
                file=sys.stderr,
            )
        else:
            print(
                f"[search-and-import] Obsidian: project created but thought add failed: "
                f"{thought_result.get('error', 'unknown')}",
                file=sys.stderr,
            )
    return {
        "status": "ok",
        "project_status": result["status"],  # 'created' or 'exists'
        "project_slug": result["slug"],
        "obsidian_path": result.get("path", ""),
        "thought_count": thought_result.get("thought_count", 0) if thought_result["status"] == "ok" else 0,
        "thought_status": thought_result.get("status", ""),
    }


# ─────────────────────────────────────────────────────────────────
# Main orchestrator
# ─────────────────────────────────────────────────────────────────
def run_search_and_import(
    query: str,
    project_name: str,
    year_min: Optional[int] = None,
    year_max: Optional[int] = None,
    limit: int = 20,
    engine: str = "all",
    out_dir: Optional[Path] = None,
    max_total_sec: int = 1800,
    skip_existing: bool = True,
    do_push: bool = True,
    with_obsidian: bool = False,
    quiet: bool = False,
) -> Dict[str, Any]:
    """Top-level orchestrator: search → fetch → bucket → push → project + note (+ optional Obsidian).

    Returns a single dict with all step results + summary stats.
    On any step error, the orchestrator records the error and
    continues if possible (e.g. Zotero push failure shouldn't stop
    the fetch from completing).

    v3.9.17.2 [P3-29.1]: when `with_obsidian=True`, also creates a
    matching Obsidian project page (idempotent) + adds a thought
    referencing the Zotero project + note. Requires
    `$PAPER_AGENT_OBSIDIAN_VAULT` env var; if unset, gracefully
    records status='skipped' and continues.
    """
    out_dir = out_dir or Path("./pdfs")
    result: Dict[str, Any] = {
        "query": query,
        "project_name": project_name,
        "steps": {},
        "errors": [],
    }

    # Step 1: search → bibtex
    try:
        bib_path, paper_list = search_to_bibtex(
            query=query,
            year_min=year_min, year_max=year_max,
            limit=limit, engine=engine,
            quiet=quiet,
        )
        result["steps"]["search"] = {
            "status": "ok",
            "n_papers": len(paper_list),
            "bib_path": str(bib_path),
        }
    except Exception as e:
        result["steps"]["search"] = {"status": "error", "error": str(e)}
        result["errors"].append(f"search: {e}")
        return result

    if not paper_list:
        result["steps"]["search"]["note"] = "0 results — nothing to do"
        return result

    # Step 2-3: fetch + bucket
    try:
        fetch_result = fetch_and_bucket(
            bib_path=bib_path,
            out_dir=out_dir,
            max_total_sec=max_total_sec,
            skip_existing=skip_existing,
            quiet=quiet,
        )
        result["steps"]["fetch"] = {
            "status": "ok",
            "n_total": fetch_result["n_total"],
            "n_downloaded": fetch_result["n_downloaded"],
            "n_failed": fetch_result["n_failed"],
            "out_dir": str(out_dir),
            "summary_json_path": str(fetch_result["summary_json_path"]),
        }
        result["downloaded"] = fetch_result["downloaded"]
        result["failed"] = fetch_result["failed"]
    except Exception as e:
        result["steps"]["fetch"] = {"status": "error", "error": str(e)}
        result["errors"].append(f"fetch: {e}")
        return result

    # Step 4-5: push (only if downloaded + do_push)
    push_results = None
    if do_push and fetch_result["downloaded"]:
        try:
            push_results = push_downloaded(
                fetch_result["downloaded"],
                pdf_dir=out_dir,  # v3.9.17.1+ PDF upload
                mode="linked_file",
                quiet=quiet,
            )
            result["steps"]["push"] = {
                "status": "ok",
                "n_pushed": push_results["n_pushed"],
                "n_skipped": push_results["n_skipped"],
                "n_failed": push_results["n_failed"],
                "n_pdf_uploaded": push_results.get("n_pdf_uploaded", 0),
                "n_pdf_failed": push_results.get("n_pdf_failed", 0),
            }
        except Exception as e:
            result["steps"]["push"] = {"status": "error", "error": str(e)}
            result["errors"].append(f"push: {e}")

    # Step 6-8: Zotero project + note
    try:
        proj_result = setup_zotero_project(
            project_name=project_name,
            downloaded=fetch_result["downloaded"],
            failed=fetch_result["failed"],
            query=query,
            do_push=do_push,
            push_results=push_results,
            quiet=quiet,
        )
        result["steps"]["project"] = proj_result
    except Exception as e:
        proj_result = {"status": "error", "error": str(e)}
        result["steps"]["project"] = proj_result
        result["errors"].append(f"project: {e}")

    # Step 9 (v3.9.17.2 [P3-29.1]): Obsidian project sync (opt-in via --with-obsidian)
    if with_obsidian:
        try:
            obs_result = setup_obsidian_project(
                project_name=project_name,
                zotero_project_key=proj_result.get("project_key", "") if isinstance(proj_result, dict) else "",
                zotero_note_key=proj_result.get("note_key", "") if isinstance(proj_result, dict) else "",
                n_downloaded=fetch_result["n_downloaded"],
                n_failed=fetch_result["n_failed"],
                quiet=quiet,
            )
            result["steps"]["obsidian"] = obs_result
        except Exception as e:
            result["steps"]["obsidian"] = {"status": "error", "error": str(e)}
            result["errors"].append(f"obsidian: {e}")

    # Cleanup the temp bib (only if we created it in a temp dir)
    if bib_path.parent == Path(tempfile.gettempdir()):
        try:
            bib_path.unlink()
        except OSError:
            pass

    # Final summary
    obs_step = result["steps"].get("obsidian") or {}
    result["summary"] = {
        "n_search_results": len(paper_list),
        "n_downloaded": fetch_result["n_downloaded"],
        "n_failed": fetch_result["n_failed"],
        "zotero_project_key": (result["steps"].get("project") or {}).get("project_key", ""),
        "zotero_note_key": (result["steps"].get("project") or {}).get("note_key", ""),
        "obsidian_project_status": obs_step.get("project_status", ""),
        "obsidian_project_slug": obs_step.get("project_slug", ""),
        "obsidian_path": obs_step.get("obsidian_path", ""),
    }
    return result
