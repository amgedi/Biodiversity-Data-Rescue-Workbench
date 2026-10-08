import http.client,json,tempfile,threading,unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from server import Handler
from storage import Store
from large_data import LargeStore
from test_upgrade import sample
from edit_sessions import write_project_id,authorized_write,registry

class EditingApiTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.server.store=Store(Path(self.temp.name)/'store');self.server.large=LargeStore(Path(self.temp.name)/'large');self.server.isolated=True;self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.project=self.server.store.save(sample())
 def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join();self.temp.cleanup()
 def call(self,path,payload,proof=None):
  headers={'Content-Type':'application/json'}
  if proof:headers.update({'X-Workspace-Session':proof['ownerSession'],'X-Workspace-Token':proof['token']})
  c=http.client.HTTPConnection('127.0.0.1',self.server.server_port);c.request('POST',path,json.dumps(payload),headers);r=c.getresponse();data=json.loads(r.read());status=r.status;c.close();return status,data
 def claim(self,session,**extra):return self.call('/api/edit-session',dict(projectId='p1',session=session,action='claim',**extra))[1]
 def test_takeover_blocks_old_editor_save_and_draft_without_changing_source(self):
  one=self.claim('window-one');two=self.claim('window-two');self.assertFalse(two['editing'])
  status,two=self.call('/api/edit-session',dict(projectId='p1',session='window-two',action='takeover',generation=one['generation']));self.assertEqual(status,200)
  self.assertEqual(self.call('/api/save',self.project,one)[0],400)
  self.assertEqual(self.call('/api/draft',dict(projectId='p1',baseRevision=1,draftRevision=0,forms={'keep':'old'}),one)[0],400)
  self.assertEqual(self.server.store.get('p1')['revision'],1)
  self.assertEqual(self.call('/api/save',self.project,two)[0],200)
 def test_anonymous_api_cannot_bypass_editor_and_release_allows_legacy_client(self):
  one=self.claim('window-one');self.assertEqual(self.call('/api/save',self.project)[0],400)
  self.assertEqual(self.call('/api/edit-session',dict(projectId='p1',session='window-one',action='release',token=one['token']))[0],200)
  self.assertEqual(self.call('/api/save',self.project)[0],200)
 def test_authority_check_and_mutation_exclude_takeover(self):
  one=self.claim('window-one');started=threading.Event();finished=threading.Event()
  def takeover():started.set();registry(self.server).claim('p1','window-two',True,one['generation']);finished.set()
  with authorized_write(self.server,'p1','window-one',one['token']):
   thread=threading.Thread(target=takeover);thread.start();self.assertTrue(started.wait(1));self.assertFalse(finished.wait(.05))
  thread.join(2);self.assertTrue(finished.is_set())
 def test_direct_migration_and_scientific_mutations_are_project_bound(self):
  for path,payload in [('/api/migrate',{'id':'p1'}),('/api/save',{'id':'p1'}),('/api/draft',{'projectId':'p1'}),('/api/snapshot',{'project':{'id':'p1'}}),('/api/project-action',{'id':'p1','action':'trash'})]:self.assertEqual(write_project_id(path,payload),'p1')
