"""Project organization is separate from scientific metadata and immutable sources."""
import copy,json,uuid,shutil
from datetime import datetime,timezone
from pathlib import Path
from storage import LOCK
from upgrades import APP_VERSION

def at():return datetime.now(timezone.utc).isoformat()
def catalog(store):
    path=store.root/'management.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'version':1,'revision':0,'projects':{}}
def record(store,pid):
    store.path(pid)
    return catalog(store)['projects'].get(pid,{'state':'active','pinned':False,'kind':'research'})
def write_catalog(store,value):
    from upgrades import atomic
    atomic(store.root/'management.json',value)
def _describe_unlocked(store):
    info=catalog(store);result=[]
    for item in store.list():
        m=info['projects'].get(item['id'],{});item.update(state=m.get('state','active'),pinned=m.get('pinned',False),kind=m.get('kind','research'),lastOpened=m.get('lastOpened'),lastBackupRequested=m.get('lastBackupRequested'),tags=m.get('tags',[]),stateChangedAt=m.get('stateChangedAt'))
        if not item.get('error'):
            p=store.get(item['id']);item.update(description=p['metadata'].get('description',{}).get('value',''),createdAt=p.get('createdAt'),appVersion=p.get('appVersion'),schemaVersion=p.get('projectSchemaVersion',2),lastBackup=p.get('recovery',{}).get('lastBackup'),lastAutosave=p.get('updatedAt'),bytes=store.path(p['id']).stat().st_size+sum(r['bytes'] for r in p['resources']),resourceNames=[r['name'] for r in p['resources']],unknowns=sum(c.get('status')=='Unknown' for t in p['tables'] for c in t['columns']),conflicts=sum(c.get('status')=='Conflicting' for t in p['tables'] for c in t['columns']),standards=p.get('profiles',{}),metadataUnknowns=sum(v.get('status')=='Unknown' for v in p['metadata'].values()),metadataConflicts=sum(v.get('status')=='Conflicting' for v in p['metadata'].values()),assertionConflicts=sum(v.get('status')=='Conflicting' for v in p.get('evidenceAssertions',[])),lastValidation=p.get('recovery',{}).get('lastValidation'),validationStatus=p.get('recovery',{}).get('validationStatus','Not recorded'))
        annotation=store.root/'workspace-state'/(item['id']+'.json')
        if annotation.exists():
            try:item['tags']=json.loads(annotation.read_text(encoding='utf-8')).get('tags',[])
            except (ValueError,OSError):pass
        result.append(item)
    from purge_transactions import pending_cleanup
    return {'revision':info['revision'],'projects':result,'purgeCleanupPending':pending_cleanup(store,info)}
def describe(store):
    with LOCK:return _describe_unlocked(store)

def action(store,payload):
    from upgrades import snapshot
    pid=payload['id'];operation=payload['action'];store.path(pid)
    with LOCK:
        data=catalog(store)
        if payload.get('managementRevision')!=data['revision']:raise ValueError('PROJECT_MANAGEMENT_CONFLICT')
        p=store.get(pid);m=data['projects'].setdefault(pid,{'state':'active','pinned':False,'kind':'research'})
        if operation=='rename':
            name=payload.get('name','').strip()
            if not name or len(name)>200:raise ValueError('PROJECT_NAME_REQUIRED')
            if m['state']!='active':raise ValueError('Restore the project before renaming.')
            if payload.get('projectRevision')!=p.get('revision'):raise ValueError('PROJECT_REVISION_CONFLICT')
            p['metadata']['title']['value']=name;p['audit'].append({'id':str(uuid.uuid4()),'at':at(),'action':'rename project','reason':'Explicit project management action','applicationVersion':APP_VERSION});store.save(p)
        elif operation in ['archive','trash','restore']:
            m['state']={'archive':'archived','trash':'trash','restore':'active'}[operation];m['stateChangedAt']=at()
        elif operation=='pin':m['pinned']=not m.get('pinned',False)
        elif operation=='backup-request':m['lastBackupRequested']=at()
        elif operation=='open':
            if m['state']!='active':raise ValueError('Restore the project before editing.')
            m['lastOpened']=at()
        elif operation=='kind':
            if payload.get('kind') not in ['research','tutorial','example']:raise ValueError('Invalid project kind.')
            m['kind']=payload['kind']
        elif operation=='duplicate':
            n=copy.deepcopy(p);n['id']=str(uuid.uuid4());n['revision']=0;n['metadata']['title']['value']+=' — copy';n['audit'].append({'id':str(uuid.uuid4()),'at':at(),'action':'fork project','sourceProjectId':pid,'reason':'Explicit fork; source retained.','applicationVersion':APP_VERSION});saved=store.save(n);data['projects'][saved['id']]={'state':'active','pinned':False,'kind':'research'};data.setdefault('history',[]).append({'id':str(uuid.uuid4()),'projectId':saved['id'],'sourceProjectId':pid,'at':at(),'action':'duplicate project','applicationVersion':APP_VERSION});data['revision']+=1;write_catalog(store,data);return {'project':saved,'managementRevision':data['revision']}
        elif operation=='snapshot':
            if m['state']!='active':raise ValueError('Restore the project before creating a snapshot.')
            if payload.get('projectRevision')!=p.get('revision'):raise ValueError('PROJECT_REVISION_CONFLICT')
            snapshot(store,p,payload.get('name','Project checkpoint'))
        else:raise ValueError('Unsupported project action.')
        data.setdefault('history',[]).append({'id':str(uuid.uuid4()),'projectId':pid,'at':at(),'action':operation,'applicationVersion':APP_VERSION});data['revision']+=1;write_catalog(store,data);return describe(store)

def deletion_preview(store,pid):
    store.path(pid);p=store.get(pid)
    return {'id':pid,'managementRevision':catalog(store)['revision'],'projectRevision':p['revision'],'title':p['metadata']['title']['value'],'backupRecorded':bool(record(store,pid).get('lastBackupRequested') or p.get('recovery',{}).get('lastBackup')),'files':['project manifest','previous manifest','pending write fragments','drafts and draft generations','snapshots','migration copies'],'originals':'Shared content-addressed originals are retained. Exported files outside this workspace are never touched.'}

def deletion_paths(store,pid):
    return [store.path(pid),store.path(pid).with_suffix('.previous.json'),store.path(pid).with_suffix('.pending'),store.path(pid).with_suffix('.previous.pending'),store.root/'drafts'/(pid+'.json'),store.root/'drafts'/(pid+'.pending'),store.root/'workspace-state'/(pid+'.json'),store.root/'workspace-state'/(pid+'.pending')]+[store.root/folder/pid for folder in ['snapshots','migrations','draft-history']]

def permanently_delete(store,payload):
    with LOCK:
        pid=payload['id'];data=catalog(store)
        if payload.get('managementRevision')!=data['revision'] or record(store,pid)['state']!='trash':raise ValueError('Only the current Trash state can be deleted.')
        preview=deletion_preview(store,pid)
        if payload.get('projectRevision')!=preview['projectRevision'] or payload.get('confirm')!=pid:raise ValueError('Review the current deletion inventory and explicitly confirm this project ID.')
        from purge_transactions import purge
        result=purge(store,[{'id':pid,'projectRevision':preview['projectRevision']}]);return dict(describe(store),**result)



def trash_preview(store):
    with LOCK:
        data=catalog(store);projects=[deletion_preview(store,p['id']) for p in describe(store)['projects'] if p['state']=='trash']
        return {'managementRevision':data['revision'],'projects':projects,'confirmation':'DELETE '+str(len(projects))+' PROJECTS','originals':'Shared originals and external exported files are retained.'}

def empty_trash(store,payload):
    with LOCK:
        preview=trash_preview(store)
        if payload.get('managementRevision')!=preview['managementRevision'] or payload.get('confirm')!=preview['confirmation']:raise ValueError('TRASH_REVIEW_CONFLICT')
        supplied=payload.get('projects')
        expected=[{'id':p['id'],'projectRevision':p['projectRevision']} for p in preview['projects']]
        if supplied!=expected:raise ValueError('TRASH_INVENTORY_CONFLICT')
        from purge_transactions import purge
        result=purge(store,expected) if expected else {'deleted':[],'purgeCleanupPending':False}
        return dict(describe(store),**result)
