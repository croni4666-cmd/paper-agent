"""Local artifact evidence for M1B. No network, uploads, or inferred consent.

These are routing policy decisions, not a legal opinion or authenticity proof.
Only article metadata is inspected; reference-list DOIs cannot verify identity.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path
from urllib.parse import urlsplit, unquote
from xml.etree import ElementTree as ET

POLICY_VERSION = 'm1b-1'
MAX_XML_BYTES = 8 * 1024 * 1024
MAX_ARTIFACT_BYTES = 100 * 1024 * 1024
SOURCE_HOSTS = {
    'pmc_xml': {'eutils.ncbi.nlm.nih.gov'},
    'pmc_xml_only': {'eutils.ncbi.nlm.nih.gov'},
    'pmc': {'europepmc.org', 'pmc.ncbi.nlm.nih.gov'},
    'pmc_europe': {'europepmc.org'},
    'arxiv': {'arxiv.org'},
}
DC = 'http://purl.org/dc/elements/1.1/'
PRISM = 'http://prismstandard.org/namespaces/basic/2.0/'
CC = 'http://creativecommons.org/ns#'


def _doi(value):
    value = unquote(str(value or '')).strip().lower()
    value = re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)', '', value)
    return value if re.fullmatch(r'10\.\d{4,9}/\S+', value) else ''


def _title(value):
    return ' '.join(re.findall(r'\w+', unicodedata.normalize('NFKC', value).casefold()))


def _parse_xml(body):
    if len(body) > MAX_XML_BYTES or b'<!ENTITY' in body.upper():
        raise ValueError('xml_limit_or_entity')
    return ET.fromstring(body)


def _metadata(path):
    """Return evidence anchored in the article header or embedded XMP."""
    if path.suffix.lower() == '.xml':
        with path.open('rb') as stream:
            tree = _parse_xml(stream.read(MAX_XML_BYTES + 1))
        # Strip JATS namespace only; never search the body or back matter.
        for node in tree.iter():
            node.tag = node.tag.rsplit('}', 1)[-1]
        if tree.tag != 'article':
            raise ValueError('not_jats_article')
        meta = tree.find('./front/article-meta')
        if meta is None:
            return [], [], [], 'jats_article_meta_missing'
        dois = [''.join(n.itertext()) for n in meta.findall('./article-id')
                if n.get('pub-id-type', '').lower() == 'doi']
        titles = [''.join(n.itertext()) for n in meta.findall('./title-group/article-title')]
        licenses = []
        for n in meta.findall('./permissions/license'):
            for elem in n.iter():
                licenses.extend(v for k, v in elem.attrib.items() if k.rsplit('}', 1)[-1] == 'href')
        return dois, titles, licenses, 'jats_article_meta'
    if path.suffix.lower() != '.pdf':
        raise ValueError('unsupported_artifact')
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz  # Compatibility with older installations.
    with fitz.open(str(path)) as doc:
        xmp = doc.get_xml_metadata()
    if not xmp:
        return [], [], [], 'pdf_xmp_missing'
    tree = _parse_xml(xmp.encode('utf-8'))
    dois, titles, licenses = [], [], []
    for node in tree.iter():
        if node.tag in (f'{{{PRISM}}}doi', f'{{{DC}}}identifier'):
            dois.extend(t.strip() for t in node.itertext() if t.strip())
        if node.tag == f'{{{DC}}}title':
            titles.extend(t.strip() for t in node.itertext() if t.strip())
        if node.tag == f'{{{CC}}}license':
            licenses.extend(node.attrib.values())
    return dois, titles, licenses, 'pdf_xmp'


def _allowed_license(value):
    return bool(re.fullmatch(
        r'https?://creativecommons\.org/(?:licenses/by/(?:2\.0|2\.5|3\.0|4\.0)|publicdomain/zero/1\.0)/?',
        value.strip().lower()))


def inspect_artifact(path, requested_doi, source='', url='', *,
                     expected_title=None, data_class='unknown'):
    """Inspect bytes on every call, including cache hits. Never authorize uploads.

    Public data classification must be explicit. Only CC BY/CC0 metadata and
    a conservative source/host allowlist qualify as an evaluation candidate.
    Missing metadata is unverified, and an unrelated DOI is a mismatch.
    No title-only fuzzy match can verify a DOI request.
    """
    artifact = Path(path)
    digest = None
    dois, titles, licenses = [], [], []
    evidence = 'metadata_unavailable'
    try:
        if artifact.stat().st_size > MAX_ARTIFACT_BYTES:
            raise ValueError('artifact_size_limit')
        sha = hashlib.sha256()
        with artifact.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                sha.update(block)
        digest = sha.hexdigest()
        dois, titles, licenses, evidence = _metadata(artifact)
    except Exception as exc:
        # Optional parser errors must not break local Fetch or leak document text.
        evidence = f'metadata_unavailable:{type(exc).__name__}'

    requested = _doi(requested_doi)
    observed = sorted({_doi(v) for v in dois} - {''})
    state, reason = 'unverified', 'article_doi_missing'
    if not requested:
        reason = 'requested_doi_invalid'
    elif len(observed) > 1:
        reason = 'conflicting_article_dois'
    elif observed:
        state = 'verified' if observed[0] == requested else 'mismatch'
        reason = 'article_doi_match' if state == 'verified' else 'article_doi_mismatch'
    if expected_title:
        if not titles and state == 'verified':
            state, reason = 'unverified', 'article_title_missing'
        elif titles and _title(expected_title) not in {_title(t) for t in titles}:
            state, reason = 'mismatch', 'article_title_mismatch'

    try:
        parsed = urlsplit(url or '')
        source_allowed = (parsed.scheme == 'https' and parsed.hostname in SOURCE_HOSTS.get(source, set())
                          and not parsed.username and not parsed.password and parsed.port in (None, 443))
    except (ValueError, TypeError):
        source_allowed = False
    # Multiple licenses, or missing/restrictive terms, require human review.
    license_allowed = bool(licenses) and all(_allowed_license(v) for v in licenses)
    rights_class = 'unknown'
    if source in ('scihub', 'annas', 'cnki'):
        rights_class = 'restricted_source'
    elif data_class in ('private', 'confidential', 'unpublished'):
        rights_class = data_class
    elif data_class == 'public' and source_allowed and license_allowed:
        rights_class = 'public_oa'
    reasons = []
    if state != 'verified':
        reasons.append(reason)
    if rights_class != 'public_oa':
        reasons.append('source_rights_not_eligible')
    if data_class != 'public':
        reasons.append('data_not_explicitly_public')
    candidate = not reasons
    return {
        'policy_version': POLICY_VERSION,
        'artifact_sha256': digest,
        'source': source,
        'identity': {'status': state, 'reason': reason, 'requested_doi': requested,
                     'observed_dois': observed, 'evidence': evidence},
        'rights': {'class': rights_class, 'source_allowlisted': bool(source_allowed),
                   'license_urls': sorted(set(licenses)), 'data_class': data_class},
        'external_evaluation_candidate': candidate,
        'external_upload_allowed': False,
        'blocking_reasons': reasons,
    }
