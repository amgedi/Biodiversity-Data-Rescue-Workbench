import copy,json,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
from storage import Store
from management import action,catalog,describe,deletion_preview,permanently_delete
from upgrades import save_draft,recovery_status,migrate
from test_upgrade import sample

class ProjectIntegrityTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.store=Store(self.temp.name);self.a=self.store.save(migrate(sample()));p=sample();p['id']='p2';self.b=self.store.save(migrate(p))
 def tearDown(self):self.temp.cleanup()
 def manage(self,operation,p=None,**kw):
  p=p or self.store.get('p1');return action(self.store,dict(id=p['id'],action=operation,managementRevision=catalog(self.store)['revision'],projectRevision=p['revision'],**kw))
 def draft(self,p,value,revision=0):return save_draft(self.store,{'projectId':p['id'],'baseRevision':p['revision'],'draftRevision':revision,'clientId':'tab-a','forms':{'metadata':{'value':value}}})
 def test_two_projects_and_restart_retain_distinct_drafts(self):
  self.draft(self.a,'A');self.draft(self.b,'B');self.draft(self.a,'A2',1);other=Store(self.temp.name)
  self.assertEqual(recovery_status(other,'p1')['draft']['forms']['metadata']['value'],'A2');self.assertEqual(recovery_status(other,'p2')['draft']['forms']['metadata']['value'],'B');self.assertEqual(len(list((self.store.root/'draft-history/p1').glob('*.json'))),1)
 def test_revisiting_another_form_does_not_drop_prior_unreviewed_forms(self):
  self.draft(self.a,'retained metadata')
  save_draft(self.store,{'projectId':'p1','baseRevision':1,'draftRevision':1,'forms':{'table:field':{'description':'new field draft'}}})
  forms=recovery_status(self.store,'p1')['draft']['forms'];self.assertEqual(forms['metadata']['value'],'retained metadata');self.assertEqual(forms['table:field']['description'],'new field draft')
 def test_explicit_clear_keeps_generation_and_revision_visible_after_reopen(self):
  self.draft(self.a,'retained')
  save_draft(self.store,{'projectId':'p1','baseRevision':1,'draftRevision':1,'forms':{},'clear':True,'reason':'Reviewed and committed separately'})
  status=recovery_status(self.store,'p1');self.assertIsNone(status['draft']);self.assertEqual(status['draftRevision'],2)
  self.draft(self.a,'new',2);self.assertEqual(recovery_status(self.store,'p1')['draftRevision'],3)
 def test_stale_tab_cannot_overwrite_new_draft_or_clear_it(self):
  self.draft(self.a,'keep')
  with self.assertRaisesRegex(ValueError,'DRAFT_REVISION'):self.draft(self.a,'stale')
  with self.assertRaisesRegex(ValueError,'EXPLICIT'):save_draft(self.store,{'projectId':'p1','baseRevision':1,'draftRevision':1,'forms':{}})
  self.assertEqual(recovery_status(self.store,'p1')['draft']['forms']['metadata']['value'],'keep')
 def test_two_threads_compare_and_swap_one_winner(self):
  results=[]
  def run(value):
   try:self.draft(self.a,value);results.append('saved')
   except ValueError:results.append('conflict')
  threads=[threading.Thread(target=run,args=(v,)) for v in ['a','b']]
  for t in threads:t.start()
  for t in threads:t.join()
  self.assertCountEqual(results,['saved','conflict'])
 def test_failed_atomic_draft_replace_retains_previous_bytes(self):
  self.draft(self.a,'keep');path=self.store.root/'drafts/p1.json';before=path.read_bytes()
  with patch('upgrades.os.replace',side_effect=OSError('simulated disk failure')):
   with self.assertRaises(OSError):self.draft(self.a,'new',1)
  self.assertEqual(path.read_bytes(),before)
 def test_rename_preserves_id_originals_and_pending_draft(self):
  self.draft(self.a,'draft');before=recovery_status(self.store,'p1')['draft'];self.manage('rename',name='Renamed project');p=self.store.get('p1');self.assertEqual(p['resources'],self.a['resources']);self.assertEqual(p['id'],'p1');self.assertEqual(recovery_status(self.store,'p1')['draft'],before)
 def test_archive_trash_restore_and_writes_guarded(self):
  self.draft(self.a,'keep');self.manage('archive')
  with self.assertRaises(ValueError):self.store.save(self.a)
  with self.assertRaises(ValueError):self.draft(self.a,'wrong',1)
  self.manage('restore');self.manage('trash');self.assertEqual(describe(self.store)['projects'][0]['state'],'trash');self.manage('restore');self.assertEqual(recovery_status(self.store,'p1')['draft']['forms']['metadata']['value'],'keep')
 def test_duplicate_is_separate_and_preserves_sources_and_audit(self):
  r=self.manage('duplicate');n=r['project'];self.assertNotEqual(n['id'],'p1');self.assertEqual(n['resources'],self.a['resources']);self.assertEqual(n['tables'],self.a['tables']);self.assertEqual(n['audit'][:-1],self.a['audit']);self.assertEqual(n['audit'][-1]['sourceProjectId'],'p1')
 def test_management_revision_and_empty_name_conflicts(self):
  with self.assertRaises(ValueError):self.manage('rename',name='  ')
  self.manage('pin')
  with self.assertRaises(ValueError):action(self.store,{'id':'p1','action':'trash','managementRevision':0})
  self.assertTrue(describe(self.store)['projects'][0]['pinned'])
 def test_permanent_delete_only_reviewed_trash_keeps_shared_originals(self):
  self.draft(self.a,'A');self.draft(self.b,'B');self.manage('trash');preview=deletion_preview(self.store,'p1');payload={'id':'p1','managementRevision':catalog(self.store)['revision'],'projectRevision':preview['projectRevision'],'confirm':'wrong'}
  with self.assertRaises(ValueError):permanently_delete(self.store,payload)
  payload['confirm']='p1';permanently_delete(self.store,payload);self.assertFalse(self.store.path('p1').exists());self.assertTrue(self.store.verify(self.b)[0]['diskMatches']);self.assertEqual(recovery_status(self.store,'p2')['draft']['forms']['metadata']['value'],'B')
