import base64,hashlib,json,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
from large_data import LargeStore
from large_preservation import metadata,save_metadata,package
from large_repair import preview,apply
from large_restore import Recovery
class LargeRestoreTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.store=LargeStore(self.root/'existing');raw=b'id,observation\n001, 0 \nNA, unknown \n';job=self.store.create('fictional.csv',len(raw));self.id=job['id'];self.store.chunk(self.id,0,base64.b64encode(raw).decode());self.store.start(self.id,background=False);self.path=self.root/'preservation.zip';self.target=LargeStore(self.root/'target')
 def tearDown(self):self.temp.cleanup()
 def archive(self):
  with package(self.store,self.id) as artifact:self.path.write_bytes(artifact.read())
 def edits(self):
  payload={'id':self.id,'columns':[1],'operation':'trim-whitespace'};apply(self.store,{**payload,**preview(self.store,payload),'reason':'Fictional whitespace only','reviewer':'Fictional reviewer'});self.store.edit(self.id,1,action='undo',reason='Undo fictional batch');self.store.edit(self.id,2,action='redo',reason='Redo fictional batch');self.store.edit(self.id,3,row=1,column=1,expected='0',value='00',reason='Fictional literal correction');self.store.edit(self.id,4,action='undo',reason='Undo literal correction')
 def test_original_no_history_restores_separately_and_keeps_unknowns(self):
  self.archive();before=self.store.page(self.id)
  with self.recovery() as recovered:
   status=recovered.publish(self.target,'Fictional curator','Recover independent fictional package')
  self.assertNotEqual(status['id'],self.id);self.assertEqual(self.store.page(self.id),before);self.assertEqual(self.target.page(status['id'])['rows'],before['rows']);self.assertTrue(status['restoration']['verifiedOriginalReplay']);self.assertEqual(metadata(self.target,status['id'])['metadata']['fields'][0]['status'],'Unknown')
 def recovery(self):
  from contextlib import closing
  return closing(Recovery(self.path))
 def test_batch_single_edits_undo_redo_metadata_and_future_editing_survive(self):
  self.edits();save_metadata(self.store,{'id':self.id,'metadataRevision':0,'workingRevision':5,'reviewer':'Curator','reason':'Fictional documented protocol','changes':[{'kind':'field','column':1,'description':'Literal observed code, unresolved','unit':'','dataType':'string','status':'Confirmed'}]});self.archive()
  with self.recovery() as recovered:
   self.assertEqual(recovered.report['workingRevision'],5);self.assertEqual(recovered.report['historyCells'],8);status=recovered.publish(self.target,'Curator','Independent recovery')
  new=status['id'];self.assertEqual(self.target.page(new)['rows'],self.store.page(self.id)['rows']);self.assertEqual(list(self.target.history(new)),list(self.store.history(self.id)));self.assertEqual(metadata(self.target,new),metadata(self.store,self.id));self.assertTrue(self.target.edit_state(new)['canRedo']);self.target.edit(new,5,action='redo',reason='Reapply after verified recovery');self.assertEqual(self.target.page(new)['rows'][0]['values'][1],'00');self.target.edit(new,6,action='undo',reason='Undo again');self.target.edit(new,7,action='undo',reason='Undo recovered batch');self.assertEqual(self.target.page(new)['rows'][0]['values'][1],' 0 ')
 def tamper(self,name,transform):
  with zipfile.ZipFile(self.path) as archive:members={n:archive.read(n) for n in archive.namelist()}
  members[name]=transform(members[name]);manifest=json.loads(members['manifest.json'])
  for item in manifest['members']:item.update(bytes=len(members[item['path']]),sha256=hashlib.sha256(members[item['path']]).hexdigest())
  members['manifest.json']=json.dumps(manifest).encode();members['checksums.sha256']=''.join(hashlib.sha256(v).hexdigest()+'  '+n+'\n' for n,v in members.items() if n!='checksums.sha256').encode()
  with zipfile.ZipFile(self.path,'w') as archive:
   for n,v in members.items():archive.writestr(n,v)
 def test_recomputed_hashes_cannot_hide_unrecorded_working_change(self):
  self.archive();self.tamper('data/working.csv',lambda raw:raw.replace(b'001, 0 ',b'001, 9 '))
  with self.assertRaisesRegex(ValueError,'RESTORE_REPLAY'):Recovery(self.path)
  self.assertEqual(self.target.list(),[])
 def test_reexport_and_second_recovery_preserve_original_and_new_batch_scopes(self):
  self.edits();self.archive()
  with self.recovery() as first:status=first.publish(self.target,'Curator','First recovery')
  id=status['id'];payload={'id':id,'columns':[1],'operation':'trim-whitespace'}
  self.target.edit(id,5,action='undo',reason='Restore whitespace to original batch state');apply(self.target,{**payload,**preview(self.target,payload),'reason':'r'*2000,'reviewer':'c'*200})
  with package(self.target,id) as artifact:self.path.write_bytes(artifact.read())
  with self.recovery() as second:new=second.publish(self.target,'Curator','Second separate recovery')
  self.assertEqual(self.target.page(new['id'])['rows'],self.target.page(id)['rows']);self.assertEqual(list(self.target.history(new['id'])),list(self.target.history(id)));self.assertEqual(len(self.target.list()),2);self.assertEqual(new['restoration']['previousRestoration'],status['restoration'])
 def test_missing_or_fabricated_history_is_rejected_without_publication(self):
  self.edits();self.archive();self.tamper('audit/edits.jsonl',lambda raw:raw.replace(b'"before": "0"',b'"before": "9"'))
  with self.assertRaises(ValueError):Recovery(self.path)
  self.assertEqual(self.target.list(),[])
 def test_review_required_and_failed_publication_keeps_other_investigations(self):
  self.archive();recovered=Recovery(self.path)
  try:
   with self.assertRaisesRegex(ValueError,'REVIEW'):recovered.publish(self.target,'','No identity')
   with patch('large_restore.os.rename',side_effect=OSError('Fictional interrupted publication')):
    with self.assertRaises(OSError):recovered.publish(self.target,'Curator','Fictional recovery')
   self.assertEqual(self.target.list(),[]);self.assertEqual(list(self.target.root.iterdir()),[]);self.assertEqual(self.store.page(self.id)['revision'],0)
  finally:recovered.close()
