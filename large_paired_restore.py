"""Replay both sides of a relationship package, then publish one reviewed group.

Archive paths are never extracted. Historical declarations remain unchanged;
the group records an explicit old-to-new investigation map for navigation.
"""
import csv,hashlib,io,json,os,shutil,tempfile,uuid,zipfile
from pathlib import Path
from large_restore import Recovery
from large_preservation import text
from tools.verify_relationship_package import verify
from upgrades import atomic,now,APP_VERSION

def single_package(archive,role,recipe,path):
 """Translate one fixed member inventory to the existing replay format, streaming."""
 document=json.loads(archive.read('metadata/'+role+'.json'))
 document['investigationId']=recipe[role+'Id'];members=[]
 with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED,allowZip64=True) as out:
  def write(name,chunks):
   digest=hashlib.sha256();size=0
   with out.open(name,'w',force_zip64=True) as target:
    for chunk in chunks:target.write(chunk);digest.update(chunk);size+=len(chunk)
   members.append({'path':name,'sha256':digest.hexdigest(),'bytes':size})
  def chunks(name):
   with archive.open(name) as source:
    while chunk:=source.read(65536):yield chunk
  write('sources/original.bin',chunks('sources/'+role+'.bin'))
  write('data/working.csv',chunks('tables/'+role+'.csv'))
  buffer=io.StringIO(newline='');writer=csv.writer(buffer,lineterminator='\n');keys=['column','name','originalName','description','unit','dataType','status','rationale','reviewer'];writer.writerow(keys)
  for field in document['metadata']['fields']:writer.writerow([field[key] for key in keys])
  write('metadata/dictionary.csv',[buffer.getvalue().encode()])
  write('metadata/metadata.json',[json.dumps(document,ensure_ascii=False).encode()])
  for kind in ['edits','metadata','batches']:write('audit/'+kind+'.jsonl',chunks('audit/'+role+'-'+kind+'.jsonl'))
  write('README.md',[b'Internal replay view of one side of a verified literal relationship package. No scientific claims are added.\n'])
  manifest={'packageVersion':1,'workingRevision':document['workingRevision'],'metadataRevision':document['metadataRevision'],'members':list(members)}
  write('manifest.json',[json.dumps(manifest).encode()]);out.writestr('checksums.sha256',''.join(item['sha256']+'  '+item['path']+'\n' for item in members))

class PairedRecovery:
 def __init__(self,path):
  self.temporary=tempfile.TemporaryDirectory(prefix='biorescue-paired-recovery-');self.recoveries={};self.closed=False;path=Path(path)
  try:
   checked=verify(path,max_bytes=1024**3);digest=hashlib.sha256()
   with path.open('rb') as source:
    while chunk:=source.read(65536):digest.update(chunk)
   with zipfile.ZipFile(path) as archive:
    recipe=json.loads(archive.read('metadata/join-recipe.json'));self.recipe=recipe
    if recipe.get('childId')==recipe.get('parentId'):raise ValueError('LARGE_RESTORE_SOURCE')
    for role in ['child','parent']:
     view=Path(self.temporary.name)/(role+'.zip');single_package(archive,role,recipe,view);self.recoveries[role]=Recovery(view)
     if self.recoveries[role].report['workingRevision']!=recipe[role+'WorkingRevision'] or self.recoveries[role].report['metadataRevision']!=recipe[role+'MetadataRevision']:raise ValueError('LARGE_RESTORE_HISTORY')
    # Retain the exact derived output and reviewed recipe as provenance, not a third scientific table.
    for name,key in [('derived/literal-left-join.csv','derived.csv'),('derived/dictionary.csv','dictionary.csv')]:
     with archive.open(name) as source,(Path(self.temporary.name)/key).open('wb') as target:shutil.copyfileobj(source,target,65536)
   investigations=[{'role':role,**recovery.report,'restoredId':recovery.id} for role,recovery in self.recoveries.items()]
   self.report={'packageKind':'literal-relationship','packageSha256':digest.hexdigest(),'sourceName':' / '.join(r['sourceName'] for r in investigations),'rows':sum(r['rows'] for r in investigations),'fields':sum(r['fields'] for r in investigations),'workingRevision':None,'metadataRevision':None,'historyCells':sum(r['historyCells'] for r in investigations),'investigations':investigations,'packageFiles':checked['files'],'verifiedOriginalReplay':True,'verifiedDerivedJoin':True,'scientificConformance':False,'policy':'Both histories replay exactly. Old relationship declarations remain historical; reviewed group mapping resolves both restored investigations without changing scientific statuses.'}
  except Exception:self.close();raise
 def close(self):
  if self.closed:return
  self.closed=True
  for recovery in self.recoveries.values():recovery.close()
  self.temporary.cleanup()
 def publish(self,target,reviewer,reason):
  text(reviewer,200);text(reason,2000)
  if not reviewer.strip() or not reason.strip():raise ValueError('LARGE_RESTORE_REVIEW')
  if self.closed:raise ValueError('LARGE_RESTORE_EXPIRED')
  group=str(uuid.uuid4());mapping={self.recipe[role+'Id']:recovery.id for role,recovery in self.recoveries.items()};published=[];staged=[]
  for role,recovery in self.recoveries.items():
   prior=recovery.report.get('previousRestoration') or {}
   for historical,current in prior.get('mapping',{}).items():
    if current==self.recipe[role+'Id']:mapping[historical]=recovery.id
  if len(mapping)>100:raise ValueError('LARGE_RESTORE_LIMIT')
  with target.lock:
   target.root.mkdir(parents=True,exist_ok=True);groups=target.root/'restore-groups';groups.mkdir(exist_ok=True)
   group_stage=target.root/('.paired-'+group+'.pending');group_final=groups/group
   try:
    group_stage.mkdir();atomic(group_stage/'provenance.json',{'version':1,'packageSha256':self.report['packageSha256'],'mapping':mapping,'recipe':self.recipe,'reviewer':reviewer.strip(),'reason':reason.strip(),'at':now()})
    for name in ['derived.csv','dictionary.csv']:shutil.copyfile(Path(self.temporary.name)/name,group_stage/name)
    for role,recovery in self.recoveries.items():
     final=target.folder(recovery.id);stage=target.root/('.restore-'+recovery.id+'.pending')
     if final.exists() or stage.exists():raise ValueError('LARGE_RESTORE_EXISTS')
     staged.append(stage);shutil.copytree(recovery.store.folder(recovery.id),stage);status=recovery.store.status(recovery.id)
     status['restoration']={**recovery.report,'packageSha256':self.report['packageSha256'],'groupId':group,'groupRole':role,'mapping':mapping,'reviewer':reviewer.strip(),'rationale':reason.strip(),'at':now(),'softwareVersion':APP_VERSION,'policy':self.report['policy']};atomic(stage/'status.json',status)
     os.replace(stage,final);published.append(final)
    os.replace(group_stage,group_final)
    # The catalog is the single visibility commit. Before it exists, neither side is usable.
    atomic(groups/(group+'.json'),{'version':1,'groupId':group,'mapping':mapping,'ids':[r.id for r in self.recoveries.values()]})
    return {'id':self.recoveries['child'].id,'parentId':self.recoveries['parent'].id,'groupId':group,'mapping':mapping,'investigations':[target.status(r.id) for r in self.recoveries.values()],'report':self.report}
   except Exception:
    # Remove only directories created by this attempt; existing investigations remain untouched.
    commit=groups/(group+'.json')
    if commit.exists():commit.unlink()
    for folder in staged+published+[group_stage,group_final]:
     resolved=folder.resolve();root=target.root.resolve()
     if resolved==root or not resolved.is_relative_to(root):raise ValueError('LARGE_RESTORE_INVALID')
     if folder.exists():shutil.rmtree(folder)
    raise

def open_recovery(path):
 try:
  with zipfile.ZipFile(path) as archive:
   if archive.getinfo('manifest.json').file_size>2*1024*1024:raise ValueError('LARGE_RESTORE_LIMIT')
   manifest=json.loads(archive.read('manifest.json'))
   if not isinstance(manifest,dict):raise ValueError('LARGE_RESTORE_INVALID')
  return PairedRecovery(path) if manifest.get('packageKind')=='literal-relationship' else Recovery(path)
 except (zipfile.BadZipFile,csv.Error,UnicodeDecodeError,AttributeError):raise ValueError('LARGE_RESTORE_INVALID') from None
