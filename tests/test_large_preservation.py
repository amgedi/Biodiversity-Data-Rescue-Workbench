import base64,csv,hashlib,io,json,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
from large_data import LargeStore
from large_preservation import metadata,save_metadata,package
from tools.verify_large_package import verify
class LargePreservationTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.store=LargeStore(self.temp.name);self.raw=b'id,note,n\n001,"quoted, value",0\n002,"multi\nline",NA\n';job=self.store.create('fictional.csv',len(self.raw));self.id=job['id'];self.store.chunk(self.id,0,base64.b64encode(self.raw).decode());self.store.start(self.id,False)
 def tearDown(self):self.temp.cleanup()
 def save(self,changes,**extra):
  state=metadata(self.store,self.id);return save_metadata(self.store,{'id':self.id,'metadataRevision':state['metadataRevision'],'workingRevision':state['workingRevision'],'reason':'Fictional source custodian explains this definition.','reviewer':'Fictional curator','changes':changes,**extra})
 def test_defaults_remain_unknown_and_definitions_never_cast_literal_values(self):
  before=self.store.page(self.id);state=metadata(self.store,self.id);self.assertTrue(all(field['status']=='Unknown' for field in state['metadata']['fields']));saved=self.save([{'kind':'field','column':2,'description':'Recorded individual count; missing convention is not known.','unit':'individuals','dataType':'integer','status':'Confirmed'}]);self.assertEqual(saved['metadataRevision'],1);self.assertEqual(saved['workingRevision'],0);self.assertEqual(self.store.page(self.id),before);self.assertEqual((self.store.folder(self.id)/'original.bin').read_bytes(),self.raw)
 def test_context_and_field_changes_are_atomic_and_require_exact_revisions(self):
  before=metadata(self.store,self.id);changes=[{'kind':'context','key':'purpose','value':'Fictional monitoring purpose','status':'Inferred'},{'kind':'field','column':999,'description':'Invalid','unit':'','dataType':'string','status':'Unknown'}]
  with self.assertRaises(ValueError):self.save(changes)
  self.assertEqual(metadata(self.store,self.id),before)
  saved=self.save(changes[:1]);self.assertEqual(saved['metadataRevision'],1)
  with self.assertRaisesRegex(ValueError,'STALE'):self.save(changes[:1],metadataRevision=0)
  self.store.edit(self.id,0,row=1,column=1,value='Reviewed literal',expected='quoted, value',reason='Fictional literal edit')
  with self.assertRaisesRegex(ValueError,'STALE'):self.save(changes[:1],workingRevision=0)
  self.assertEqual(metadata(self.store,self.id)['metadataRevision'],1)
 def test_confirmed_context_requires_review_identity_and_rejects_unsupported_payloads(self):
  before=metadata(self.store,self.id)
  for change in [{'kind':'context','key':'purpose','value':'Example','status':'Confirmed'},{'kind':'context','key':'contact','value':'Do not fabricate contacts','status':'Unknown'},{'kind':'field','column':True,'description':'No guessed column','unit':'','dataType':'string','status':'Unknown'}]:
   with self.assertRaises(ValueError):self.save([change],reviewer='')
  self.assertEqual(metadata(self.store,self.id),before)
 def test_package_has_exact_source_literal_csv_dictionary_histories_and_verifiable_checksums(self):
  self.save([{'kind':'context','key':'purpose','value':'Fictional purpose','status':'Inferred'}]);self.store.edit(self.id,0,row=1,column=1,value='Reviewed, literal',expected='quoted, value',reason='Reviewed fictional punctuation')
  with package(self.store,self.id) as artifact,zipfile.ZipFile(artifact) as archive:
   self.assertEqual(archive.read('sources/original.bin'),self.raw);data=list(csv.reader(io.StringIO(archive.read('data/working.csv').decode())));self.assertEqual(data[1],['001','Reviewed, literal','0']);self.assertEqual(data[2],['002','multi\nline','NA']);document=json.loads(archive.read('metadata/metadata.json'));self.assertEqual((document['workingRevision'],document['metadataRevision']),(1,1));self.assertEqual(document['metadata']['context']['purpose']['status'],'Inferred');self.assertEqual(len(archive.read('audit/edits.jsonl').splitlines()),1);self.assertEqual(len(archive.read('audit/metadata.jsonl').splitlines()),1)
   for line in archive.read('checksums.sha256').decode().splitlines():digest,name=line.split('  ',1);self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(),digest)
   for item in json.loads(archive.read('manifest.json'))['members']:self.assertEqual(len(archive.read(item['path'])),item['bytes'])
 def test_malformed_nested_values_are_rejected_atomically_as_validation_errors(self):
  before=metadata(self.store,self.id)
  for change in [{'kind':[], 'key':'purpose','value':'x','status':'Unknown'},{'kind':'context','key':{},'value':'x','status':'Unknown'},{'kind':'context','key':'purpose','value':'x','status':[]},{'kind':'field','column':0,'description':'x','unit':'','dataType':{},'status':'Unknown'}]:
   with self.assertRaisesRegex(ValueError,'LARGE_METADATA_INVALID'):self.save([change])
   self.assertEqual(metadata(self.store,self.id),before)
 def test_standalone_verifier_needs_no_server_and_rejects_corrupt_or_duplicate_members(self):
  path=Path(self.temp.name)/'fictional.zip'
  with package(self.store,self.id) as archive:path.write_bytes(archive.read())
  self.assertEqual(verify(path)['rows'],2)
  with zipfile.ZipFile(path,'a') as archive:archive.writestr('unexpected.txt','not part of the package')
  with self.assertRaisesRegex(ValueError,'Unexpected'):verify(path)
 def test_standalone_verifier_rejects_checksum_change(self):
  path=Path(self.temp.name)/'fictional-modified.zip'
  with package(self.store,self.id) as artifact,zipfile.ZipFile(artifact) as archive,zipfile.ZipFile(path,'w') as modified:
   for name in archive.namelist():modified.writestr(name,b'altered' if name=='data/working.csv' else archive.read(name))
  with self.assertRaisesRegex(ValueError,'Checksum'):verify(path)
 def test_corrupted_original_blocks_package_without_rewriting_or_repairing_it(self):
  original=self.store.folder(self.id)/'original.bin';original.write_bytes(b'corrupted original')
  with self.assertRaisesRegex(ValueError,'SOURCE_INTEGRITY'):package(self.store,self.id)
  self.assertEqual(original.read_bytes(),b'corrupted original')
 def test_concurrent_edit_during_package_does_not_mix_revisions_data_or_history(self):
  original_open=zipfile.ZipFile.open;store=self.store;id=self.id
  def open_member(archive,name,*args,**kwargs):
   if name=='data/working.csv':store.edit(id,0,row=1,column=1,value='After snapshot',expected='quoted, value',reason='Concurrent fictional edit')
   return original_open(archive,name,*args,**kwargs)
  with patch.object(zipfile.ZipFile,'open',open_member):artifact=package(store,id)
  with artifact,zipfile.ZipFile(artifact) as archive:self.assertEqual(json.loads(archive.read('manifest.json'))['workingRevision'],0);self.assertIn(b'quoted, value',archive.read('data/working.csv'));self.assertEqual(archive.read('audit/edits.jsonl'),b'')
  self.assertEqual(store.page(id)['rows'][0]['values'][1],'After snapshot')
