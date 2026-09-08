import io
from pathlib import Path
import tempfile
import unittest
from pypdf import PdfWriter
from pa_cli.fetch_output import _complete_pdf


def make_pdf(pages=1, encrypted=False):
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=100, height=100)
    if encrypted:
        writer.encrypt('fixture-password')
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


class PdfStructureTests(unittest.TestCase):
    def test_marker_only_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'fake.pdf'
            path.write_bytes(b'%PDF-1.7\nnot a document\n%%EOF')
            self.assertFalse(_complete_pdf(path))

    def test_real_document_is_accepted(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'valid.pdf'
            path.write_bytes(make_pdf(2))
            self.assertTrue(_complete_pdf(path))

    def test_unreadable_documents_are_rejected(self):
        valid = make_pdf()
        for body in (make_pdf(0), make_pdf(encrypted=True),
                     valid.replace(b'/Pages', b'/Bogus'), valid[:100] + b'\n%%EOF'):
            with self.subTest(body=body[:30]), tempfile.TemporaryDirectory() as temp:
                path = Path(temp) / 'bad.pdf'
                path.write_bytes(body)
                self.assertFalse(_complete_pdf(path))

    def test_missing_page_content_object_is_rejected(self):
        from pypdf.generic import NameObject, IndirectObject
        writer = PdfWriter()
        page = writer.add_blank_page(width=100, height=100)
        page[NameObject('/Contents')] = IndirectObject(999, 0, writer)
        output = io.BytesIO()
        writer.write(output)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'missing-content.pdf'
            path.write_bytes(output.getvalue())
            self.assertFalse(_complete_pdf(path))

    def test_invalid_content_array_is_rejected(self):
        from pypdf.generic import NameObject, ArrayObject, NumberObject
        writer = PdfWriter()
        page = writer.add_blank_page(width=100, height=100)
        page[NameObject('/Contents')] = ArrayObject([NumberObject(42)])
        output = io.BytesIO()
        writer.write(output)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'bad-array.pdf'
            path.write_bytes(output.getvalue())
            self.assertFalse(_complete_pdf(path))
