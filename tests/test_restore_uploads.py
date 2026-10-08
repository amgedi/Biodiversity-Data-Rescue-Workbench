import base64,tempfile,unittest
from pathlib import Path
from large_data import LargeStore
from large_preservation import package
from restore_uploads import RestoreUploads
class RestoreUploadTests(unittest.TestCase):
 def setUp(self):self.temp=tempfile.TemporaryDirectory();self.clock=[0];self.uploads=RestoreUploads(lambda:self.clock[0]);self.store=LargeStore(Path(self.temp.name)/'large');raw=b'id,count\n001,0\n';job=self.store.create('fictional.csv',len(raw));self.store.chunk(job['id'],0,base64.b64encode(raw).decode());self.store.start(job['id'],False);self.id=job['id']
 def tearDown(self):self.uploads.close();self.temp.cleanup()
 def test_limits_offset_expiration_and_cancellation_release_temporary_files(self):
  for size in [True,0,512*1024*1024+1]:
   with self.assertRaisesRegex(ValueError,'LIMIT'):self.uploads.create(size)
  token=self.uploads.create(20)['token'];entry=self.uploads.entries[token];path=entry['temporary'].name;self.uploads.create(20)
  with self.assertRaisesRegex(ValueError,'BUSY'):self.uploads.create(20)
  with self.assertRaisesRegex(ValueError,'OFFSET'):self.uploads.chunk(token,1,'YQ==')
  self.uploads.chunk(token,0,'YQ==')
  with self.assertRaisesRegex(ValueError,'INCOMPLETE'):self.uploads.preview(token)
  self.clock[0]=901
  with self.assertRaisesRegex(ValueError,'EXPIRED'):self.uploads.preview(token)
  self.assertFalse(Path(path).exists());self.assertEqual(self.uploads.entries,{})
 def test_verified_preview_is_read_only_digest_guarded_and_single_publication(self):
  with package(self.store,self.id) as artifact:raw=artifact.read()
  token=self.uploads.create(len(raw))['token'];self.uploads.chunk(token,0,base64.b64encode(raw).decode());report=self.uploads.preview(token);self.assertEqual(len(self.store.list()),1)
  with self.assertRaisesRegex(ValueError,'PREVIEW'):self.uploads.publish(token,self.store,'wrong','Curator','Fictional recovery')
  result=self.uploads.publish(token,self.store,report['packageSha256'],'Curator','Fictional recovery');self.assertNotEqual(result['id'],self.id);self.assertEqual(len(self.store.list()),2)
  with self.assertRaisesRegex(ValueError,'EXPIRED'):self.uploads.publish(token,self.store,report['packageSha256'],'Curator','Duplicate')
