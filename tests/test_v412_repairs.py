"""Regression contracts for the three failures observed in the v4.1.1 live flow."""
import json
from unittest.mock import patch

from click.testing import CliRunner
from pa_cli.bibtex import to_bibtex
from pa_cli.scaffold import load_bibtex
from pa_cli.cite_check import extract_cite_keys, run_cite_check
from pa_cli.cli import main
from pa_cli import search_saved


def test_export_roundtrip_keeps_pubmed_identifiers(tmp_path):
    paper = {"title": "Menopause sleep", "pmid": "39631008", "pmcid": "PMC9914174",
             "abstract": "Sleep improved (P < 0.05).", "doi": "10.1000/test"}
    bib = tmp_path / "refs.bib"
    bib.write_text(to_bibtex(paper), encoding="utf-8")
    entry = load_bibtex(bib)[0]
    assert entry["pmid"] == "39631008"
    assert entry["pmcid"] == "PMC9914174"
    assert entry["abstract"] == "Sleep improved (P < 0.05)."


def test_grouped_citations_all_keys_and_per_line_dedup():
    text = "Text [@known; @second; @missing_entry] [@known]\n[@known, @third]"
    assert extract_cite_keys(text) == [
        ("known", 1), ("second", 1), ("missing_entry", 1), ("known", 2), ("third", 2)]


def test_grouped_citations_report_missing_later_key(tmp_path):
    bib = tmp_path / "refs.bib"
    bib.write_text("@article{known,title={Known}}\n@article{second,title={Second}}", encoding="utf-8")
    doc = tmp_path / "draft.md"
    doc.write_text("[@known; @second; @missing_entry]", encoding="utf-8")
    result, _ = run_cite_check(bib, doc)
    assert result["n_placeholders"] == 3
    assert any(item["key"] == "missing_entry" for item in result["missing"])


def test_saved_search_click_executes_stored_query(tmp_path):
    store = tmp_path / "saved.json"
    search_saved.add("menopause", "menopause sleep", path=store, engine="pubmed", limit=5)
    response = {"query": "menopause sleep", "results": [], "engine_status": {"pubmed": "ok"}}
    # Only the network boundary is replaced: real preset loading, Click dispatch,
    # default injection, search processing and JSON output remain exercised.
    with patch.object(search_saved, "DEFAULT_PATH", store), patch("pa_cli.search.run_search", return_value=response):
        result = CliRunner().invoke(main, ["search-saved", "run", "menopause", "--quiet"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["query"] == "menopause sleep"
