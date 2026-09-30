"""Offline M2 contract tests; requires existing optional PyMuPDF."""
import sys
import tempfile
import unittest
import subprocess
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pymupdf


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pdf = Path(self.tmp.name) / 'study.pdf'
        with pymupdf.open() as doc:
            doc.new_page().insert_text((72,72), 'Methods\nWe randomized workers into two groups.\nEmployment was measured monthly.')
            doc.new_page().insert_text((72,72), 'Results\nEmployment increased in the treatment group.\nUncertainty remains substantial.')
            doc.new_page()
            doc.save(self.pdf)

    def index(self, **kwargs):
        from pa_cli.evidence import build_index
        return build_index(self.pdf, **kwargs)

    def test_spans_roundtrip_and_ids_are_stable(self):
        first, second = self.index(), self.index()
        self.assertEqual(first, second)
        self.assertEqual(len(first['pages']), 3)
        for span in first['spans']:
            page = first['pages'][span['page'] - 1]
            self.assertEqual(span['text'], page['text'][span['start']:span['end']])
        self.assertEqual(first['pages'][2]['status'], 'empty_needs_review')
        self.assertTrue(any(s['section'] == 'methods' for s in first['spans']))

    def test_packet_has_bounded_exact_evidence(self):
        from pa_cli.evidence import build_packet
        import json
        index = self.index()
        packet = build_packet(index, 'employment', max_bytes=3000, max_spans=2, required_sections=['methods','results'])
        self.assertEqual(packet['status'], 'ready_for_local_review')
        self.assertLessEqual(len(packet['evidence']), 2)
        self.assertLessEqual(len(json.dumps(packet, ensure_ascii=False, sort_keys=True).encode()), 3000)
        self.assertFalse(packet['external_upload_allowed'])
        for excerpt in packet['evidence']:
            page = index['pages'][excerpt['page'] - 1]
            self.assertEqual(excerpt['text'], page['text'][excerpt['start']:excerpt['end']])

    def test_no_match_does_not_fill_with_unrelated_text(self):
        from pa_cli.evidence import build_packet
        p = build_packet(self.index(), 'nonexistentkeyword')
        self.assertEqual(p['evidence'], [])
        self.assertEqual(p['status'], 'insufficient_evidence')

    def test_missing_required_section_is_not_complete(self):
        from pa_cli.evidence import build_packet
        p = build_packet(self.index(), 'employment', required_sections=['limitations'])
        self.assertEqual(p['status'], 'insufficient_evidence')
        self.assertEqual(p['missing_sections'], ['limitations'])

    def test_tampered_span_is_rejected(self):
        from pa_cli.evidence import build_packet
        index = self.index()
        index['spans'][0]['text'] = 'Invented conclusion'
        with self.assertRaises(ValueError):
            build_packet(index, 'conclusion')

    def test_small_budget_and_invalid_limits(self):
        from pa_cli.evidence import build_packet
        with self.assertRaises(ValueError):
            build_packet(self.index(), 'employment', max_bytes=10)
        with self.assertRaises(ValueError):
            self.index(max_pages=2)
        with self.assertRaises(ValueError):
            self.index(chunk_chars=0)

    def test_changed_pdf_changes_artifact_and_evidence_ids(self):
        a = self.index()
        self.pdf.write_bytes(self.pdf.read_bytes() + b'\n% changed bytes\n')
        b = self.index()
        self.assertNotEqual(a['artifact_sha256'], b['artifact_sha256'])
        self.assertNotEqual(a['spans'][0]['evidence_id'], b['spans'][0]['evidence_id'])

    def test_cli_export_and_no_overwrite(self):
        output = self.pdf.with_suffix('.packet.json')
        cmd = [sys.executable, '-B', '-m', 'pa_cli.evidence', str(self.pdf),
               '--query', 'employment', '--output', str(output), '--max-bytes', '3000']
        first = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(first.returncode, 0, first.stderr)
        original = output.read_bytes()
        self.assertLessEqual(len(original), 3000)
        self.assertEqual(json.loads(original)['status'], 'ready_for_local_review')
        second = subprocess.run(cmd, capture_output=True, text=True)
        self.assertNotEqual(second.returncode, 0)
        self.assertEqual(output.read_bytes(), original)

    def test_character_budget_cannot_silently_drop_pages(self):
        with self.assertRaises(ValueError):
            self.index(max_chars=10)

    def test_packet_budget_can_return_empty_without_claiming_success(self):
        from pa_cli.evidence import build_packet
        baseline = build_packet(self.index(), 'absentterm')
        budget = len(json.dumps(baseline, ensure_ascii=False, sort_keys=True).encode()) + 10
        packet = build_packet(self.index(), 'employment', max_bytes=budget)
        self.assertEqual(packet['evidence'], [])
        self.assertEqual(packet['status'], 'insufficient_evidence')


if __name__ == '__main__':
    unittest.main()
