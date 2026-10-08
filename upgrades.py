"""Explicit schema migration, content-addressed checkpoints and recovery records."""
import base64, copy, hashlib, io, json, os, re, uuid, zipfile
from datetime import datetime, timezone
from pathlib import PurePosixPath
from storage import LOCK, validate
from migration_registry import Migration, MigrationRegistry
APP_VERSION='0.7.0-dev.0'
SCHEMA_VERSION=3
def now():return datetime.now(timezone.utc).isoformat()
def atomic(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    pending=path.with_suffix('.pending')
    with pending.open('w',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False);f.flush();os.fsync(f.fileno())
    os.replace(pending,path)
def migration_preview(p):
    if not isinstance(p,dict):raise ValueError('Unsupported project manifest or identifier.')
    version=p.get('projectSchemaVersion',2)
    steps=MIGRATIONS.path(version);validate(p)
    return {'from':version,'to':SCHEMA_VERSION,'needed':bool(steps),'changes':[step.description for step in steps],'steps':[{'id':step.identity,'from':step.source,'to':step.target} for step in steps],'sources':[{k:r[k] for k in ('id','name','sha256')} for r in p['resources']]}

def schema_2_to_3(n,context):
    at=context['at'];n['projectSchemaVersion']=3;n['appVersion']=APP_VERSION
    n.setdefault('migrationHistory',[]).append({'from':2,'to':3,'id':'schema-2-to-3-evidence-recovery','at':at,'applicationVersion':APP_VERSION,'sourceChecksums':{r['id']:r['sha256'] for r in n['resources']}})
    n.setdefault('evidenceAssertions',[]);n.setdefault('recovery',{});n['updatedAt']=at
    n['audit'].append({'id':str(uuid.uuid4()),'at':at,'action':'schema migration 2 → 3','reason':'Additive migration. Original pre-migration backup retained on disk. No scientific interpretations changed.','applicationVersion':APP_VERSION})

MIGRATIONS=MigrationRegistry([Migration(2,3,'schema-2-to-3-evidence-recovery','Add explicit schema identity, migration history, evidence assertions and recovery metadata. Existing unknown fields, sources, relationships and audit events remain intact.',schema_2_to_3)],SCHEMA_VERSION)
def migrate(p):
    migration_preview(p);n=MIGRATIONS.migrate(p,{'at':now()})
    validate(n);assert [(r['id'],r['sha256'],r['base64']) for r in n['resources']]==[(r['id'],r['sha256'],r['base64']) for r in p['resources']]
    return n
def migrate_saved(store,p):
    with LOCK:
        preview=migration_preview(p)
        if not preview['needed']:return p
        backup=store.root/'migrations'/p['id']/f'schema-{preview["from"]}-revision-{p.get("revision",0)}.json'
        original=store.get(p['id']) if store.path(p['id']).exists() else p
        if original.get('revision',0)!=p.get('revision',0):raise ValueError('Migration conflict: reopen the latest committed project.')
        if not backup.exists():atomic(backup,original)
        return store.save(migrate(p))
def snapshot(store,p,label):
    if not isinstance(label,str) or not label.strip() or len(label)>120:raise ValueError('A checkpoint name of 1–120 characters is required.')
    current=store.get(p['id'])
    if p.get('revision')!=current.get('revision'):raise ValueError('Snapshot requires the latest committed revision.')
    # Only disk-verified originals may be referenced without embedded bytes.
    if not all(r['diskMatches'] for r in store.verify(current)):raise ValueError('Verify or recover originals before creating a snapshot.')
    sid=str(uuid.uuid4());at=now();compact=copy.deepcopy(current)
    for r in compact['resources']:r.pop('base64',None)
    # Audit snapshots may contain full tables; kept deliberately until delta history lands.
    atomic(store.root/'snapshots'/p['id']/(sid+'.json'),{'id':sid,'name':label.strip(),'at':at,'project':compact})
    current['audit'].append({'id':str(uuid.uuid4()),'at':at,'action':'create snapshot','reason':label.strip(),'snapshotId':sid,'applicationVersion':APP_VERSION})
    saved=store.save(current)
    return {'snapshotId':sid,'project':saved}
def snapshots(store,pid):
    store.path(pid);folder=store.root/'snapshots'/pid
    return [{k:v[k] for k in ('id','name','at')} for f in sorted(folder.glob('*.json')) for v in [json.loads(f.read_text(encoding='utf-8'))]]
def open_snapshot(store,pid,sid):
    store.path(pid);store.path(sid);record=json.loads((store.root/'snapshots'/pid/(sid+'.json')).read_text(encoding='utf-8'));p=record['project']
    for r in p['resources']:
        data=(store.objects/r['sha256']).read_bytes()
        if hashlib.sha256(data).hexdigest()!=r['sha256']:raise ValueError('Snapshot original integrity mismatch.')
        r['base64']=base64.b64encode(data).decode()
    validate(p);return p
def compare(a,b):
    def table_map(p):return {t['id']:t for t in p['tables']}
    old,new=table_map(a),table_map(b);results=[]
    from collections import Counter
    for id in old.keys()|new.keys():
        x,y=old.get(id),new.get(id)
        if not x or not y:results.append({'table':(x or y)['name'],'status':'added' if y else 'removed'});continue
        left,right=Counter(tuple(r) for r in x['rows']),Counter(tuple(r) for r in y['rows'])
        results.append({'table':y['name'],'addedRows':sum((right-left).values()),'removedRows':sum((left-right).values()),'addedColumns':[h for h in y['headers'] if h not in x['headers']],'removedColumns':[h for h in x['headers'] if h not in y['headers']],'dictionaryChanged':x['columns']!=y['columns'],'note':'Literal row multiset comparison, not semantic equivalence or key-aligned changes.'})
    return {'tables':results,'metadataChanged':a['metadata']!=b['metadata'],'relationshipsChanged':a['relationships']!=b['relationships'],'sourceHashesChanged':{r['id']:r['sha256'] for r in a['resources']}!={r['id']:r['sha256'] for r in b['resources']}}
def recovery_status(store,pid):
    path=store.path(pid);p=store.get(pid)
    draftpath=store.root/'drafts'/(pid+'.json');draft=json.loads(draftpath.read_text(encoding='utf-8')) if draftpath.exists() else None
    draft_revision=draft.get('draftRevision',0) if draft else 0
    if draft and not draft.get('forms'):draft=None
    return {'projectId':pid,'revision':p['revision'],'draftRevision':draft_revision,'lastAutosave':p.get('updatedAt'),'manifestBytes':path.stat().st_size,'originalBytes':sum(r['bytes'] for r in p['resources']),'previousRevisionAvailable':path.with_suffix('.previous.json').exists(),'incompleteWrite':path.with_suffix('.pending').exists(),'draft':draft,'draftStale':bool(draft and draft.get('baseRevision')!=p['revision']),'directory':str(store.root),'sourceIntegrity':store.verify(p)}
def save_draft(store,payload):
    from management import record
    with LOCK:
        pid=payload['projectId'];store.path(pid);current=store.get(pid);forms=payload.get('forms',{})
        if record(store,pid)['state']!='active':raise ValueError('PROJECT_NOT_ACTIVE')
        if not isinstance(forms,dict) or len(json.dumps(forms))>2*1024*1024:raise ValueError('Recovery draft exceeds 2 MiB.')
        path=store.root/'drafts'/(pid+'.json');prior=json.loads(path.read_text(encoding='utf-8')) if path.exists() else None
        revision=prior.get('draftRevision',0) if prior else 0
        if payload.get('draftRevision',0)!=revision:raise ValueError('DRAFT_REVISION_CONFLICT: earlier draft retained; review before merging.')
        if prior and prior.get('forms') and payload['baseRevision']<prior['baseRevision']:raise ValueError('DRAFT_BASE_CONFLICT')
        if not forms and prior and prior.get('forms') and not (payload.get('clear') is True and payload.get('reason')):raise ValueError('DRAFT_CLEAR_REQUIRES_EXPLICIT_ACTION')
        # Visiting a different form must not discard unreviewed forms from an earlier visit.
        if prior and not payload.get('clear'):forms={**prior.get('forms',{}),**forms}
        if len(json.dumps(forms))>2*1024*1024:raise ValueError('Merged recovery draft exceeds 2 MiB; previous draft retained.')
        if prior:atomic(store.root/'draft-history'/pid/(str(uuid.uuid4())+'.json'),prior)
        value={'projectId':pid,'baseRevision':payload['baseRevision'],'draftRevision':revision+1,'clientId':payload.get('clientId','legacy'),'savedAt':now(),'forms':forms}
        atomic(path,value)
        return {'saved':True,'draftRevision':revision+1,'stale':payload['baseRevision']!=current['revision']}
def safe_archive(data):
    z=zipfile.ZipFile(io.BytesIO(data));entries=z.infolist()
    if len(entries)>1000 or sum(i.file_size for i in entries)>100*1024*1024:raise ValueError('Archive expansion exceeds 100 MiB / 1,000 entries.')
    seen=set()
    for i in entries:
        name=i.orig_filename;path=PurePosixPath(name)
        if not name or chr(92) in name or path.is_absolute() or '..' in path.parts or ':' in name or name in seen:raise ValueError('Unsafe or duplicate archive member path.')
        if (i.external_attr>>16)&0o170000==0o120000:raise ValueError('Archive symlinks are unsupported.')
        if i.file_size>20*1024*1024 or i.file_size/max(i.compress_size,1)>200:raise ValueError('Archive member expansion limit exceeded.')
        seen.add(name)
    return z
def verify_package(data):
    with safe_archive(data) as z:
        if 'checksums.sha256' not in z.namelist():raise ValueError('No checksums.sha256 manifest found.')
        records=[];listed=set()
        for line in z.read('checksums.sha256').decode('utf-8').splitlines():
            digest,name=line.split('  ',1)
            if not re.fullmatch('[a-f0-9]{64}',digest) or name in listed or name not in z.namelist():raise ValueError('Invalid checksum entry.')
            actual=hashlib.sha256(z.read(name)).hexdigest();listed.add(name);records.append({'path':name,'matches':actual==digest})
        extra=set(z.namelist())-listed-{'checksums.sha256'}
        return {'valid':all(r['matches'] for r in records) and not extra,'entries':records,'unlisted':sorted(extra),'note':'Integrity against this manifest, not authenticity of its author.'}
