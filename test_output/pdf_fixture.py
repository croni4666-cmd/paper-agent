"""Generated valid documents for cache tests; never use header padding as a PDF."""
import io
from pypdf import PdfWriter

def make_pdf(variant=0):
    writer=PdfWriter()
    for i in range(650):writer.add_blank_page(width=100+i+variant,height=100)
    stream=io.BytesIO();writer.write(stream);return stream.getvalue()
