import unittest

from pa_cli import search


class PubMedDetailsTests(unittest.TestCase):
    def test_parse_pubmed_details_extracts_abstract_and_mesh(self):
        xml = b"""<PubmedArticleSet><PubmedArticle><MedlineCitation>
        <PMID>123</PMID><Article><Abstract><AbstractText Label="BACKGROUND">First.</AbstractText>
        <AbstractText>Second.</AbstractText></Abstract></Article>
        <MeshHeadingList><MeshHeading><DescriptorName>Diabetes Mellitus</DescriptorName></MeshHeading>
        <MeshHeading><DescriptorName>Insulin</DescriptorName></MeshHeading></MeshHeadingList>
        </MedlineCitation></PubmedArticle></PubmedArticleSet>"""

        details = search._parse_pubmed_details(xml)

        self.assertEqual(details["123"]["abstract"], "BACKGROUND: First. Second.")
        self.assertEqual(details["123"]["mesh_terms"], ["Diabetes Mellitus", "Insulin"])


if __name__ == "__main__":
    unittest.main()