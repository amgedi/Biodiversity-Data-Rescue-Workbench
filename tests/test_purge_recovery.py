import copy,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from storage import Store
from management import action,catalog,trash_preview,empty_trash
from purge_transactions import recover
from test_upgrade import sample
class SimulatedCrash(BaseException):pass
class PurgeRecoveryTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.store=Store(Path(self.temp.name)/'store')
  for pid in ['p1','p2']:
   p=sample();p['id']=pid;self.store.save(p);action(self.store,{'id':pid,'action':'trash','managementRevision':catalog(self.store)['revision']})
  self.external=Path(self.temp.name)/'export.csv';self.external.write_bytes(b'001,original export\n');self.before={pid:self.store.path(pid).read_bytes() for pid in ['p1','p2']}
 def tearDown(self):self.temp.cleanup()
 def payload(self):
  view=trash_preview(self.store);return {'managementRevision':view['managementRevision'],'confirm':view['confirmation'],'projects':[{'id':p['id'],'projectRevision':p['projectRevision']} for p in view['projects']]}
 def interrupted(self,error):
  original=os.replace;count=0
  def failing(source,dest):
   nonlocal count
   if 'purge-staging' in str(dest) and 'projects' in str(dest):
    count+=1
    if count==2:raise error
   return original(source,dest)
  with patch('purge_transactions.os.replace',side_effect=failing):
   with self.assertRaises(type(error)):empty_trash(self.store,self.payload())
 def test_os_failure_restores_every_reviewed_project_before_commit(self):
  revision=catalog(self.store)['revision'];self.interrupted(OSError('Simulated filesystem error'))
  self.assertEqual(catalog(self.store)['revision'],revision)
  for pid,data in self.before.items():self.assertEqual(self.store.path(pid).read_bytes(),data)
  self.assertEqual(len(trash_preview(self.store)['projects']),2)
 def test_crash_before_commit_is_restored_on_recovery_without_guessing(self):
  self.interrupted(SimulatedCrash('Simulated process interruption'));self.assertFalse(self.store.path('p1').exists());result=recover(self.store);self.assertEqual(result[0]['result'],'restored')
  for pid,data in self.before.items():self.assertEqual(self.store.path(pid).read_bytes(),data)
  self.assertEqual(self.external.read_bytes(),b'001,original export\n')
 def test_cleanup_failure_retries_committed_deletion_and_keeps_shared_originals(self):
  originals={p.name:p.read_bytes() for p in self.store.objects.iterdir()}
  with patch('purge_transactions.shutil.rmtree',side_effect=OSError('Simulated temporary cleanup lock')):result=empty_trash(self.store,self.payload())
  self.assertTrue(result['purgeCleanupPending']);self.assertFalse(self.store.path('p1').exists());self.assertFalse(self.store.path('p2').exists());self.assertEqual(len({e['purgeTransactionId'] for e in catalog(self.store)['history'] if 'purgeTransactionId' in e}),1)
  self.assertEqual(recover(self.store)[0]['result'],'completed');self.assertEqual({p.name:p.read_bytes() for p in self.store.objects.iterdir()},originals);self.assertEqual(self.external.read_bytes(),b'001,original export\n')
 def test_tampered_recovery_inventory_cannot_touch_originals(self):
  self.interrupted(SimulatedCrash('Simulated interruption'));path=next((self.store.root/'purge-journal').glob('*.json'));journal=json.loads(path.read_text());journal['paths'].append('originals/unreviewed');path.write_text(json.dumps(journal))
  with self.assertRaisesRegex(ValueError,'inventory'):recover(self.store)
  self.assertTrue(self.store.objects.exists())

 def test_crash_after_management_commit_does_not_restore_deleted_projects(self):
  import purge_transactions
  original=purge_transactions._write
  def interrupted_write(path,journal,root):
   if journal['phase']=='committed':raise SimulatedCrash('Commit completed before journal marker')
   return original(path,journal,root)
  with patch('purge_transactions._write',side_effect=interrupted_write):
   with self.assertRaises(SimulatedCrash):empty_trash(self.store,self.payload())
  self.assertEqual(recover(self.store)[0]['result'],'completed');self.assertFalse(self.store.path('p1').exists());self.assertFalse(self.store.path('p2').exists())
 def test_nested_junction_is_rejected_before_any_project_is_staged(self):
  nested=self.store.root/'snapshots'/'p2'/'unsafe-link';nested.mkdir(parents=True)
  with patch.object(Path,'is_junction',lambda p:p==nested):
   with self.assertRaisesRegex(ValueError,'escapes'):empty_trash(self.store,self.payload())
  for pid,data in self.before.items():self.assertEqual(self.store.path(pid).read_bytes(),data)
