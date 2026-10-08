import base64,io,json,tempfile,unittest
from pathlib import Path
from large_encryption import encrypt,decrypt,MAGIC
from large_data import LargeStore
from large_preservation import package
from restore_uploads import RestoreUploads
from unittest.mock import patch
class LargeEncryptionTests(unittest.TestCase):
 def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.path=self.root/'encrypted.backup';self.password='Fictional strong passphrase only'
 def tearDown(self):self.temp.cleanup()
 def make(self,raw=b'Literal 001, 1, 0, NA and blank\n'):
  with encrypt(io.BytesIO(raw),self.password) as artifact:self.path.write_bytes(artifact.read())
  return raw
 def test_unavailable_optional_provider_has_clear_recoverable_error(self):
  import builtins
  real=builtins.__import__
  def unavailable(name,*args,**kwargs):
   if name.startswith('cryptography'):raise ImportError('Fictional provider absence')
   return real(name,*args,**kwargs)
  self.make()
  with patch('builtins.__import__',unavailable):
   with self.assertRaisesRegex(ValueError,'UNAVAILABLE'):encrypt(io.BytesIO(b'data'),self.password)
   with self.assertRaisesRegex(ValueError,'UNAVAILABLE'):decrypt(self.path,self.password)
 def test_stream_roundtrip_is_exact_randomized_and_authenticated(self):
  raw=self.make(b'0,NA,001\n'*20000);first=self.path.read_bytes();output,report=decrypt(self.path,self.password)
  with output:self.assertEqual(output.read(),raw)
  self.assertTrue(report['authenticated']);self.make(raw);self.assertNotEqual(self.path.read_bytes(),first);self.assertNotIn(self.password.encode(),first)
 def test_wrong_passphrase_changed_ciphertext_and_truncation_never_return_plaintext(self):
  self.make();original=self.path.read_bytes()
  with self.assertRaisesRegex(ValueError,'AUTHENTICATION'):decrypt(self.path,'A different fictional password')
  changed=bytearray(original);changed[-18]^=1;self.path.write_bytes(changed)
  with self.assertRaisesRegex(ValueError,'AUTHENTICATION'):decrypt(self.path,self.password)
  self.path.write_bytes(original[:-1])
  with self.assertRaisesRegex(ValueError,'FORMAT'):decrypt(self.path,self.password)
 def test_untrusted_kdf_limits_and_header_do_not_select_arbitrary_algorithms(self):
  self.make();raw=self.path.read_bytes();line=raw[len(MAGIC):].split(b'\n',1)[0];header=json.loads(line);header['iterations']=999999999999;self.path.write_bytes(MAGIC+json.dumps(header).encode()+b'\n'+raw[len(MAGIC)+len(line)+1:])
  with self.assertRaisesRegex(ValueError,'FORMAT'):decrypt(self.path,self.password)
  for password in [None,'short',123,'x'*1025]:
   with self.assertRaisesRegex(ValueError,'PASSWORD'):encrypt(io.BytesIO(b'data'),password)
 def test_actual_encrypted_investigation_authenticates_before_reviewed_restore(self):
  store=LargeStore(self.root/'source');target=LargeStore(self.root/'target');raw=b'id,count\n001,0\n1,NA\n';job=store.create('fictional.csv',len(raw));store.chunk(job['id'],0,base64.b64encode(raw).decode());store.start(job['id'],False)
  with package(store,job['id']) as clear,encrypt(clear,self.password) as encrypted:contents=encrypted.read()
  uploads=RestoreUploads()
  try:
   token=uploads.create(len(contents))['token'];uploads.chunk(token,0,base64.b64encode(contents).decode())
   with self.assertRaisesRegex(ValueError,'AUTHENTICATION'):uploads.preview(token,'A wrong fictional password')
   self.assertIsNone(uploads.entries[token]['recovery']);self.assertFalse((uploads.entries[token]['path'].parent/'authenticated-package.zip').exists());self.assertEqual(target.list(),[])
   report=uploads.preview(token,self.password);self.assertTrue(report['encryption']['authenticated']);self.assertNotIn(self.password,json.dumps(report));result=uploads.publish(token,target,report['packageSha256'],'Fictional reviewer','Restore authenticated fictional backup');self.assertEqual(target.page(result['id'])['rows'],store.page(job['id'])['rows']);self.assertEqual((target.folder(result['id'])/'original.bin').read_bytes(),raw)
  finally:uploads.close()
