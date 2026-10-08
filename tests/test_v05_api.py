import http.client,json,tempfile,threading,unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from server import Handler
from storage import Store
from large_data import LargeStore
from test_upgrade import sample
class ApiV05Tests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.server.store=Store(Path(self.temp.name)/'store');self.server.large=LargeStore(Path(self.temp.name)/'large');self.server.isolated=True;self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.project=self.server.store.save(sample())
 def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join();self.temp.cleanup()
 def call(self,path,payload=None):
  c=http.client.HTTPConnection('127.0.0.1',self.server.server_port);c.request('GET' if payload is None else 'POST',path,body=json.dumps(payload) if payload is not None else None,headers={'Content-Type':'application/json'});r=c.getresponse();data=r.read();status=r.status;c.close();return status,json.loads(data)
 def manage(self,operation,**extra):
  _,hub=self.call('/api/project-hub');return self.call('/api/project-action',dict(id='p1',action=operation,managementRevision=hub['revision'],projectRevision=self.server.store.get('p1')['revision'],**extra))
 def test_hub_rename_archive_restore_and_conflict_through_api(self):
  self.assertEqual(self.manage('rename',name='Renamed via API')[0],200);self.assertEqual(self.server.store.get('p1')['metadata']['title']['value'],'Renamed via API');self.assertEqual(self.manage('archive')[0],200);self.assertEqual(self.call('/api/save',self.server.store.get('p1'))[0],400);self.assertEqual(self.manage('restore')[0],200)
  self.assertEqual(self.call('/api/project-action',{'id':'p1','action':'pin','managementRevision':0})[0],400)
 def test_isolation_and_capability_are_explicit(self):
  self.assertTrue(self.call('/api/workspace')[1]['isolated']);result=self.call('/api/standards-center')[1];self.assertFalse(result['dwcDP']['conformanceAvailable']);self.assertEqual(result['profiles']['roCrate']['version'],'1.3')
 def test_stale_draft_is_rejected_and_project_save_is_independent(self):
  d={'projectId':'p1','baseRevision':1,'draftRevision':0,'forms':{'metadata':{'value':'retained'}}};self.assertEqual(self.call('/api/draft',d)[0],200);self.assertEqual(self.call('/api/draft',d)[0],400);self.assertEqual(self.call('/api/recovery?id=p1')[1]['draft']['forms']['metadata']['value'],'retained');self.assertEqual(self.server.store.get('p1')['revision'],1)
 def test_backup_request_record_never_claims_download_completion(self):
  self.assertFalse(self.call('/api/delete-preview?id=p1')[1]['backupRecorded']);self.assertEqual(self.manage('backup-request')[0],200);self.assertTrue(self.call('/api/delete-preview?id=p1')[1]['backupRecorded']);self.assertEqual(self.server.store.get('p1')['revision'],1)
