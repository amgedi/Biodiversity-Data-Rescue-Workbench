import base64,unittest
import test_editing_api
from large_preservation import package
class LargeRestoreApiTests(unittest.TestCase):
 call=test_editing_api.EditingApiTests.call
 def setUp(self):
  test_editing_api.EditingApiTests.setUp(self);raw=b'id,value\n001,0\n';job=self.server.large.create('fictional.csv',len(raw));self.id=job['id'];self.server.large.chunk(self.id,0,base64.b64encode(raw).decode());self.server.large.start(self.id,False)
 def tearDown(self):
  if hasattr(self.server,'restore_uploads'):self.server.restore_uploads.close()
  test_editing_api.EditingApiTests.tearDown(self)
 def upload(self):
  with package(self.server.large,self.id) as artifact:raw=artifact.read()
  status,created=self.call('/api/large-restore-create',{'size':len(raw)});self.assertEqual(status,200);token=created['token'];self.assertEqual(self.call('/api/large-restore-chunk',{'token':token,'offset':0,'data':base64.b64encode(raw).decode()})[0],200);return token
 def test_actual_read_only_preview_and_reviewed_separate_publication(self):
  before=self.server.large.page(self.id);token=self.upload();status,report=self.call('/api/large-restore-preview',{'token':token});self.assertEqual(status,200);self.assertEqual(len(self.server.large.list()),1)
  payload={'token':token,'digest':report['packageSha256'],'reviewer':'Fictional curator','reason':'Separate recovery'};status,restored=self.call('/api/large-restore-publish',payload);self.assertEqual(status,200);self.assertNotEqual(restored['id'],self.id);self.assertEqual(self.server.large.page(self.id),before);self.assertEqual(self.call('/api/large-restore-publish',payload)[0],400)
 def test_invalid_zip_and_unreviewed_publication_do_not_create_investigations(self):
  token=self.upload();self.assertEqual(self.call('/api/large-restore-publish',{'token':token,'digest':'unverified','reviewer':'','reason':''})[0],400);self.assertEqual(self.call('/api/large-restore-cancel',{'token':token})[0],200)
  token=self.call('/api/large-restore-create',{'size':7})[1]['token'];self.call('/api/large-restore-chunk',{'token':token,'offset':0,'data':base64.b64encode(b'bad ZIP').decode()});status,result=self.call('/api/large-restore-preview',{'token':token});self.assertEqual(status,400);self.assertEqual(result['error'],'LARGE_RESTORE_INVALID');self.assertEqual(len(self.server.large.list()),1)
