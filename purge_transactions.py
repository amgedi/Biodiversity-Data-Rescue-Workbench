"""Reviewed purge transactions: stage locally, commit management once, recover interruptions."""
import json,os,re,shutil,uuid
from pathlib import Path
from storage import LOCK
from upgrades import atomic,now,APP_VERSION

def _bounded(path,root):
 for ancestor in [path,*path.parents]:
  if ancestor==root:break
  if ancestor.is_symlink() or ancestor.is_junction():raise ValueError('Deletion path escapes workspace.')
 if path.is_symlink() or path.is_junction() or not path.resolve().is_relative_to(root):raise ValueError('Deletion path escapes workspace.')
 if path.is_dir():
  for parent,dirs,files in os.walk(path,followlinks=False):
   for name in dirs+files:
    child=Path(parent)/name
    if child.is_symlink() or child.is_junction() or not child.resolve().is_relative_to(root):raise ValueError('Deletion path escapes workspace.')

def _write(path,journal,root):
 _bounded(path,root);_bounded(path.with_suffix('.pending'),root);atomic(path,journal)

def _locations(store,journal):
 from management import deletion_paths
 root=store.root.resolve();tx=journal.get('id','')
 if not isinstance(tx,str) or not re.fullmatch(r'[a-f0-9-]{36}',tx):raise ValueError('Invalid purge recovery record.')
 allowed={path.relative_to(store.root).as_posix() for p in journal.get('projects',[]) for path in deletion_paths(store,p['id'])}
 staging=root/'purge-staging'/tx;_bounded(staging,root)
 locations=[]
 for rel in journal.get('paths',[]):
  if rel not in allowed:raise ValueError('Invalid purge recovery inventory.')
  source=root/rel;dest=staging/rel;_bounded(source,root);_bounded(dest,root);locations.append((source,dest))
 return root,staging,locations

def _rollback(store,journal,path):
 root,staging,locations=_locations(store,journal)
 for source,dest in reversed(locations):
  if not source.exists() and not dest.exists():raise ValueError('Purge recovery needs review: a recorded file is unavailable. No recovery success is claimed.')
  if dest.exists():
   if source.exists():raise ValueError('Purge recovery needs review: both saved copies exist. Nothing was overwritten.')
   source.parent.mkdir(parents=True,exist_ok=True);os.replace(dest,source)
 journal['phase']='rolled-back';journal['recoveredAt']=now();_write(path,journal,store.root.resolve())
 if staging.exists():_bounded(staging,root);shutil.rmtree(staging)

def _cleanup(store,journal,path):
 root,staging,_=_locations(store,journal)
 try:
  if staging.exists():_bounded(staging,root);shutil.rmtree(staging)
 except (OSError,ValueError):
  journal['phase']='cleanup-pending';_write(path,journal,store.root.resolve());return False
 journal['phase']='complete';journal['completedAt']=now();_write(path,journal,store.root.resolve());return True

def recover(store):
 from management import catalog
 with LOCK:
  folder=store.root/'purge-journal';out=[]
  if not folder.exists():return out
  _bounded(folder,store.root.resolve())
  for path in sorted(folder.glob('*.json')):
   _bounded(path,store.root.resolve());journal=json.loads(path.read_text(encoding='utf-8'))
   if journal.get('phase') in ['complete','rolled-back']:continue
   committed=any(event.get('purgeTransactionId')==journal.get('id') for event in catalog(store).get('history',[]))
   if committed:out.append({'id':journal['id'],'result':'completed' if _cleanup(store,journal,path) else 'cleanup-pending'})
   else:_rollback(store,journal,path);out.append({'id':journal['id'],'result':'restored'})
  return out

def purge(store,projects):
 from management import catalog,write_catalog,deletion_paths
 with LOCK:
  recover(store);data=catalog(store);root=store.root.resolve();tx=str(uuid.uuid4());staging=root/'purge-staging'/tx
  paths=[path for p in projects for path in deletion_paths(store,p['id']) if path.exists() or path.is_symlink() or path.is_junction()]
  for path in paths:_bounded(path,root)
  path=root/'purge-journal'/(tx+'.json');_bounded(path,root);_bounded(staging,root)
  journal={'version':1,'id':tx,'createdAt':now(),'phase':'staging','projects':projects,'paths':[p.relative_to(root).as_posix() for p in paths],'applicationVersion':APP_VERSION}
  _write(path,journal,store.root.resolve())
  try:
   for source,dest in _locations(store,journal)[2]:dest.parent.mkdir(parents=True,exist_ok=True);os.replace(source,dest)
   for p in projects:
    data['projects'].pop(p['id'],None);data.setdefault('history',[]).append({'id':str(uuid.uuid4()),'projectId':p['id'],'at':now(),'action':'permanently delete project','purgeTransactionId':tx,'applicationVersion':APP_VERSION})
   data['revision']+=1;write_catalog(store,data)
  except Exception:
   # The management commit is authoritative even if an OS error followed its replacement.
   if not any(e.get('purgeTransactionId')==tx for e in catalog(store).get('history',[])):
    _rollback(store,journal,path);raise
  journal['phase']='committed'
  try:
   _write(path,journal,store.root.resolve());pending=not _cleanup(store,journal,path)
  except OSError:pending=True
  return {'deleted':[p['id'] for p in projects],'purgeCleanupPending':pending}

def pending_cleanup(store,data=None):
 folder=store.root/'purge-journal'
 if not folder.exists():return 0
 _bounded(folder,store.root.resolve())
 if data is None:
  from management import catalog
  data=catalog(store)
 committed={e.get('purgeTransactionId') for e in data.get('history',[]) if e.get('purgeTransactionId')}
 return sum(journal.get('phase') not in ['complete','rolled-back'] and journal.get('id') in committed for journal in [json.loads(path.read_text(encoding='utf-8')) for path in folder.glob('*.json')])
