from upgrades import APP_VERSION
import copy,tempfile,unittest
from pathlib import Path
from storage import Store
from management import action,catalog,describe,trash_preview,empty_trash
from test_upgrade import sample
class TrashInventoryTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.store=Store(Path(self.temp.name)/'store');self.a=self.store.save(sample());p=sample();p['id']='p2';self.b=self.store.save(p);self.external=Path(self.temp.name)/'external-export.csv';self.external.write_bytes(b'outside,export\n')
 def tearDown(self):self.temp.cleanup()
 def action(self,pid,op,**kwargs):return action(self.store,dict(id=pid,action=op,managementRevision=catalog(self.store)['revision'],projectRevision=self.store.get(pid)['revision'],**kwargs))
 def payload(self):
  preview=trash_preview(self.store);return dict(managementRevision=preview['managementRevision'],confirm=preview['confirmation'],projects=[{'id':p['id'],'projectRevision':p['projectRevision']} for p in preview['projects']])
 def test_empty_trash_preserves_active_project_shared_originals_and_external_export(self):
  self.action('p1','trash');result=empty_trash(self.store,self.payload());self.assertEqual(result['deleted'],['p1']);self.assertTrue(self.store.path('p2').exists());self.assertTrue(self.store.verify(self.b)[0]['diskMatches']);self.assertEqual(self.external.read_bytes(),b'outside,export\n');self.assertTrue(catalog(self.store)['history'])
 def test_stale_inventory_rejects_all_deletion(self):
  self.action('p1','trash');payload=self.payload();self.action('p2','trash')
  with self.assertRaisesRegex(ValueError,'CONFLICT'):empty_trash(self.store,payload)
  self.assertTrue(self.store.path('p1').exists());self.assertTrue(self.store.path('p2').exists())
 def test_wrong_typed_confirmation_or_manifest_revision_deletes_nothing(self):
  self.action('p1','trash');payload=self.payload();payload['confirm']='DELETE ALL'
  with self.assertRaisesRegex(ValueError,'CONFLICT'):empty_trash(self.store,payload)
  payload=self.payload();payload['projects'][0]['projectRevision']+=1
  with self.assertRaisesRegex(ValueError,'INVENTORY'):empty_trash(self.store,payload)
  self.assertTrue(self.store.path('p1').exists())
 def test_management_history_uses_actual_dev_version_and_retains_scientific_id(self):
  self.action('p1','rename',name='Same name');self.action('p1','pin');self.assertEqual(self.store.get('p1')['id'],'p1');self.assertTrue(all(x['applicationVersion']==APP_VERSION for x in catalog(self.store)['history']));item=describe(self.store)['projects'][0];self.assertIn('metadataUnknowns',item);self.assertIn('validationStatus',item)
