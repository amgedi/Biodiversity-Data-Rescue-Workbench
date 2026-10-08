import io,unittest
from temporary_exports import TemporaryExports
class TemporaryExportTests(unittest.TestCase):
 def test_native_download_is_one_use_and_expiry_closes_artifact(self):
  now=[0];registry=TemporaryExports(clock=lambda:now[0],ttl=5);first=io.BytesIO(b'fictional');prepared=registry.create(lambda:first);self.assertEqual(prepared['bytes'],9);item=registry.take(prepared['token']);self.assertIs(item['file'],first)
  with self.assertRaisesRegex(ValueError,'EXPIRED'):registry.take(prepared['token'])
  first.close();second=io.BytesIO(b'other');prepared=registry.create(lambda:second);now[0]=6
  with self.assertRaisesRegex(ValueError,'EXPIRED'):registry.take(prepared['token'])
  self.assertTrue(second.closed);registry.close()
 def test_pending_and_completed_packages_are_bounded_and_failure_frees_reservation(self):
  registry=TemporaryExports();files=[]
  for i in range(3):files.append(io.BytesIO(b'fictional'));registry.create(lambda:files[-1])
  with self.assertRaisesRegex(ValueError,'BUSY'):registry.create(lambda:io.BytesIO(b'excess'))
  registry.close();self.assertTrue(all(file.closed for file in files))
  def broken():raise ValueError('fictional build failure')
  with self.assertRaises(ValueError):registry.create(broken)
  self.assertEqual(registry.pending,set());prepared=registry.create(lambda:io.BytesIO(b'retry'));registry.take(prepared['token'])['file'].close()
