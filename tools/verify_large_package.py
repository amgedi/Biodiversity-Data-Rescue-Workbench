"""Offline checksum, byte-length, metadata/dictionary and row-shape verification.

Reads ZIP members without extracting files or requiring the Workbench server.
This verifies preservation consistency, not scientific truth or standards conformance.
"""
import argparse,csv,hashlib,io,json,zipfile
from pathlib import Path
MEMBERS={'sources/original.bin','data/working.csv','metadata/dictionary.csv','metadata/metadata.json','audit/edits.jsonl','audit/batches.jsonl','audit/metadata.jsonl','README.md','manifest.json','checksums.sha256'}

def verify(path,max_bytes=4*1024**3):
 with zipfile.ZipFile(path) as archive:
  infos=archive.infolist();names=[item.filename for item in infos]
  if len(names)!=len(set(names)) or set(names)!=MEMBERS:raise ValueError('Unexpected or duplicate package members.')
  if any(item.flag_bits&1 or item.is_dir() for item in infos) or sum(item.file_size for item in infos)>max_bytes:raise ValueError('Encrypted or oversized package; nothing extracted.')
  facts={}
  for name in sorted(MEMBERS-{'checksums.sha256'}):
   digest=hashlib.sha256();size=0
   with archive.open(name) as source:
    while chunk:=source.read(65536):size+=len(chunk);digest.update(chunk)
   facts[name]={'sha256':digest.hexdigest(),'bytes':size}
  if archive.getinfo('checksums.sha256').file_size>10000:raise ValueError('Oversized checksum inventory.')
  lines=archive.read('checksums.sha256').decode('utf-8').splitlines();checks={}
  for line in lines:
   digest,name=line.split('  ',1)
   if name in checks or name not in facts or digest!=facts[name]['sha256']:raise ValueError('Checksum mismatch or duplicate inventory entry.')
   checks[name]=digest
  if set(checks)!=set(facts):raise ValueError('Incomplete checksum inventory.')
  for name in ['manifest.json','metadata/metadata.json']:
   if archive.getinfo(name).file_size>2*1024*1024:raise ValueError('Oversized metadata document.')
  manifest=json.loads(archive.read('manifest.json'));document=json.loads(archive.read('metadata/metadata.json'));listed={}
  if manifest.get('packageVersion')!=1:raise ValueError('Unsupported preservation package version.')
  for item in manifest['members']:
   name=item['path']
   if name in listed or name not in facts or facts[name]!={'sha256':item['sha256'],'bytes':item['bytes']}:raise ValueError('Manifest length/hash mismatch.')
   listed[name]=item
  if set(listed)!=MEMBERS-{'manifest.json','checksums.sha256'}:raise ValueError('Incomplete manifest.')
  for key in ['workingRevision','metadataRevision']:
   if type(document.get(key)) is not int or document[key]<0 or document[key]!=manifest.get(key):raise ValueError('Inconsistent revision.')
  if facts['sources/original.bin']!={'sha256':document['source']['sha256'],'bytes':document['source']['bytes']}:raise ValueError('Original source integrity mismatch.')
  fields=document['metadata']['fields']
  if not isinstance(fields,list) or not 1<=len(fields)<=250:raise ValueError('Invalid field dictionary.')
  if archive.getinfo('metadata/dictionary.csv').file_size>4*1024*1024:raise ValueError('Oversized CSV dictionary.')
  csv.field_size_limit(1024*1024)
  with archive.open('metadata/dictionary.csv') as source:
   dictionary=[]
   for row in csv.DictReader(io.TextIOWrapper(source,encoding='utf-8',newline='')):
    dictionary.append(row)
    if len(dictionary)>250:raise ValueError('Oversized field dictionary.')
  if len(dictionary)!=len(fields) or any(any(row.get(key)!=str(field[key]) for key in ['column','name','originalName','description','unit','dataType','status','rationale','reviewer']) for row,field in zip(dictionary,fields)):raise ValueError('CSV and JSON dictionaries differ.')
  csv.field_size_limit(1024*1024);rows=0
  with archive.open('data/working.csv') as source:
   reader=csv.reader(io.TextIOWrapper(source,encoding='utf-8',newline=''),strict=True)
   if next(reader)!=[field['name'] for field in fields]:raise ValueError('Working headers differ from dictionary.')
   for row in reader:
    if len(row)!=len(fields):raise ValueError('Working row shape differs from dictionary.')
    rows+=1
  if rows!=document['rows']:raise ValueError('Recorded row count differs from working CSV.')
  return {'verified':True,'files':len(MEMBERS),'rows':rows,'fields':len(fields),'workingRevision':document['workingRevision'],'metadataRevision':document['metadataRevision'],'scientificConformance':False}

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('package',type=Path);parser.add_argument('--max-bytes',type=int,default=4*1024**3);args=parser.parse_args()
 try:print(json.dumps(verify(args.package,args.max_bytes),indent=2))
 except (ValueError,KeyError,TypeError,OSError,zipfile.BadZipFile,csv.Error) as error:print(json.dumps({'verified':False,'error':str(error)}));raise SystemExit(1)
