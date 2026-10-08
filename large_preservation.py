"""Audited dictionary/context and consistent open-format large-investigation packages."""
import copy,csv,hashlib,io,json,sqlite3,tempfile,zipfile
from contextlib import closing
from upgrades import APP_VERSION,now
CONTEXT=('title','purpose','methods','samplingProtocol','limitations','license')
STATES={'Unknown','Inferred','Confirmed','Conflicting','Not Applicable'}
TYPES={'string','integer','number','boolean','date'}
def initialize(conn):
 conn.execute('CREATE TABLE IF NOT EXISTS large_metadata (singleton INTEGER PRIMARY KEY CHECK(singleton=1),revision INTEGER NOT NULL,payload TEXT NOT NULL)')
 conn.execute('CREATE TABLE IF NOT EXISTS large_metadata_history (sequence INTEGER PRIMARY KEY,at TEXT,reviewer TEXT,reason TEXT,before TEXT,after TEXT,working_revision INTEGER)')
 conn.commit()
def defaults(status):
 return {'version':1,'context':{key:{'value':'','status':'Unknown','rationale':'','reviewer':''} for key in CONTEXT},'fields':[{'column':index,'name':name,'originalName':status['originalHeaders'][index],'description':'','unit':'','dataType':'string','status':'Unknown','rationale':'','reviewer':''} for index,name in enumerate(status['headers'])]}
def read_snapshot(conn,status):
 row=conn.execute('SELECT revision,payload FROM large_metadata WHERE singleton=1').fetchone()
 return {'metadataRevision':row[0] if row else 0,'workingRevision':conn.execute("SELECT value FROM edit_meta WHERE key='revision'").fetchone()[0],'metadata':json.loads(row[1]) if row else defaults(status)}
def metadata(store,id):
 with closing(store.edit_connection(id)) as conn:
  initialize(conn);conn.execute('BEGIN');return read_snapshot(conn,store.status(id))
def text(value,maximum=4000):
 if not isinstance(value,str) or len(value)>maximum:raise ValueError('LARGE_METADATA_INVALID')
 return value
def save_metadata(store,payload):
 id=payload['id'];reason=text(payload.get('reason'),2000).strip();reviewer=text(payload.get('reviewer',''),200).strip()
 if not reason:raise ValueError('LARGE_METADATA_REASON')
 changes=payload.get('changes')
 if not isinstance(changes,list) or not 1<=len(changes)<=250:raise ValueError('LARGE_METADATA_INVALID')
 with store.lock,closing(store.edit_connection(id)) as conn:
  initialize(conn)
  try:
   conn.execute('BEGIN IMMEDIATE');before=read_snapshot(conn,store.status(id));next=copy.deepcopy(before['metadata']);seen=set()
   if type(payload.get('metadataRevision')) is not int or type(payload.get('workingRevision')) is not int or (payload['metadataRevision'],payload['workingRevision'])!=(before['metadataRevision'],before['workingRevision']):raise ValueError('LARGE_METADATA_STALE')
   for change in changes:
    if not isinstance(change,dict):raise ValueError('LARGE_METADATA_INVALID')
    kind=change.get('kind');key=change.get('key') if kind=='context' else change.get('column')
    if not isinstance(kind,str) or kind not in ('context','field') or (kind=='context' and not isinstance(key,str)) or (kind=='field' and type(key) is not int):raise ValueError('LARGE_METADATA_INVALID')
    identity=(kind,key)
    if identity in seen:raise ValueError('LARGE_METADATA_INVALID')
    seen.add(identity);state=change.get('status')
    if not isinstance(state,str) or state not in STATES:raise ValueError('LARGE_METADATA_INVALID')
    if state=='Confirmed' and not reviewer:raise ValueError('LARGE_METADATA_REVIEWER')
    if kind=='context':
     if key not in CONTEXT or set(change)-{'kind','key','value','status'}:raise ValueError('LARGE_METADATA_INVALID')
     value=text(change.get('value'))
     if state=='Confirmed' and not value.strip():raise ValueError('LARGE_METADATA_INVALID')
     next['context'][key]={'value':value,'status':state,'rationale':reason,'reviewer':reviewer}
    elif kind=='field':
     if not 0<=key<len(next['fields']) or set(change)-{'kind','column','description','unit','dataType','status'} or not isinstance(change.get('dataType'),str) or change['dataType'] not in TYPES:raise ValueError('LARGE_METADATA_INVALID')
     definition=next['fields'][key];description=text(change.get('description'));unit=text(change.get('unit'),200)
     if state=='Confirmed' and not description.strip():raise ValueError('LARGE_METADATA_INVALID')
     definition.update(description=description,unit=unit,dataType=change['dataType'],status=state,rationale=reason,reviewer=reviewer)
    else:raise ValueError('LARGE_METADATA_INVALID')
   if next==before['metadata']:raise ValueError('LARGE_METADATA_UNCHANGED')
   serialized=json.dumps(next,ensure_ascii=False)
   if len(serialized.encode())>2*1024*1024:raise ValueError('LARGE_METADATA_INVALID')
   conn.execute('INSERT INTO large_metadata VALUES (1,?,?) ON CONFLICT(singleton) DO UPDATE SET revision=excluded.revision,payload=excluded.payload',(before['metadataRevision']+1,serialized))
   conn.execute('INSERT INTO large_metadata_history(at,reviewer,reason,before,after,working_revision) VALUES (?,?,?,?,?,?)',(now(),reviewer,reason,json.dumps(before['metadata'],ensure_ascii=False),serialized,before['workingRevision']))
   conn.commit();return metadata(store,id)
  except Exception:conn.rollback();raise
def package(store,id):
 status=store.status(id);output=tempfile.TemporaryFile('w+b')
 try:
  with closing(store.edit_connection(id)) as conn:
   initialize(conn);conn.execute('BEGIN');snapshot=read_snapshot(conn,status);members=[]
   with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,allowZip64=True) as archive:
    def write(name,chunks):
     digest=hashlib.sha256();size=0
     with archive.open(name,'w',force_zip64=True) as target:
      for chunk in chunks:target.write(chunk);digest.update(chunk);size+=len(chunk)
     item={'path':name,'bytes':size,'sha256':digest.hexdigest()};members.append(item);return item
    def raw():
     with (store.folder(id)/'original.bin').open('rb') as source:
      while chunk:=source.read(65536):yield chunk
    source=write('sources/original.bin',raw())
    if source['sha256']!=status['sha256'] or source['bytes']!=status['expectedBytes']:raise ValueError('LARGE_SOURCE_INTEGRITY')
    def csv_chunks(rows):
     buffer=io.StringIO(newline='');writer=csv.writer(buffer,lineterminator='\n')
     for row in rows:
      writer.writerow(row)
      if buffer.tell()>65536:yield buffer.getvalue().encode('utf-8');buffer.seek(0);buffer.truncate()
     if buffer.tell():yield buffer.getvalue().encode('utf-8')
    def working():
     yield status['headers']
     for (record,) in conn.execute('SELECT data FROM rows ORDER BY id'):yield json.loads(record)
    write('data/working.csv',csv_chunks(working()))
    dictionary=snapshot['metadata']['fields'];keys=['column','name','originalName','description','unit','dataType','status','rationale','reviewer']
    write('metadata/dictionary.csv',csv_chunks([keys]+[[field[key] for key in keys] for field in dictionary]))
    document={**snapshot,'investigationId':id,'source':{'name':status['name'],'sha256':status['sha256'],'bytes':status['expectedBytes'],'encoding':status['encoding'],'delimiter':status['delimiter']},'rows':status['rows'],'software':{'name':'Biodiversity Data Rescue Workbench','version':APP_VERSION},'restoration':status.get('restoration'),'interpretation':'Declared metadata only; values remain literal. No standards conformance is implied.'}
    write('metadata/metadata.json',[json.dumps(document,ensure_ascii=False,indent=2).encode('utf-8')])
    def history():
     for seq,row,col,before,after,action,reference,reason,at in conn.execute('SELECT * FROM edit_history ORDER BY seq'):
      yield (json.dumps({'sequence':seq,'sourceRecord':row,'column':col,'before':before,'after':after,'action':action,'reference':reference,'rationale':reason,'at':at},ensure_ascii=False)+'\n').encode()
    write('audit/edits.jsonl',history())
    def batches():
     from large_repair import batch_records
     for group in batch_records(conn,id):yield (json.dumps(group)+'\n').encode()
    write('audit/batches.jsonl',batches())
    def metadata_history():
     for seq,at,reviewer,reason,before,after,revision in conn.execute('SELECT * FROM large_metadata_history ORDER BY sequence'):
      yield (json.dumps({'sequence':seq,'at':at,'reviewer':reviewer,'rationale':reason,'before':json.loads(before),'after':json.loads(after),'workingRevision':revision},ensure_ascii=False)+'\n').encode()
    write('audit/metadata.jsonl',metadata_history())
    write('README.md',[b'# Large-investigation preservation package\n\nOpen UTF-8 CSV, JSON and JSON Lines. Original bytes are in sources/original.bin; the original name and reading conventions are retained in metadata/metadata.json. Field definitions may remain Unknown, Inferred or Conflicting. This package does not assert normative standards conformance. Working data, metadata and histories share one SQLite read snapshot. Import-time profiles are not recalculated. Keep the package private if it contains sensitive data.\n'])
    manifest={'packageVersion':1,'createdAt':now(),'workingRevision':snapshot['workingRevision'],'metadataRevision':snapshot['metadataRevision'],'members':members}
    write('manifest.json',[json.dumps(manifest,ensure_ascii=False,indent=2).encode()])
    archive.writestr('checksums.sha256',''.join(item['sha256']+'  '+item['path']+'\n' for item in members))
  output.seek(0);return output
 except Exception:output.close();raise
