"""Offline, provenance-preserving MeSH descriptor lookup (standard library)."""
from __future__ import annotations

import argparse
from contextlib import closing
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime, timezone


def download_mesh(year: int, directory: Path) -> dict:
    """Explicitly fetch a fixed official NLM descriptor snapshot, not code."""
    import requests
    from ._http import get_proxy_dict
    if not 2000 <= year <= 2099:
        raise ValueError('MeSH year must be in 2000..2099')
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    url = f'https://nlmpubs.nlm.nih.gov/projects/mesh/MESH_FILES/xmlmesh/desc{year}.gz'
    target = directory / f'desc{year}.gz'
    fd, name = tempfile.mkstemp(prefix='mesh-download-', suffix='.part', dir=directory)
    os.close(fd)
    temp = Path(name)
    digest, size = hashlib.sha256(), 0
    try:
        with requests.get(url,stream=True,proxies=get_proxy_dict(),timeout=(10,60)) as response:
            response.raise_for_status()
            with temp.open('wb') as handle:
                # NLM may mark the .gz entity as Content-Encoding: gzip.
                # requests.iter_content would silently decode the snapshot.
                for chunk in response.raw.stream(1024*1024,decode_content=False):
                    size += len(chunk)
                    if size > 100*1024*1024:
                        raise ValueError('MeSH compressed snapshot exceeds 100 MiB download budget')
                    handle.write(chunk)
                    digest.update(chunk)
        with temp.open('rb') as handle:
            if handle.read(2) != b'\x1f\x8b':
                raise ValueError('Official snapshot response is not a gzip file')
        os.replace(temp,target)
        return {'path':str(target),'url':url,'bytes':size,'sha256':digest.hexdigest()}
    finally:
        if temp.exists():
            temp.unlink()


def normalize(text: str) -> str:
    return re.sub(r'[\W_]+', ' ', unicodedata.normalize('NFKC', text).casefold()).strip()


def import_mesh(source: Path, output: Path, *, source_url: str, year: int) -> dict:
    """Import an official descriptor XML or gzip snapshot atomically.

    Related concepts remain discoverable, but are not promoted to synonyms.
    Downloading and replacing an existing snapshot is an explicit caller action.
    """
    source, output = Path(source), Path(output)
    digest = hashlib.sha256()
    with source.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='mesh-import-', suffix='.sqlite', dir=output.parent)
    os.close(fd)
    temp = Path(name)
    connection = None
    try:
        connection = sqlite3.connect(temp)
        connection.executescript('''
            CREATE TABLE descriptors (id TEXT PRIMARY KEY, label TEXT NOT NULL,
                scope TEXT NOT NULL, synonyms TEXT NOT NULL, trees TEXT NOT NULL);
            CREATE TABLE terms (term TEXT NOT NULL, id TEXT NOT NULL, kind TEXT NOT NULL,
                PRIMARY KEY (term,id,kind));
            CREATE INDEX term_lookup ON terms(term);
            CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        ''')
        count = 0
        opener = gzip.open if source.suffix == '.gz' else open
        with opener(source, 'rb') as handle:
            events = ET.iterparse(handle, events=('start', 'end'))
            event, root = next(events)
            if event != 'start' or root.tag != 'DescriptorRecordSet':
                raise ValueError('Expected a MeSH DescriptorRecordSet XML snapshot')
            for event, record in events:
                if event != 'end' or record.tag != 'DescriptorRecord':
                    continue
                did = record.findtext('DescriptorUI', '').strip()
                label = record.findtext('DescriptorName/String', '').strip()
                if not re.fullmatch(r'D\d+', did) or not label:
                    raise ValueError('Invalid MeSH descriptor ID or label')
                synonyms, related, scope = [], [], ''
                for concept in record.findall('ConceptList/Concept'):
                    preferred = concept.get('PreferredConceptYN') == 'Y'
                    terms = [t.text.strip() for t in concept.findall('TermList/Term/String') if t.text]
                    if preferred:
                        synonyms.extend(terms)
                        scope = concept.findtext('ScopeNote', '')
                    else:
                        related.extend(terms)
                synonyms = list(dict.fromkeys([label, *synonyms]))
                trees = [t.text for t in record.findall('TreeNumberList/TreeNumber') if t.text]
                connection.execute('INSERT INTO descriptors VALUES (?,?,?,?,?)',
                                   (did, label, scope, json.dumps(synonyms), json.dumps(trees)))
                for term, kind in [(label,'preferred'), *((t,'synonym') for t in synonyms),
                                   *((t,'related') for t in related)]:
                    connection.execute('INSERT OR IGNORE INTO terms VALUES (?,?,?)',
                                       (normalize(term), did, kind))
                count += 1
                record.clear()
        if count == 0:
            raise ValueError('MeSH snapshot contains no descriptors')
        manifest = {'schema_version':1, 'vocabulary':'NLM MeSH descriptors', 'year':year,
                    'source_url':source_url, 'source_file':source.name,
                    'source_sha256':digest.hexdigest(), 'descriptor_count':count,
                    'imported_at':datetime.now(timezone.utc).isoformat(),
                    'terms_url':'https://www.nlm.nih.gov/databases/download/terms_and_conditions.html',
                    'scope':'Descriptor records only; no SCR/qualifier or translated vocabulary',
                    'synonym_policy':'Preferred concept terms only; related concepts not auto-expanded'}
        connection.execute('INSERT INTO metadata VALUES (?,?)', ('manifest',json.dumps(manifest)))
        connection.commit()
        connection.close()
        connection = None
        os.replace(temp, output)
        return manifest
    finally:
        if connection is not None:
            connection.close()
        if temp.exists():
            temp.unlink()


class MeshIndex:
    def __init__(self, path: Path):
        self.path = Path(path).resolve()
        if not self.path.is_file():
            raise FileNotFoundError(f'MeSH index missing: {self.path}; import the official XML first')
        with closing(self._connect()) as connection:
            row = connection.execute("SELECT value FROM metadata WHERE key='manifest'").fetchone()
        if not row:
            raise ValueError('MeSH index has no provenance manifest')
        self.manifest = json.loads(row[0])
        if self.manifest.get('schema_version') != 1:
            raise ValueError('Unsupported MeSH index schema')

    def _connect(self):
        return sqlite3.connect(self.path.as_uri() + '?mode=ro', uri=True)

    def lookup(self, term: str) -> list[dict]:
        with closing(self._connect()) as connection:
            if re.fullmatch(r'D\d+', term.strip()):
                rows = connection.execute("SELECT d.*, 'id' FROM descriptors d WHERE id=?",
                                          (term.strip(),)).fetchall()
            else:
                rows = connection.execute('''SELECT d.*, t.kind FROM terms t
                    JOIN descriptors d ON t.id=d.id WHERE t.term=?
                    ORDER BY CASE t.kind WHEN 'preferred' THEN 0 WHEN 'synonym' THEN 1 ELSE 2 END, d.id''',
                                          (normalize(term),)).fetchall()
        results, seen = [], set()
        for did, label, scope, synonyms, trees, kind in rows:
            if did not in seen:
                seen.add(did)
                results.append({'id':did, 'label':label, 'scope':scope,
                                'synonyms':json.loads(synonyms), 'trees':json.loads(trees),
                                'match_kind':kind, 'url':'https://id.nlm.nih.gov/mesh/'+did})
        return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    download = commands.add_parser('download')
    download.add_argument('--year',type=int,required=True)
    download.add_argument('--directory',type=Path,required=True)
    imp = commands.add_parser('import')
    imp.add_argument('source', type=Path)
    imp.add_argument('--output', type=Path, required=True)
    imp.add_argument('--source-url', required=True)
    imp.add_argument('--year', type=int, required=True)
    lookup = commands.add_parser('lookup')
    lookup.add_argument('term')
    lookup.add_argument('--index', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'download':
        result = download_mesh(args.year,args.directory)
    elif args.command == 'import':
        result = import_mesh(args.source,args.output,source_url=args.source_url,year=args.year)
    else:
        index = MeshIndex(args.index)
        result = {'results':index.lookup(args.term), 'provenance':index.manifest}
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
