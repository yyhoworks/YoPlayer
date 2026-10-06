"""Display-only library membership; unknown sources never erase media state."""
import posixpath
import re
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET


def hidden(library, preferences):
    key=library['id']
    return bool(preferences.get('items',{}).get(key,{}).get('hidden') or
                ('selected' in preferences and key not in preferences['selected']))


def directory_identity(path):
    if not isinstance(path,str) or not path:return None
    if re.match(r'^[A-Za-z]:[\\/]',path):
        return ('windows','',posixpath.normpath(path.replace('\\','/')).casefold())
    parsed=urlsplit(path)
    scheme=parsed.scheme.lower()
    if scheme not in ('','file','smb','nfs'):return None
    authority=(parsed.hostname or '').casefold()
    normalized=posixpath.normpath(unquote(parsed.path).replace('\\','/'))
    if scheme=='smb':normalized=normalized.casefold()
    return scheme,authority,normalized


def inside(media, directory):
    item,base=directory_identity(media),directory_identity(directory)
    return bool(item and base and item[:2]==base[:2] and
                (item[2]==base[2] or item[2].startswith(base[2].rstrip('/')+'/')))


def native_filter(text):
    """Translate the supported native node rules exactly, never approximate."""
    node=ET.fromstring(text)
    kind=node.findtext('content')
    if node.tag not in ('node','smartplaylist') or kind not in ('movies','tvshows'):
        return None
    if node.tag=='node' and node.get('type')!='filter':return None
    fields={'tag','path','title','year','genre'} | ({'set'} if kind=='movies' else set())
    operators={'is','isnot','contains','doesnotcontain','startswith','endswith','greaterthan','lessthan','after','before'}
    rules=[]
    for child in node:
        if child.tag in ('label','content','match','order','icon'):continue
        if child.tag!='rule' or child.get('field') not in fields or child.get('operator') not in operators:return None
        values=[v.text or '' for v in child.findall('value')] or [child.text or '']
        rules.append({'field':child.get('field'),'operator':child.get('operator'),'value':values})
    if not rules:return None
    match=node.findtext('match','all')
    if match not in ('all','one'):return None
    return kind, rules[0] if len(rules)==1 else {'and' if match=='all' else 'or':rules}


class Membership:
    def __init__(self, libraries, preferences, lookup):
        self.entries=[]
        if not any(hidden(l,preferences) for l in libraries):return
        for library in libraries:
            path=library['path']
            membership=lookup(library) if directory_identity(path) is None else ('directory',path)
            if membership is not None:self.entries.append((hidden(library,preferences),membership))

    def visible(self,row):
        invisible=False
        for hide,(kind,members) in self.entries:
            if kind=='directory':matches=inside(row.get('file',''),members)
            elif kind=='movies':matches=row.get('kind','movie')=='movie' and row.get('movieid') in members
            else:matches=row.get('kind') in ('episode','tvshow') and row.get('tvshowid') in members
            if matches:
                if not hide:return True  # A reliable visible membership wins.
                invisible=True
        return not invisible  # Unknown membership remains visible.
