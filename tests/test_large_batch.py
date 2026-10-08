import base64,json,tempfile,unittest
from contextlib import closing
from pathlib import Path
from large_data import LargeStore
from large_repair import preview,apply
from large_preservation import metadata
class LargeBatchTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.store=LargeStore(self.temp.name);self.raw=b'id,note,count\n 001 , A ,0\n002, B ,NA\n';job=self.store.create('fictional.csv',len(self.raw));self.id=job['id'];self.store.chunk(self.id,0,base64.b64encode(self.raw).decode());self.store.start(self.id,False);self.payload={'id':self.id,'operation':'trim-whitespace','columns':[0,1]}
 def tearDown(self):self.temp.cleanup()
 def apply(self,proposal=None,**extra):
  proposal=proposal or preview(self.store,self.payload);return apply(self.store,{**self.payload,**proposal,'reason':'Fictional curator reviewed exact whitespace differences.','reviewer':'Fictional curator',**extra})
 def test_preview_is_bounded_and_never_mutates_data_metadata_or_original(self):
  before=self.store.page(self.id);definition=metadata(self.store,self.id);proposal=preview(self.store,self.payload);self.assertEqual(proposal['changedCells'],3);self.assertEqual(proposal['recordsScanned'],2);self.assertTrue(proposal['canApply']);self.assertEqual(self.store.page(self.id),before);self.assertEqual(metadata(self.store,self.id),definition);self.assertEqual((self.store.folder(self.id)/'original.bin').read_bytes(),self.raw)
 def test_one_atomic_commit_and_grouped_undo_redo_preserve_original_and_zero_unknown(self):
  result=self.apply();self.assertEqual(result['revision'],1);self.assertEqual(result['changedCells'],3);self.assertEqual(self.store.page(self.id)['rows'][0]['values'],['001','A','0']);self.assertEqual(self.store.page(self.id)['rows'][1]['values'],['002','B','NA']);self.assertEqual(len(list(self.store.history(self.id))),3);self.store.edit(self.id,1,action='undo',reason='Undo reviewed batch');self.assertEqual(self.store.page(self.id)['rows'][0]['values'],[' 001 ',' A ','0']);self.assertFalse(self.store.edit_state(self.id)['canUndo']);self.store.edit(self.id,2,action='redo',reason='Redo reviewed batch');self.assertEqual(self.store.page(self.id)['rows'][0]['values'],['001','A','0']);self.assertEqual(len(list(self.store.history(self.id))),9);self.assertEqual((self.store.folder(self.id)/'original.bin').read_bytes(),self.raw);self.assertTrue(all(field['status']=='Unknown' for field in metadata(self.store,self.id)['metadata']['fields']))
 def test_stale_or_altered_preview_and_scientific_operations_are_rejected(self):
  proposal=preview(self.store,self.payload)
  for extra in [{'digest':'0'*64},{'reason':''},{'operation':'date-format'},{'columns':[0,0]},{'columns':[True]},{'columns':[]}]:
   with self.assertRaises(ValueError):self.apply(proposal,**extra)
  self.store.edit(self.id,0,row=1,column=1,value='After preview',expected=' A ',reason='Concurrent reviewed edit')
  with self.assertRaisesRegex(ValueError,'STALE'):self.apply(proposal)
  self.assertEqual(self.store.page(self.id)['rows'][0]['values'],[' 001 ','After preview','0'])
 def test_failure_mid_commit_rolls_back_all_cells_history_and_revision(self):
  with closing(self.store.edit_connection(self.id)) as conn:conn.execute("CREATE TRIGGER fail_later BEFORE UPDATE ON rows WHEN NEW.id=2 BEGIN SELECT RAISE(ABORT,'fictional disk failure');END");conn.commit()
  before=self.store.page(self.id)
  with self.assertRaises(Exception):self.apply()
  self.assertEqual(self.store.page(self.id),before);self.assertEqual(list(self.store.history(self.id)),[])
 def test_undo_conflict_rolls_back_every_cell_in_group(self):
  self.apply()
  with closing(self.store.edit_connection(self.id)) as conn:conn.execute('UPDATE rows SET data=? WHERE id=2',(json.dumps(['002','Untracked change','NA']),));conn.commit()
  before=self.store.page(self.id)
  with self.assertRaisesRegex(ValueError,'HISTORY'):self.store.edit(self.id,1,action='undo',reason='Attempt group undo')
  self.assertEqual(self.store.page(self.id),before);self.assertEqual(len(list(self.store.history(self.id))),3)
 def test_new_edit_after_undo_retains_audit_but_clears_redo(self):
  self.apply();self.store.edit(self.id,1,action='undo',reason='Undo batch');self.store.edit(self.id,2,row=1,column=1,value='Other choice',expected=' A ',reason='A different reviewed edit');self.assertFalse(self.store.edit_state(self.id)['canRedo']);self.assertEqual(len(list(self.store.history(self.id))),7)
 def test_whole_table_preview_limits_examples_and_blocks_oversized_commit(self):
  raw=b'id\n'+b' x \n'*50001;job=self.store.create('fictional-bound.csv',len(raw));id=job['id'];self.store.chunk(id,0,base64.b64encode(raw).decode());self.store.start(id,False);payload={'id':id,'operation':'trim-whitespace','columns':[0]};proposal=preview(self.store,payload);self.assertEqual(proposal['changedCells'],50001);self.assertEqual(len(proposal['examples']),10);self.assertFalse(proposal['canApply'])
  with self.assertRaisesRegex(ValueError,'LIMIT'):apply(self.store,{**payload,**proposal,'reason':'Oversized fictional proposal'})
  self.assertEqual(self.store.page(id)['revision'],0);self.assertEqual(list(self.store.history(id)),[])
