import base64,http.client,json,tempfile,threading,unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from server import Handler
from storage import Store
from large_data import LargeStore
from exporters import eml_draft
from test_upgrade import sample
class ApiV04Tests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.server.store=Store(Path(self.temp.name)/'store');self.server.large=LargeStore(Path(self.temp.name)/'large');self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
 def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join();self.temp.cleanup()
 def call(self,path,payload=None):
  c=http.client.HTTPConnection('127.0.0.1',self.server.server_port);c.request('GET' if payload is None else 'POST',path,body=json.dumps(payload) if payload is not None else None,headers={'Content-Type':'application/json'});r=c.getresponse();data=r.read();status=r.status;c.close();return status,json.loads(data)
 def test_large_edit_api_rejects_stale_save_and_retains_audit(self):
  raw=b'id,n\n001,0\n';j=self.server.large.create('a.csv',len(raw));self.server.large.chunk(j['id'],0,base64.b64encode(raw).decode());self.server.large.start(j['id'],False);status,page=self.call('/api/large-page?id='+j['id']+'&limit=1');self.assertEqual(page['revision'],0);payload={'id':j['id'],'revision':0,'row':1,'column':1,'value':'2','expected':'0','reason':'HTTP fixture review'};status,state=self.call('/api/large-edit',payload);self.assertEqual(status,200);self.assertTrue(state['canUndo']);status,error=self.call('/api/large-edit',payload);self.assertEqual(status,400);self.assertIn('Revision',error['error']);status,_=self.call('/api/large-edit',{'id':j['id'],'revision':1,'action':'undo','reason':'HTTP undo'});self.assertEqual(status,200);self.assertEqual(self.server.large.page(j['id'])['rows'][0]['values'],['001','0'])
 def test_snapshot_restore_creates_separate_project(self):
  _,p=self.call('/api/save',sample());_,p=self.call('/api/migrate',p);_,snap=self.call('/api/snapshot',{'project':p,'name':'API restore fixture'});p=snap['project'];_,restored=self.call('/api/snapshot-restore',{'projectId':p['id'],'snapshotId':snap['snapshotId']});self.assertNotEqual(restored['id'],p['id']);self.assertEqual(restored['resources'],p['resources']);self.assertEqual(self.server.store.get(p['id'])['revision'],p['revision'])
 def test_eml_validator_returns_actual_xsd_result_and_rejects_entities(self):
  data,_=eml_draft(sample());status,r=self.call('/api/validate-standard',{'source':{'name':'fixture.xml','base64':base64.b64encode(data).decode()}});self.assertEqual(status,200);self.assertTrue(r['xsdValidated']);status,r=self.call('/api/validate-standard',{'source':{'name':'bad.xml','base64':base64.b64encode(b'<!DOCTYPE x><x/>').decode()}});self.assertEqual(status,400);self.assertIn('DTD',r['error'])
