import base64,http.client,json,tempfile,threading,unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from server import Handler
from storage import Store
from large_data import LargeStore
from test_upgrade import sample
class ApiV03Tests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.server.store=Store(Path(self.temp.name)/'store');self.server.large=LargeStore(Path(self.temp.name)/'large');self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
 def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join();self.temp.cleanup()
 def call(self,path,payload=None):
  c=http.client.HTTPConnection('127.0.0.1',self.server.server_port);c.request('GET' if payload is None else 'POST',path,body=json.dumps(payload) if payload is not None else None,headers={'Content-Type':'application/json'});r=c.getresponse();data=r.read();status=r.status;c.close();return status,json.loads(data)
 def test_migration_preview_backup_and_snapshot_api(self):
  status,p=self.call('/api/save',sample());self.assertEqual(status,200);status,plan=self.call('/api/migration-preview',p);self.assertTrue(plan['needed']);status,p=self.call('/api/migrate',p);self.assertEqual(p['projectSchemaVersion'],3);status,s=self.call('/api/snapshot',{'project':p,'name':'API checkpoint'});self.assertEqual(status,200);status,items=self.call('/api/snapshots?id='+p['id']);self.assertEqual(len(items),1);status,diff=self.call('/api/snapshot-compare',{'project':s['project'],'snapshotId':items[0]['id']});self.assertFalse(diff['metadataChanged'])
 def test_public_preview_contains_no_source_baseline_or_private_values(self):
  p=sample();status,v=self.call('/api/public-preview',{'project':p,'policy':{'mode':'redact'}});self.assertEqual(status,200);text=json.dumps(v);self.assertNotIn('originalTable',text);self.assertNotIn('base64',text);self.assertNotIn('53.54123',text);self.assertNotIn('-113.4978',text)
 def test_chunk_upload_cancel_and_restart_status_api(self):
  status,j=self.call('/api/large-create',{'name':'a.csv','size':10});self.assertEqual(status,200);status,_=self.call('/api/large-chunk',{'id':j['id'],'offset':0,'data':base64.b64encode(b'id,n\n01,0\n').decode()});self.assertEqual(status,200);status,v=self.call('/api/large-cancel',{'id':j['id']});self.assertEqual(v['status'],'cancelled');status,s=self.call('/api/large-status?id='+j['id']);self.assertEqual(s['status'],'cancelled')
