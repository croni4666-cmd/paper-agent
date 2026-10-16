"""Topic-routed official pages, kept separate from academic paper records."""
from __future__ import annotations

from html.parser import HTMLParser
import ipaddress
import json
from pathlib import Path
from urllib.parse import urljoin, urlparse

from .mesh_lexicon import normalize


def default_registry() -> dict:
    return json.loads((Path(__file__).parent/'data/institution_sources.json').read_text(encoding='utf-8'))


def _validate_url(url: str, allowed_hosts: list[str]):
    p=urlparse(url)
    host=(p.hostname or '').lower()
    if p.scheme!='https' or not host or host not in allowed_hosts or p.username or p.password or p.port not in (None,443):
        raise ValueError('Institution URLs must be HTTPS on explicitly allowed official hosts')
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if host=='localhost' or host.endswith(('.localhost','.local')):
            raise ValueError('Local institution URLs are not accepted')
    else:
        raise ValueError('IP-literal institution URLs are not accepted')


def route_sources(spec: dict, registry: dict | None = None, *, limit: int = 3) -> list[dict]:
    if limit<0:
        raise ValueError('Source budget must be nonnegative')
    registry=registry if registry is not None else default_registry()
    if registry.get('schema_version')!=1 or not isinstance(registry.get('sources'),list):
        raise ValueError('Invalid institutional source registry')
    topics={normalize(t) for t in spec.get('topics',[]) if isinstance(t,str)}
    routed=[]
    for entry in registry['sources']:
        if not entry.get('enabled',True) or entry.get('domain')!=spec.get('domain','medicine'):
            continue
        _validate_url(entry['url'],entry.get('allowed_hosts',[]))
        overlap=sorted(topics & {normalize(t) for t in entry.get('topics',[])})
        if topics and not overlap:
            continue
        terms=[g.get('terms',[''])[0] for g in spec.get('groups',[]) if g.get('terms')]
        routed.append({**entry,'topic_overlap':overlap,
                       'suggested_site_query':'site:'+urlparse(entry['url']).hostname+' '+' '.join(terms),
                       'routing_note':'Topic routing only; institution identity is not quality certification'})
    routed.sort(key=lambda e:(-len(e['topic_overlap']),e.get('order',100),e['id']))
    return routed[:limit]


class _VisibleText(HTMLParser):
    def __init__(self):
        super().__init__();self.parts=[];self.title=[];self.hidden=0;self.in_title=False
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style','nav','header','footer','noscript','svg'):
            self.hidden+=1
        if tag=='title':self.in_title=True
    def handle_endtag(self,tag):
        if tag in ('script','style','nav','header','footer','noscript','svg'):
            self.hidden=max(0,self.hidden-1)
        if tag=='title':self.in_title=False
    def handle_data(self,data):
        if self.in_title:self.title.append(data)
        if not self.hidden and data.strip():self.parts.append(data.strip())


def inspect_page(source: dict, body: bytes, status: int, content_type: str) -> dict:
    base={'source_id':source['id'],'name':source['name'],'url':source['url'],
          'role':source['role'],'document_type':source['document_type'],
          'candidate_only':True,'quality_certified':False,'http_status':status}
    if status!=200:
        return {**base,'status':'blocked' if status in (401,403,429) else 'error',
                'access':'blocked','access_note':'Official page request did not succeed'}
    if 'html' not in content_type.lower():
        return {**base,'status':'metadata_only','access':'metadata_only',
                'access_note':'Only HTML extraction is supported; this response was not inspected'}
    text=body.decode('utf-8',errors='replace')
    parser=_VisibleText();parser.feed(text)
    visible=' '.join(parser.parts)
    title=' '.join(parser.title).strip()
    markers=('checking your browser','verify you are human','enable javascript and cookies','just a moment...')
    if any(m in (title+' '+visible[:1500]).casefold() for m in markers) or len(visible)<150:
        return {**base,'title':title,'status':'blocked','access':'blocked',
                'access_note':'Challenge, empty, or unusable page; not evidence text'}
    access='metadata_only' if source.get('entry_kind')=='listing' else 'partial_text'
    return {**base,'title':title,'status':'ok','access':access,'location':'Visible HTML text, truncated excerpt',
            'text_excerpt':visible[:4000],'extracted_characters':len(visible),
            'access_note':'Listing only, not individual study evidence' if access=='metadata_only' else
                          'Visible page text inspected; tables, PDFs and appendices not verified'}


def fetch_source(source: dict, *, timeout: float = 20, cache_dir: Path | None = None) -> dict:
    import requests
    from ._http import get_proxy_dict
    url=source['url']
    try:
        for _ in range(4):
            _validate_url(url,source['allowed_hosts'])
            with requests.get(url,stream=True,allow_redirects=False,proxies=get_proxy_dict(),
                              timeout=(min(10,timeout),timeout),
                              headers={'User-Agent':'paper-agent official-source-reader/1'}) as response:
                if response.status_code in (301,302,303,307,308):
                    url=urljoin(url,response.headers.get('Location',''))
                    continue
                chunks,size=[],0
                for chunk in response.iter_content(65536):
                    size+=len(chunk)
                    if size>2*1024*1024:
                        raise ValueError('Institution page exceeds 2 MiB extraction budget')
                    chunks.append(chunk)
                body=b''.join(chunks)
                result=inspect_page(source,body,response.status_code,response.headers.get('Content-Type',''))
                result['retrieved_url']=url
                if cache_dir is not None:
                    # IDs are registry-controlled, not article titles or URLs.
                    safe_id=''.join(c for c in source['id'] if c.isalnum() or c in '-_')
                    path=Path(cache_dir);path.mkdir(parents=True,exist_ok=True)
                    (path/(safe_id+'.html')).write_bytes(body)
                return result
        raise ValueError('Institution redirect budget exhausted')
    except Exception as exc:
        return {'source_id':source['id'],'name':source['name'],'url':source['url'],
                'status':'error','access':'blocked','candidate_only':True,
                'access_note':type(exc).__name__+'; page not inspected'}
