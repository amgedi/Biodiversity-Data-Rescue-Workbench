"""Local filesystem persistence: immutable content-addressed sources and atomic manifests."""
import base64
import json
import os
import re
import threading
from pathlib import Path
from rescue import source_bytes, sha

LOCK=threading.RLock()
ID=re.compile(r'^[a-zA-Z0-9_-]{1,80}$')


def validate(project):
    if not isinstance(project,dict) or project.get('version')!=2 or project.get('projectSchemaVersion',2)>3 or not ID.fullmatch(project.get('id','')):
        raise ValueError('Unsupported project manifest or identifier.')
    for key in ['creator','contributors']:
        party=project.get('metadata',{}).get(key,{})
        if 'partyType' in party and party['partyType'] not in ['Unknown','Person','Organization']:raise ValueError('Invalid typed party metadata.')
        identifier=party.get('identifier','')
        if not isinstance(identifier,str) or (identifier and (len(identifier)>2000 or not re.fullmatch(r'[A-Za-z][A-Za-z0-9+.-]*:[^\s]+',identifier))):raise ValueError('Party identifiers must be absolute URIs without whitespace.')
    resources=project.get('resources',[]);tables=project.get('tables',[])

    if not isinstance(resources,list) or not isinstance(tables,list) or len(resources)>500 or len(tables)>100:
        raise ValueError('Project resource/table limits exceeded.')
    resource_ids=set()
    for resource in resources:
        data=source_bytes(resource, allow_empty=True)
        if sha(data)!=resource.get('sha256'):raise ValueError(f'Original checksum mismatch: {resource.get("name")}')
        if resource.get('bytes')!=len(data):raise ValueError('Original byte-size mismatch.')
        if not ID.fullmatch(resource.get('id','')) or resource['id'] in resource_ids:raise ValueError('Duplicate or invalid resource ID.')
        resource_ids.add(resource['id'])
    names=set()
    for table in tables:
        if table.get('id') in names or not ID.fullmatch(table.get('id','')) or table.get('resourceId') not in resource_ids:raise ValueError('Invalid table identifier/source.')
        names.add(table['id']);headers=table.get('headers',[]);rows=table.get('rows',[])
        if not headers or len(headers)>250 or len(set(headers))!=len(headers) or any(not isinstance(h,str) or not h.strip() for h in headers):raise ValueError('Invalid table headers.')
        if len(rows)>100000 or any(not isinstance(r,list) or len(r)!=len(headers) or any(not isinstance(v,str) for v in r) for r in rows):raise ValueError('Invalid working rows.')
        if len(table.get('columns',[]))!=len(headers):raise ValueError('Field dictionary length mismatch.')
    return project


class Store:
    def __init__(self, root):
        self.root=Path(root);self.manifests=self.root/'projects';self.objects=self.root/'originals'

    def path(self,id):
        if not ID.fullmatch(id):raise ValueError('Invalid project identifier.')
        return self.manifests/(id+'.json')

    def list(self):
        with LOCK:return self._list_unlocked()

    def _list_unlocked(self):
        if not self.manifests.exists():return []
        result=[]
        for path in self.manifests.glob('*.json'):
            if path.name.endswith('.previous.json'):continue
            try:
                p=json.loads(path.read_text(encoding='utf-8'));result.append({'id':p['id'],'title':p['metadata']['title']['value'],'updatedAt':p['updatedAt'],'tables':len(p['tables']),'resources':len(p['resources']),'revision':p.get('revision',0)})
            except (ValueError,KeyError,OSError):result.append({'id':path.stem,'title':'Damaged manifest — recovery required','error':True})
        return result

    def get(self,id,previous=False):
        with LOCK:return self._get_unlocked(id,previous)

    def _get_unlocked(self,id,previous=False):
        path=self.path(id)
        if previous:path=path.with_suffix('.previous.json')
        try:return json.loads(path.read_text(encoding='utf-8'))
        except (ValueError,OSError) as exc:raise ValueError('Project unavailable. Try the previous saved revision or a portable backup.') from exc

    def save(self,p):
        validate(p)
        with LOCK:
            path=self.path(p['id']);old=self.get(p['id']) if path.exists() else None
            if old:
                from management import record
                if record(self,p['id'])['state']!='active':raise ValueError('PROJECT_NOT_ACTIVE: restore archived or trashed projects before saving.')
            if old and p.get('revision',0)!=old.get('revision',0):raise ValueError('Save conflict: another window saved a newer revision. Download your backup, then reopen the project before merging changes.')
            if old:
                if old.get('projectSchemaVersion',2)>=3:
                    if p.get('projectSchemaVersion',2)<3:raise ValueError('Schema downgrade is not permitted; preserve a separate legacy backup.')
                    if p.get('audit',[])[:len(old.get('audit',[]))]!=old.get('audit',[]):raise ValueError('Historical audit entries are immutable; append a corrective event.')
                    if p.get('evidenceAssertions',[])[:len(old.get('evidenceAssertions',[]))]!=old.get('evidenceAssertions',[]):raise ValueError('Evidence assertions are immutable; append a superseding interpretation.')
                incoming={r['id']:r for r in p['resources']}
                for original in old['resources']:
                    current=incoming.get(original['id'])
                    if not current or any(current.get(k)!=original.get(k) for k in ('sha256','base64','name','bytes','importedAt','format','archaeology','adapterVersion')):raise ValueError('Preserved source resources cannot be overwritten or removed.')
                old_tables={t['id']:t for t in old['tables']}
                for table in p['tables']:
                    original=old_tables.get(table['id'])
                    if original and any(table.get(k)!=original.get(k) for k in ('originalTable','resourceId','sheet','parsing')):raise ValueError('Import baselines and parsing provenance are immutable. Re-import as a new table to change parsing.')
            self.manifests.mkdir(parents=True,exist_ok=True);self.objects.mkdir(parents=True,exist_ok=True)
            for resource in p['resources']:
                data=source_bytes(resource, allow_empty=True);obj=self.objects/resource['sha256']
                if obj.exists():
                    if sha(obj.read_bytes())!=resource['sha256']:raise ValueError('Archived original checksum mismatch. Restore from a verified backup; existing evidence will not be overwritten.')
                else:
                    with obj.open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
            p=json.loads(json.dumps(p));p['updatedAt']=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat();p['revision']=(old.get('revision',0) if old else 0)+1
            temp=path.with_suffix('.pending')
            with temp.open('w',encoding='utf-8') as f:json.dump(p,f,ensure_ascii=False);f.flush();os.fsync(f.fileno())
            if old:
                previous=path.with_suffix('.previous.json');backup=path.with_suffix('.previous.pending')
                with backup.open('wb') as f:f.write(path.read_bytes());f.flush();os.fsync(f.fileno())
                os.replace(backup,previous)
            os.replace(temp,path)
            return p

    def verify(self,p):
        result=[]
        for resource in p['resources']:
            retained=source_bytes(resource, allow_empty=True);actual=sha(retained);path=self.objects/resource['sha256']
            disk=path.read_bytes() if path.exists() else None;archived=sha(disk) if disk is not None else None
            result.append({'resourceId':resource['id'],'name':resource['name'],'expected':resource['sha256'],'expectedBytes':resource['bytes'],'backupBytes':len(retained),'diskBytes':len(disk) if disk is not None else None,'backupByteLengthMatches':len(retained)==resource['bytes'],'diskByteLengthMatches':disk is not None and len(disk)==resource['bytes'],'backupMatches':actual==resource['sha256'],'diskMatches':archived==resource['sha256'],'archived':path.exists()})
        return result
