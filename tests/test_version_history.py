import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from scripts.launcher import versions as v
class VersionSafety(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
  self.a=patch.object(v,'ROOT',self.root);self.b=patch.object(v,'STATE',self.root/'versions/CURRENT.json');self.a.start();self.b.start()
  self.state={'activeBuildId':'current','previousBuildId':'previous','versions':{}}
  for bid in ['current','previous']:
   folder=self.root/'versions'/bid;(folder/'engine/_internal/web').mkdir(parents=True)
   (folder/'Biodiversity Workbench.exe').write_bytes(bid.encode())
   ident={'buildId':bid,'version':'0.7.0-dev.0','sourceFingerprint':bid,'executableSHA256':v.sha(folder/'Biodiversity Workbench.exe')}
   (folder/'build-identity.json').write_text(json.dumps(ident));(folder/'engine/_internal/web/build-identity.json').write_text(json.dumps(ident))
   v.atomic(folder/'SHA256.json',{p.relative_to(folder).as_posix():v.sha(p) for p in folder.rglob('*') if p.is_file()})
   self.state['versions'][bid]={'directory':'versions/'+bid,'identity':ident}
  v.atomic(v.STATE,self.state)
 def tearDown(self):self.b.stop();self.a.stop();self.temp.cleanup()
 def test_rollback_and_reactivation_preserve_each_runtime(self):
  with patch.object(v,'running',return_value=b''):
   v.activate('previous');self.assertEqual(v.read()['activeBuildId'],'previous');v.activate('current')
  self.assertEqual(v.read()['activeBuildId'],'current');v.verify(v.read(),'previous')
 def test_running_workbench_cannot_switch_pointer(self):
  before=v.STATE.read_bytes()
  with patch.object(v,'running',return_value=b'123'),self.assertRaises(RuntimeError):v.activate('previous')
  self.assertEqual(v.STATE.read_bytes(),before)
 def test_corrupt_desktop_cannot_activate(self):
  (self.root/'versions/previous/Biodiversity Workbench.exe').write_bytes(b'corrupt')
  with self.assertRaises((AssertionError,KeyError)):v.activate('previous')
  self.assertEqual(v.read()['activeBuildId'],'current')
 def test_corrupt_engine_inventory_cannot_activate(self):
  (self.root/'versions/previous/engine/_internal/web/build-identity.json').write_text('{}')
  with self.assertRaises((AssertionError,KeyError)):v.activate('previous')
  self.assertEqual(v.read()['activeBuildId'],'current')
 def test_directory_escape_rejected(self):
  self.state['versions']['previous']['directory']='../outside'
  with self.assertRaises(ValueError):v.verify(self.state,'previous')
 def test_manifest_path_escape_rejected(self):
  v.atomic(self.root/'versions/previous/SHA256.json',{'../../outside':'hash'})
  with self.assertRaises(ValueError):v.verify(self.state,'previous')
 def test_unregistered_build_never_guessed(self):
  with self.assertRaises(KeyError):v.activate('newest-looking-folder')
  self.assertEqual(v.read()['activeBuildId'],'current')
if __name__=='__main__':unittest.main()

