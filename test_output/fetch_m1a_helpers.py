"""Pickle-safe offline fetch helpers for the M1A subprocess tests."""

from pathlib import Path
import time


FAKE_PDF = b"%PDF-1.4\n%m1a\n" + b"offline padding\n" * 4000


def successful_pdf_fetch(doi=None, out_path=None, prefer="auto"):
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(FAKE_PDF)
    return {
        "source": "offline-test",
        "path": str(path),
        "size": len(FAKE_PDF),
        "pdf_url": "https://example.test/paper.pdf",
    }


def xml_only_fetch(doi=None, out_path=None, prefer="auto"):
    path = Path(out_path).with_suffix(".xml")
    path.parent.mkdir(parents=True, exist_ok=True)
    body = b"<article><body><p>offline</p></body></article>"
    path.write_bytes(body)
    return {
        "source": "pmc_xml_only",
        "xml_path": str(path),
        "xml_size": len(body),
        "pdf_path": None,
    }


def invalid_artifact_fetch(doi=None, out_path=None, prefer="auto"):
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"not a pdf")
    return {
        "source": "offline-invalid",
        "path": str(path),
        "size": path.stat().st_size,
    }


def slow_fetch(doi=None, out_path=None, prefer="auto"):
    time.sleep(0.5)
    return successful_pdf_fetch(doi=doi, out_path=out_path, prefer=prefer)
