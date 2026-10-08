"""Bounded, reviewed whitespace-only large-table repair, with atomic grouped undo."""
import hashlib,json,re
from contextlib import closing
from upgrades import now
MAX_CHANGES=50000

def initialize(conn):
 conn.execute('CREATE TABLE IF NOT EXISTS large_batch_groups (reference INTEGER PRIMARY KEY,last_sequence INTEGER,count INTEGER,digest TEXT)');conn.execute('CREATE TABLE IF NOT EXISTS large_batch_origins (reference INTEGER PRIMARY KEY,digest_scope TEXT NOT NULL)');conn.commit()

def batch_records(conn,id):
 if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='large_batch_groups'").fetchone():return
 origins=bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='large_batch_origins'").fetchone())
 for first,last,count,digest in conn.execute('SELECT * FROM large_batch_groups ORDER BY reference'):
  origin=conn.execute('SELECT digest_scope FROM large_batch_origins WHERE reference=?',(first,)).fetchone() if origins else None
  yield {'firstSequence':first,'lastSequence':last,'changedCells':count,'previewDigest':digest,'digestInvestigationId':origin[0] if origin else id}

def columns(store,payload):
 selected=payload.get('columns');headers=store.status(payload['id'])['headers']
 if not isinstance(selected,list) or not 1<=len(selected)<=100 or any(type(column) is not int or not 0<=column<len(headers) for column in selected) or len(set(selected))!=len(selected):raise ValueError('LARGE_BATCH_COLUMNS')
 if payload.get('operation')!='trim-whitespace':raise ValueError('LARGE_BATCH_OPERATION')
 return sorted(selected)

def scan(conn,id,selected,revision):
 digest=hashlib.sha256(json.dumps([id,selected,revision,'trim-whitespace']).encode());count=0;examples=[];records=0
 for row,raw in conn.execute('SELECT id,data FROM rows ORDER BY id'):
  records+=1;values=json.loads(raw)
  for column in selected:
   before=values[column];after=before.strip()
   if before==after:continue
   count+=1;digest.update(json.dumps([row,column,before,after],ensure_ascii=False,separators=(',',':')).encode())
   if len(examples)<10:examples.append({'sourceRecord':row,'column':column,'before':before,'after':after})
 return {'workingRevision':revision,'columns':selected,'changedCells':count,'recordsScanned':records,'examples':examples,'digest':digest.hexdigest(),'canApply':0<count<=MAX_CHANGES,'limit':MAX_CHANGES}

def preview(store,payload):
 selected=columns(store,payload)
 with closing(store.edit_connection(payload['id'])) as conn:
  conn.execute('BEGIN');revision=conn.execute("SELECT value FROM edit_meta WHERE key='revision'").fetchone()[0]
  return scan(conn,payload['id'],selected,revision)

def apply(store,payload):
 selected=columns(store,payload);reason=payload.get('reason');reviewer=payload.get('reviewer','')
 if not isinstance(reason,str) or not reason.strip() or len(reason)>2000 or not isinstance(reviewer,str) or len(reviewer)>200:raise ValueError('LARGE_BATCH_REASON')
 if type(payload.get('workingRevision')) is not int or not isinstance(payload.get('digest'),str) or not re.fullmatch('[0-9a-f]{64}',payload['digest']):raise ValueError('LARGE_BATCH_PREVIEW')
 id=payload['id']
 with store.lock,closing(store.edit_connection(id)) as conn:
  initialize(conn)
  try:
   conn.execute('BEGIN IMMEDIATE');revision,cursor=(conn.execute('SELECT value FROM edit_meta WHERE key=?',(key,)).fetchone()[0] for key in ['revision','cursor'])
   if payload['workingRevision']!=revision:raise ValueError('LARGE_BATCH_STALE')
   proposal=scan(conn,id,selected,revision)
   if proposal['digest']!=payload['digest']:raise ValueError('LARGE_BATCH_PREVIEW')
   if not proposal['canApply']:raise ValueError('LARGE_BATCH_LIMIT')
   first=last=None;at=now();rationale=json.dumps({'reviewer':reviewer.strip(),'reason':reason.strip(),'operation':'trim-whitespace','previewDigest':proposal['digest']},ensure_ascii=False)
   for row,raw in conn.execute('SELECT id,data FROM rows ORDER BY id'):
    values=json.loads(raw);changed=False
    for column in selected:
     before=values[column];after=before.strip()
     if before==after:continue
     changed=True;values[column]=after;last=conn.execute('INSERT INTO edit_history(row_id,col,before,after,action,reference,reason,at) VALUES (?,?,?,?,?,?,?,?)',(row,column,before,after,'batch-trim',None,rationale,at)).lastrowid
     if first is None:first=last
    if changed:conn.execute('UPDATE rows SET data=? WHERE id=?',(json.dumps(values,ensure_ascii=False),row))
   conn.execute('INSERT INTO large_batch_groups VALUES (?,?,?,?)',(first,last,proposal['changedCells'],proposal['digest']));conn.execute('DELETE FROM edit_stack WHERE position>?',(cursor,));conn.execute('INSERT INTO edit_stack VALUES (?,?)',(cursor+1,first));conn.execute("UPDATE edit_meta SET value=? WHERE key='cursor'",(cursor+1,));conn.execute("UPDATE edit_meta SET value=? WHERE key='revision'",(revision+1,));conn.commit()
  except Exception:conn.rollback();raise
 return {**store.edit_state(id),'changedCells':proposal['changedCells']}

def undo_group(conn,reference,action,reason):
 exists=conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='large_batch_groups'").fetchone()
 group=conn.execute('SELECT last_sequence,count FROM large_batch_groups WHERE reference=?',(reference,)).fetchone() if exists else None
 if not group:return False
 at=now()
 for seq,row,column,old,new in conn.execute('SELECT seq,row_id,col,before,after FROM edit_history WHERE seq>=? AND seq<=? ORDER BY seq',(reference,group[0])):
  record=conn.execute('SELECT data FROM rows WHERE id=?',(row,)).fetchone()
  if record is None:raise ValueError('LARGE_BATCH_HISTORY')
  values=json.loads(record[0]);before=values[column];after=old if action=='undo' else new
  if before!=(new if action=='undo' else old):raise ValueError('LARGE_BATCH_HISTORY')
  values[column]=after;conn.execute('UPDATE rows SET data=? WHERE id=?',(json.dumps(values,ensure_ascii=False),row));conn.execute('INSERT INTO edit_history(row_id,col,before,after,action,reference,reason,at) VALUES (?,?,?,?,?,?,?,?)',(row,column,before,after,'batch-'+action,seq,reason.strip(),at))
 return True
