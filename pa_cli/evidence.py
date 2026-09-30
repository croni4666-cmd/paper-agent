"""M2 local PDF evidence indexing and bounded lexical retrieval.

Offsets are Python character offsets into the stored page text, not PDF byte
offsets. Section scores are heuristics, not calibrated probabilities. This
module performs no network calls, OCR, consent decisions, or model judgments.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

VERSION = 'evidence-m2-1'
SECTIONS = {
    'methods': 'methods', 'methodology': 'methods', 'materials and methods': 'methods',
    'results': 'results', 'discussion': 'discussion', 'limitations': 'limitations',
    'abstract': 'abstract', 'introduction': 'introduction', 'conclusion': 'conclusion',
    'conclusions': 'conclusion', 'references': 'references',
}


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _hash(value):
    return hashlib.sha256(_json(value).encode('utf-8')).hexdigest()


def _span_id(artifact, extractor, page, start, end, text):
    return _hash([VERSION, artifact, extractor, page, start, end, text])


def _positive(name, value):
    if type(value) is not int or value <= 0:
        raise ValueError(f'{name} must be a positive integer')


def build_index(path, *, chunk_chars=1200, max_pages=500,
                max_chars=2_000_000, max_bytes=100 * 1024 * 1024):
    """Index a bounded PDF snapshot; retain exact page strings and spans.

    Failure to read a page fails the operation rather than silently omitting
    it. Empty pages remain visible as needing review. No OCR is attempted.
    """
    for key, value in [('chunk_chars', chunk_chars), ('max_pages', max_pages),
                       ('max_chars', max_chars), ('max_bytes', max_bytes)]:
        _positive(key, value)
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz
    with Path(path).open('rb') as stream:
        body = stream.read(max_bytes + 1)
    if len(body) > max_bytes:
        raise ValueError('artifact exceeds max_bytes')
    if not body.startswith(b'%PDF'):
        raise ValueError('expected PDF')
    artifact = hashlib.sha256(body).hexdigest()
    extractor = f'PyMuPDF/{fitz.VersionBind};text;sort=false;{VERSION}'
    pages, spans = [], []
    total = 0
    section = 'unknown'
    with fitz.open(stream=body, filetype='pdf') as doc:
        if doc.needs_pass:
            raise ValueError('encrypted PDF requires local decryption')
        if len(doc) > max_pages:
            raise ValueError('PDF exceeds max_pages')
        for number, page in enumerate(doc, 1):
            text = page.get_text('text', sort=False)
            total += len(text)
            if total > max_chars:
                raise ValueError('extracted text exceeds max_chars')
            status = 'text_extracted' if text.strip() else 'empty_needs_review'
            pages.append({'page': number, 'text': text, 'status': status,
                          'ocr_status': 'not_attempted'})
            # Split at explicit heading lines so a methods label cannot silently
            # carry into results on the same page. Unknown layouts stay advisory.
            boundaries = [(0, section)]
            for match in re.finditer(r'^.*$', text, re.MULTILINE):
                heading = re.sub(r'^\s*\d+(?:\.\d+)*[.)]?\s*', '', match.group()).strip().rstrip(':').casefold()
                if heading in SECTIONS:
                    section = SECTIONS[heading]
                    if match.start() == 0:
                        boundaries[0] = (0, section)
                    else:
                        boundaries.append((match.start(), section))
            boundaries.append((len(text), section))
            for (begin, label), (end, _) in zip(boundaries, boundaries[1:]):
                for start in range(begin, end, chunk_chars):
                    stop = min(start + chunk_chars, end)
                    excerpt = text[start:stop]
                    if not excerpt.strip():
                        continue
                    spans.append({
                        'evidence_id': _span_id(artifact, extractor, number, start, stop, excerpt),
                        'page': number, 'start': start, 'end': stop, 'text': excerpt,
                        'section': label, 'section_confidence': 0.5 if label != 'unknown' else 0.0,
                        'section_method': 'heading_heuristic',
                    })
    index = {'schema_version': VERSION, 'artifact_sha256': artifact,
             'extractor': extractor, 'pages': pages, 'spans': spans,
             'chunk_chars': chunk_chars, 'ocr_status': 'not_attempted'}
    index['index_hash'] = _hash(index)
    return index


def _validate(index):
    if index.get('schema_version') != VERSION:
        raise ValueError('unsupported index schema')
    if index.get('index_hash') != _hash({k:v for k,v in index.items() if k != 'index_hash'}):
        raise ValueError('index integrity mismatch; rebuild from local PDF')
    for span in index['spans']:
        page = index['pages'][span['page'] - 1]
        if (page['page'] != span['page'] or not 0 <= span['start'] < span['end'] <= len(page['text'])
                or page['text'][span['start']:span['end']] != span['text']
                or span['evidence_id'] != _span_id(index['artifact_sha256'], index['extractor'],
                                                 span['page'], span['start'], span['end'], span['text'])):
            raise ValueError('evidence does not match indexed page')


def build_packet(index, query, *, max_bytes=16000, max_spans=6, required_sections=()):
    """Select matching spans within the full serialized UTF-8 budget.

    Exact lexical matching is deliberately limited. Absence of a match is not
    evidence that a claim is false. Required section names are advisory checks.
    """
    _positive('max_bytes', max_bytes)
    _positive('max_spans', max_spans)
    if not isinstance(query, str) or not query.strip() or len(query) > 2000:
        raise ValueError('query must contain 1..2000 characters')
    required = sorted(set(required_sections))
    if any(s not in set(SECTIONS.values()) for s in required):
        raise ValueError('unsupported required section')
    _validate(index)
    terms = set(re.findall(r'\w+', query.casefold()))
    candidates = []
    for span in index['spans']:
        score = len(terms & set(re.findall(r'\w+', span['text'].casefold())))
        if score:
            candidates.append((score, span))
    candidates.sort(key=lambda item: (-item[0], item[1]['page'], item[1]['start']))
    # Give each requested section a chance before filling remaining capacity.
    ordered = []
    for section in required:
        first = next((s for _, s in candidates if s['section'] == section), None)
        if first is not None:
            ordered.append(first)
    seen = {s['evidence_id'] for s in ordered}
    ordered.extend(s for _, s in candidates if s['evidence_id'] not in seen)

    def assemble(evidence):
        missing = sorted(set(required) - {s['section'] for s in evidence})
        packet = {
            'schema_version': VERSION, 'artifact_sha256': index['artifact_sha256'],
            'index_hash': index['index_hash'], 'extractor': index['extractor'],
            'query': query, 'evidence': evidence, 'missing_sections': missing,
            'status': 'ready_for_local_review' if evidence and not missing else 'insufficient_evidence',
            'pages_needing_review': [p['page'] for p in index['pages'] if p['status'] != 'text_extracted'],
            'ocr_status': 'not_attempted', 'external_upload_allowed': False,
        }
        packet['packet_hash'] = _hash(packet)
        return packet

    selected = []
    if len(_json(assemble(selected)).encode('utf-8')) > max_bytes:
        raise ValueError('max_bytes cannot hold packet metadata')
    for span in ordered:
        if len(selected) >= max_spans:
            break
        attempt = assemble(selected + [span])
        if len(_json(attempt).encode('utf-8')) <= max_bytes:
            selected.append(dict(span))
    return assemble(selected)


def main():
    parser = argparse.ArgumentParser(description='Build local PDF evidence index or query packet; no uploads.')
    parser.add_argument('pdf', type=Path)
    parser.add_argument('--query')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--max-bytes', type=int, default=16000, help='packet UTF-8 byte budget')
    args = parser.parse_args()
    if args.output.resolve() == args.pdf.resolve():
        parser.error('output must not overwrite source PDF')
    index = build_index(args.pdf)
    result = build_packet(index, args.query, max_bytes=args.max_bytes) if args.query else index
    # Exclusive creation avoids silently overwriting prior audit artifacts.
    with args.output.open('x', encoding='utf-8', newline='') as stream:
        stream.write(_json(result))


if __name__ == '__main__':
    main()
