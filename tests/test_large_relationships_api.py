import base64,http.client,io,json,unittest,zipfile
import test_editing_api
class LargeRelationshipApiTests(unittest.TestCase):
 call=test_editing_api.EditingApiTests.call
 def setUp(self):
  test_editing_api.EditingApiTests.setUp(self);self.child=self.create('child.csv',b'id,count\n001,0\nmissing,NA\n');self.parent=self.create('parent.csv',b'id,site\n001,Fictional site\n');self.payload={'id':self.child,'parentId':self.parent,'childColumns':[0],'parentColumns':[0]}
 def create(self,name,raw):
  job=self.server.large.create(name,len(raw));id=job['id'];self.server.large.chunk(id,0,base64.b64encode(raw).decode());self.server.large.start(id,False);return id
 def tearDown(self):
  if hasattr(self.server,'temporary_exports'):self.server.temporary_exports.close()
  test_editing_api.EditingApiTests.tearDown(self)
 def reviewed(self,proposal):return {**self.payload,**proposal,'digest':proposal['digest'],'status':'Confirmed','reason':'Fictional curator declares exact key pairing.','reviewer':'Fictional curator'}
 def get(self,path):
  connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port);connection.request('GET',path);response=connection.getresponse();result=response.status,dict(response.headers),response.read();connection.close();return result
 def test_preview_is_read_only_but_metadata_save_requires_current_child_authority(self):
  status,proposal=self.call('/api/large-link-preview',self.payload);self.assertEqual(status,200);self.assertEqual(proposal['counts']['linkedChildRecords'],1);claim_status,proof=self.call('/api/edit-session',dict(projectId='large:'+self.child,session='window-one',action='claim'));self.assertEqual(claim_status,200);reviewed=self.reviewed(proposal);self.assertEqual(self.call('/api/large-link-save',reviewed)[0],400);self.assertEqual(self.call('/api/large-link-save',reviewed,proof)[0],200);self.assertEqual(self.call('/api/large-link-save',reviewed,proof)[0],400)
 def test_native_download_is_verified_and_one_use_without_scientific_mutation(self):
  proposal=self.call('/api/large-link-preview',self.payload)[1];status,prepared=self.call('/api/large-link-export',self.reviewed(proposal));self.assertEqual(status,200);status,headers,body=self.get('/api/large-link-download?token='+prepared['token']);self.assertEqual(status,200);self.assertEqual(headers['Content-Type'],'application/zip');self.assertEqual(headers['Cache-Control'],'no-store');self.assertEqual(int(headers['Content-Length']),len(body))
  with zipfile.ZipFile(io.BytesIO(body)) as archive:self.assertIn('derived/literal-left-join.csv',archive.namelist());self.assertIn(b'0,001,Fictional site',archive.read('derived/literal-left-join.csv'))
  self.assertEqual(self.get('/api/large-link-download?token='+prepared['token'])[0],400);self.assertEqual(self.server.large.page(self.child)['revision'],0)
 def test_corrupt_original_never_produces_download_token(self):
  proposal=self.call('/api/large-link-preview',self.payload)[1];(self.server.large.folder(self.parent)/'original.bin').write_bytes(b'Fictional corruption');status,result=self.call('/api/large-link-export',self.reviewed(proposal));self.assertEqual(status,400);self.assertIn('LARGE_SOURCE_INTEGRITY',result['error']);self.assertNotIn('token',result);self.assertEqual(len(self.server.temporary_exports.files),0)
