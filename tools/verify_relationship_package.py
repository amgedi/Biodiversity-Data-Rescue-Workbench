"""Standalone, offline inventory/integrity and exact literal-left-join verification.

No ZIP extraction, server or scientific inference. A temporary SQLite index keeps
parent matching off the Python heap. Verification is not normative conformance.
"""
import argparse,csv,hashlib,io,json,sqlite3,tempfile,zipfile
from contextlib import closing
from pathlib import Path
MEMBERS={'sources/child.bin','sources/parent.bin','tables/child.csv','tables/parent.csv','derived/literal-left-join.csv','derived/dictionary.csv','metadata/child.json','metadata/parent.json','metadata/join-recipe.json','README.md','manifest.json','checksums.sha256'}|{'audit/'+role+'-'+kind+'.jsonl' for role in ['child','parent'] for kind in ['edits','metadata','batches']}
def verify(path,max_bytes=4*1024**3):
 with zipfile.ZipFile(path) as archive:
  infos=archive.infolist();names=[item.filename for item in infos]
  if len(names)!=len(set(names)) or set(names)!=MEMBERS or any(item.flag_bits&1 or item.is_dir() for item in infos):raise ValueError('Unexpected, duplicate or encrypted package members.')
  if sum(item.file_size for item in infos)>max_bytes:raise ValueError('Expanded package exceeds verification limit.')
  facts={}
  for name in sorted(MEMBERS-{'checksums.sha256'}):
   digest=hashlib.sha256();size=0
   with archive.open(name) as source:
    while chunk:=source.read(65536):digest.update(chunk);size+=len(chunk)
   facts[name]={'sha256':digest.hexdigest(),'bytes':size}
  if archive.getinfo('checksums.sha256').file_size>20000:raise ValueError('Oversized checksum inventory.')
  checked={}
  for line in archive.read('checksums.sha256').decode().splitlines():
   digest,name=line.split('  ',1)
   if name in checked or name not in facts or facts[name]['sha256']!=digest:raise ValueError('Checksum mismatch or duplicate checksum inventory.')
   checked[name]=digest
  if set(checked)!=set(facts):raise ValueError('Incomplete checksum inventory.')
  def document(name):
   if archive.getinfo(name).file_size>2*1024*1024:raise ValueError('Oversized metadata document.')
   return json.loads(archive.read(name))
  manifest=document('manifest.json');recipe=document('metadata/join-recipe.json');metadata={role:document('metadata/'+role+'.json') for role in ['child','parent']};listed={}
  if manifest.get('packageVersion')!=1 or manifest.get('packageKind')!='literal-relationship' or recipe.get('version')!=1 or recipe.get('operation')!='literal-left-join':raise ValueError('Unsupported relationship preservation format.')
  for item in manifest['members']:
   name=item['path']
   if name in listed or name not in facts or facts[name]!={'sha256':item['sha256'],'bytes':item['bytes']}:raise ValueError('Manifest length or hash mismatch.')
   listed[name]=True
  if set(listed)!=MEMBERS-{'manifest.json','checksums.sha256'}:raise ValueError('Incomplete manifest.')
  for role in ['child','parent']:
   state=metadata[role]
   if not isinstance(state['metadata']['fields'],list) or not 1<=len(state['metadata']['fields'])<=250:raise ValueError('Invalid independent field dictionary.')
   for key in ['workingRevision','metadataRevision']:
    if type(state.get(key)) is not int or state[key]!=recipe.get(role+key[0].upper()+key[1:]):raise ValueError('Inconsistent paired revisions.')
   if facts['sources/'+role+'.bin']!={'sha256':state['source']['sha256'],'bytes':state['source']['bytes']}:raise ValueError('Original source integrity mismatch.')
  selected=[recipe['childColumns'],recipe['parentColumns']]
  for columns,role in zip(selected,['child','parent']):
   if not isinstance(columns,list) or not 1<=len(columns)<=5 or any(type(column) is not int or not 0<=column<len(metadata[role]['metadata']['fields']) for column in columns) or len(set(columns))!=len(columns):raise ValueError('Invalid key recipe.')
  if len(selected[0])!=len(selected[1]):raise ValueError('Unbalanced composite keys.')
  csv.field_size_limit(1024*1024)
  def reader(source):return csv.reader(io.TextIOWrapper(source,encoding='utf-8',newline=''),strict=True)
  headers={role:[field['name'] for field in metadata[role]['metadata']['fields']] for role in ['child','parent']}
  expected_headers=['__child_source_record','__parent_source_record','__link_status']+['child:'+name for name in headers['child']]+['parent:'+name for name in headers['parent']]
  if archive.getinfo('derived/dictionary.csv').file_size>4*1024*1024:raise ValueError('Oversized derived dictionary.')
  with archive.open('derived/dictionary.csv') as source:
   dictionary=csv.DictReader(io.TextIOWrapper(source,encoding='utf-8',newline=''));field_names=[];definitions=[]
   for field in dictionary:
    field_names.append(field['name']);definitions.append(field)
    if len(field_names)>503:raise ValueError('Oversized derived dictionary.')
   if field_names!=expected_headers:raise ValueError('Derived dictionary differs from data headers.')
  for field in definitions[:3]:
   if field.get('role')!='technical' or field.get('status')!='Confirmed' or field.get('sourceColumn')!='' or field.get('originalName')!='':raise ValueError('Invalid technical outcome dictionary.')
  offset=3
  for role in ['child','parent']:
   for field,source in zip(definitions[offset:offset+len(headers[role])],metadata[role]['metadata']['fields']):
    if field.get('role')!=role or field.get('sourceColumn')!=str(source['column']) or any(field.get(key)!=str(source[key]) for key in ['originalName','dataType','status','unit','description']):raise ValueError('Derived dictionary changed an independent source definition or meaning status.')
   offset+=len(headers[role])
  def key(values,columns):
   parts=[values[column] for column in columns];return None if any(part=='' for part in parts) else json.dumps(parts,ensure_ascii=False,separators=(',',':'))
  counts={'linked':0,'missing':0,'unmatched':0,'conflicting':0};parent_rows=0;child_rows=0
  with tempfile.TemporaryDirectory(prefix='biorescue-verify-links-') as temporary,closing(sqlite3.connect(Path(temporary)/'index.sqlite')) as index:
   index.execute('CREATE TABLE keys (key TEXT PRIMARY KEY,count INTEGER,row INTEGER,data TEXT)')
   with archive.open('tables/parent.csv') as source:
    rows=reader(source)
    if next(rows)!=headers['parent']:raise ValueError('Parent headers differ from metadata.')
    for number,values in enumerate(rows,1):
     parent_rows+=1
     if len(values)!=len(headers['parent']):raise ValueError('Parent row shape differs from metadata.')
     literal=key(values,selected[1])
     if literal is not None:index.execute('INSERT INTO keys VALUES (?,1,?,?) ON CONFLICT(key) DO UPDATE SET count=count+1,data=NULL',(literal,number,json.dumps(values,ensure_ascii=False)))
   index.commit()
   with archive.open('tables/child.csv') as source,archive.open('derived/literal-left-join.csv') as derived:
    rows=reader(source);joined=reader(derived)
    if next(rows)!=headers['child'] or next(joined)!=expected_headers:raise ValueError('Child or derived headers differ from metadata.')
    for number,values in enumerate(rows,1):
     child_rows+=1
     if len(values)!=len(headers['child']):raise ValueError('Child row shape differs from metadata.')
     literal=key(values,selected[0]);match=index.execute('SELECT count,row,data FROM keys WHERE key=?',(literal,)).fetchone() if literal is not None else None;outcome='missing' if literal is None else 'unmatched' if match is None else 'conflicting' if match[0]!=1 else 'linked';counts[outcome]+=1
     expected=[str(number),str(match[1]) if outcome=='linked' else '',outcome]+values+(json.loads(match[2]) if outcome=='linked' else ['']*len(headers['parent']))
     if next(joined,None)!=expected:raise ValueError('Derived row differs from exact literal left join; child was dropped, parent guessed or values changed.')
    if next(joined,None) is not None:raise ValueError('Unexpected extra derived rows.')
  if child_rows!=metadata['child']['rows'] or parent_rows!=metadata['parent']['rows'] or any(recipe['counts'][key]!=value for key,value in counts.items()):raise ValueError('Recipe or recorded row counts differ from literal data.')
  return {'verified':True,'files':len(MEMBERS),'childRows':child_rows,'parentRows':parent_rows,'counts':counts,'allChildRecordsRetained':True,'scientificConformance':False}
if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('package',type=Path);parser.add_argument('--max-bytes',type=int,default=4*1024**3);args=parser.parse_args()
 try:print(json.dumps(verify(args.package,args.max_bytes),indent=2))
 except (ValueError,KeyError,TypeError,OSError,zipfile.BadZipFile,csv.Error,StopIteration) as error:print(json.dumps({'verified':False,'error':str(error)}));raise SystemExit(1)
