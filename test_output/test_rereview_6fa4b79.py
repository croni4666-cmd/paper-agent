"""Regression test suite for GPT re-review issues (commit 6fa4b79).

Covers:
1. SQLite prediction loading from M3 shadow database (no NameError, real schema).
2. Probability boundary and finiteness validation in extract_p_yes.
3. Prediction case_id vs artifact/packet/rubric hash consistency check.
4. Non-updated BibTeX entries preservation during merge (year=2021, journal=jmacro, nested braces).
5. OpenAlex book-chapter mapping to incollection and clean load_bibtex round-trip.
6. Crossref remapping on cite-key collision and deduplication in merge_projects.
"""
from __future__ import annotations

import json
import math
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pa_cli.bibtex import format_bibtex_entry, _TYPE_MAP
from pa_cli.evidence import _hash
from pa_cli.jev_eval_join import (
    extract_p_yes,
    load_predictions_from_db,
    load_predictions_from_json,
)
from pa_cli.project import init_project, corpus_merge, project_enrich
from pa_cli.scaffold import load_bibtex, parse_bibtex
from pa_cli.shadow import APP_ID as SHADOW_APP_ID, _connect, _dump


class TestRereviewFixes(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.root = self.tmpdir / "projects"
        self.root.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    # ---------- Finding 1: SQLite M3 Loader ----------

    def test_sqlite_prediction_loader_m3_schema(self):
        """Test load_predictions_from_db with an actual M3 shadow SQLite DB."""
        db_path = self.tmpdir / "shadow_m3.db"
        conn = _connect(db_path)
        try:
            art_sha = "a" * 64
            packet = {"packet_hash": "p" * 64, "data": "test_packet"}
            rubric = {"task": "relevance", "version": "1.0", "labels": ["included", "excluded"]}
            p_json = _dump(packet)
            r_json = _dump(rubric)

            req_id = "req_1"
            conn.execute(
                """INSERT INTO requests (request_id, created_at, artifact_sha256, packet_json,
                                        provenance_json, rubric_json, provider_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (req_id, "2026-10-02T00:00:00Z", art_sha, p_json, "{}", r_json, "{}"),
            )
            ans = {
                "model": "gpt-eval-1",
                "probabilities": {"included": 0.88, "excluded": 0.12},
                "label": "included",
            }
            conn.execute(
                "INSERT INTO suggestions (request_id, answer_json, synthetic) VALUES (?, ?, 1)",
                (req_id, _dump(ans)),
            )
            conn.commit()
        finally:
            conn.close()

        # Load predictions from DB
        pred_map = load_predictions_from_db(db_path)
        self.assertEqual(len(pred_map), 1)
        expected_case_key = _hash([art_sha, packet["packet_hash"], _hash(rubric)])
        self.assertIn(expected_case_key, pred_map)

        item = pred_map[expected_case_key]
        self.assertEqual(item["p_yes"], 0.88)
        self.assertTrue(item["is_synthetic"])
        self.assertEqual(item["model"], "gpt-eval-1")

    # ---------- Finding 1 & Review Section 5: Probability Boundaries ----------

    def test_extract_p_yes_boundaries_and_finiteness(self):
        # Valid p_yes
        self.assertEqual(extract_p_yes({"p_yes": 0.75}), 0.75)
        # Valid positive class mapping
        self.assertEqual(extract_p_yes({"probabilities": {"included": 0.9}}), 0.9)
        # Valid negative class mapping
        self.assertEqual(extract_p_yes({"probabilities": {"excluded": 0.8}}), 0.2)

        # Invalid: non-finite or out of range
        with self.assertRaises(ValueError):
            extract_p_yes({"p_yes": float("nan")})
        with self.assertRaises(ValueError):
            extract_p_yes({"p_yes": 1.5})
        with self.assertRaises(ValueError):
            extract_p_yes({"p_yes": -0.1})
        with self.assertRaises(ValueError):
            extract_p_yes({"probabilities": {"included": 1.2}})
        with self.assertRaises(ValueError):
            extract_p_yes({"probabilities": {"unknown_class": 0.5}})

    def test_json_prediction_hash_consistency_check(self):
        json_file = self.tmpdir / "preds.json"
        art = "b" * 64
        p_hash = "c" * 64
        r_hash = "d" * 64
        correct_key = _hash([art, p_hash, r_hash])

        # Consistent case_id succeeds
        data = [{
            "case_id": correct_key,
            "artifact_sha256": art,
            "packet_hash": p_hash,
            "rubric_hash": r_hash,
            "p_yes": 0.95
        }]
        json_file.write_text(json.dumps(data), encoding="utf-8")
        preds = load_predictions_from_json(json_file)
        self.assertIn(correct_key, preds)

        # Inconsistent case_id raises ValueError
        data[0]["case_id"] = "mismatched_key"
        json_file.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(ValueError) as ctx:
            load_predictions_from_json(json_file)
        self.assertIn("mismatch", str(ctx.exception))

    # ---------- Finding 2: BibTeX merge preserves untouched entries ----------

    def test_merge_stub_preserves_untouched_full_bibtex_entry(self):
        """Updating a stub must NOT strip year=2021, journal=jmacro, or nested braces from other entries."""
        init_project("target_proj", root=self.root)
        target_refs = self.root / "target_proj" / "refs.bib"
        target_refs.write_text("""@article{stub,
  title = {Paper 10.1000/stub},
  doi = {10.1000/stub}
}

@article{complete2021,
  title = {An {RNA} study},
  author = {{World Health Organization}},
  journal = jmacro,
  year = 2021,
  doi = {10.1000/complete}
}
""", encoding="utf-8")

        init_project("source_proj", root=self.root)
        source_refs = self.root / "source_proj" / "refs.bib"
        source_refs.write_text("""@article{stub,
  title = {Rich Stub Title},
  author = {Doe, John},
  year = {2024},
  doi = {10.1000/stub}
}
""", encoding="utf-8")

        res = corpus_merge("target_proj", "source_proj", root=self.root)
        self.assertEqual(res["updated"], 1)

        # Re-parse target refs.bib
        entries = load_bibtex(target_refs)
        by_key = {e["key"]: e for e in entries}

        self.assertIn("stub", by_key)
        self.assertEqual(by_key["stub"]["title"], "Rich Stub Title")
        self.assertEqual(by_key["stub"]["author"], "Doe, John")

        self.assertIn("complete2021", by_key)
        comp = by_key["complete2021"]
        self.assertEqual(comp.get("year"), "2021")
        self.assertEqual(comp.get("journal"), "jmacro")
        # Nested braces preserved
        self.assertIn("{RNA}", comp.get("title", ""))
        self.assertIn("{World Health Organization}", comp.get("author", ""))

    # ---------- Finding 3: OpenAlex book-chapter mapping & round-trip ----------

    def test_enrich_book_chapter_maps_to_incollection_and_roundtrips(self):
        init_project("enrich_chapter_proj", root=self.root)
        refs = self.root / "enrich_chapter_proj" / "refs.bib"
        refs.write_text("""@article{chap_stub,
  title = {Paper 10.1000/chap},
  doi = {10.1000/chap}
}
""", encoding="utf-8")

        fake_openalex_data = {
            "title": "A Great Chapter on Macroeconomics",
            "authorships": [{"author": {"display_name": "Smith, Adam"}}],
            "publication_year": 2023,
            "type": "book-chapter",
            "primary_location": {"source": {"display_name": "Handbook of Macroeconomics"}},
            "abstract_inverted_index": {"Chapter": [0], "abstract": [1]}
        }

        with patch("pa_cli.citations.get_work_by_doi", return_value=fake_openalex_data):
            res = project_enrich("enrich_chapter_proj", root=self.root)
            self.assertEqual(res["enriched"], 1)

        raw_bib = refs.read_text(encoding="utf-8")
        self.assertNotIn("@book-chapter", raw_bib)
        self.assertIn("@incollection", raw_bib)

        # load_bibtex must read back exactly 1 entry of type 'incollection'
        reloaded = load_bibtex(refs)
        self.assertEqual(len(reloaded), 1)
        self.assertEqual(reloaded[0]["type"], "incollection")
        self.assertEqual(reloaded[0]["key"], "chap_stub")

    # ---------- Finding 4: Crossref remapping on key collision & dedup ----------

    def test_merge_crossref_remapping_on_key_collision(self):
        init_project("target_p", root=self.root)
        t_refs = self.root / "target_p" / "refs.bib"
        t_refs.write_text("""@book{parent,
  title = {Target Parent Book},
  doi = {10.1000/parent_target}
}
""", encoding="utf-8")

        init_project("source_p", root=self.root)
        s_refs = self.root / "source_p" / "refs.bib"
        s_refs.write_text("""@book{parent,
  title = {Source Parent Book},
  doi = {10.1000/parent_source}
}
@incollection{child,
  title = {Chapter in Source Parent},
  crossref = {parent},
  doi = {10.1000/child_source}
}
""", encoding="utf-8")

        res = corpus_merge("target_p", "source_p", root=self.root)
        self.assertEqual(res["added"], 2)

        entries = load_bibtex(t_refs)
        by_key = {e["key"]: e for e in entries}

        # Parent in source collides with target parent -> renamed to parent_v2
        self.assertIn("parent", by_key)
        self.assertEqual(by_key["parent"]["doi"], "10.1000/parent_target")

        self.assertIn("parent_v2", by_key)
        self.assertEqual(by_key["parent_v2"]["doi"], "10.1000/parent_source")

        # Child crossref must be updated to parent_v2!
        self.assertIn("child", by_key)
        self.assertEqual(by_key["child"].get("crossref"), "parent_v2")

    def test_merge_crossref_remapping_on_deduplication(self):
        init_project("target_dedup", root=self.root)
        t_refs = self.root / "target_dedup" / "refs.bib"
        t_refs.write_text("""@book{existing_book,
  title = {The Shared Book},
  author = {Euler, Leonhard},
  doi = {10.1000/shared_book}
}
""", encoding="utf-8")

        init_project("source_dedup", root=self.root)
        s_refs = self.root / "source_dedup" / "refs.bib"
        s_refs.write_text("""@book{src_book,
  title = {The Shared Book},
  author = {Euler, Leonhard},
  doi = {10.1000/shared_book}
}
@incollection{child_sec,
  title = {Section One},
  crossref = {src_book},
  doi = {10.1000/child_sec}
}
""", encoding="utf-8")

        res = corpus_merge("target_dedup", "source_dedup", root=self.root)
        self.assertEqual(res["duplicates_skipped"], 1)  # src_book was deduped
        self.assertEqual(res["added"], 1)    # child_sec was added

        entries = load_bibtex(t_refs)
        by_key = {e["key"]: e for e in entries}

        self.assertIn("child_sec", by_key)
        # Child's crossref must now point to existing_book!
        self.assertEqual(by_key["child_sec"].get("crossref"), "existing_book")


if __name__ == "__main__":
    unittest.main()
