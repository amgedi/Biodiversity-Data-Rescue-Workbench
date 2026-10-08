import base64,csv,hashlib,io,json,tempfile,unittest,zipfile
from pathlib import Path
from contextlib import closing
from unittest.mock import patch
from large_data import LargeStore
from large_relationships import inspect,save,package
from large_preservation import metadata
from tools.verify_relationship_package import verify
class LargeRelationshipTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.store=LargeStore(self.temp.name);self.parent=self.create('parent.csv',b'site,period,note\n001,2020,one\n001,2021,two\nA,2020,duplicate one\nA,2020,duplicate two\n0,2020,zero\nNA,2020,literal NA\n,2020,missing\n');self.child=self.create('child.csv',b'site,period,count\n001,2020,0\n001,2021,1\nA,2020,2\n 001 ,2020,3\n0,2020,0\nNA,2020,4\n,2020,5\n009,2020,6\n');self.payload={'id':self.child,'parentId':self.parent,'childColumns':[0,1],'parentColumns':[0,1]}
 def create(self,name,raw):
  job=self.store.create(name,len(raw));id=job['id'];self.store.chunk(id,0,base64.b64encode(raw).decode());self.store.start(id,False);return id
 def tearDown(self):self.temp.cleanup()
 def reviewed(self,report=None,**extra):return save(self.store,{**self.payload,'digest':(report or inspect(self.store,self.payload))['digest'],'reason':'Fictional source protocol declares these composite keys.','reviewer':'Fictional curator','status':'Confirmed',**extra})
 def test_exact_composite_index_preserves_zero_na_whitespace_and_conflicting_parents(self):
  before=(self.store.page(self.child),self.store.page(self.parent));report=inspect(self.store,self.payload);self.assertEqual(report['counts'],{'parentRecords':7,'missingParentKeys':1,'duplicateParentKeys':1,'duplicateParentRecords':2,'childRecords':8,'missingChildKeys':1,'unmatchedChildKeys':2,'conflictingChildKeys':1,'linkedChildRecords':4});self.assertEqual(report['examples']['unmatched'][0]['literalKey'],[' 001 ','2020']);self.assertIsNone(report['examples']['conflicting'][0]['parentSourceRecord']);self.assertEqual((self.store.page(self.child),self.store.page(self.parent)),before)
 def test_declared_relationship_records_review_and_snapshots_without_claiming_integrity(self):
  result=self.reviewed();self.assertEqual(result['metadataRevision'],1);self.assertEqual(result['workingRevision'],0);entry=result['relationship'];self.assertEqual(entry['status'],'Confirmed');self.assertEqual(entry['report']['counts']['conflictingChildKeys'],1);self.assertEqual(entry['report']['childSourceHash'],self.store.status(self.child)['sha256']);self.assertEqual(metadata(self.store,self.parent)['metadataRevision'],0);self.assertTrue(all(field['status']=='Unknown' for field in result['metadata']['fields']))
 def test_rejects_changed_child_parent_or_metadata_after_preview(self):
  for target,expected,value in [(self.child,'0','7'),(self.parent,'one','Updated protocol')]:
   report=inspect(self.store,self.payload);column=2;self.store.edit(target,0,row=1,column=column,expected=expected,value=value,reason='Concurrent fictional edit')
   with self.assertRaisesRegex(ValueError,'STALE'):self.reviewed(report)
  report=inspect(self.store,self.payload);self.reviewed(report)
  with self.assertRaisesRegex(ValueError,'STALE'):self.reviewed(report)
 def test_invalid_unbalanced_duplicate_or_bool_columns_and_missing_review_are_rejected(self):
  for extra in [{'childColumns':[True,1]},{'parentColumns':[0]},{'childColumns':[0,0]},{'parentColumns':[99,1]},{'childColumns':[]},{'status':'Confirmed','reviewer':''},{'reason':''}]:
   with self.assertRaises(ValueError):self.reviewed(**extra)
  self.assertEqual(metadata(self.store,self.child)['metadataRevision'],0)
 def test_update_requires_existing_relationship_identity_and_preserves_history(self):
  first=self.reviewed();id=first['relationship']['id'];second=self.reviewed(relationshipId=id,status='Inferred');self.assertEqual(len(second['metadata']['relationships']),1);self.assertEqual(second['metadata']['relationships'][0]['status'],'Inferred');self.assertEqual(second['metadataRevision'],2)
  with self.assertRaisesRegex(ValueError,'INVALID'):self.reviewed(relationshipId='foreign')
  with closing(self.store.edit_connection(self.child)) as conn:self.assertEqual(conn.execute('SELECT count(*) FROM large_metadata_history').fetchone()[0],2)
 def exported(self,report=None,**extra):return package(self.store,{**self.payload,**(report or inspect(self.store,self.payload)),'reason':'Reviewed fictional literal key operation only.','reviewer':'Fictional curator',**extra})
 def test_join_package_retains_every_child_original_unknown_and_conflict(self):
  before=(self.store.page(self.child),self.store.page(self.parent))
  with self.exported() as artifact,zipfile.ZipFile(artifact) as archive:
   for role,id in [('child',self.child),('parent',self.parent)]:self.assertEqual(archive.read('sources/'+role+'.bin'),(self.store.folder(id)/'original.bin').read_bytes())
   rows=list(csv.reader(io.StringIO(archive.read('derived/literal-left-join.csv').decode())));self.assertEqual(len(rows),9);self.assertEqual(rows[1],['1','1','linked','001','2020','0','001','2020','one']);self.assertEqual(rows[3][2],'conflicting');self.assertEqual(rows[3][-3:],['','','']);self.assertEqual(rows[4][2],'unmatched');self.assertEqual(rows[5][3],'0');self.assertEqual(rows[6][3],'NA');self.assertEqual(rows[7][2],'missing');self.assertEqual(rows[8][2],'unmatched');recipe=json.loads(archive.read('metadata/join-recipe.json'));self.assertEqual(recipe['counts']['linked'],4)
   for line in archive.read('checksums.sha256').decode().splitlines():digest,name=line.split('  ',1);self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(),digest)
  self.assertEqual((self.store.page(self.child),self.store.page(self.parent)),before)
 def test_join_export_rejects_stale_revisions_and_corrupt_parent_without_repair(self):
  report=inspect(self.store,self.payload);self.store.edit(self.parent,0,row=1,column=2,value='After preview',expected='one',reason='Fictional concurrent edit')
  with self.assertRaisesRegex(ValueError,'STALE'):self.exported(report)
  original=self.store.folder(self.parent)/'original.bin';original.write_bytes(b'Fictional corruption')
  with self.assertRaisesRegex(ValueError,'SOURCE_INTEGRITY'):self.exported()
  self.assertEqual(original.read_bytes(),b'Fictional corruption')
 def test_fingerprints_reject_untracked_working_changes_without_revision_increment(self):
  report=inspect(self.store,self.payload)
  with closing(self.store.edit_connection(self.parent)) as conn:conn.execute('UPDATE rows SET data=? WHERE id=1',(json.dumps(['001','2020','Untracked change']),));conn.commit()
  with self.assertRaisesRegex(ValueError,'STALE'):self.reviewed(report)
  with self.assertRaisesRegex(ValueError,'STALE'):self.exported(report)
 def test_paired_snapshot_export_stays_consistent_during_parent_edit(self):
  original_open=zipfile.ZipFile.open
  def open_member(archive,name,*args,**kwargs):
   if name=='derived/literal-left-join.csv':self.store.edit(self.parent,0,row=1,column=2,value='After snapshot',expected='one',reason='Concurrent fictional edit')
   return original_open(archive,name,*args,**kwargs)
  with patch.object(zipfile.ZipFile,'open',open_member):artifact=self.exported()
  with artifact,zipfile.ZipFile(artifact) as archive:self.assertEqual(json.loads(archive.read('metadata/parent.json'))['workingRevision'],0);self.assertIn(b',one\n',archive.read('derived/literal-left-join.csv'));self.assertEqual(archive.read('audit/parent-edits.jsonl'),b'')
  self.assertEqual(self.store.page(self.parent)['revision'],1)
 def test_independent_verifier_recomputes_join_and_checks_all_source_records(self):
  path=Path(self.temp.name)/'fictional-relationship.zip'
  with self.exported() as artifact:path.write_bytes(artifact.read())
  result=verify(path);self.assertTrue(result['allChildRecordsRetained']);self.assertEqual(result['childRows'],8);self.assertEqual(result['counts'],{'linked':4,'missing':1,'unmatched':2,'conflicting':1})
 def test_working_shape_corruption_is_not_cast_padded_or_dropped(self):
  report=inspect(self.store,self.payload)
  with closing(self.store.edit_connection(self.child)) as conn:conn.execute('UPDATE rows SET data=? WHERE id=1',(json.dumps(['001','2020',0]),));conn.commit()
  with self.assertRaisesRegex(ValueError,'WORKING_SHAPE'):inspect(self.store,self.payload)
  with self.assertRaisesRegex(ValueError,'WORKING_SHAPE'):self.exported(report)
 def test_bounded_key_preview_never_truncates_matching_values(self):
  value='x'*600;parent=self.create('long-parent.csv',('id\n'+value+'\n').encode());child=self.create('long-child.csv',('id\n'+value+'\n'+value+'different\n').encode());report=inspect(self.store,{'id':child,'parentId':parent,'childColumns':[0],'parentColumns':[0]});self.assertEqual(report['counts']['linkedChildRecords'],1);self.assertEqual(report['counts']['unmatchedChildKeys'],1);self.assertTrue(report['examples']['linked'][0]['keyPreviewTruncated']);self.assertEqual(len(report['examples']['linked'][0]['literalKey'][0]),500)
 def test_missing_tail_record_blocks_preview_and_save_for_both_tables(self):
  for target in [self.child,self.parent]:
   with self.subTest(target=target),closing(self.store.edit_connection(target)) as conn:
    last=conn.execute('SELECT id,data FROM rows ORDER BY id DESC LIMIT 1').fetchone();conn.execute('DELETE FROM rows WHERE id=?',(last[0],));conn.commit()
    try:
     with self.assertRaisesRegex(ValueError,'WORKING_SHAPE'):inspect(self.store,self.payload)
     with self.assertRaisesRegex(ValueError,'WORKING_SHAPE'):self.reviewed()
    finally:conn.execute('INSERT INTO rows(id,data) VALUES (?,?)',last);conn.commit()
 def test_verifier_rejects_arbitrary_parent_even_with_recomputed_manifest_and_checksums(self):
  path=Path(self.temp.name)/'fictional-guessed-parent.zip'
  with self.exported() as artifact,zipfile.ZipFile(artifact) as archive:members={name:archive.read(name) for name in archive.namelist()}
  members['derived/literal-left-join.csv']=members['derived/literal-left-join.csv'].replace(b'3,,conflicting,A,2020,2,,,\n',b'3,3,linked,A,2020,2,A,2020,duplicate one\n')
  manifest=json.loads(members['manifest.json'])
  for item in manifest['members']:item.update(bytes=len(members[item['path']]),sha256=hashlib.sha256(members[item['path']]).hexdigest())
  members['manifest.json']=json.dumps(manifest).encode();members['checksums.sha256']=''.join(hashlib.sha256(data).hexdigest()+'  '+name+'\n' for name,data in members.items() if name!='checksums.sha256').encode()
  with zipfile.ZipFile(path,'w') as modified:
   for name,data in members.items():modified.writestr(name,data)
  with self.assertRaisesRegex(ValueError,'exact literal left join'):verify(path)
