import os
import unittest
from pa_cli.jats_to_pdf import jats_xml_to_html, jats_xml_to_pdf

ARTICLE = b'<article><front><article-meta><title-group><article-title>Rendering contract</article-title></title-group></article-meta></front><body><sec><title>Results</title><p>Verified body text.</p></sec></body></article>'

class JatsRenderingTests(unittest.TestCase):
    def test_root_and_wrapped_articles_render_same_content(self):
        wrapped = b'<article-set>' + ARTICLE + b'</article-set>'
        self.assertEqual(jats_xml_to_html(ARTICLE), jats_xml_to_html(wrapped))

    def test_namespaced_article(self):
        content = jats_xml_to_html(ARTICLE.replace(b'<article>', b'<article xmlns="urn:jats">', 1))
        self.assertIn('Verified body text.', content)

    @unittest.skipUnless(os.environ.get('PA_TEST_BROWSER') == '1', 'opt-in Chromium integration')
    def test_actual_chromium_pdf_contains_article_text(self):
        import io
        from pypdf import PdfReader
        pdf = jats_xml_to_pdf(ARTICLE, embed_figures=False)
        self.assertTrue(pdf.startswith(b'%PDF'))
        reader = PdfReader(io.BytesIO(pdf))
        self.assertGreater(len(reader.pages), 0)
        text = ' '.join(' '.join(page.extract_text() for page in reader.pages).split())
        self.assertIn('Rendering contract', text)
        self.assertIn('Verified body text.', text)
