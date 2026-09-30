"""Offline provenance gates: python test_output/test_fetch_m1b.py."""
import sys
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pa_cli import fetch, cache

DOI = '10.1234/article'
URL = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pmc&id=1'


def jats(doi=DOI, license_url='https://creativecommons.org/licenses/by/4.0/'):
    return f'''<article xmlns:xlink="http://www.w3.org/1999/xlink"><front><article-meta>
    <article-id pub-id-type="doi">{doi}</article-id><title-group><article-title>Example study</article-title></title-group>
    <permissions><license xlink:href="{license_url}"/></permissions></article-meta></front>
    <body><p>Study text</p></body><back><ref-list><ref><article-id pub-id-type="doi">10.9999/reference</article-id></ref></ref-list></back></article>'''.encode()


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def assess(self, body=None, **kwargs):
        from pa_cli.provenance import inspect_artifact
        path = self.root / 'article.xml'
        path.write_bytes(jats() if body is None else body)
        args = dict(path=path, requested_doi=DOI, source='pmc_xml_only', url=URL, data_class='public')
        args.update(kwargs)
        return inspect_artifact(**args)

    def test_fetch_exposes_policy_for_xml(self):
        path = self.root / 'article.xml'
        path.write_bytes(jats())
        with patch.object(fetch, 'fetch', return_value={'source':'pmc_xml_only', 'xml_path':str(path), 'source_url':URL}):
            result = fetch.fetch_doi(DOI, output_dir=str(self.root), use_cache=False)
        self.assertIn('provenance', result)
        self.assertEqual(result['provenance']['identity']['status'], 'verified')
        self.assertFalse(result['provenance']['external_upload_allowed'])

    def test_reference_doi_does_not_override_article_identity(self):
        p = self.assess()
        self.assertEqual(p['identity']['status'], 'verified')
        self.assertEqual(p['rights']['class'], 'public_oa')
        self.assertTrue(p['external_evaluation_candidate'])
        self.assertFalse(p['external_upload_allowed'])

    def test_wrong_or_missing_article_doi(self):
        self.assertEqual(self.assess(jats('10.1234/other'))['identity']['status'], 'mismatch')
        self.assertEqual(self.assess(jats(''))['identity']['status'], 'unverified')
        self.assertFalse(self.assess(jats('10.1234/other'))['external_evaluation_candidate'])

    def test_title_conflict_and_doi_normalization(self):
        self.assertEqual(self.assess(requested_doi='https://doi.org/10.1234/ARTICLE')['identity']['status'], 'verified')
        self.assertEqual(self.assess(expected_title='Different study')['identity']['status'], 'mismatch')

    def test_missing_license_and_spoofed_host_stay_local(self):
        for body, url in [(jats(license_url=''), URL), (jats(), 'https://eutils.ncbi.nlm.nih.gov.evil.test/a'), (jats(), '')]:
            with self.subTest(url=url):
                self.assertFalse(self.assess(body, url=url)['external_evaluation_candidate'])

    def test_gray_private_and_unpublished_stay_local(self):
        for source, data_class in [('scihub', 'public'), ('annas', 'public'), ('pmc_xml_only', 'private'), ('pmc_xml_only', 'unpublished'), ('pmc_xml_only', 'unknown')]:
            with self.subTest(source=source, data_class=data_class):
                self.assertFalse(self.assess(source=source, data_class=data_class)['external_evaluation_candidate'])

    def test_malformed_and_entity_xml_fail_closed(self):
        for body in [b'<article>', b'<!DOCTYPE article [<!ENTITY x "10.1234/article">]><article>&x;</article>', b'not xml']:
            p = self.assess(body)
            self.assertEqual(p['identity']['status'], 'unverified')
            self.assertFalse(p['external_evaluation_candidate'])

    def test_unknown_pdf_cache_is_not_promoted_by_doi_key(self):
        body = b'%PDF-1.4\n' + b'padding\n' * 8000
        with patch.object(cache, 'get_cache_root', return_value=self.root):
            cache.cache_put(DOI, body, channel='pmc', url=URL)
            result = fetch.fetch_doi(DOI)
        self.assertEqual(result['final_status'], 'SUCCESS_CACHE_HIT')
        self.assertEqual(result['provenance']['identity']['status'], 'unverified')
        self.assertFalse(result['provenance']['external_evaluation_candidate'])

    @unittest.skipUnless(importlib.util.find_spec('pymupdf') or importlib.util.find_spec('fitz'), 'optional PyMuPDF is not installed')
    def test_pdf_metadata_and_per_call_privacy_on_cache_hit(self):
        try:
            import pymupdf as fitz
        except ImportError:
            import fitz
        doc = fitz.open()
        doc.new_page()
        doc.set_xml_metadata('''<x:xmpmeta xmlns:x="adobe:ns:meta/" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><rdf:RDF>
        <rdf:Description xmlns:prism="http://prismstandard.org/namespaces/basic/2.0/" xmlns:cc="http://creativecommons.org/ns#">
        <prism:doi>10.1234/article</prism:doi><cc:license rdf:resource="https://creativecommons.org/licenses/by/4.0/"/>
        </rdf:Description></rdf:RDF></x:xmpmeta>''')
        body = doc.tobytes() + b'\n%' + b'padding' * 10000
        doc.close()
        with patch.object(cache, 'get_cache_root', return_value=self.root):
            cache.cache_put(DOI, body, channel='pmc', url='https://europepmc.org/articles/PMC1?pdf=render')
            public = fetch.fetch_doi(DOI, data_class='public')['provenance']
            private = fetch.fetch_doi(DOI, data_class='unpublished')['provenance']
            default = fetch.fetch_doi(DOI)['provenance']
        self.assertEqual(public['identity']['status'], 'verified')
        self.assertTrue(public['external_evaluation_candidate'])
        self.assertFalse(public['external_upload_allowed'])
        self.assertFalse(private['external_evaluation_candidate'])
        self.assertFalse(default['external_evaluation_candidate'])

    def test_xml_only_does_not_adopt_leftover_pdf(self):
        path = self.root / 'article.xml'
        path.write_bytes(jats())
        (self.root / '10_1234_article.pdf').write_bytes(b'%PDF-1.4\n' + b'padding' * 10000)
        with patch.object(cache, 'get_cache_root', return_value=self.root), patch.object(fetch, 'fetch', return_value={
            'source':'pmc_xml_only', 'xml_path':str(path), 'pdf_path':None, 'source_url':URL
        }):
            result = fetch.fetch_doi(DOI, output_dir=str(self.root), use_cache=False)
        self.assertEqual(result['final_status'], 'SUCCESS_XML_ONLY')
        self.assertEqual(result['provenance']['identity']['status'], 'verified')


if __name__ == '__main__':
    unittest.main()
