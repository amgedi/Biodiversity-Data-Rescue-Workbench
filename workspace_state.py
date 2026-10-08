"""Local working annotations, separate from scientific manifests and exports."""
import copy,json
from storage import LOCK
from upgrades import atomic,now
STATES={'Needs review','Reviewed','Accepted','Rejected','Intentionally unresolved'}
def path(store,pid):
 store.get(pid)
 return store.root/'workspace-state'/(pid+'.json')
def read(store,pid):
 with LOCK:
  target=path(store,pid)
  return json.loads(target.read_text(encoding='utf-8')) if target.exists() else {'version':1,'projectId':pid,'revision':0,'reviews':{},'history':[],'notes':[],'bookmarks':[],'tags':[],'savedViews':[],'resume':{}}
def save(store,payload):
 with LOCK:
  pid=payload['projectId'];old=read(store,pid)
  from management import record
  if record(store,pid)['state']!='active':raise ValueError('Restore the project before changing working annotations.')
  if type(payload.get('revision')) is not int or payload['revision']!=old['revision']:raise ValueError('WORKSPACE_STATE_STALE: reload the working annotations before saving.')
  action=payload.get('action');next=copy.deepcopy(old)
  if action in {'review','batch-review'}:
   decisions=payload.get('decisions') if action=='batch-review' else [payload]
   if not isinstance(decisions,list) or not 1<=len(decisions)<=100:raise ValueError('Invalid review annotation.')
   seen=set();prepared=[]
   for decision in decisions:
    if not isinstance(decision,dict):raise ValueError('Invalid review annotation.')
    key=decision.get('key');state=decision.get('state');reason=decision.get('reason','');reviewer=decision.get('reviewer','')
    if not isinstance(key,str) or not key or len(key)>240 or key in seen or state not in STATES or not isinstance(reason,str) or len(reason)>4000 or not isinstance(reviewer,str) or len(reviewer)>200:raise ValueError('Invalid review annotation.')
    if state in {'Accepted','Rejected','Intentionally unresolved'} and not reason.strip():raise ValueError('Explain this review decision; unknown remains a valid answer.')
    seen.add(key);prepared.append({'at':now(),'key':key,'state':state,'reason':reason.strip(),'reviewer':reviewer.strip()})
   for decision in prepared:next['reviews'][decision['key']]=decision;next['history'].append(decision)
  elif action in {'notes','bookmarks','tags','savedViews','resume'}:
   value=payload.get('value')
   if action=='resume':
    if not isinstance(value,dict) or any(k not in {'view','tableId','field','issue','filter'} for k in value) or not all(isinstance(v,str) and len(v)<=240 for v in value.values()):raise ValueError('Invalid resume context.')
   elif not isinstance(value,list) or len(value)>1000:raise ValueError('Working annotation lists are limited to 1,000 entries.')
   if action=='tags' and any(not isinstance(v,str) or not v.strip() or len(v)>80 for v in value):raise ValueError('Invalid project tags.')
   if action in {'notes','bookmarks','savedViews'} and any(not isinstance(v,dict) or not isinstance(v.get('id'),str) for v in value):raise ValueError('Working annotation entries require stable IDs.')
   if action in {'notes','bookmarks','savedViews'}:
    ids=set()
    for entry in value:
     key=entry['id']
     if not key or len(key)>240 or key in ids or any(not isinstance(v,str) for v in entry.values()):raise ValueError('Working annotation entries require stable IDs.')
     ids.add(key)
     if action=='notes' and (not isinstance(entry.get('text'),str) or len(entry['text'])>4000 or not entry['text'].strip()):raise ValueError('Invalid review annotation.')
     if action=='savedViews' and ('name' in entry and (not entry['name'].strip() or len(entry['name'])>200)):raise ValueError('Invalid resume context.')
     if action=='savedViews' and entry.get('view','Review queue') not in {'Review queue','Translate & standardize'}:raise ValueError('Invalid resume context.')
     if action=='savedViews' and entry.get('filter') not in {'All','Important','Data','Documentation','Dates','Units','Geography','Taxonomy','Relationships','Standards','Privacy','Resolved'}:raise ValueError('Invalid resume context.')
     if action=='bookmarks' and (not (entry.get('issue') or entry.get('view')) or len(entry.get('issue',''))>240):raise ValueError('Invalid resume context.')
   next[action]=value
  else:raise ValueError('Unsupported working annotation action.')
  next['revision']+=1;next['updatedAt']=now()
  if len(json.dumps(next,ensure_ascii=False).encode())>1024*1024:raise ValueError('Working annotations exceed the 1 MiB limit; export a local copy before adding more.')
  atomic(path(store,pid),next);return next
