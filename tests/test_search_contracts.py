import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch, Mock
from pa_cli import search, aminer_channel

class SearchContracts(unittest.TestCase):
    def check_record(self, record, source, year=2025):
        self.assertEqual(record['source'], source)
        self.assertEqual(record['title'], 'Example study')
        self.assertEqual(record['year'], year)
        for key in ('doi', 'title', 'venue'):
            self.assertIsInstance(record[key], str)
        self.assertIsInstance(record['authors'], list)
        self.assertTrue(all(isinstance(a, str) for a in record['authors']))
        self.assertIsInstance(record['cited_by_count'], int)

    def test_crossref_fixture(self):
        self.check_record(search._normalize_crossref({'title':['Example study'],
            'DOI':'10.1000/example', 'published-online':{'date-parts':[[2025]]},
            'author':[{'family':'Example','given':'A'}]}), 'crossref')

    def test_openalex_fixture(self):
        self.check_record(search._normalize_openalex({'title':'Example study',
            'publication_date':'2025-01-01', 'doi':'https://doi.org/10.1000/example',
            'authorships':[{'author':{'display_name':'A Example'}}]}), 'openalex')

    def test_pubmed_fixture(self):
        self.check_record(search._normalize_pubmed({'title':'Example study',
            'uid':'123','pubdate':'2025 Jan','authors':[{'name':'Example A'}]}),'pubmed')

    def test_clinicaltrials_fixture(self):
        self.check_record(search._normalize_clinicaltrial({'protocolSection':{
            'identificationModule':{'nctId':'NCT00000001','briefTitle':'Example study'},
            'statusModule':{'startDateStruct':{'date':'2025-01'}}}}),'clinicaltrials')

    def test_arxiv_fixture(self):
        result=SimpleNamespace(doi=None, entry_id='https://arxiv.org/abs/2501.00001v1',
            title='Example study',authors=[SimpleNamespace(name='A Example')],
            published=datetime(2025,1,1),pdf_url='https://arxiv.org/pdf/2501.00001v1')
        sdk=SimpleNamespace(Client=Mock(),Search=Mock(),SortCriterion=SimpleNamespace(Relevance='relevance'))
        sdk.Client.return_value.results.return_value=[result]
        with patch.dict('sys.modules',{'arxiv':sdk}):
            records=search.search_arxiv('example',limit=1)
        self.check_record(records[0],'arxiv')
        self.assertEqual(records[0]['arxiv_id'],'2501.00001v1')

    def test_aminer_pro_fixture(self):
        with patch.object(aminer_channel,'_aminer_token',return_value='test-token'), \
             patch.object(aminer_channel.time,'sleep'), \
             patch.object(aminer_channel,'_http_get',return_value=(200,{'data':[{
                 'title':'Example study','year':'2025','authors':[{'name':'A Example'}],
                 'n_citation':'3'}]})):
            records=aminer_channel.search_aminer_pro('example',limit=1)
        self.check_record(records[0],'aminer')

    def test_optional_crossref_dates_and_counts(self):
        record=search._normalize_crossref({'title':['Example study'],
            'published-print':{'date-parts':[]},'is-referenced-by-count':None})
        self.check_record(record,'crossref',None)

    def test_optional_openalex_dates_and_authors(self):
        record=search._normalize_openalex({'title':'Example study',
            'publication_date':'unknown','authorships':[{'author':None}],
            'cited_by_count':None})
        self.check_record(record,'openalex',None)
