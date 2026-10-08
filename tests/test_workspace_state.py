import tempfile,unittest,json
from pathlib import Path
from storage import Store
from test_upgrade import sample
from workspace_state import read,save
from edit_sessions import write_project_id
class WorkspaceStateTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.store=Store(self.temp.name);self.project=sample();self.project['id']='e59a4a5d-9984-4d44-9a0b-d7848c28320e';self.store.save(self.project);self.pid=self.project['id'];self.before=self.store.path(self.pid).read_bytes()
 def test_reviews_and_notes_do_not_mutate_scientific_manifest_or_originals(self):
  originals={p.name:p.read_bytes() for p in self.store.objects.iterdir()};s=save(self.store,{'projectId':self.pid,'revision':0,'action':'review','key':'meaning:t:c:source','state':'Intentionally unresolved','reason':'Surviving protocol is incomplete.'});save(self.store,{'projectId':self.pid,'revision':s['revision'],'action':'notes','value':[{'id':'note-1','text':'Personal research question'}]});self.assertEqual(self.store.path(self.pid).read_bytes(),self.before);self.assertEqual({p.name:p.read_bytes() for p in self.store.objects.iterdir()},originals);self.assertEqual(read(self.store,self.pid)['history'][0]['state'],'Intentionally unresolved')
 def test_stale_writes_are_rejected_and_history_is_retained(self):
  save(self.store,{'projectId':self.pid,'revision':0,'action':'review','key':'issue','state':'Rejected','reason':'No supporting evidence'})
  with self.assertRaisesRegex(ValueError,'STALE'):save(self.store,{'projectId':self.pid,'revision':0,'action':'tags','value':['museum']})
  self.assertEqual(read(self.store,self.pid)['history'][0]['reason'],'No supporting evidence')
 def test_invalid_decisions_and_resume_context_do_not_create_state(self):
  for payload in [{'action':'review','key':'issue','state':'Confirmed','reason':'Guess'},{'action':'review','key':'issue','state':'Accepted','reason':''},{'action':'resume','value':{'destructiveDialog':'delete'}}]:
   with self.assertRaises(ValueError):save(self.store,{'projectId':self.pid,'revision':0,**payload})
  self.assertEqual(read(self.store,self.pid)['revision'],0)
 def test_state_endpoint_participates_in_authoritative_edit_lease(self):
  self.assertEqual(write_project_id('/api/workspace-state',{'projectId':self.pid}),self.pid)
 def test_batch_review_is_atomic_and_preserves_scientific_data(self):
  decisions=[{'key':'date:one','state':'Intentionally unresolved','reason':'No convention survives','reviewer':'Fictional archivist'},{'key':'code:two','state':'Rejected','reason':'Competing codebook','reviewer':'Fictional archivist'}]
  result=save(self.store,{'projectId':self.pid,'revision':0,'action':'batch-review','decisions':decisions})
  self.assertEqual(result['revision'],1);self.assertEqual(len(result['history']),2);self.assertEqual(result['reviews']['code:two']['reviewer'],'Fictional archivist');self.assertEqual(self.store.path(self.pid).read_bytes(),self.before)
 def test_invalid_batch_does_not_partially_record_valid_entries(self):
  with self.assertRaises(ValueError):save(self.store,{'projectId':self.pid,'revision':0,'action':'batch-review','decisions':[{'key':'valid','state':'Reviewed','reason':'Reviewed'},{'key':'invalid','state':'Accepted','reason':''}]})
  self.assertEqual(read(self.store,self.pid)['revision'],0);self.assertEqual(read(self.store,self.pid)['history'],[])
 def test_invalid_structured_entries_are_rejected_without_writing(self):
  for action,value in [('savedViews',[{'id':'bad','filter':'Unknown filter'}]),('notes',[{'id':'bad','text':{'nested':'value'}}]),('bookmarks',[{'id':'bad'}]),('notes',[{'id':'repeat','text':'first'},{'id':'repeat','text':'second'}])]:
   with self.assertRaises(ValueError):save(self.store,{'projectId':self.pid,'revision':0,'action':action,'value':value})
  self.assertEqual(read(self.store,self.pid)['revision'],0)
  self.assertEqual(self.store.path(self.pid).read_bytes(),self.before)
 def test_archived_project_cannot_mutate_working_annotations(self):
  from management import action
  action(self.store,{'id':self.pid,'action':'archive','managementRevision':0})
  with self.assertRaisesRegex(ValueError,'Restore'):save(self.store,{'projectId':self.pid,'revision':0,'action':'tags','value':['test']})
 def test_named_views_are_private_and_invalid_labels_do_not_write(self):
  entry={'id':'view-one','name':'Unresolved dates for curator','filter':'Dates','view':'Review queue'}
  result=save(self.store,{'projectId':self.pid,'revision':0,'action':'savedViews','value':[entry]})
  self.assertEqual(result['savedViews'],[entry]);self.assertEqual(self.store.path(self.pid).read_bytes(),self.before)
  for invalid in [{**entry,'name':' '},{**entry,'name':'x'*201},{**entry,'view':'delete'}]:
   with self.assertRaises(ValueError):save(self.store,{'projectId':self.pid,'revision':1,'action':'savedViews','value':[invalid]})
  self.assertEqual(read(self.store,self.pid)['revision'],1)
