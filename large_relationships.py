"""Literal composite-key investigation across independent large datasets.

Uses a file-backed temporary index, bounded examples, and paired read snapshots.
No keys are cast, trimmed, inferred, or silently substituted.
"""
import copy,csv,hashlib,io,json,sqlite3,tempfile,uuid,zipfile
from contextlib import closing,contextmanager
from pathlib import Path
from large_preservation import initialize,read_snapshot,STATES,text
from upgrades import now,APP_VERSION

def declaration(store,payload):
 child=store.status(payload['id']);parent=store.status(payload.get('parentId',''));left=payload.get('childColumns');right=payload.get('parentColumns')
 if child['status']!='ready' or parent['status']!='ready':raise ValueError('LARGE_LINK_NOT_READY')
 for selected,status in [(left,child),(right,parent)]:
  if not isinstance(selected,list) or not 1<=len(selected)<=5 or any(type(index) is not int or not 0<=index<len(status['headers']) for index in selected) or len(set(selected))!=len(selected):raise ValueError('LARGE_LINK_COLUMNS')
 if len(left)!=len(right):raise ValueError('LARGE_LINK_COLUMNS')
 return child,parent,left,right

@contextmanager
def paired_snapshots(store,id,parent_id):
 with closing(store.edit_connection(id)) as child,closing(store.edit_connection(parent_id)) as parent:
  initialize(child);initialize(parent)
  with store.lock:
   child.execute('BEGIN');parent.execute('BEGIN');left=read_snapshot(child,store.status(id));right=read_snapshot(parent,store.status(parent_id))
  yield child,parent,left,right

def key(values,selected):
 if not isinstance(values,list) or any(not isinstance(value,str) for value in values):raise ValueError('LARGE_LINK_WORKING_SHAPE')
 parts=[values[column] for column in selected]
 return None if any(part=='' for part in parts) else json.dumps(parts,ensure_ascii=False,separators=(',',':'))

@contextmanager
def index(parent,selected,width):
 with tempfile.TemporaryDirectory(prefix='biorescue-key-index-') as temporary,closing(sqlite3.connect(Path(temporary)/'keys.sqlite')) as keys:
  keys.execute('CREATE TABLE keys (key TEXT PRIMARY KEY,occurrences INTEGER,source_record INTEGER,record TEXT)');missing=0;records=0;fingerprint=hashlib.sha256()
  for source_record,raw in parent.execute('SELECT id,data FROM rows ORDER BY id'):
   records+=1;values=json.loads(raw)
   if source_record!=records or not isinstance(values,list) or len(values)!=width:raise ValueError('LARGE_LINK_WORKING_SHAPE')
   fingerprint.update(str(source_record).encode()+b'\0'+json.dumps(values,ensure_ascii=False).encode()+b'\0');literal=key(values,selected)
   if literal is None:missing+=1;continue
   keys.execute('INSERT INTO keys VALUES (?,1,?,?) ON CONFLICT(key) DO UPDATE SET occurrences=occurrences+1,record=NULL',(literal,source_record,raw))
  keys.commit();yield keys,{'parentRecords':records,'missingParentKeys':missing,'duplicateParentKeys':keys.execute('SELECT count(*) FROM keys WHERE occurrences>1').fetchone()[0],'duplicateParentRecords':keys.execute('SELECT coalesce(sum(occurrences),0) FROM keys WHERE occurrences>1').fetchone()[0]},fingerprint.hexdigest()

def inspect(store,payload):
 child_status,parent_status,child_columns,parent_columns=declaration(store,payload);id=payload['id'];parent_id=payload['parentId']
 with paired_snapshots(store,id,parent_id) as (child,parent,left,right),index(parent,parent_columns,len(parent_status['headers'])) as (keys,counts,parent_fingerprint):
  examples={kind:[] for kind in ['missing','unmatched','conflicting','linked']};counts.update(childRecords=0,missingChildKeys=0,unmatchedChildKeys=0,conflictingChildKeys=0,linkedChildRecords=0)
  child_fingerprint=hashlib.sha256()
  for row,raw in child.execute('SELECT id,data FROM rows ORDER BY id'):
   values=json.loads(raw);counts['childRecords']+=1
   if row!=counts['childRecords'] or not isinstance(values,list) or len(values)!=len(child_status['headers']):raise ValueError('LARGE_LINK_WORKING_SHAPE')
   child_fingerprint.update(str(row).encode()+b'\0'+json.dumps(values,ensure_ascii=False).encode()+b'\0');literal=key(values,child_columns);match=keys.execute('SELECT occurrences,source_record FROM keys WHERE key=?',(literal,)).fetchone() if literal is not None else None
   outcome='missing' if literal is None else 'unmatched' if match is None else 'conflicting' if match[0]!=1 else 'linked';counts[{'missing':'missingChildKeys','unmatched':'unmatchedChildKeys','conflicting':'conflictingChildKeys','linked':'linkedChildRecords'}[outcome]]+=1
   if len(examples[outcome])<10:
    parts=json.loads(literal) if literal is not None else [json.loads(raw)[column] for column in child_columns];examples[outcome].append({'childSourceRecord':row,'parentSourceRecord':match[1] if outcome=='linked' else None,'literalKey':[part[:500] for part in parts],'keyPreviewTruncated':any(len(part)>500 for part in parts)})
  if counts['childRecords']!=child_status['rows'] or counts['parentRecords']!=parent_status['rows']:raise ValueError('LARGE_LINK_WORKING_SHAPE')
  report={'version':1,'childId':id,'parentId':parent_id,'childColumns':child_columns,'parentColumns':parent_columns,'childNames':[child_status['headers'][column] for column in child_columns],'parentNames':[parent_status['headers'][column] for column in parent_columns],'childSourceHash':child_status['sha256'],'parentSourceHash':parent_status['sha256'],'childWorkingFingerprint':child_fingerprint.hexdigest(),'parentWorkingFingerprint':parent_fingerprint,'childWorkingRevision':left['workingRevision'],'parentWorkingRevision':right['workingRevision'],'childMetadataRevision':left['metadataRevision'],'parentMetadataRevision':right['metadataRevision'],'counts':counts,'examples':examples,'policy':'Exact literal composite keys. Only empty strings mean an absent key. NA, zero, leading zeros and whitespace remain literal. Duplicate parent keys are conflicts; no parent is chosen. No scientific relationship is inferred. Examples are limited to ten per outcome and 500 characters per key component; matching uses complete values.'}
  report['digest']=hashlib.sha256(json.dumps(report,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest();return report

def save(store,payload):
 reason=text(payload.get('reason'),2000).strip();reviewer=text(payload.get('reviewer',''),200).strip();state=payload.get('status')
 if not reason:raise ValueError('LARGE_LINK_REASON')
 if not isinstance(state,str) or state not in STATES or state=='Confirmed' and not reviewer:raise ValueError('LARGE_LINK_REVIEW')
 if not isinstance(payload.get('digest'),str):raise ValueError('LARGE_LINK_STALE')
 with store.lock:
  report=inspect(store,payload)
  if report['digest']!=payload['digest']:raise ValueError('LARGE_LINK_STALE')
  with closing(store.edit_connection(payload['id'])) as conn:
   initialize(conn)
   try:
    conn.execute('BEGIN IMMEDIATE');before=read_snapshot(conn,store.status(payload['id']))
    if before['workingRevision']!=report['childWorkingRevision'] or before['metadataRevision']!=report['childMetadataRevision']:raise ValueError('LARGE_LINK_STALE')
    next=copy.deepcopy(before['metadata']);links=next.setdefault('relationships',[]);relationship_id=payload.get('relationshipId')
    if relationship_id is not None and (not isinstance(relationship_id,str) or not any(link['id']==relationship_id for link in links)):raise ValueError('LARGE_LINK_INVALID')
    if relationship_id is None and len(links)>=100:raise ValueError('LARGE_LINK_LIMIT')
    entry={'id':relationship_id or str(uuid.uuid4()),'status':state,'reviewer':reviewer,'rationale':reason,'at':now(),'report':report,'meaning':'Human-declared key relationship; integrity counts are a separate literal check, not a confirmation of scientific meaning.'}
    if relationship_id is None:links.append(entry)
    else:links[:]=[entry if link['id']==relationship_id else link for link in links]
    serialized=json.dumps(next,ensure_ascii=False)
    if len(serialized.encode())>2*1024*1024:raise ValueError('LARGE_LINK_LIMIT')
    conn.execute('INSERT INTO large_metadata VALUES (1,?,?) ON CONFLICT(singleton) DO UPDATE SET revision=excluded.revision,payload=excluded.payload',(before['metadataRevision']+1,serialized));conn.execute('INSERT INTO large_metadata_history(at,reviewer,reason,before,after,working_revision) VALUES (?,?,?,?,?,?)',(now(),reviewer,reason,json.dumps(before['metadata'],ensure_ascii=False),serialized,before['workingRevision']));conn.commit();return {'relationship':entry,**read_snapshot(conn,store.status(payload['id']))}
   except Exception:conn.rollback();raise

def package(store,payload):
 """Derived literal left join, both originals and working tables, never dropping children."""
 child_status,parent_status,child_columns,parent_columns=declaration(store,payload);reason=text(payload.get('reason'),2000).strip();reviewer=text(payload.get('reviewer',''),200).strip()
 if not reason or not reviewer:raise ValueError('LARGE_LINK_REVIEW')
 output=tempfile.TemporaryFile('w+b')
 try:
  with paired_snapshots(store,payload['id'],payload['parentId']) as (child,parent,left,right),index(parent,parent_columns,len(parent_status['headers'])) as (keys,counts,parent_fingerprint):
   # Compare explicit revision inputs rather than regenerating a second snapshot.
   for supplied,actual in [('childWorkingRevision',left['workingRevision']),('parentWorkingRevision',right['workingRevision']),('childMetadataRevision',left['metadataRevision']),('parentMetadataRevision',right['metadataRevision'])]:
    if type(payload.get(supplied)) is not int or payload[supplied]!=actual:raise ValueError('LARGE_LINK_STALE')
   child_fingerprint=hashlib.sha256()
   child_rows=0
   for row,raw in child.execute('SELECT id,data FROM rows ORDER BY id'):
    child_rows+=1;values=json.loads(raw)
    if row!=child_rows or not isinstance(values,list) or len(values)!=len(child_status['headers']):raise ValueError('LARGE_LINK_WORKING_SHAPE')
    key(values,child_columns);child_fingerprint.update(str(row).encode()+b'\0'+json.dumps(values,ensure_ascii=False).encode()+b'\0')
   if child_rows!=child_status['rows'] or counts['parentRecords']!=parent_status['rows']:raise ValueError('LARGE_LINK_WORKING_SHAPE')
   if payload.get('parentWorkingFingerprint')!=parent_fingerprint or payload.get('childWorkingFingerprint')!=child_fingerprint.hexdigest():raise ValueError('LARGE_LINK_STALE')
   members=[];link_counts={'linked':0,'missing':0,'unmatched':0,'conflicting':0}
   with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,allowZip64=True) as archive:
    def write(name,chunks):
     digest=hashlib.sha256();size=0
     with archive.open(name,'w',force_zip64=True) as target:
      for chunk in chunks:
       if name=='derived/literal-left-join.csv' and size+len(chunk)>512*1024*1024:raise ValueError('LARGE_LINK_EXPORT_LIMIT')
       target.write(chunk);digest.update(chunk);size+=len(chunk)
     item={'path':name,'bytes':size,'sha256':digest.hexdigest()};members.append(item);return item
    def raw(id):
     with (store.folder(id)/'original.bin').open('rb') as source:
      while chunk:=source.read(65536):yield chunk
    for role,id,status in [('child',payload['id'],child_status),('parent',payload['parentId'],parent_status)]:
     item=write('sources/'+role+'.bin',raw(id))
     if item['sha256']!=status['sha256'] or item['bytes']!=status['expectedBytes']:raise ValueError('LARGE_SOURCE_INTEGRITY')
    def csv_chunks(rows):
     buffer=io.StringIO(newline='');writer=csv.writer(buffer,lineterminator='\n')
     for row in rows:
      writer.writerow(row)
      if buffer.tell()>65536:yield buffer.getvalue().encode();buffer.seek(0);buffer.truncate()
     if buffer.tell():yield buffer.getvalue().encode()
    def records(conn,status):
     yield status['headers']
     for row,raw in conn.execute('SELECT id,data FROM rows ORDER BY id'):yield json.loads(raw)
    write('tables/child.csv',csv_chunks(records(child,child_status)));write('tables/parent.csv',csv_chunks(records(parent,parent_status)))
    def joined():
     yield ['__child_source_record','__parent_source_record','__link_status']+['child:'+header for header in child_status['headers']]+['parent:'+header for header in parent_status['headers']]
     for row,raw in child.execute('SELECT id,data FROM rows ORDER BY id'):
      values=json.loads(raw);literal=key(values,child_columns);match=keys.execute('SELECT occurrences,source_record,record FROM keys WHERE key=?',(literal,)).fetchone() if literal is not None else None
      outcome='missing' if literal is None else 'unmatched' if match is None else 'conflicting' if match[0]!=1 else 'linked';link_counts[outcome]+=1
      yield [str(row),str(match[1]) if outcome=='linked' else '',outcome]+values+(json.loads(match[2]) if outcome=='linked' else ['']*len(parent_status['headers']))
    write('derived/literal-left-join.csv',csv_chunks(joined()))
    dictionary=[['name','role','sourceColumn','originalName','dataType','status','unit','description'],['__child_source_record','technical','','','integer','Confirmed','','One-based parsed child source-record identity.'],['__parent_source_record','technical','','','integer','Confirmed','','One-based parsed parent source-record identity, present only for an exact unique literal link.'],['__link_status','technical','','','string','Confirmed','','Mechanical key outcome: linked, missing, unmatched or conflicting. Not confirmation of scientific meaning.']]
    for role,state in [('child',left),('parent',right)]:
     for definition in state['metadata']['fields']:dictionary.append([role+':'+definition['name'],role,definition['column'],definition['originalName'],definition['dataType'],definition['status'],definition['unit'],definition['description']])
    write('derived/dictionary.csv',csv_chunks(dictionary))
    for role,conn,state,status in [('child',child,left,child_status),('parent',parent,right,parent_status)]:
     document={**state,'source':{'name':status['name'],'sha256':status['sha256'],'bytes':status['expectedBytes'],'encoding':status['encoding'],'delimiter':status['delimiter']},'rows':status['rows'],'restoration':status.get('restoration')};serialized=json.dumps(document,ensure_ascii=False,indent=2).encode()
     if len(serialized)>2*1024*1024:raise ValueError('LARGE_LINK_LIMIT')
     write('metadata/'+role+'.json',[serialized])
     def history(connection):
      for seq,row,column,before,after,action,reference,reason,at in connection.execute('SELECT * FROM edit_history ORDER BY seq'):
       yield (json.dumps({'sequence':seq,'sourceRecord':row,'column':column,'before':before,'after':after,'action':action,'reference':reference,'rationale':reason,'at':at},ensure_ascii=False)+'\n').encode()
     write('audit/'+role+'-edits.jsonl',history(conn))
     def metadata_history(connection):
      for seq,at,reviewer,reason,before,after,revision in connection.execute('SELECT * FROM large_metadata_history ORDER BY sequence'):
       yield (json.dumps({'sequence':seq,'at':at,'reviewer':reviewer,'rationale':reason,'before':json.loads(before),'after':json.loads(after),'workingRevision':revision},ensure_ascii=False)+'\n').encode()
     write('audit/'+role+'-metadata.jsonl',metadata_history(conn))
     def batches(connection):
      from large_repair import batch_records
      for group in batch_records(connection,payload['id'] if role=='child' else payload['parentId']):yield (json.dumps(group)+'\n').encode()
     write('audit/'+role+'-batches.jsonl',batches(conn))
    recipe={'version':1,'operation':'literal-left-join','software':{'name':'Biodiversity Data Rescue Workbench','version':APP_VERSION},'reviewer':reviewer,'rationale':reason,'createdAt':now(),'childId':payload['id'],'parentId':payload['parentId'],'childColumns':child_columns,'parentColumns':parent_columns,'childWorkingFingerprint':child_fingerprint.hexdigest(),'parentWorkingFingerprint':parent_fingerprint,'childWorkingRevision':left['workingRevision'],'parentWorkingRevision':right['workingRevision'],'childMetadataRevision':left['metadataRevision'],'parentMetadataRevision':right['metadataRevision'],'counts':{**counts,**link_counts},'policy':'No casts, trims, fuzzy matches or dropped child records. Only exact unique nonempty composite keys link. Missing/unmatched/conflicting records retain child values and explicit outcome; parent cells remain empty. This is a reviewed mechanical representation, not confirmation of scientific relationship or normative conformance.'}
    write('metadata/join-recipe.json',[json.dumps(recipe,ensure_ascii=False,indent=2).encode()]);write('README.md',[b'# Literal relationship preservation package\n\nPrivate original bytes, literal working tables, reviewed left-join representation, independent dictionaries/context and histories. Every child record is retained. Parent duplicates are conflicts; never an arbitrary chosen record. Keys are exact strings; zero, NA, leading zeros and whitespace remain literal. Both table snapshots freeze under the common edit lock. This is no assertion of scientific truth or standards conformance. Original source names and reading conventions are in metadata/child.json and metadata/parent.json.\n']);manifest={'packageVersion':1,'packageKind':'literal-relationship','members':members};write('manifest.json',[json.dumps(manifest,indent=2).encode()]);archive.writestr('checksums.sha256',''.join(item['sha256']+'  '+item['path']+'\n' for item in members))
  output.seek(0);return output
 except Exception:output.close();raise
