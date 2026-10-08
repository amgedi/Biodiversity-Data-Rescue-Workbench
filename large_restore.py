"""Verify and replay an open preservation package into a separate investigation.

No archive paths are extracted. Original parsing and existing editing operations
must reproduce the entire packaged working table before publication.
"""
import base64,csv,hashlib,io,json,os,shutil,tempfile,uuid,zipfile
from contextlib import closing,contextmanager
from pathlib import Path
from large_data import LargeStore
from large_preservation import defaults,initialize,STATES,TYPES,CONTEXT,text
from large_repair import preview,apply,scan
from tools.verify_large_package import verify
from upgrades import atomic,now,APP_VERSION

def records(archive,name):
 with archive.open(name) as source,io.TextIOWrapper(source,encoding='utf-8') as lines:
  archive._biorescue_streams.append(lines)
  while line:=lines.readline(4*1024*1024+1):
   if len(line)>4*1024*1024:raise ValueError('LARGE_RESTORE_HISTORY')
   item=json.loads(line)
   if not isinstance(item,dict):raise ValueError('LARGE_RESTORE_HISTORY')
   yield item

@contextmanager
def replay_archive(path):
 with zipfile.ZipFile(path) as archive:
  archive._biorescue_streams=[]
  try:yield archive
  finally:
   # A failed history replay can retain its generator in an exception traceback.
   # Close member handles before deleting owned temporary files on Windows.
   for stream in archive._biorescue_streams:stream.close()

def definition(value,status):
 if not isinstance(value,dict) or value.get('version')!=1 or set(value.get('context',{}))!=set(CONTEXT):raise ValueError('LARGE_RESTORE_METADATA')
 fields=value.get('fields')
 if not isinstance(fields,list) or len(fields)!=len(status['headers']):raise ValueError('LARGE_RESTORE_METADATA')
 for key,item in value['context'].items():
  if not isinstance(item,dict) or item.get('status') not in STATES:raise ValueError('LARGE_RESTORE_METADATA')
  for name,limit in [('value',4000),('rationale',2000),('reviewer',200)]:text(item.get(name),limit)
  if item['status']=='Confirmed' and (not item['reviewer'].strip() or not item['value'].strip()):raise ValueError('LARGE_RESTORE_METADATA')
 for column,item in enumerate(fields):
  if not isinstance(item,dict) or item.get('column')!=column or type(item.get('column')) is not int or item.get('name')!=status['headers'][column] or item.get('originalName')!=status['originalHeaders'][column] or item.get('status') not in STATES or item.get('dataType') not in TYPES:raise ValueError('LARGE_RESTORE_METADATA')
  for name,limit in [('description',4000),('unit',200),('rationale',2000),('reviewer',200)]:text(item.get(name),limit)
  if item['status']=='Confirmed' and (not item['reviewer'].strip() or not item['description'].strip()):raise ValueError('LARGE_RESTORE_METADATA')
 links=value.get('relationships',[])
 if not isinstance(links,list) or len(links)>100:raise ValueError('LARGE_RESTORE_METADATA')
 for link in links:
  if not isinstance(link,dict) or link.get('status') not in STATES or not isinstance(link.get('report'),dict) or not isinstance(link.get('id'),str):raise ValueError('LARGE_RESTORE_METADATA')
  text(link.get('reviewer'),200);text(link.get('rationale'),2000)
  if link['status']=='Confirmed' and not link['reviewer'].strip():raise ValueError('LARGE_RESTORE_METADATA')
 return value

class Recovery:
 def __init__(self,path):
  self.temporary=tempfile.TemporaryDirectory(prefix='biorescue-recovery-');self.store=LargeStore(self.temporary.name);self.closed=False
  try:self.report=self.replay(Path(path))
  except Exception as error:
   self.close()
   if isinstance(error,(ValueError,OSError,KeyError,TypeError)):raise
   raise ValueError('LARGE_RESTORE_INVALID') from error
 def close(self):
  if not self.closed:self.closed=True;self.temporary.cleanup()
 def replay(self,path):
  integrity=verify(path,max_bytes=1024**3);digest=hashlib.sha256()
  with path.open('rb') as package_file:
   while block:=package_file.read(65536):digest.update(block)
  with replay_archive(path) as archive:
   document=json.loads(archive.read('metadata/metadata.json'));source=document['source'];previous_restoration=document.get('restoration');ancestor=previous_restoration;depth=0
   while ancestor is not None:
    if not isinstance(ancestor,dict) or depth>=32:raise ValueError('LARGE_RESTORE_LIMIT')
    depth+=1;ancestor=ancestor.get('previousRestoration')
   job=self.store.create(source['name'],source['bytes'],source['encoding'],source['delimiter']);self.id=job['id'];offset=0
   with archive.open('sources/original.bin') as original:
    while chunk:=original.read(1024*1024):self.store.chunk(self.id,offset,base64.b64encode(chunk).decode());offset+=len(chunk)
   status=self.store.start(self.id,background=False)
   if status['status']!='ready' or status['rows']!=document['rows']:raise ValueError('LARGE_RESTORE_SOURCE')
   definition(document['metadata'],status)
   batches={}
   for group in records(archive,'audit/batches.jsonl'):
    first,last,count=group.get('firstSequence'),group.get('lastSequence'),group.get('changedCells')
    if any(type(v) is not int for v in [first,last,count]) or not 1<=count<=50000 or last-first+1!=count or first<1 or first in batches or any(first<=old['lastSequence'] and last>=old_first for old_first,old in batches.items()):raise ValueError('LARGE_RESTORE_HISTORY')
    batches[first]=group
   iterator=iter(records(archive,'audit/edits.jsonl'));pending=next(iterator,None);sequence=0;revision=0;used=set()
   while pending is not None:
    start=sequence+1;action=pending.get('action');reason=pending.get('rationale');text(reason,4000 if action=='batch-trim' else 2000)
    if action=='batch-trim':
     group=batches.get(start)
     if not group:raise ValueError('LARGE_RESTORE_HISTORY')
     entries=[pending]+[next(iterator,None) for _ in range(group['changedCells']-1)]
     if any(not isinstance(e,dict) or e.get('action')!='batch-trim' or e.get('rationale')!=reason for e in entries):raise ValueError('LARGE_RESTORE_HISTORY')
     rationale=json.loads(reason)
     if rationale.get('operation')!='trim-whitespace' or rationale.get('previewDigest')!=group.get('previewDigest'):raise ValueError('LARGE_RESTORE_HISTORY')
     columns=sorted({e['column'] for e in entries});payload={'id':self.id,'columns':columns,'operation':'trim-whitespace'}
     with closing(self.store.edit_connection(self.id)) as conn:
      checked=scan(conn,group.get('digestInvestigationId',document['investigationId']),columns,revision)
     if checked['digest']!=group['previewDigest'] or checked['changedCells']!=len(entries):raise ValueError('LARGE_RESTORE_HISTORY')
     apply(self.store,{**payload,**preview(self.store,payload),'reason':rationale['reason'],'reviewer':rationale['reviewer']});used.add(start)
    elif action in ['edit','undo','redo','batch-undo','batch-redo']:
     before_sequence=sequence;operation=action.removeprefix('batch-')
     if operation=='edit':self.store.edit(self.id,revision,row=pending.get('sourceRecord'),column=pending.get('column'),expected=pending.get('before'),value=pending.get('after'),reason=reason)
     else:self.store.edit(self.id,revision,action=operation,reason=reason)
     with closing(self.store.edit_connection(self.id)) as conn:count=conn.execute('SELECT count(*) FROM edit_history WHERE seq>?',(before_sequence,)).fetchone()[0]
     entries=[pending]+[next(iterator,None) for _ in range(count-1)]
    else:raise ValueError('LARGE_RESTORE_HISTORY')
    with closing(self.store.edit_connection(self.id)) as conn:
     generated=conn.execute('SELECT seq,row_id,col,before,after,action,reference FROM edit_history WHERE seq>=? ORDER BY seq',(start,)).fetchall()
     if len(generated)!=len(entries):raise ValueError('LARGE_RESTORE_HISTORY')
     for row,event in zip(generated,entries):
      if not isinstance(event,dict) or any(type(event.get(k)) is not int for k in ['sequence','sourceRecord','column']) or list(row)!=[event.get(k) for k in ['sequence','sourceRecord','column','before','after','action','reference']]:raise ValueError('LARGE_RESTORE_HISTORY')
      text(event.get('at'),100);text(event.get('rationale'),4000 if event['action']=='batch-trim' else 2000);conn.execute('UPDATE edit_history SET reason=?,at=? WHERE seq=?',(event['rationale'],event['at'],row[0]))
     conn.commit()
    sequence+=len(entries);revision+=1;pending=next(iterator,None)
   if set(batches)!=used or revision!=document['workingRevision']:raise ValueError('LARGE_RESTORE_HISTORY')
   with closing(self.store.edit_connection(self.id)) as conn:
    initialize(conn);previous=defaults(status);metarevision=0;last_working=0
    for event in records(archive,'audit/metadata.jsonl'):
     metarevision+=1;working=event.get('workingRevision')
     if type(event.get('sequence')) is not int or event['sequence']!=metarevision or type(working) is not int or not last_working<=working<=revision or event.get('before')!=previous:raise ValueError('LARGE_RESTORE_METADATA')
     after=definition(event.get('after'),status)
     for key,limit in [('reviewer',200),('rationale',2000),('at',100)]:text(event.get(key),limit)
     if not event['rationale'].strip() or after==previous:raise ValueError('LARGE_RESTORE_METADATA')
     conn.execute('INSERT INTO large_metadata_history VALUES (?,?,?,?,?,?,?)',(metarevision,event['at'],event['reviewer'],event['rationale'],json.dumps(previous,ensure_ascii=False),json.dumps(after,ensure_ascii=False),working));previous=after;last_working=working
    if metarevision!=document['metadataRevision'] or previous!=document['metadata']:raise ValueError('LARGE_RESTORE_METADATA')
    if metarevision:conn.execute('INSERT INTO large_metadata VALUES (1,?,?)',(metarevision,json.dumps(previous,ensure_ascii=False)))
    for first,group in batches.items():
     conn.execute('UPDATE large_batch_groups SET digest=? WHERE reference=?',(group['previewDigest'],first));conn.execute('INSERT INTO large_batch_origins VALUES (?,?)',(first,group.get('digestInvestigationId',document['investigationId'])))
    with archive.open('data/working.csv') as source,io.TextIOWrapper(source,encoding='utf-8',newline='') as stream:
     reader=csv.reader(stream,strict=True)
     if next(reader,None)!=status['headers']:raise ValueError('LARGE_RESTORE_SOURCE')
     for (raw,) in conn.execute('SELECT data FROM rows ORDER BY id'):
      if next(reader,None)!=json.loads(raw):raise ValueError('LARGE_RESTORE_REPLAY')
     if next(reader,None) is not None:raise ValueError('LARGE_RESTORE_REPLAY')
    conn.commit();conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
   return {'packageSha256':digest.hexdigest(),'sourceInvestigationId':document['investigationId'],'sourceName':document['source']['name'] or 'Recovered source','rows':status['rows'],'fields':len(status['headers']),'workingRevision':revision,'metadataRevision':metarevision,'historyCells':sequence,'verifiedOriginalReplay':True,'scientificConformance':False,'packageFiles':integrity['files'],'previousRestoration':previous_restoration}
 def publish(self,target,reviewer,reason):
  text(reviewer,200);text(reason,2000)
  if not reviewer.strip() or not reason.strip():raise ValueError('LARGE_RESTORE_REVIEW')
  if self.closed:raise ValueError('LARGE_RESTORE_EXPIRED')
  with target.lock:
   final=target.folder(self.id)
   if final.exists():raise ValueError('LARGE_RESTORE_EXISTS')
   target.root.mkdir(parents=True,exist_ok=True);staging=target.root/('.restore-'+self.id+'.pending')
   try:
    shutil.copytree(self.store.folder(self.id),staging)
    status=self.store.status(self.id);status['restoration']={**self.report,'reviewer':reviewer.strip(),'rationale':reason.strip(),'at':now(),'softwareVersion':APP_VERSION,'policy':'Recovered as a separate investigation. Historical relationship identifiers retain their original scope; they are not automatically relinked.'};atomic(staging/'status.json',status)
    os.rename(staging,final);target.jobs[self.id]={**status,'cancel':False}
   except Exception:
    if staging.exists() and staging.resolve().parent==target.root.resolve():shutil.rmtree(staging)
    raise
  self.close();return dict(status)
