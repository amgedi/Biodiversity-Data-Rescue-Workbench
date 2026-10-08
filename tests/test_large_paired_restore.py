import base64,hashlib,json,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
from large_data import LargeStore
from large_relationships import inspect,save,package
from large_preservation import metadata
from large_repair import apply,preview
from large_paired_restore import PairedRecovery,open_recovery
from restore_uploads import RestoreUploads
from upgrades import atomic
class PairedRestoreTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.source=LargeStore(self.root/'source');self.target=LargeStore(self.root/'target');self.child=self.create('child.csv',b'key,n\n001, 0 \n1,NA\n,unknown\nA,2\n');self.parent=self.create('parent.csv',b'key,note\n001,First\n1,Second\nA,one\nA,two\n');self.payload={'id':self.child,'parentId':self.parent,'childColumns':[0],'parentColumns':[0]};self.path=self.root/'pair.zip'
 def tearDown(self):self.temp.cleanup()
 def create(self,name,raw):
  j=self.source.create(name,len(raw));self.source.chunk(j['id'],0,base64.b64encode(raw).decode());self.source.start(j['id'],False);return j['id']
 def archive(self):
  report=inspect(self.source,self.payload)
  with package(self.source,{**self.payload,**report,'reason':'Fictional reviewed literal relationship','reviewer':'Fictional curator'}) as artifact:self.path.write_bytes(artifact.read())
 def recover(self):return open_recovery(self.path)
 def test_both_originals_dictionaries_histories_and_derived_join_replay_into_independent_group(self):
  batch={'id':self.child,'operation':'trim-whitespace','columns':[1]};apply(self.source,{**batch,**preview(self.source,batch),'reason':'Fictional trim','reviewer':'Fictional curator'});self.source.edit(self.child,1,action='undo',reason='Keep literal spaces');self.source.edit(self.child,2,action='redo',reason='Restore reviewed trim')
  report=inspect(self.source,self.payload);save(self.source,{**self.payload,'digest':report['digest'],'reason':'Fictional source explains linkage','reviewer':'Fictional curator','status':'Inferred'});self.archive();before=[self.source.page(i) for i in [self.child,self.parent]];recovery=self.recover()
  try:
   self.assertIsInstance(recovery,PairedRecovery);self.assertTrue(recovery.report['verifiedDerivedJoin']);result=recovery.publish(self.target,'Fictional archivist','Restore both as independent copies')
   self.assertEqual(len(self.target.list()),2);self.assertEqual(result['mapping'],{self.child:result['id'],self.parent:result['parentId']});self.assertEqual([self.target.page(i)['rows'] for i in [result['id'],result['parentId']]],[item['rows'] for item in before]);self.assertEqual(metadata(self.target,result['id'])['metadata'],metadata(self.source,self.child)['metadata']);self.assertEqual(self.target.edit_state(result['id'])['revision'],3)
   for old,new in result['mapping'].items():self.assertEqual((self.target.folder(new)/'original.bin').read_bytes(),(self.source.folder(old)/'original.bin').read_bytes())
   provenance=self.target.root/'restore-groups'/result['groupId'];self.assertTrue((provenance/'derived.csv').exists());self.assertEqual(json.loads((provenance/'provenance.json').read_text())['recipe']['childId'],self.child)
   self.target.edit(result['id'],3,action='undo',reason='Undo restored batch');self.assertEqual(self.target.page(result['id'])['rows'][0]['values'][1],' 0 ');self.assertEqual([self.source.page(i) for i in [self.child,self.parent]],before)
  finally:recovery.close()
 def test_no_partial_group_visible_before_single_commit_and_failed_commit_rolls_back_only_new_copies(self):
  self.archive();recovery=self.recover();observed=[]
  def write(path,value):
   if path.parent.name=='restore-groups' and path.suffix=='.json':observed.append(self.target.list());raise OSError('Fictional commit failure')
   return atomic(path,value)
  try:
   with patch('large_paired_restore.atomic',write),self.assertRaisesRegex(OSError,'commit failure'):recovery.publish(self.target,'Fictional reviewer','Test atomic paired restore')
   self.assertEqual(observed,[[]]);self.assertEqual(self.target.list(),[]);self.assertFalse(any((self.target.root).glob('*/status.json')));self.assertEqual(len(self.source.list()),2)
  finally:recovery.close()
 def test_missing_commit_or_missing_member_after_restart_never_exposes_a_half_restore(self):
  self.archive();recovery=self.recover()
  try:result=recovery.publish(self.target,'Fictional reviewer','Keep pair visibility together')
  finally:recovery.close()
  commit=self.target.root/'restore-groups'/(result['groupId']+'.json');saved=commit.read_bytes();commit.unlink();reopened=LargeStore(self.target.root);self.assertEqual(reopened.list(),[])
  with self.assertRaisesRegex(ValueError,'GROUP_INCOMPLETE'):reopened.status(result['id'])
  inventory=reopened.interrupted_restores();self.assertEqual(len(inventory['items']),2);self.assertTrue(all(item['originalRetained'] for item in inventory['items']));self.assertEqual(commit.exists(),False)
  commit.write_bytes(saved);self.assertEqual(len(reopened.list()),2);(self.target.folder(result['parentId'])/'status.json').unlink();self.assertEqual(reopened.list(),[]);self.assertTrue((self.target.folder(result['id'])/'original.bin').exists())
  self.assertEqual(len(reopened.interrupted_restores()['items']),1)
 def test_staged_crash_inventory_retains_files_without_automatic_publication(self):
  folder=self.target.root/'.restore-fictional.pending';folder.mkdir(parents=True);(folder/'original.bin').write_bytes(b'001,0,NA\n')
  result=self.target.interrupted_restores();self.assertEqual(result['items'][0]['state'],'staged');self.assertTrue(result['items'][0]['originalRetained']);self.assertEqual(self.target.list(),[]);self.assertEqual((folder/'original.bin').read_bytes(),b'001,0,NA\n')
 def test_existing_upload_preview_review_and_digest_gate_support_paired_packages(self):
  self.archive();uploads=RestoreUploads()
  try:
   raw=self.path.read_bytes();token=uploads.create(len(raw))['token'];uploads.chunk(token,0,base64.b64encode(raw).decode());report=uploads.preview(token);self.assertEqual(len(report['investigations']),2)
   with self.assertRaisesRegex(ValueError,'PREVIEW'):uploads.publish(token,self.target,'incorrect','Fictional reviewer','Test digest')
   with self.assertRaisesRegex(ValueError,'REVIEW'):uploads.publish(token,self.target,report['packageSha256'],'','')
   result=uploads.publish(token,self.target,report['packageSha256'],'Fictional reviewer','Restore the checked pair');self.assertEqual(len(result['investigations']),2);self.assertEqual(uploads.entries,{})
  finally:uploads.close()
 def test_reexport_restoration_maps_older_declarations_without_rewriting_their_history(self):
  report=inspect(self.source,self.payload);save(self.source,{**self.payload,'digest':report['digest'],'reason':'Fictional key declaration','reviewer':'Fictional curator','status':'Inferred'});self.archive();recovery=self.recover()
  try:first=recovery.publish(self.target,'Fictional archivist','First paired recovery')
  finally:recovery.close()
  payload={**self.payload,'id':first['id'],'parentId':first['parentId']};report=inspect(self.target,payload)
  with package(self.target,{**payload,**report,'reason':'Re-export unchanged restored pair','reviewer':'Fictional curator'}) as artifact:self.path.write_bytes(artifact.read())
  again=self.recover()
  try:second=again.publish(self.target,'Fictional archivist','Second paired recovery')
  finally:again.close()
  self.assertEqual(second['mapping'][self.parent],second['parentId']);self.assertEqual(second['mapping'][first['parentId']],second['parentId']);self.assertEqual(metadata(self.target,second['id'])['metadata'],metadata(self.source,self.child)['metadata']);self.assertEqual(len(self.target.list()),4)
 def test_recalculated_checksums_cannot_hide_a_parent_history_that_does_not_replay(self):
  self.source.edit(self.parent,0,row=1,column=1,expected='First',value='Reviewed First',reason='Fictional reviewed change');self.archive()
  with zipfile.ZipFile(self.path) as archive:members={name:archive.read(name) for name in archive.namelist()}
  entry=json.loads(members['audit/parent-edits.jsonl']);entry['before']='A fabricated former value';members['audit/parent-edits.jsonl']=(json.dumps(entry)+'\n').encode();manifest=json.loads(members['manifest.json'])
  for item in manifest['members']:item.update(bytes=len(members[item['path']]),sha256=hashlib.sha256(members[item['path']]).hexdigest())
  members['manifest.json']=json.dumps(manifest).encode();members['checksums.sha256']=''.join(hashlib.sha256(raw).hexdigest()+'  '+name+'\n' for name,raw in members.items() if name!='checksums.sha256').encode()
  with zipfile.ZipFile(self.path,'w') as archive:
   for name,raw in members.items():archive.writestr(name,raw)
  with self.assertRaises(ValueError):self.recover()
  self.assertEqual(self.target.list(),[]);self.assertEqual(len(self.source.list()),2)
