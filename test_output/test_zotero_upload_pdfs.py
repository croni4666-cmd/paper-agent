"""Tests for pa_cli.zotero_api.upload_pdfs — v3.9.17.1 [P2-17.1].

All mock-based: no real Zotero account needed. Tests cover both
linked_file and imported_file modes + edge cases.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pa_cli import zotero_api


# ─────────────────────────────────────────────────────────────────
# TestUploadPdfsLinkedFile
# ─────────────────────────────────────────────────────────────────
class TestUploadPdfsLinkedFile:
    def test_linked_file_uses_create_items_with_linkmode(self, tmp_path):
        """linked_file mode: build attachment template + create_items."""
        client = MagicMock()
        template = {
            "itemType": "attachment",
            "linkMode": "linked_file",
            "title": "",
            "path": "",
        }
        client.item_template.return_value = template
        client.create_items.return_value = [
            {"successful": {"key": "ATT1", "data": {"key": "ATT1"}}}
        ]
        pdf = tmp_path / "paper.pdf"
        pdf.write_text("fake pdf content", encoding="utf-8")

        with patch("builtins.print"):
            result = zotero_api.upload_pdfs(
                client,
                [{"pdf_path": str(pdf), "parent_key": "PARENT1", "title": "paper.pdf"}],
                mode="linked_file",
            )
        assert result["n_uploaded"] == 1
        assert result["n_failed"] == 0
        assert result["results"][0]["status"] == "uploaded"
        assert result["results"][0]["mode"] == "linked_file"
        assert result["results"][0]["zotero_key"] == "ATT1"
        # Verify create_items was called with linked_file mode + parentid
        client.create_items.assert_called_once()
        call_args = client.create_items.call_args
        payload = call_args[0][0]
        assert payload[0]["linkMode"] == "linked_file"
        assert payload[0]["path"] == str(pdf.resolve())
        assert call_args[1].get("parentid") == "PARENT1"

    def test_linked_file_uses_absolute_path(self, tmp_path):
        """Zotero requires absolute path for linked_file."""
        client = MagicMock()
        client.item_template.return_value = {
            "itemType": "attachment", "linkMode": "linked_file",
            "title": "", "path": "",
        }
        client.create_items.return_value = [
            {"successful": {"key": "ATT1"}}
        ]
        # Create a file in tmp_path
        pdf = tmp_path / "subdir" / "paper.pdf"
        pdf.parent.mkdir(parents=True, exist_ok=True)
        pdf.write_text("x", encoding="utf-8")

        with patch("builtins.print"):
            result = zotero_api.upload_pdfs(
                client,
                [{"pdf_path": str(pdf), "parent_key": "P1"}],
                mode="linked_file",
            )
        assert result["n_uploaded"] == 1
        # Path should be absolute (resolved)
        payload = client.create_items.call_args[0][0]
        # On Windows, resolve() may add the drive; just check it's absolute
        assert Path(payload[0]["path"]).is_absolute()


# ─────────────────────────────────────────────────────────────────
# TestUploadPdfsImportedFile
# ─────────────────────────────────────────────────────────────────
class TestUploadPdfsImportedFile:
    def test_imported_file_uses_attachment_simple(self, tmp_path):
        """imported_file mode: pyzotero handles upload via attachment_simple."""
        client = MagicMock()
        client.attachment_simple.return_value = [
            {"successful": {"key": "ATT2", "data": {"key": "ATT2"}}}
        ]
        pdf = tmp_path / "paper.pdf"
        pdf.write_text("fake", encoding="utf-8")

        with patch("builtins.print"):
            result = zotero_api.upload_pdfs(
                client,
                [{"pdf_path": str(pdf), "parent_key": "P1"}],
                mode="imported_file",
            )
        assert result["n_uploaded"] == 1
        # attachment_simple should be called, NOT create_items
        client.attachment_simple.assert_called_once()
        client.create_items.assert_not_called()
        # parentid should be passed
        call_args = client.attachment_simple.call_args
        assert call_args[0][0] == [str(pdf.resolve())]
        assert call_args[1].get("parentid") == "P1"

    def test_imported_file_response_successful(self, tmp_path):
        client = MagicMock()
        client.attachment_simple.return_value = [{"successful": {"key": "ATT_OK"}}]
        pdf = tmp_path / "p.pdf"
        pdf.write_text("x", encoding="utf-8")
        with patch("builtins.print"):
            result = zotero_api.upload_pdfs(
                client, [{"pdf_path": str(pdf), "parent_key": "P"}],
                mode="imported_file",
            )
        assert result["results"][0]["zotero_key"] == "ATT_OK"
        assert result["results"][0]["mode"] == "imported_file"


# ─────────────────────────────────────────────────────────────────
# TestUploadPdfsEdgeCases
# ─────────────────────────────────────────────────────────────────
class TestUploadPdfsEdgeCases:
    def test_empty_uploads_returns_zeros(self):
        client = MagicMock()
        result = zotero_api.upload_pdfs(client, [], mode="linked_file")
        assert result == {"n_uploaded": 0, "n_failed": 0, "results": []}

    def test_missing_file_marked_failed(self):
        client = MagicMock()
        with patch("builtins.print"):
            result = zotero_api.upload_pdfs(
                client,
                [{"pdf_path": "/nonexistent/file.pdf", "parent_key": "P"}],
                mode="linked_file",
            )
        assert result["n_uploaded"] == 0
        assert result["n_failed"] == 1
        assert result["results"][0]["status"] == "failed"
        assert "not found" in result["results"][0]["error"]

    def test_missing_parent_key_marked_failed(self, tmp_path):
        client = MagicMock()
        pdf = tmp_path / "p.pdf"
        pdf.write_text("x", encoding="utf-8")
        with patch("builtins.print"):
            result = zotero_api.upload_pdfs(
                client,
                [{"pdf_path": str(pdf), "parent_key": ""}],
                mode="linked_file",
            )
        assert result["n_failed"] == 1
        assert "missing" in result["results"][0]["error"]

    def test_default_title_uses_filename(self, tmp_path):
        """If title not provided, use Path(pdf_path).name."""
        client = MagicMock()
        client.item_template.return_value = {
            "itemType": "attachment", "linkMode": "linked_file",
            "title": "", "path": "",
        }
        client.create_items.return_value = [{"successful": {"key": "A1"}}]
        pdf = tmp_path / "wang2020.pdf"
        pdf.write_text("x", encoding="utf-8")
        with patch("builtins.print"):
            zotero_api.upload_pdfs(
                client, [{"pdf_path": str(pdf), "parent_key": "P"}],
                mode="linked_file",
            )
        # Title should default to "wang2020.pdf"
        payload = client.create_items.call_args[0][0]
        assert payload[0]["title"] == "wang2020.pdf"

    def test_explicit_title_overrides_default(self, tmp_path):
        client = MagicMock()
        client.item_template.return_value = {
            "itemType": "attachment", "linkMode": "linked_file",
            "title": "", "path": "",
        }
        client.create_items.return_value = [{"successful": {"key": "A1"}}]
        pdf = tmp_path / "p.pdf"
        pdf.write_text("x", encoding="utf-8")
        with patch("builtins.print"):
            zotero_api.upload_pdfs(
                client,
                [{"pdf_path": str(pdf), "parent_key": "P", "title": "Custom Title"}],
                mode="linked_file",
            )
        payload = client.create_items.call_args[0][0]
        assert payload[0]["title"] == "Custom Title"

    def test_linked_file_create_items_failure_marked_failed(self, tmp_path):
        client = MagicMock()
        client.item_template.return_value = {
            "itemType": "attachment", "linkMode": "linked_file",
            "title": "", "path": "",
        }
        client.create_items.return_value = [{"failed": "permission denied"}]
        pdf = tmp_path / "p.pdf"
        pdf.write_text("x", encoding="utf-8")
        with patch("builtins.print"):
            result = zotero_api.upload_pdfs(
                client, [{"pdf_path": str(pdf), "parent_key": "P"}],
                mode="linked_file",
            )
        assert result["n_uploaded"] == 0
        assert result["n_failed"] == 1
        assert "permission" in result["results"][0]["error"].lower()

    def test_imported_file_attachment_simple_failure(self, tmp_path):
        client = MagicMock()
        client.attachment_simple.return_value = [{"failed": "upload failed"}]
        pdf = tmp_path / "p.pdf"
        pdf.write_text("x", encoding="utf-8")
        with patch("builtins.print"):
            result = zotero_api.upload_pdfs(
                client, [{"pdf_path": str(pdf), "parent_key": "P"}],
                mode="imported_file",
            )
        assert result["n_failed"] == 1
        assert "upload failed" in result["results"][0]["error"].lower()

    def test_exception_during_upload_marked_failed(self, tmp_path):
        client = MagicMock()
        client.item_template.side_effect = RuntimeError("network down")
        pdf = tmp_path / "p.pdf"
        pdf.write_text("x", encoding="utf-8")
        with patch("builtins.print"):
            result = zotero_api.upload_pdfs(
                client, [{"pdf_path": str(pdf), "parent_key": "P"}],
                mode="linked_file",
            )
        assert result["n_failed"] == 1
        assert "network down" in result["results"][0]["error"]

    def test_multiple_uploads_mixed_results(self, tmp_path):
        """Test a batch where some succeed and some fail."""
        client = MagicMock()
        client.item_template.return_value = {
            "itemType": "attachment", "linkMode": "linked_file",
            "title": "", "path": "",
        }
        # 1st call succeeds, 2nd fails, 3rd succeeds
        client.create_items.side_effect = [
            [{"successful": {"key": "A1"}}],
            [{"failed": "permission denied"}],
            [{"successful": {"key": "A3"}}],
        ]
        pdf1 = tmp_path / "p1.pdf"; pdf1.write_text("1")
        pdf2 = tmp_path / "p2.pdf"; pdf2.write_text("2")
        pdf3 = tmp_path / "p3.pdf"; pdf3.write_text("3")
        with patch("builtins.print"):
            result = zotero_api.upload_pdfs(
                client,
                [
                    {"pdf_path": str(pdf1), "parent_key": "P1"},
                    {"pdf_path": str(pdf2), "parent_key": "P2"},
                    {"pdf_path": str(pdf3), "parent_key": "P3"},
                ],
                mode="linked_file",
            )
        assert result["n_uploaded"] == 2
        assert result["n_failed"] == 1
        assert result["results"][0]["zotero_key"] == "A1"
        assert result["results"][1]["status"] == "failed"
        assert result["results"][2]["zotero_key"] == "A3"


# ─────────────────────────────────────────────────────────────────
# TestPushItemsIntegratesUpload
# ─────────────────────────────────────────────────────────────────
class TestPushItemsIntegratesUpload:
    def test_push_items_calls_upload_pdfs_when_pdf_dir_set(self, tmp_path):
        """push_items() should call upload_pdfs() if pdf_dir is set
        and matching PDFs exist."""
        # Setup client
        client = MagicMock()
        client.check_items.return_value = [None, None]  # not existing
        client.create_items.return_value = [
            {"successful": {"key": "ZOTERO_KEY_1", "data": {}}},
            {"successful": {"key": "ZOTERO_KEY_2", "data": {}}},
        ]
        # Setup pdf_dir with matching PDFs
        pdf_dir = tmp_path / "pdfs"
        pdf_dir.mkdir()
        (pdf_dir / "k1.pdf").write_text("pdf 1")
        (pdf_dir / "k2.pdf").write_text("pdf 2")
        # Build entries
        entries = [
            {"key": "k1", "doi": "10.1/k1", "type": "article", "title": "K1"},
            {"key": "k2", "doi": "10.1/k2", "type": "article", "title": "K2"},
        ]
        with patch.object(zotero_api, "upload_pdfs") as mock_upload:
            mock_upload.return_value = {
                "n_uploaded": 2, "n_failed": 0,
                "results": [
                    {"pdf_path": str(pdf_dir / "k1.pdf"), "parent_key": "ZOTERO_KEY_1",
                     "zotero_key": "ATT1", "mode": "linked_file", "status": "uploaded"},
                    {"pdf_path": str(pdf_dir / "k2.pdf"), "parent_key": "ZOTERO_KEY_2",
                     "zotero_key": "ATT2", "mode": "linked_file", "status": "uploaded"},
                ],
            }
            result = zotero_api.push_items(
                client=client,
                bibtex_entries=entries,
                pdf_dir=pdf_dir,
                mode="linked_file",
                skip_existing=True,
            )
        # upload_pdfs was called with the right uploads
        assert mock_upload.called
        call_args = mock_upload.call_args
        uploads = call_args[0][1]  # second positional arg
        assert len(uploads) == 2
        assert all("parent_key" in u for u in uploads)
        assert all(u["parent_key"].startswith("ZOTERO_KEY") for u in uploads)
        # Result includes PDF stats
        assert result["n_pdf_uploaded"] == 2
        assert result["n_pdf_failed"] == 0
        # Per-item results include the PDF upload statuses
        pdf_results = [r for r in result["results"] if r.get("status", "").startswith("pdf_")]
        assert len(pdf_results) == 2

    def test_push_items_skips_upload_when_no_pdf_dir(self, tmp_path):
        """No pdf_dir = no upload step."""
        client = MagicMock()
        client.check_items.return_value = [None]
        client.create_items.return_value = [
            {"successful": {"key": "K1"}},
        ]
        entries = [{"key": "k1", "doi": "10.1/k1", "type": "article", "title": "K1"}]
        with patch.object(zotero_api, "upload_pdfs") as mock_upload:
            result = zotero_api.push_items(
                client=client,
                bibtex_entries=entries,
                pdf_dir=None,
                mode="linked_file",
                skip_existing=True,
            )
        assert not mock_upload.called
        assert result["n_pdf_uploaded"] == 0
        assert result["n_pdf_failed"] == 0

    def test_push_items_skips_upload_when_no_matching_pdfs(self, tmp_path):
        """pdf_dir set but no matching PDFs = no upload."""
        client = MagicMock()
        client.check_items.return_value = [None]
        client.create_items.return_value = [{"successful": {"key": "K1"}}]
        pdf_dir = tmp_path / "pdfs"
        pdf_dir.mkdir()
        # No PDFs inside
        entries = [{"key": "k1", "doi": "10.1/k1", "type": "article", "title": "K1"}]
        with patch.object(zotero_api, "upload_pdfs") as mock_upload:
            result = zotero_api.push_items(
                client=client,
                bibtex_entries=entries,
                pdf_dir=pdf_dir,
                mode="linked_file",
                skip_existing=True,
            )
        assert not mock_upload.called
        assert result["n_pdf_uploaded"] == 0
