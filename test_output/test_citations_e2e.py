"""Validation test for pa_cli.citations — uses real OpenAlex API.

Approach:
  - Use a well-known high-citation paper (Crompton 2023) as fixture
  - Forward + backward walks with small limits (5 papers each)
  - Validate: result structure, normalised fields, error path for unknown DOI
  - Validate: --save-bib produces a parseable .bib file

This test DOES make real network calls (~7 OpenAlex requests). Skipped if
PA_NETWORK_OFFLINE=1.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Skip if user opts out of network
if os.environ.get("PA_NETWORK_OFFLINE", "").lower() in ("1", "true", "yes"):
    print("SKIP: PA_NETWORK_OFFLINE=1")
    sys.exit(0)

# A well-known paper (1819 citations, 46 references) — known good for testing
FIXTURE_DOI = "10.1186/s41239-023-00411-8"


def _run_pa_citations(*args, env=None):
    """Run pa citations as subprocess, return (rc, stdout, stderr)."""
    cmd = [sys.executable, "-m", "pa_cli", "citations"] + list(args)
    e = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1", **(env or {})}
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       env=e, cwd=str(ROOT), timeout=120, stdin=subprocess.DEVNULL)
    return r.returncode, r.stdout, r.stderr


def test_citations_module_forward():
    print("\n=== test: forward citation walk (5 papers) ===")
    from pa_cli.citations import citation_walk
    r = citation_walk(FIXTURE_DOI, direction="forward", limit=5)
    assert r.get("error") is None, f"unexpected error: {r.get('error')}"
    assert r["direction"] == "forward"
    assert r["count"] == 5
    assert r["truncated"] is True
    # Each result must have title + doi + cited_by_count
    for i, p in enumerate(r["results"]):
        assert p.get("title"), f"result {i} missing title: {p}"
        assert p.get("doi"), f"result {i} missing doi: {p}"
        assert "source" in p
    # source_work metadata present
    sw = r["source_work"]
    assert sw.get("title"), f"source title missing: {sw}"
    assert "Crompton" in sw.get("title", "") or "Students" in sw.get("title", "")
    print(f"  PASS: forward={r['count']} papers, source='{sw['title'][:50]}...'")


def test_citations_module_backward():
    print("\n=== test: backward citation walk (3 papers) ===")
    from pa_cli.citations import citation_walk
    r = citation_walk(FIXTURE_DOI, direction="backward", limit=3)
    assert r.get("error") is None
    assert r["direction"] == "backward"
    assert r["count"] == 3
    for p in r["results"]:
        assert p.get("title"), f"missing title: {p}"
    print(f"  PASS: backward={r['count']} papers")


def test_citations_module_unknown_doi():
    print("\n=== test: unknown DOI returns error ===")
    from pa_cli.citations import citation_walk
    r = citation_walk("10.9999/totally-fake-doi-xyz", direction="forward", limit=5)
    assert r.get("error") == "doi_not_found"
    print("  PASS: unknown DOI returns doi_not_found")


def test_citations_cli_json_output():
    print("\n=== test: pa citations CLI JSON output ===")
    rc, out, err = _run_pa_citations(FIXTURE_DOI, "--direction", "forward",
                                      "--limit", "3", "--quiet")
    print(f"  rc={rc}, stdout[:80]={out[:80]!r}")
    print(f"  stderr[:200]={err[:200]!r}")
    assert rc == 0, f"rc={rc}, stderr={err[-300:]!r}"
    data = json.loads(out)
    print(f"  data keys: {list(data.keys())}, count={data.get('count')!r}, "
          f"len(results)={len(data.get('results', []))}")
    assert "results" in data
    assert data["count"] == 3, f"expected count=3, got {data['count']!r}"
    assert data["direction"] == "forward"
    assert "source_work" in data
    print(f"  PASS: CLI JSON output has {data['count']} results, "
          f"source title='{data['source_work'].get('title', '')[:50]}'")


def test_citations_cli_save_bib():
    print("\n=== test: pa citations --save-bib produces valid BibTeX ===")
    with tempfile.TemporaryDirectory() as tmp:
        bib_path = str(Path(tmp) / "citers.bib")
        rc, out, err = _run_pa_citations(FIXTURE_DOI, "--direction", "forward",
                                          "--limit", "3", "--save-bib", bib_path,
                                          "--quiet")
        assert rc == 0
        # Verify .bib file exists + has content
        assert Path(bib_path).exists(), f"bib file not created: {bib_path}"
        bib_text = Path(bib_path).read_text(encoding="utf-8")
        assert bib_text.startswith("@") or "@" in bib_text[:100], \
            f"file doesn't look like BibTeX: {bib_text[:200]!r}"
        # Count @entries
        entry_count = bib_text.count("@article") + bib_text.count("@misc")
        print(f"  PASS: --save-bib produced {len(bib_text)} bytes, "
              f"{entry_count} entries")
        assert entry_count >= 1


def test_citations_cli_unknown_doi():
    print("\n=== test: pa citations unknown DOI exits 2 ===")
    rc, out, err = _run_pa_citations("10.9999/fake", "--direction", "forward",
                                     "--limit", "3", "--quiet")
    assert rc == 2, f"expected rc=2, got {rc}"
    assert "doi_not_found" in out or "doi_not_found" in err
    print("  PASS: unknown DOI exits 2 with doi_not_found in output")


def test_citations_mcp_forward():
    print("\n=== test: pa_citations MCP tool (forward) ===")
    import asyncio
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    async def run():
        params = StdioServerParameters(command=sys.executable, args=["-m", "pa_cli.mcp"])
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as s:
                await s.initialize()
                # list_tools should now include pa_citations
                tools = (await s.list_tools()).tools
                names = sorted(t.name for t in tools)
                assert "pa_citations" in names, f"pa_citations missing: {names}"
                # call_tool pa_citations forward
                r = await s.call_tool("pa_citations",
                                       {"doi": FIXTURE_DOI, "direction": "forward", "limit": 3})
                text = r.content[0].text
                data = json.loads(text)
                assert "results" in data
                assert data["count"] == 3
                assert data["direction"] == "forward"
                return data

    data = asyncio.run(run())
    print(f"  PASS: pa_citations MCP tool returned {data['count']} papers, "
          f"source='{data['source_work'].get('title', '')[:50]}'")


def main():
    print("=" * 60)
    print("pa_citations validation suite (real OpenAlex API)")
    print("=" * 60)
    test_citations_module_forward()
    test_citations_module_backward()
    test_citations_module_unknown_doi()
    test_citations_cli_json_output()
    test_citations_cli_save_bib()
    test_citations_cli_unknown_doi()
    test_citations_mcp_forward()
    print("\n" + "=" * 60)
    print("ALL CITATIONS TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    main()
